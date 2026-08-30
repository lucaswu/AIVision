#!/usr/bin/env python3
"""Build and sign one model-delivery release bundle for model-agent.

model-agent (model/weld/model_agent.py) only accepts a specific zip layout:

    release.zip
    |-- manifest.json      canonical JSON, see manifest field table in
    |                      docs/release-runbook.md section 4.2
    |-- manifest.sig       base64 Ed25519 signature over manifest.json's
    |                      canonical encoding
    |-- key_id             plain text, must be a key currently listed (and
    |                      not revoked) in deploy/model-trust/keys.json
    `-- weights/<file>     exactly one file, no subdirectories, no symlinks

This is a general-purpose tool: every field that varies bundle-to-bundle is a
CLI flag. There is no per-slot table baked in here on purpose -- future slots
and future model updates use the same command with different flag values.

Usage (one bundle per slot; a profile with 4 slots needs 4 separate runs):

    python3 build_model_bundle.py \
      --weight-file /path/to/weldROI4.pt \
      --slot roi \
      --release-id rel-2026-08-29-roi-bootstrap \
      --minimum-inference-version 1.0.0 \
      --preprocess-contract-version v1 \
      --preprocess-config-sha256 <shared across every slot in the profile> \
      --postprocess-contract-version v1 \
      --input-size 640 \
      --coordinate-space roi_crop@v1 \
      --produces roi_crop@v1 \
      --consumes image@v1 \
      --key-id delivery-ed25519-v2 \
      --signing-key-file /secure/place/delivery-signing-key.b64 \
      --output release-roi.zip

The signing private key is never accepted inline on the command line (shell
history, `ps`, CI logs would all leak it) -- pass a path via
--signing-key-file, or set SIGNING_KEY_B64 in the environment.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_signing_key(args: argparse.Namespace) -> Ed25519PrivateKey:
    if args.signing_key_file:
        raw_b64 = Path(args.signing_key_file).read_text(encoding="utf-8").strip()
    else:
        raw_b64 = os.environ.get("SIGNING_KEY_B64", "").strip()
    if not raw_b64:
        sys.exit("signing key required: pass --signing-key-file or set SIGNING_KEY_B64")
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(raw_b64, validate=True))


def build_manifest(args: argparse.Namespace, digest: str) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "release_id": args.release_id,
        "slot": args.slot,
        "manifest_version": 2,
        "artifact": {
            "sha256": digest,
            "relative_path": f"weights/{Path(args.weight_file).name}",
        },
        "compatibility": {
            "minimum_inference_version": args.minimum_inference_version,
            "preprocess_contract_version": args.preprocess_contract_version,
            "preprocess_config_sha256": args.preprocess_config_sha256,
            "postprocess_contract_version": args.postprocess_contract_version,
            "input_size": args.input_size,
            "interface": {
                "coordinate_space": args.coordinate_space,
                "produces": args.produces,
                "consumes": args.consumes,
            },
        },
    }
    if args.ordered_class_map:
        manifest["compatibility"]["ordered_class_map"] = json.loads(args.ordered_class_map)
    if args.class_map_group:
        manifest["compatibility"]["class_map_group"] = args.class_map_group
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--weight-file", required=True, help="path to the single weight file this bundle carries")
    parser.add_argument("--slot", required=True, choices=["roi", "primary", "correction", "location_0", "location_1"])
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--minimum-inference-version", required=True, help="semver, must be <= the running INFERENCE_VERSION")
    parser.add_argument("--preprocess-contract-version", required=True)
    parser.add_argument("--preprocess-config-sha256", required=True, help="must be byte-identical across every slot in the same profile")
    parser.add_argument("--postprocess-contract-version", required=True)
    parser.add_argument("--input-size", required=True, type=int)
    parser.add_argument("--coordinate-space", required=True)
    parser.add_argument("--produces", nargs="*", default=[], help="coordinate spaces this slot's output is in")
    parser.add_argument("--consumes", nargs="*", default=[], help="coordinate spaces this slot needs as input (use image@v1 for the raw input image)")
    parser.add_argument("--ordered-class-map", help="JSON array string; omit if this slot has no class map")
    parser.add_argument("--class-map-group", help="only meaningful together with --ordered-class-map")
    parser.add_argument("--key-id", required=True, help="must be listed (and not revoked) in deploy/model-trust/keys.json")
    parser.add_argument("--signing-key-file", help="path to a file containing the base64 Ed25519 private key")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    weight_path = Path(args.weight_file)
    if not weight_path.is_file():
        sys.exit(f"weight file not found: {weight_path}")

    signer = load_signing_key(args)
    digest = sha256_file(weight_path)
    manifest = build_manifest(args, digest)
    signature = base64.b64encode(signer.sign(canonical(manifest))).decode()

    output_path = Path(args.output)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", canonical(manifest))
        archive.writestr("manifest.sig", signature)
        archive.writestr("key_id", args.key_id)
        archive.write(weight_path, f"weights/{weight_path.name}")

    print(f"{output_path} ready  slot={args.slot}  sha256={digest}  release_id={args.release_id}")


if __name__ == "__main__":
    main()
