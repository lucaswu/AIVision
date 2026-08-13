"""Read-only parsing for the model-agent owned revision-set state file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RevisionSetStateError(ValueError):
    pass


def load_active_set(path: Path) -> dict[str, Any]:
    payload = load_state(path)
    return _expand_set(payload, payload.get("active_set_id"), require_active=True)


def load_pending_committing_set(path: Path) -> dict[str, Any] | None:
    payload = load_state(path)
    committing = [item for item in payload.get("sets", {}).values() if item.get("state") == "COMMITTING"]
    if not committing:
        return None
    if len(committing) != 1:
        raise RevisionSetStateError("only one COMMITTING set is allowed")
    return _expand_set(payload, committing[0].get("set_id"), require_active=False)


def load_state(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RevisionSetStateError(f"revision set state not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RevisionSetStateError(f"revision set state is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise RevisionSetStateError("revision state must be an object")
    return payload


def _expand_set(payload: dict[str, Any], set_id: Any, *, require_active: bool) -> dict[str, Any]:
    active_id = set_id
    sets = payload.get("sets")
    if not isinstance(active_id, str) or not isinstance(sets, dict):
        raise RevisionSetStateError("revision state requires active_set_id and sets")
    active = sets.get(active_id)
    if not isinstance(active, dict) or (require_active and active.get("state") != "ACTIVE"):
        raise RevisionSetStateError("requested set is not valid")
    if active.get("set_id") != active_id or not isinstance(active.get("generation"), int):
        raise RevisionSetStateError("active set is missing set_id or generation")
    if not isinstance(active.get("revisions"), dict) or not active["revisions"]:
        raise RevisionSetStateError("active set has no profile revisions")
    catalog = payload.get("revision_catalog", {})
    if not isinstance(catalog, dict):
        raise RevisionSetStateError("revision_catalog must be an object")
    profiles: dict[str, dict[str, Any]] = {}
    for profile_id, revision_id in active["revisions"].items():
        revision = catalog.get(revision_id)
        if not isinstance(profile_id, str) or not isinstance(revision, dict):
            raise RevisionSetStateError(f"profile {profile_id!r} has no revision catalog entry")
        if revision.get("revision_id") != revision_id or not isinstance(revision.get("slots"), dict):
            raise RevisionSetStateError(f"invalid revision catalog entry {revision_id!r}")
        profiles[profile_id] = revision
    return {**active, "profiles": profiles}


def artifact_path(store_root: Path, slot: dict[str, Any]) -> str:
    sha256 = slot.get("sha256")
    relative_path = slot.get("relative_path")
    if not isinstance(sha256, str) or len(sha256) != 64:
        raise RevisionSetStateError("slot sha256 is required")
    if not isinstance(relative_path, str) or not relative_path:
        raise RevisionSetStateError("slot relative_path is required")
    filename = Path(relative_path).name
    candidate = (store_root / sha256 / filename).resolve()
    root = store_root.resolve()
    if root not in candidate.parents:
        raise RevisionSetStateError("slot path escapes model store")
    if not candidate.is_file():
        raise RevisionSetStateError(f"installed artifact is missing: {candidate}")
    return str(candidate)
