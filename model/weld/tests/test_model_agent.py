from __future__ import annotations

import base64
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_agent import BundleError, ModelAgent, canonical_json


def _write_trust(tmp_path: Path, signing_public: bytes) -> tuple[Path, Ed25519PrivateKey]:
    root = Ed25519PrivateKey.generate()
    payload = {
        "list_version": 1,
        "root_key_id": "root-1",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "keys": {"release-1": base64.b64encode(signing_public).decode()},
    }
    payload["signature"] = base64.b64encode(root.sign(canonical_json(payload))).decode()
    trust = tmp_path / "keys.json"
    trust.write_text(json.dumps(payload))
    (tmp_path / "root.pub").write_text(base64.b64encode(root.public_key().public_bytes_raw()).decode())
    return trust, root


def test_signed_bundle_installs_by_digest(tmp_path):
    signing = Ed25519PrivateKey.generate()
    trust, _root = _write_trust(tmp_path, signing.public_key().public_bytes_raw())
    content = b"weights"
    digest = hashlib.sha256(content).hexdigest()
    manifest = {"manifest_version": 2, "release_id": "rel-1", "slot": "primary", "artifact": {"sha256": digest, "relative_path": "model/model.pth"}}
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("manifest.json", canonical_json(manifest))
        archive.writestr("manifest.sig", base64.b64encode(signing.sign(canonical_json(manifest))))
        archive.writestr("key_id", "release-1")
        archive.writestr("weights/model.pth", content)

    store = tmp_path / "store"
    agent = ModelAgent(store_root=store, state_path=tmp_path / "state.json", trust_path=trust, inference_url="http://none", control_token="x")
    assert agent.install_bundle(bundle)["release_id"] == "rel-1"
    assert (store / digest / "model.pth").read_bytes() == content


def test_unsigned_or_tampered_trust_list_is_rejected(tmp_path):
    signing = Ed25519PrivateKey.generate()
    trust, _root = _write_trust(tmp_path, signing.public_key().public_bytes_raw())
    payload = json.loads(trust.read_text())
    payload["list_version"] = 99
    trust.write_text(json.dumps(payload))
    agent = ModelAgent(store_root=tmp_path / "store", state_path=tmp_path / "state.json", trust_path=trust, inference_url="http://none", control_token="x")
    with pytest.raises(BundleError, match="INVALID_TRUST_LIST"):
        agent._trusted_key("release-1")


def _agent_with_state(tmp_path: Path, state: dict) -> ModelAgent:
    agent = ModelAgent(
        store_root=tmp_path / "store", state_path=tmp_path / "state.json",
        trust_path=tmp_path / "keys.json", inference_url="http://none", control_token="x",
    )
    (tmp_path / "state.json").write_text(json.dumps(state))
    return agent


def test_delete_artifact_refuses_sha_referenced_by_active_set(tmp_path):
    sha = "1" * 64
    state = {
        "active_set_id": "set-1",
        "sets": {"set-1": {"set_id": "set-1", "state": "ACTIVE", "revisions": {"default": "rev-1"}}},
        "revision_catalog": {"rev-1": {"revision_id": "rev-1", "slots": {"primary": {"sha256": sha}}}},
    }
    agent = _agent_with_state(tmp_path, state)
    (agent.store_root / sha).mkdir(parents=True)
    with pytest.raises(BundleError, match="ARTIFACT_IN_USE"):
        agent.delete_artifact(sha)
    assert (agent.store_root / sha).is_dir()


def test_delete_artifact_removes_unreferenced_sha(tmp_path):
    sha = "2" * 64
    state = {"active_set_id": None, "sets": {}, "revision_catalog": {}}
    agent = _agent_with_state(tmp_path, state)
    (agent.store_root / sha).mkdir(parents=True)
    (agent.store_root / sha / "manifest.json").write_text("{}")
    result = agent.delete_artifact(sha)
    assert result == {"sha256": sha, "deleted": True}
    assert not (agent.store_root / sha).exists()


def test_delete_artifact_rejects_bad_sha_or_missing_artifact(tmp_path):
    agent = _agent_with_state(tmp_path, {"active_set_id": None, "sets": {}, "revision_catalog": {}})
    with pytest.raises(BundleError, match="INVALID_ARTIFACT_SHA256"):
        agent.delete_artifact("not-a-sha")
    with pytest.raises(BundleError, match="ARTIFACT_NOT_FOUND"):
        agent.delete_artifact("3" * 64)
