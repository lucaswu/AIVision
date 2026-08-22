"""Local model-delivery agent for verified offline bundles.

The agent is the sole writer for the model store and revision-set state.  It is
designed to run in a separate container with no inference code imports.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import stat
import ssl
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature


#: Decompression caps. A signed bundle carries exactly one checkpoint plus
#: three small metadata members, so these are generous but bounded.
MAX_TOTAL_UNCOMPRESSED_BYTES = int(os.environ.get("MODEL_BUNDLE_MAX_TOTAL_BYTES", str(8 * 1024**3)))
MAX_WEIGHT_BYTES = int(os.environ.get("MODEL_BUNDLE_MAX_WEIGHT_BYTES", str(8 * 1024**3)))
MAX_METADATA_BYTES = int(os.environ.get("MODEL_BUNDLE_MAX_METADATA_BYTES", str(1024 * 1024)))


class BundleError(ValueError):
    pass


def canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _error_code(response: "httpx.Response") -> str:
    """Extract the runtime's error code from a FastAPI detail payload."""
    try:
        detail = response.json().get("detail")
    except Exception:
        return f"HTTP_{response.status_code}"
    if isinstance(detail, dict):
        return str(detail.get("code") or f"HTTP_{response.status_code}")
    if isinstance(detail, str) and detail:
        return detail.split(":", 1)[0].strip()
    return f"HTTP_{response.status_code}"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


class ModelAgent:
    def __init__(self, *, store_root: Path, state_path: Path, trust_path: Path, inference_url: str, control_token: str):
        self.store_root = store_root
        self.state_path = state_path
        self.trust_path = trust_path
        self.inference_url = inference_url.rstrip("/")
        self.control_token = control_token
        if os.environ.get("BUILD_FLAVOR", "development").strip().lower() == "production" and not self.inference_url.startswith("https://"):
            raise BundleError("MODEL_AGENT_MTLS_URL_REQUIRED")

    def _inference_client(self, timeout: int) -> httpx.Client:
        ca_file = os.environ.get("MODEL_AGENT_CA_FILE")
        cert_file = os.environ.get("MODEL_AGENT_CLIENT_CERT_FILE")
        key_file = os.environ.get("MODEL_AGENT_CLIENT_KEY_FILE")
        # trust_env=False keeps the container-internal control plane off any
        # HTTP_PROXY the site sets for outbound traffic: proxying mTLS control
        # calls would both break them and expose the control token.
        if self.inference_url.startswith("https://"):
            if not all((ca_file, cert_file, key_file)):
                raise BundleError("MODEL_AGENT_MTLS_CONFIG_MISSING")
            context = ssl.create_default_context(cafile=ca_file)
            context.load_cert_chain(certfile=cert_file, keyfile=key_file)
            return httpx.Client(
                timeout=timeout, headers={"X-Model-Agent-Token": self.control_token},
                verify=context, trust_env=False,
            )
        return httpx.Client(
            timeout=timeout, headers={"X-Model-Agent-Token": self.control_token}, trust_env=False,
        )

    def _trust_payload(self) -> dict[str, Any]:
        try:
            trust = json.loads(self.trust_path.read_text(encoding="utf-8"))
            signature = base64.b64decode(trust.pop("signature"), validate=True)
            root_path = self.trust_path.with_name("root.pub")
            root_public = Ed25519PublicKey.from_public_bytes(base64.b64decode(root_path.read_text(encoding="utf-8").strip(), validate=True))
            list_version = trust.get("list_version")
            if not isinstance(list_version, int) or not isinstance(trust.get("root_key_id"), str):
                raise ValueError("missing versioned trust fields")
            expires_at = datetime.fromisoformat(str(trust["expires_at"]).replace("Z", "+00:00"))
            if expires_at <= datetime.now(timezone.utc):
                raise ValueError("trust list expired")
            if not isinstance(trust.get("keys"), dict):
                raise ValueError("keys must be an object")
            root_public.verify(signature, canonical_json(trust))
        except (KeyError, OSError, ValueError, json.JSONDecodeError, InvalidSignature) as exc:
            raise BundleError("INVALID_TRUST_LIST") from exc

        # A valid root signature proves authenticity but not freshness. Refuse
        # any list older than the highest one this site has already accepted,
        # otherwise a replayed old list can reinstate a revoked key.
        state = self.load_state()
        seen = state.get("trust_list_version")
        if isinstance(seen, int) and list_version < seen:
            raise BundleError(f"TRUST_LIST_ROLLBACK: {list_version} < {seen}")
        if not isinstance(seen, int) or list_version > seen:
            state["trust_list_version"] = list_version
            atomic_write_json(self.state_path, state)
        return trust

    def trust_list_version(self) -> int | None:
        version = self.load_state().get("trust_list_version")
        return version if isinstance(version, int) else None

    def _trusted_key(self, key_id: str) -> Ed25519PublicKey:
        # BundleError subclasses ValueError, so let a specific trust failure
        # (expired, rollback, bad root signature) through instead of masking it
        # as an unknown key.
        trust = self._trust_payload()
        try:
            encoded = trust["keys"][key_id]
            return Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded, validate=True))
        except (KeyError, ValueError) as exc:
            raise BundleError(f"UNTRUSTED_SIGNING_KEY: {key_id}") from exc

    def install_bundle(self, bundle_path: Path) -> dict[str, Any]:
        """Verify a release bundle and place its exact artifact under its SHA."""
        try:
            with zipfile.ZipFile(bundle_path) as archive:
                names = archive.namelist()
                required = {"manifest.json", "manifest.sig", "key_id"}
                if len(names) != len(set(names)) or not required.issubset(names) or any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
                    raise BundleError("INVALID_BUNDLE_LAYOUT")
                weights = [name for name in names if name.startswith("weights/") and not name.endswith("/")]
                allowed = required | set(weights)
                has_unsafe_member = any(
                    info.is_dir() or stat.S_ISLNK(info.external_attr >> 16) or info.filename not in allowed
                    for info in archive.infolist()
                )
                if len(weights) != 1 or has_unsafe_member:
                    raise BundleError("INVALID_BUNDLE_LAYOUT")
                # Declared sizes are attacker-controlled, so cap them before any
                # read and cap again while streaming: a zip bomb must not be
                # able to exhaust memory or the model volume.
                if sum(info.file_size for info in archive.infolist()) > MAX_TOTAL_UNCOMPRESSED_BYTES:
                    raise BundleError("BUNDLE_TOO_LARGE")
                for name in ("manifest.json", "manifest.sig", "key_id"):
                    if archive.getinfo(name).file_size > MAX_METADATA_BYTES:
                        raise BundleError("BUNDLE_METADATA_TOO_LARGE")
                if archive.getinfo(weights[0]).file_size > MAX_WEIGHT_BYTES:
                    raise BundleError("BUNDLE_WEIGHT_TOO_LARGE")
                manifest = json.loads(archive.read("manifest.json"))
                signature = base64.b64decode(archive.read("manifest.sig"), validate=True)
                key_id = archive.read("key_id").decode("utf-8").strip()
                try:
                    self._trusted_key(key_id).verify(signature, canonical_json(manifest))
                except InvalidSignature as exc:
                    # A forged signature under a known key_id must fail with the
                    # same kind of auditable code as an unknown key, not a raw
                    # cryptography exception.
                    raise BundleError(f"INVALID_MANIFEST_SIGNATURE: {key_id}") from exc
                artifact = manifest.get("artifact", {})
                sha256 = artifact.get("sha256")
                if not isinstance(sha256, str) or len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
                    raise BundleError("INVALID_MANIFEST_SHA256")
                target = self.store_root / sha256
                target.mkdir(parents=True, exist_ok=True)
                artifact_name = Path(artifact.get("relative_path", "")).name
                if not artifact_name:
                    raise BundleError("INVALID_MANIFEST_ARTIFACT_PATH")
                staged = target / f".{artifact_name}.{uuid.uuid4().hex}.tmp"
                digest = hashlib.sha256()
                written = 0
                try:
                    with archive.open(weights[0]) as source, staged.open("wb") as sink:
                        while chunk := source.read(4 * 1024 * 1024):
                            written += len(chunk)
                            if written > MAX_WEIGHT_BYTES:
                                raise BundleError("BUNDLE_WEIGHT_TOO_LARGE")
                            digest.update(chunk)
                            sink.write(chunk)
                    if digest.hexdigest() != sha256:
                        raise BundleError("MODEL_ARTIFACT_DIGEST_MISMATCH")
                    os.replace(staged, target / artifact_name)
                except BaseException:
                    staged.unlink(missing_ok=True)
                    raise
                atomic_write_json(target / "manifest.json", manifest)
                return manifest
        except zipfile.BadZipFile as exc:
            raise BundleError("INVALID_BUNDLE_ARCHIVE") from exc

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"generation": 0, "active_set_id": None, "sets": {}, "revision_catalog": {}}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _load_slot_manifest(self, slot: dict[str, Any]) -> dict[str, Any]:
        sha256 = slot.get("sha256")
        if not isinstance(sha256, str) or len(sha256) != 64:
            raise BundleError("INVALID_REVISION_SLOT")
        manifest_path = self.store_root / sha256 / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BundleError(f"INSTALLED_MANIFEST_MISSING: {sha256}") from exc
        artifact = manifest.get("artifact", {})
        if artifact.get("sha256") != sha256:
            raise BundleError("INSTALLED_MANIFEST_DIGEST_MISMATCH")
        return manifest

    @staticmethod
    def _semver_at_least(actual: str, required: str) -> bool:
        def parse(value: str) -> tuple[int, int, int]:
            core = value.split("+", 1)[0].split("-", 1)[0]
            parts = core.split(".")
            if len(parts) != 3 or not all(item.isdigit() for item in parts):
                raise BundleError(f"INVALID_INFERENCE_VERSION: {value}")
            return tuple(int(item) for item in parts)  # type: ignore[return-value]

        return parse(actual) >= parse(required)

    def _validate_revisions(self, revisions: dict[str, dict[str, Any]]) -> None:
        """Validate installed artifacts and cross-slot contracts before PREPARED."""
        with self._inference_client(timeout=20) as client:
            response = client.get(f"{self.inference_url}/models")
            response.raise_for_status()
            inference_version = response.json().get("inference_version")
        if not isinstance(inference_version, str):
            raise BundleError("INFERENCE_VERSION_UNAVAILABLE")

        for profile_id, revision in revisions.items():
            slots = revision.get("slots")
            if revision.get("profile_id") != profile_id or not isinstance(slots, dict):
                raise BundleError("INVALID_REVISION_SET")
            manifests = {slot_name: self._load_slot_manifest(slot) for slot_name, slot in slots.items()}
            if not manifests:
                raise BundleError("EMPTY_REVISION")
            for slot_name, manifest in manifests.items():
                if manifest.get("slot") != slot_name:
                    raise BundleError("REVISION_SLOT_MANIFEST_MISMATCH")
            compatibility = [manifest.get("compatibility", {}) for manifest in manifests.values()]
            if any(manifest.get("manifest_version") != 2 for manifest in manifests.values()):
                raise BundleError("UNSUPPORTED_MANIFEST_VERSION")
            for contract in compatibility:
                if not self._semver_at_least(inference_version, str(contract.get("minimum_inference_version", ""))):
                    raise BundleError("INFERENCE_VERSION_TOO_OLD")
            preprocess = {(item.get("preprocess_contract_version"), item.get("preprocess_config_sha256")) for item in compatibility}
            if len(preprocess) != 1:
                raise BundleError("CROSS_SLOT_PREPROCESS_MISMATCH")
            postprocess = {item.get("postprocess_contract_version") for item in compatibility}
            if len(postprocess) != 1:
                raise BundleError("CROSS_SLOT_POSTPROCESS_MISMATCH")
            # Slots feeding the same business defect-type mapping must agree on
            # the ordered class map; a silent reordering corrupts every result.
            # Grouping matters: a ROI detector and a defect detector are both
            # "detection" but classify different things, so comparing them would
            # reject every legitimate combination.
            groups: dict[str, dict[str, Any]] = {}
            for slot_name, manifest in manifests.items():
                contract = manifest.get("compatibility", {})
                class_map = contract.get("ordered_class_map")
                # A slot may legitimately carry no class map at all: the
                # orientation-correction model classifies nothing the business
                # mapping consumes. Only slots that declare one are compared.
                if not isinstance(class_map, list) or not class_map:
                    continue
                group = str(contract.get("class_map_group") or contract.get("task_type") or slot_name)
                groups.setdefault(group, {})[slot_name] = class_map
            for group, class_maps in groups.items():
                distinct = {json.dumps(value, ensure_ascii=False, sort_keys=False) for value in class_maps.values()}
                if len(distinct) != 1:
                    raise BundleError(f"CROSS_SLOT_CLASS_MAP_MISMATCH: group={group} slots={sorted(class_maps)}")
            # input_size is each model's own inference resolution, not the size
            # of the crop it hands downstream, so comparing it across slots is
            # meaningless: the shipped registry legitimately pairs roi=640 with
            # primary=840. Only validate that each slot declares a sane value.
            # Enforcing a real producer/consumer size constraint would need the
            # manifest to carry the produced extent, which it does not today.
            sizes = {slot_name: manifest.get("compatibility", {}).get("input_size") for slot_name, manifest in manifests.items()}
            if any(not isinstance(value, int) or value <= 0 for value in sizes.values()):
                raise BundleError("CROSS_SLOT_INPUT_SIZE_INVALID")
            produced_spaces: dict[str, set[str]] = {}
            consumed_spaces: list[tuple[str, str | None]] = []
            for contract in compatibility:
                interface = contract.get("interface")
                if not isinstance(interface, dict):
                    raise BundleError("CROSS_SLOT_INTERFACE_MISSING")
                coordinate = interface.get("coordinate_space")
                produces = interface.get("produces", [])
                consumes = interface.get("consumes", [])
                if not isinstance(produces, list) or not isinstance(consumes, list):
                    raise BundleError("CROSS_SLOT_INTERFACE_INVALID")
                for value in produces:
                    if not isinstance(value, str):
                        raise BundleError("CROSS_SLOT_INTERFACE_INVALID")
                    produced_spaces.setdefault(value, set()).add(coordinate or "")
                for value in consumes:
                    if not isinstance(value, str):
                        raise BundleError("CROSS_SLOT_INTERFACE_INVALID")
                    consumed_spaces.append((value, coordinate))
            external_inputs = {"image@v1"}
            available = set(produced_spaces) | external_inputs
            if any(value not in available for value, _ in consumed_spaces):
                raise BundleError("CROSS_SLOT_INTERFACE_MISMATCH")
            for value, consumer_space in consumed_spaces:
                if value in produced_spaces and consumer_space and consumer_space not in produced_spaces[value]:
                    raise BundleError("CROSS_SLOT_COORDINATE_SPACE_MISMATCH")

    def build_revisions(self, profile_specs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Create content-addressed revisions from installed manifests only.

        A profile spec carries slot -> SHA values and runtime settings.  It
        never contains a path, artifact filename, release ID, or compatibility
        contract supplied by an administrator.
        """
        revisions: dict[str, dict[str, Any]] = {}
        for profile_id, spec in profile_specs.items():
            requested_slots = spec.get("slots")
            if not isinstance(requested_slots, dict) or not requested_slots:
                raise BundleError("INVALID_PROFILE_SLOT_SPEC")
            slots: dict[str, dict[str, str]] = {}
            for slot_name, sha256 in requested_slots.items():
                if not isinstance(slot_name, str) or not isinstance(sha256, str):
                    raise BundleError("INVALID_PROFILE_SLOT_SPEC")
                manifest = self._load_slot_manifest({"sha256": sha256})
                if manifest.get("slot") != slot_name:
                    raise BundleError("REVISION_SLOT_MANIFEST_MISMATCH")
                artifact = manifest["artifact"]
                slots[slot_name] = {
                    "sha256": sha256,
                    "release_id": manifest["release_id"],
                    "relative_path": artifact["relative_path"],
                    "model_name": artifact.get("model_name"),
                }
            runtime = spec.get("runtime", {})
            if not isinstance(runtime, dict):
                raise BundleError("INVALID_PROFILE_RUNTIME")
            # Capacity admission needs a measured budget per profile; without it
            # the manager cannot tell a drainable switch from an impossible one.
            budget = spec.get("gpu_budget_mb")
            if not isinstance(budget, int) or budget <= 0:
                raise BundleError(f"PROFILE_GPU_BUDGET_REQUIRED: {profile_id}")
            identity = canonical_json({"profile_id": profile_id, "slots": slots, "runtime": runtime})
            revisions[profile_id] = {
                "revision_id": f"rdr_{hashlib.sha256(identity).hexdigest()[:20]}",
                "profile_id": profile_id,
                "slots": slots,
                "runtime": runtime,
                "gpu_budget_mb": budget,
            }
        return revisions

    def rollback(self, reason: str = "") -> dict[str, Any]:
        """Re-activate the previous successful set. Never touches the network."""
        state = self.load_state()
        active_id = state.get("active_set_id")
        active = state.get("sets", {}).get(active_id) if isinstance(active_id, str) else None
        if not isinstance(active, dict):
            raise BundleError("NO_ACTIVE_SET_TO_ROLL_BACK")
        previous_id = active.get("previous_set_id")
        previous = state.get("sets", {}).get(previous_id) if isinstance(previous_id, str) else None
        if not isinstance(previous, dict):
            raise BundleError("NO_PREVIOUS_SET_RETAINED")
        catalog = state.get("revision_catalog", {})
        try:
            revisions = {profile: catalog[revision_id] for profile, revision_id in previous["revisions"].items()}
        except KeyError as exc:
            raise BundleError("PREVIOUS_SET_REVISION_MISSING") from exc
        # A rollback is an ordinary activation of an older combination: it goes
        # through the same PREPARED/COMMITTING/ACTIVE protocol and takes a new,
        # higher generation so a later poll cannot resurrect the bad set.
        rollback_set_id = f"{previous_id}-rb{uuid.uuid4().hex[:8]}"
        result = self.activate_set(rollback_set_id, revisions)
        state = self.load_state()
        state["sets"][rollback_set_id]["rolled_back_from"] = active_id
        state["sets"][rollback_set_id]["rollback_reason"] = reason
        state["sets"][active_id]["state"] = "ROLLED_BACK"
        atomic_write_json(self.state_path, state)
        return result

    @staticmethod
    def _protected_sha256(state: dict[str, Any]) -> set[str]:
        """sha256 values the active set or its one-hop rollback target still
        need. Duplicated (not imported) from revision_sets.py: this agent is
        deliberately built with no inference-code imports, so the small
        amount of duplication buys independence from that module's Docker
        image and dependency footprint.
        """
        sets = state.get("sets", {})
        catalog = state.get("revision_catalog", {})
        candidates: list[dict[str, Any]] = []
        active_id = state.get("active_set_id")
        active = sets.get(active_id) if isinstance(active_id, str) else None
        if isinstance(active, dict):
            candidates.append(active)
            previous_id = active.get("previous_set_id")
            previous = sets.get(previous_id) if isinstance(previous_id, str) else None
            if isinstance(previous, dict):
                candidates.append(previous)
        candidates.extend(
            item for item in sets.values() if isinstance(item, dict) and item.get("state") in {"PREPARED", "COMMITTING"}
        )
        protected: set[str] = set()
        for item in candidates:
            for revision_id in item.get("revisions", {}).values():
                revision = catalog.get(revision_id)
                slots = revision.get("slots") if isinstance(revision, dict) else None
                if not isinstance(slots, dict):
                    continue
                for slot in slots.values():
                    sha256 = slot.get("sha256") if isinstance(slot, dict) else None
                    if isinstance(sha256, str):
                        protected.add(sha256)
        return protected

    def delete_artifact(self, sha256: str) -> dict[str, Any]:
        """Remove a verified artifact from the content-addressed store.

        Refuses anything the active set or its immediate rollback target
        still reference, so this can never break the one-hop rollback
        guarantee rollback() depends on. Older, superseded artifacts (the
        actual target of a cleanup) are unprotected and removed outright.
        """
        if not isinstance(sha256, str) or len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
            raise BundleError("INVALID_ARTIFACT_SHA256")
        state = self.load_state()
        if sha256 in self._protected_sha256(state):
            raise BundleError(f"ARTIFACT_IN_USE: {sha256}")
        target = self.store_root / sha256
        if not target.is_dir():
            raise BundleError(f"ARTIFACT_NOT_FOUND: {sha256}")
        shutil.rmtree(target)
        return {"sha256": sha256, "deleted": True}

    def process_commands(self, inbox: Path) -> int:
        """Run activate/rollback requests queued by the local management API."""
        commands = inbox / "commands"
        if not commands.is_dir():
            return 0
        handled = 0
        for path in sorted(commands.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                kind = payload.get("kind")
                if kind == "activate":
                    self.activate_set(payload["set_id"], self.build_revisions(payload["profiles"]))
                elif kind == "rollback":
                    self.rollback(payload.get("reason", ""))
                elif kind == "delete":
                    self.delete_artifact(payload["sha256"])
                else:
                    raise BundleError(f"UNKNOWN_COMMAND: {kind}")
                path.rename(path.with_suffix(".done"))
                print(f"executed {kind} command {payload.get('job_id')}")
            except Exception as exc:
                path.rename(path.with_suffix(".failed"))
                print(f"failed command {path.name}: {exc}")
            handled += 1
        return handled

    def recover_committing_set(self) -> dict[str, Any] | None:
        """Finish the durable half of a commit after either process restarts."""
        state = self.load_state()
        candidates = [item for item in state.get("sets", {}).values() if item.get("state") == "COMMITTING"]
        if not candidates:
            return None
        if len(candidates) != 1:
            raise BundleError("MULTIPLE_COMMITTING_SETS")
        candidate = candidates[0]
        set_id, generation, operation_id = candidate["set_id"], candidate["generation"], candidate["operation_id"]
        revisions = {profile: state["revision_catalog"][revision_id] for profile, revision_id in candidate["revisions"].items()}
        payload = {"set_id": set_id, "generation": generation, "operation_id": operation_id}
        with self._inference_client(timeout=600) as client:
            ready = client.get(f"{self.inference_url}/readyz")
            if ready.status_code != 200 or ready.json().get("set_id") != set_id or ready.json().get("generation") != generation:
                client.post(f"{self.inference_url}/internal/runtime/prepare", json={**payload, "revisions": revisions}).raise_for_status()
                client.post(f"{self.inference_url}/internal/runtime/begin-commit", json=payload).raise_for_status()
                client.post(f"{self.inference_url}/internal/runtime/commit", json=payload).raise_for_status()
                ready = client.get(f"{self.inference_url}/readyz")
                ready.raise_for_status()
            runtime = ready.json()
        if runtime.get("set_id") != set_id or runtime.get("generation") != generation:
            raise BundleError("RUNTIME_COMMIT_NOT_CONFIRMED")
        state["generation"] = generation
        state["active_set_id"] = set_id
        candidate["state"] = "ACTIVE"
        atomic_write_json(self.state_path, state)
        return candidate

    def abort_prepared_sets(self) -> int:
        """Clean up durable PREPARED operations left by an interrupted agent."""
        state = self.load_state()
        prepared = [item for item in state.get("sets", {}).values() if item.get("state") == "PREPARED"]
        if len(prepared) > 1:
            raise BundleError("MULTIPLE_PREPARED_SETS")
        if not prepared:
            return 0
        candidate = prepared[0]
        operation_id = candidate.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            raise BundleError("PREPARED_SET_OPERATION_MISSING")
        try:
            with self._inference_client(timeout=30) as client:
                client.post(
                    f"{self.inference_url}/internal/runtime/abort",
                    json={"set_id": candidate["set_id"], "generation": candidate["generation"], "operation_id": operation_id},
                ).raise_for_status()
        except httpx.HTTPError as exc:
            raise BundleError("PREPARED_SET_ABORT_FAILED") from exc
        candidate["state"] = "ABORTED"
        atomic_write_json(self.state_path, state)
        return 1

    def activate_set(self, set_id: str, revisions: dict[str, dict[str, Any]], timeout_seconds: int = 600) -> dict[str, Any]:
        """Persist PREPARED/COMMITTING/ACTIVE around the manager's set transaction."""
        self._validate_revisions(revisions)
        state = self.load_state()
        generation = int(state.get("generation", 0)) + 1
        operation_id = str(uuid.uuid4())
        catalog = state.setdefault("revision_catalog", {})
        for profile_id, revision in revisions.items():
            if revision.get("profile_id") != profile_id or not revision.get("revision_id"):
                raise BundleError("INVALID_REVISION_SET")
            catalog[revision["revision_id"]] = revision
        revision_ids = {profile_id: revision["revision_id"] for profile_id, revision in revisions.items()}
        state["sets"][set_id] = {
            "set_id": set_id,
            "generation": generation,
            "state": "PREPARED",
            "operation_id": operation_id,
            "revisions": revision_ids,
            "previous_set_id": state.get("active_set_id"),
        }
        atomic_write_json(self.state_path, state)

        payload = {"set_id": set_id, "generation": generation, "operation_id": operation_id}
        with self._inference_client(timeout=timeout_seconds) as client:
            response = client.post(
                f"{self.inference_url}/internal/runtime/prepare",
                json={**payload, "revisions": revisions, "drain_timeout_seconds": timeout_seconds},
            )
            if response.status_code >= 400:
                # Surface the runtime's own code so the operator can tell an
                # impossible profile set from a drain that merely timed out.
                state["sets"][set_id]["state"] = "ABORTED"
                state["sets"][set_id]["error"] = _error_code(response)
                atomic_write_json(self.state_path, state)
                raise BundleError(_error_code(response))
            client.post(f"{self.inference_url}/internal/runtime/begin-commit", json=payload).raise_for_status()
            state["sets"][set_id]["state"] = "COMMITTING"
            atomic_write_json(self.state_path, state)
            client.post(f"{self.inference_url}/internal/runtime/commit", json=payload).raise_for_status()
            ready = client.get(f"{self.inference_url}/readyz").json()
        if ready.get("set_id") != set_id or ready.get("generation") != generation or ready.get("runtime_state") != "active":
            raise BundleError("RUNTIME_COMMIT_NOT_CONFIRMED")
        state["generation"] = generation
        state["active_set_id"] = set_id
        state["sets"][set_id]["state"] = "ACTIVE"
        atomic_write_json(self.state_path, state)
        return state["sets"][set_id]


def main() -> None:
    parser = argparse.ArgumentParser(description="AIVision model delivery agent")
    parser.add_argument("--inbox", default="/app/model/inbox")
    parser.add_argument("--store", default="/app/model/store")
    parser.add_argument("--state", default="/app/model/active/revision_sets.json")
    parser.add_argument("--trust", default="/opt/model-trust/keys.json")
    parser.add_argument("--activate-set", help="JSON file with {set_id, profiles}; performs one set activation")
    parser.add_argument("--rollback", action="store_true", help="re-activate the previous successful set and exit")
    parser.add_argument("--delete", metavar="SHA256", help="remove one unreferenced artifact from the store and exit")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    agent = ModelAgent(
        store_root=Path(args.store), state_path=Path(args.state), trust_path=Path(args.trust),
        inference_url=os.environ.get("INFERENCE_INTERNAL_URL", "http://ai-inference:8000"),
        control_token=os.environ.get("MODEL_AGENT_CONTROL_TOKEN", ""),
    )
    inbox = Path(args.inbox)
    if args.activate_set:
        payload = json.loads(Path(args.activate_set).read_text(encoding="utf-8"))
        result = agent.activate_set(payload["set_id"], agent.build_revisions(payload["profiles"]))
        print(f"activated {result['set_id']}@{result['generation']}")
        return
    if args.rollback:
        result = agent.rollback("operator requested rollback")
        print(f"rolled back to {result['set_id']}@{result['generation']}")
        return
    if args.delete:
        agent.delete_artifact(args.delete)
        print(f"deleted {args.delete}")
        return
    while True:
        try:
            agent.abort_prepared_sets()
            agent.recover_committing_set()
        except Exception as exc:
            print(f"failed to recover committing set: {exc}")
        for package in sorted(inbox.glob("*.zip")):
            try:
                manifest = agent.install_bundle(package)
                package.rename(package.with_suffix(".installed"))
                print(f"installed release {manifest['release_id']}")
            except Exception as exc:
                package.rename(package.with_suffix(".failed"))
                print(f"failed to install {package.name}: {exc}")
        try:
            agent.process_commands(inbox)
        except Exception as exc:
            print(f"failed to process queued commands: {exc}")
        if args.once:
            return
        time.sleep(5)


if __name__ == "__main__":
    main()
