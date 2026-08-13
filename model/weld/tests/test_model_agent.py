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
