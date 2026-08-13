from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from revision_sets import RevisionSetStateError, artifact_path, load_active_set


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
