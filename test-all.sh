#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_HEALTH_URL="${API_HEALTH_URL:-http://localhost:9541/actuator/health}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-900}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

RUN_REBUILD=true
RUN_BACKEND=true
RUN_FRONTEND=true
RUN_PLAYWRIGHT=true
RUN_API=true
RUN_AI_FLOW=true
WAIT_FOR_SERVICES=true

log_info() {
  printf '[INFO] %s\n' "$1"
}

log_success() {
  printf '[OK] %s\n' "$1"
}

log_error() {
  printf '[ERROR] %s\n' "$1" >&2
}

show_help() {
  cat <<'EOF'
Usage: ./test-all.sh [options]

Runs the full local regression flow:
  1. ./rebuild.sh
  2. wait for Docker services
  3. backend Maven tests
  4. frontend Vitest tests
  5. frontend Playwright smoke tests
  6. Python API tests
  7. Python full AI inference flow

Options:
  --skip-rebuild       Do not rebuild images or restart Docker services.
  --skip-backend       Skip backend Maven tests.
  --skip-frontend      Skip frontend Vitest tests.
  --skip-playwright    Skip frontend Playwright smoke tests.
  --skip-api           Skip Python API tests.
  --skip-ai-flow       Skip the long AI inference full-flow test.
  --no-wait            Do not wait for API Gateway health before E2E tests.
  --smoke              Run a shorter smoke pass: skip rebuild and AI full-flow.
  --help               Show this help.

Environment:
  API_HEALTH_URL              Default: http://localhost:9541/actuator/health
  HEALTH_TIMEOUT_SECONDS      Default: 900
  PYTHON_BIN                  Default: python3
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-rebuild)
      RUN_REBUILD=false
      ;;
    --skip-backend)
      RUN_BACKEND=false
      ;;
    --skip-frontend)
      RUN_FRONTEND=false
      ;;
    --skip-playwright)
      RUN_PLAYWRIGHT=false
      ;;
    --skip-api)
      RUN_API=false
      ;;
    --skip-ai-flow)
      RUN_AI_FLOW=false
      ;;
    --no-wait)
      WAIT_FOR_SERVICES=false
      ;;
    --smoke)
      RUN_REBUILD=false
      RUN_AI_FLOW=false
      ;;
    --help)
      show_help
      exit 0
      ;;
    *)
      log_error "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
  shift
done

run_step() {
  local name="$1"
  shift

  log_info "$name"
  "$@"
  log_success "$name"
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local start
  local elapsed

  start="$(date +%s)"
  log_info "Waiting for $name at $url"

  while true; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log_success "$name is ready"
      return 0
    fi

    elapsed=$(($(date +%s) - start))
    if ((elapsed >= HEALTH_TIMEOUT_SECONDS)); then
      log_error "$name did not become ready within ${HEALTH_TIMEOUT_SECONDS}s"
      return 1
    fi

    sleep 5
  done
}

ensure_python_e2e_deps() {
  if "$PYTHON_BIN" -c 'import pytest, requests' >/dev/null 2>&1; then
    return 0
  fi

  log_info "Installing Python E2E dependencies"
  "$PYTHON_BIN" -m pip install -r "$ROOT_DIR/e2e/requirements.txt"
}

cd "$ROOT_DIR"

if [[ "$RUN_REBUILD" == true ]]; then
  run_step "Rebuild Docker images and restart services" "$ROOT_DIR/rebuild.sh"
fi

if [[ "$RUN_BACKEND" == true ]]; then
  run_step "Run backend Maven tests" "$ROOT_DIR/backEnd/api_gateway/mvnw" -f "$ROOT_DIR/backEnd/api_gateway/pom.xml" test
fi

if [[ "$RUN_FRONTEND" == true ]]; then
  run_step "Run frontend Vitest tests" npm --prefix "$ROOT_DIR/frontEnd" test
fi

if [[ "$RUN_PLAYWRIGHT" == true ]]; then
  run_step "Run frontend Playwright smoke tests" npm --prefix "$ROOT_DIR/frontEnd" run e2e
fi

if [[ "$WAIT_FOR_SERVICES" == true && ("$RUN_API" == true || "$RUN_AI_FLOW" == true) ]]; then
  wait_for_url "API Gateway" "$API_HEALTH_URL"
fi

if [[ "$RUN_API" == true ]]; then
  ensure_python_e2e_deps
  (
    cd "$ROOT_DIR/e2e"
    run_step "Run Python API tests" "$PYTHON_BIN" -m pytest -q test_user_api.py test_project_api.py test_file_api.py test_task_api.py
  )
fi

if [[ "$RUN_AI_FLOW" == true ]]; then
  ensure_python_e2e_deps
  (
    cd "$ROOT_DIR/e2e"
    run_step "Run Python full AI inference flow" "$PYTHON_BIN" -m pytest -q test_e2e_full_flow.py
  )
fi

log_success "All requested tests finished"
