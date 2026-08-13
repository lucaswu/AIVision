# Model Delivery Trust Material

This directory is mounted read-only into `model-agent`. It must contain:

```text
root.pub
keys.json
```

`root.pub` is the base64-encoded 32-byte Ed25519 root public key. `keys.json`
contains the following canonical JSON fields before its `signature` is added:

```json
{
  "list_version": 1,
  "root_key_id": "delivery-root-v1",
  "expires_at": "2026-12-31T00:00:00+00:00",
  "keys": {
    "delivery-ed25519-v1": "<base64 Ed25519 public key>"
  }
}
```

`signature` must be a base64 Ed25519 signature made by `root.pub` over the
canonical JSON encoding: UTF-8, sorted keys, and `,`/`:` separators. Do not
store a signing private key in this directory or in the repository.
