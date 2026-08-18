from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from revision_sets import RevisionSetStateError, artifact_path, load_active_set, protected_sha256


def test_active_set_expands_profile_revisions(tmp_path):
    state = tmp_path / "revision_sets.json"
    state.write_text(json.dumps({
        "active_set_id": "set-1",
        "sets": {"set-1": {"set_id": "set-1", "generation": 3, "state": "ACTIVE", "revisions": {"default": "rev-1"}}},
        "revision_catalog": {"rev-1": {"revision_id": "rev-1", "slots": {"primary": {}}}},
    }))
    active = load_active_set(state)
    assert active["profiles"]["default"]["revision_id"] == "rev-1"


def test_committing_set_is_not_reported_as_active(tmp_path):
    from revision_sets import load_pending_committing_set

    state = tmp_path / "revision_sets.json"
    state.write_text(json.dumps({
        "active_set_id": "old",
        "sets": {
            "old": {"set_id": "old", "generation": 1, "state": "ACTIVE", "revisions": {"default": "old-r"}},
            "new": {"set_id": "new", "generation": 2, "state": "COMMITTING", "operation_id": "op", "revisions": {"default": "new-r"}},
        },
        "revision_catalog": {
            "old-r": {"revision_id": "old-r", "slots": {}},
            "new-r": {"revision_id": "new-r", "slots": {}},
        },
    }))
    assert load_active_set(state)["set_id"] == "old"
    assert load_pending_committing_set(state)["set_id"] == "new"


def test_artifact_path_rejects_missing_or_escaping_file(tmp_path):
    with pytest.raises(RevisionSetStateError):
        artifact_path(tmp_path, {"sha256": "a" * 64, "relative_path": "../escape.pth"})


def test_protected_sha256_covers_active_and_one_hop_rollback_only():
    state = {
        "active_set_id": "set-2",
        "sets": {
            "set-0": {"set_id": "set-0", "state": "ROLLED_BACK", "revisions": {"default": "rev-0"}},
            "set-1": {"set_id": "set-1", "state": "ROLLED_BACK", "revisions": {"default": "rev-1"}},
            "set-2": {
                "set_id": "set-2", "state": "ACTIVE", "previous_set_id": "set-1",
                "revisions": {"default": "rev-2"},
            },
        },
        "revision_catalog": {
            "rev-0": {"revision_id": "rev-0", "slots": {"primary": {"sha256": "0" * 64}}},
            "rev-1": {"revision_id": "rev-1", "slots": {"primary": {"sha256": "1" * 64}}},
            "rev-2": {"revision_id": "rev-2", "slots": {"primary": {"sha256": "2" * 64}}},
        },
    }
    protected = protected_sha256(state)
    assert protected == {"1" * 64, "2" * 64}
    assert "0" * 64 not in protected


def test_protected_sha256_covers_in_flight_activation():
    state = {
        "active_set_id": "set-1",
        "sets": {
            "set-1": {"set_id": "set-1", "state": "ACTIVE", "revisions": {"default": "rev-1"}},
            "set-2": {"set_id": "set-2", "state": "COMMITTING", "revisions": {"default": "rev-2"}},
        },
        "revision_catalog": {
            "rev-1": {"revision_id": "rev-1", "slots": {"primary": {"sha256": "1" * 64}}},
            "rev-2": {"revision_id": "rev-2", "slots": {"primary": {"sha256": "2" * 64}}},
        },
    }
    assert protected_sha256(state) == {"1" * 64, "2" * 64}
