#!/bin/sh
set -eu

if [ "${BUILD_FLAVOR:-development}" = "production" ]; then
  : "${INFERENCE_TLS_CERT_FILE:?INFERENCE_TLS_CERT_FILE is required in production}"
  : "${INFERENCE_TLS_KEY_FILE:?INFERENCE_TLS_KEY_FILE is required in production}"
  : "${INFERENCE_TLS_CA_FILE:?INFERENCE_TLS_CA_FILE is required in production}"
  nginx -c /app/model/nginx-model-control.conf
  # Bind to loopback so the public 8000 listener and the mTLS 9443 listener are
  # the only ways in. Without this the /internal control plane would be
  # reachable directly on the published port and mTLS would prove nothing.
  exec uvicorn api_server:app --host 127.0.0.1 --port 8001 --workers 1
fi

exec uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 1
