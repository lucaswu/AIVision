# Model Agent mTLS Material

Production model control uses `https://ai-inference:9443`; the public inference
API remains on port `8000`. Place these files here with read-only mounts:

```text
ca.crt
inference.crt
inference.key
agent.crt
agent.key
```

`inference.crt` must identify `ai-inference` and be signed by `ca.crt`.
`agent.crt` must be a client certificate signed by the same CA. Use an external
secret manager or a secure deployment mechanism for private keys; never commit
real certificate material. Set production `INFERENCE_INTERNAL_URL` to
`https://ai-inference:9443` and provide a non-empty `MODEL_AGENT_CONTROL_TOKEN`
as an additional application-level control identity.
