"""Set-scoped, in-process runtime ownership for inference bundles.

The manager owns the only references to preloaded model bundles.  Callers get a
lease, never a model path, so a task cannot silently switch models midway.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


class RuntimeErrorBase(RuntimeError):
    code = "RUNTIME_UNAVAILABLE"


class RuntimeNotReady(RuntimeErrorBase):
    code = "RUNTIME_NOT_READY"


class RuntimeSwitchInProgress(RuntimeErrorBase):
    code = "MODEL_SWITCH_IN_PROGRESS"


class RuntimeProfileNotProvisioned(RuntimeErrorBase):
    code = "RUNTIME_PROFILE_NOT_PROVISIONED"


class StaleGeneration(RuntimeErrorBase):
    code = "STALE_GENERATION"


class OperationTimedOut(RuntimeErrorBase):
    code = "OPERATION_TIMED_OUT"


class ProfileSetUnschedulable(RuntimeErrorBase):
    code = "PROFILE_SET_UNSCHEDULABLE"


class DrainTimeout(RuntimeErrorBase):
    code = "DRAIN_TIMEOUT"


@dataclass(frozen=True)
class RuntimeLease:
    set_id: str
    generation: int
    profile_id: str
    revision_id: str
    slots: dict[str, dict[str, str]]
    bundle: dict[str, Any]


@dataclass
class _PreparedSet:
    set_id: str
    generation: int
    operation_id: str
    profiles: dict[str, dict[str, Any]]
    #: profile_id -> the immutable spec used to build it, so a failed drain can
    #: rebuild the set it already freed.
    specs: dict[str, dict[str, Any]] = field(default_factory=dict)

    def budget_mb(self) -> int:
        return sum(int(spec.get("gpu_budget_mb", 0)) for spec in self.specs.values())


def _specs_budget_mb(profile_specs: dict[str, dict[str, Any]]) -> int:
    return sum(int(spec.get("gpu_budget_mb", 0)) for spec in profile_specs.values())


class ModelRuntimeManager:
    """Atomically activates all profiles from a DeploymentRevisionSet."""

    def __init__(
        self,
        close_bundle: Callable[[dict[str, Any]], None],
        freeze_timeout_seconds: int = 600,
        free_vram_mb: Callable[[], int | None] | None = None,
        safety_margin_mb: int = 1024,
    ):
        self._close_bundle = close_bundle
        self._freeze_timeout_seconds = freeze_timeout_seconds
        self._free_vram_mb = free_vram_mb or (lambda: None)
        self._safety_margin_mb = safety_margin_mb
        self._lock = threading.RLock()
        self._active: _PreparedSet | None = None
        self._prepared: _PreparedSet | None = None
        self._retiring: dict[str, _PreparedSet] = {}
        self._leases: dict[str, int] = {}
        self._state = "WARMING"
        self._freeze_operation: str | None = None
        self._freeze_deadline: float | None = None
        self._timed_out_operations: set[str] = set()
        self._completed_operations: dict[str, tuple[str, int]] = {}
        #: Guards the long, unlocked build phase against a concurrent prepare.
        self._building_operation: str | None = None
        self._drained = threading.Condition(self._lock)
        self._last_plan: str | None = None
        #: Set the moment a drain frees the active set, so a failed candidate
        #: can rebuild exactly what was released.
        self._drained_backup: _PreparedSet | None = None
        self._rebuild_profile: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None

    def bootstrap(
        self,
        set_id: str,
        generation: int,
        profiles: dict[str, dict[str, Any]],
        specs: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Install a fully warmed set during startup; no leases may exist yet."""
        with self._lock:
            self._active = _PreparedSet(set_id, generation, "bootstrap", profiles, specs or {})
            self._leases.setdefault(set_id, 0)
            self._state = "ACTIVE"

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._check_freeze_timeout_locked()
            active = self._active
            profiles: dict[str, Any] = {}
            if active:
                for profile_id, profile in active.profiles.items():
                    spec = active.specs.get(profile_id, {})
                    profiles[profile_id] = {
                        "revision_id": profile.get("revision_id"),
                        "slots": profile.get("slots", {}),
                        "warmed": profile.get("bundle") is not None,
                        "gpu_budget_mb": int(spec.get("gpu_budget_mb", 0)),
                        # Deployment tooling rebuilds the next set from this, so
                        # the runtime parameters must round-trip.
                        "runtime": spec.get("runtime", {}),
                    }
            return {
                "runtime_state": self._state.lower(),
                "set_id": active.set_id if active else None,
                "generation": active.generation if active else None,
                "profiles": sorted(profiles),
                "profile_details": profiles,
                "lease_count": self._leases.get(active.set_id, 0) if active else 0,
                "prepared_set_id": self._prepared.set_id if self._prepared else None,
                "prepared_generation": self._prepared.generation if self._prepared else None,
                "gpu_free_mb": self._free_vram_mb(),
                "gpu_required_mb": active.budget_mb() if active else 0,
                "last_activation_plan": self._last_plan,
            }

    def acquire(self, profile_id: str) -> RuntimeLease:
        with self._lock:
            self._check_freeze_timeout_locked()
            if self._state in {"COMMITTING", "DRAINING"}:
                raise RuntimeSwitchInProgress("runtime set is switching")
            if self._state != "ACTIVE" or self._active is None:
                raise RuntimeNotReady("no active, prewarmed runtime set")
            profile = self._active.profiles.get(profile_id)
            if profile is None:
                raise RuntimeProfileNotProvisioned(profile_id)
            self._leases[self._active.set_id] = self._leases.get(self._active.set_id, 0) + 1
            return RuntimeLease(
                set_id=self._active.set_id,
                generation=self._active.generation,
                profile_id=profile_id,
                revision_id=profile["revision_id"],
                slots=profile.get("slots", {}),
                bundle=profile["bundle"],
            )

    def release(self, lease: RuntimeLease) -> None:
        retire: _PreparedSet | None = None
        with self._lock:
            count = self._leases.get(lease.set_id, 0)
            if count <= 0:
                raise RuntimeError("runtime lease underflow")
            self._leases[lease.set_id] = count - 1
            if self._leases[lease.set_id] == 0:
                retire = self._retiring.pop(lease.set_id, None)
                self._drained.notify_all()
        if retire is not None:
            self._retire(retire)

    # ------------------------------------------------------------------
    # Capacity admission
    # ------------------------------------------------------------------

    def plan_activation(self, profile_specs: dict[str, dict[str, Any]]) -> str:
        """Decide between a blue-green swap and a drain, or refuse outright.

        Returns ``"BLUE_GREEN"`` or ``"DRAIN"``.  Raises
        ``ProfileSetUnschedulable`` when even an emptied device cannot hold the
        candidate, because draining cannot help in that case.
        """
        with self._lock:
            free_mb = self._free_vram_mb()
            required_new = _specs_budget_mb(profile_specs) + self._safety_margin_mb
            active_mb = self._active.budget_mb() if self._active else 0
            if free_mb is None:
                # No GPU accounting available (CPU build, or budgets undeclared).
                plan = "BLUE_GREEN"
            elif required_new <= self._safety_margin_mb:
                raise ProfileSetUnschedulable("every profile must declare gpu_budget_mb")
            elif free_mb >= required_new:
                plan = "BLUE_GREEN"
            elif free_mb + active_mb >= required_new:
                plan = "DRAIN"
            else:
                raise ProfileSetUnschedulable(
                    f"needs {required_new}MB, at most {free_mb + active_mb}MB obtainable"
                )
            self._last_plan = plan
            return plan

    # ------------------------------------------------------------------
    # Two-phase activation
    # ------------------------------------------------------------------

    def prepare(
        self,
        *,
        set_id: str,
        generation: int,
        operation_id: str,
        profile_specs: dict[str, dict[str, Any]],
        build_profile: Callable[[str, dict[str, Any]], dict[str, Any]],
        drain_timeout_seconds: int = 900,
    ) -> dict[str, Any]:
        """Build every profile before altering the active set."""
        with self._lock:
            if operation_id in self._timed_out_operations:
                raise OperationTimedOut(operation_id)
            if self._completed_operations.get(operation_id) == (set_id, generation):
                return {
                    "set_id": set_id,
                    "generation": generation,
                    "plan": self._last_plan or "BLUE_GREEN",
                    "profiles": sorted(self._active.profiles) if self._active else [],
                }
            if self._active and generation <= self._active.generation:
                raise StaleGeneration(str(generation))
            if self._prepared and self._prepared.operation_id == operation_id:
                return {
                    "set_id": set_id,
                    "generation": generation,
                    "plan": self._last_plan or "BLUE_GREEN",
                    "profiles": sorted(self._prepared.profiles),
                }
            if self._prepared is not None or self._building_operation is not None:
                raise RuntimeSwitchInProgress("another revision set is prepared")
            plan = self.plan_activation(profile_specs)
            # Claim the build slot so a concurrent prepare cannot start a second
            # build and orphan the bundles this one is about to create.
            self._building_operation = operation_id
            # Preparing a candidate must not make an already active set stop
            # accepting leases. Only begin_commit creates an admission freeze.
            self._state = "ACTIVE" if self._active else "WARMING"

        try:
            if plan == "DRAIN":
                self._drain_active(operation_id, drain_timeout_seconds)
            built = self._build_all(profile_specs, build_profile, plan)
        except Exception:
            with self._lock:
                self._building_operation = None
                self._state = "ACTIVE" if self._active else "FAILED"
            raise

        with self._lock:
            self._prepared = _PreparedSet(set_id, generation, operation_id, built, dict(profile_specs))
            self._leases.setdefault(set_id, 0)
            self._building_operation = None
            self._state = "ACTIVE" if self._active else "WARMING"
            return {"set_id": set_id, "generation": generation, "plan": plan, "profiles": sorted(built)}

    def _build_all(
        self,
        profile_specs: dict[str, dict[str, Any]],
        build_profile: Callable[[str, dict[str, Any]], dict[str, Any]],
        plan: str,
    ) -> dict[str, dict[str, Any]]:
        built: dict[str, dict[str, Any]] = {}
        current: dict[str, Any] | None = None
        try:
            for profile_id, spec in profile_specs.items():
                current = None
                current = build_profile(profile_id, spec)
                built[profile_id] = current
                current = None
        except Exception:
            # A profile that failed midway may still hold a partially built
            # bundle; close it together with the completed ones.
            if isinstance(current, dict) and current.get("bundle") is not None:
                self._close_bundle(current["bundle"])
            for profile in built.values():
                self._close_bundle(profile["bundle"])
            if plan == "DRAIN":
                self._restore_drained_active()
            raise
        return built

    def _drain_active(self, operation_id: str, timeout_seconds: int) -> None:
        """Free the active set so a candidate can fit on a single device."""
        with self._lock:
            if self._active is None:
                return
            if not self._active.specs:
                raise ProfileSetUnschedulable("active set has no recorded specs; cannot rebuild after drain")
            self._state = "DRAINING"
            self._freeze_operation = operation_id
            self._freeze_deadline = time.monotonic() + timeout_seconds
            deadline = time.monotonic() + timeout_seconds
            active_set_id = self._active.set_id
            while self._leases.get(active_set_id, 0) > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._state = "ACTIVE"
                    self._freeze_operation = None
                    self._freeze_deadline = None
                    raise DrainTimeout(f"{self._leases.get(active_set_id, 0)} leases still in flight")
                self._drained.wait(min(remaining, 1.0))
            drained = self._active
            self._active = None
            self._drained_backup = drained
        self._retire(drained)

    def _restore_drained_active(self) -> None:
        """Rebuild the set a failed drain had already freed."""
        backup: _PreparedSet | None = getattr(self, "_drained_backup", None)
        if backup is None:
            return
        rebuilt: dict[str, dict[str, Any]] = {}
        builder = getattr(self, "_rebuild_profile", None)
        if builder is None:
            return
        try:
            for profile_id, spec in backup.specs.items():
                rebuilt[profile_id] = builder(profile_id, spec)
        except Exception:
            for profile in rebuilt.values():
                self._close_bundle(profile["bundle"])
            with self._lock:
                self._state = "FAILED"
            return
        with self._lock:
            self._active = _PreparedSet(backup.set_id, backup.generation, backup.operation_id, rebuilt, backup.specs)
            self._leases.setdefault(backup.set_id, 0)
            self._state = "ACTIVE"
            self._drained_backup = None

    def set_rebuild_profile(self, build_profile: Callable[[str, dict[str, Any]], dict[str, Any]]) -> None:
        """Register the builder used to restore an active set after a failed drain."""
        self._rebuild_profile = build_profile

    def begin_commit(
        self, set_id: str, generation: int, operation_id: str, timeout_seconds: int | None = None
    ) -> dict[str, Any]:
        with self._lock:
            if operation_id in self._timed_out_operations:
                raise OperationTimedOut(operation_id)
            if self._completed_operations.get(operation_id) == (set_id, generation):
                return {"lease_count": self._leases.get(self._active.set_id, 0) if self._active else 0}
            self._require_prepared_locked(set_id, generation, operation_id)
            self._state = "COMMITTING"
            self._freeze_operation = operation_id
            self._freeze_deadline = time.monotonic() + (timeout_seconds or self._freeze_timeout_seconds)
            return {"lease_count": self._leases.get(self._active.set_id, 0) if self._active else 0}

    def commit(self, set_id: str, generation: int, operation_id: str) -> dict[str, Any]:
        with self._lock:
            if operation_id in self._timed_out_operations:
                raise OperationTimedOut(operation_id)
            if self._completed_operations.get(operation_id) == (set_id, generation):
                return self.status()
            self._require_prepared_locked(set_id, generation, operation_id)
            if self._state != "COMMITTING" or self._freeze_operation != operation_id:
                raise RuntimeSwitchInProgress("begin_commit must succeed before commit")
            old = self._active
            self._active = self._prepared
            self._prepared = None
            self._state = "ACTIVE"
            self._freeze_operation = None
            self._freeze_deadline = None
            self._drained_backup = None
            self._completed_operations[operation_id] = (set_id, generation)
        if old is not None:
            with self._lock:
                if self._leases.get(old.set_id, 0) == 0:
                    retire_now = old
                else:
                    self._retiring[old.set_id] = old
                    retire_now = None
            if retire_now is not None:
                self._retire(retire_now)
        return self.status()

    def abort(self, operation_id: str) -> None:
        with self._lock:
            if self._prepared is None or self._prepared.operation_id != operation_id:
                # Still clear an admission freeze this operation is holding, so
                # a failed candidate cannot keep the service refusing tasks.
                if self._freeze_operation == operation_id:
                    self._freeze_operation = None
                    self._freeze_deadline = None
                    self._state = "ACTIVE" if self._active else "FAILED"
                return
            prepared = self._prepared
            self._prepared = None
            self._state = "ACTIVE" if self._active else "FAILED"
            self._freeze_operation = None
            self._freeze_deadline = None
        self._retire(prepared)
        if self._active is None:
            self._restore_drained_active()

    def _require_prepared_locked(self, set_id: str, generation: int, operation_id: str) -> None:
        prepared = self._prepared
        if prepared is None or (prepared.set_id, prepared.generation, prepared.operation_id) != (
            set_id,
            generation,
            operation_id,
        ):
            raise RuntimeNotReady("requested revision set is not prepared")

    def _check_freeze_timeout_locked(self) -> None:
        if self._freeze_deadline is None or time.monotonic() < self._freeze_deadline:
            return
        operation_id = self._freeze_operation
        prepared = self._prepared
        self._freeze_deadline = None
        self._freeze_operation = None
        self._prepared = None
        self._state = "ACTIVE" if self._active else "FAILED"
        if operation_id:
            self._timed_out_operations.add(operation_id)
        if prepared:
            threading.Thread(target=self._retire, args=(prepared,), daemon=True).start()

    def _retire(self, revision_set: _PreparedSet) -> None:
        for profile in revision_set.profiles.values():
            bundle = profile.get("bundle")
            if bundle is not None:
                self._close_bundle(bundle)
