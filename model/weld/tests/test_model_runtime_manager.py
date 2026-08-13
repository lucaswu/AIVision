from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_runtime_manager import ModelRuntimeManager, OperationTimedOut, RuntimeSwitchInProgress


def _profile(profile_id: str, revision_id: str) -> dict:
    return {"revision_id": revision_id, "slots": {}, "bundle": {"id": revision_id, "profile": profile_id}}


def _builder(profile_id: str, spec: dict) -> dict:
    return _profile(profile_id, spec["revision_id"])


def test_commit_switches_every_profile_as_one_set():
    retired = []
    manager = ModelRuntimeManager(lambda bundle: retired.append(bundle["id"]))
    manager.bootstrap("old", 1, {"default": _profile("default", "old-default"), "high": _profile("high", "old-high")})

    manager.prepare(
        set_id="new", generation=2, operation_id="op-1",
        profile_specs={"default": {"revision_id": "new-default"}, "high": {"revision_id": "new-high"}},
        build_profile=_builder,
    )
    manager.begin_commit("new", 2, "op-1")
    manager.commit("new", 2, "op-1")

    default = manager.acquire("default")
    high = manager.acquire("high")
    assert (default.set_id, default.revision_id) == ("new", "new-default")
    assert (high.set_id, high.revision_id) == ("new", "new-high")
    manager.release(default)
    manager.release(high)
    assert set(retired) == {"old-default", "old-high"}


def test_lease_keeps_old_set_alive_until_task_finishes():
    retired = []
    manager = ModelRuntimeManager(lambda bundle: retired.append(bundle["id"]))
    manager.bootstrap("old", 1, {"default": _profile("default", "old")})
    lease = manager.acquire("default")
    manager.prepare(
        set_id="new", generation=2, operation_id="op",
        profile_specs={"default": {"revision_id": "new"}}, build_profile=_builder,
    )
    manager.begin_commit("new", 2, "op")
    manager.commit("new", 2, "op")
    assert retired == []
    manager.release(lease)
    assert retired == ["old"]


def test_freeze_timeout_restores_admission_and_rejects_late_commit(monkeypatch):
    manager = ModelRuntimeManager(lambda _bundle: None, freeze_timeout_seconds=1)
    manager.bootstrap("old", 1, {"default": _profile("default", "old")})
    manager.prepare(
        set_id="new", generation=2, operation_id="op",
        profile_specs={"default": {"revision_id": "new"}}, build_profile=_builder,
    )
    manager.begin_commit("new", 2, "op", timeout_seconds=1)
    with pytest.raises(RuntimeSwitchInProgress):
        manager.acquire("default")
    import model_runtime_manager

    monkeypatch.setattr(model_runtime_manager.time, "monotonic", lambda: 10**9)
    assert manager.acquire("default").set_id == "old"
    with pytest.raises(OperationTimedOut):
        manager.commit("new", 2, "op")
