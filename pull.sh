#!/bin/bash
set -uo pipefail

# Check if tag is provided, default to latest if not
TAG=${1:-latest}

echo "Using tag: $TAG"

# Registry address
REGISTRY="crpi-wypvanlammbrxwe3.cn-hangzhou.personal.cr.aliyuncs.com/aivisondocker"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$SCRIPT_DIR/deploy"
ENV_FILE="$DEPLOY_DIR/.env"

# 部署机每个服务的容器名固定在 docker-compose.yml 里，直接按名字探活比解析
# `docker compose ps` 的输出格式更稳（不同 compose 版本输出列不一样）。
CONTAINERS=(ai-detection-postgres ai-detection-inference ai-detection-model-agent ai-detection-gateway ai-detection-frontend)

# --- 1. 拉取镜像 ---
echo "Pulling images..."
docker pull "${REGISTRY}/aivision-ai-inference:${TAG}" || exit 1
docker pull "${REGISTRY}/aivision-frontend:${TAG}" || exit 1
docker pull "${REGISTRY}/aivision-backend:${TAG}" || exit 1
docker pull "${REGISTRY}/aivision-model-agent:${TAG}" || exit 1

# --- 2. 重新打成 docker-compose.yml 期待的裸镜像名 ---
# backend/frontend 在 compose 里写死了 aivision-backend:latest / aivision-frontend:latest；
# ai-inference/model-agent 虽然可以通过 .env 里的 AI_INFERENCE_IMAGE/MODEL_AGENT_IMAGE 指到
# 带仓库前缀的镜像名，但这台机器的 .env 用的是裸名，所以统一在这里 retag，
# 不然 `docker compose up -d` 会继续用本地旧镜像，pull 了个寂寞。
echo "Tagging images for docker compose..."
docker tag "${REGISTRY}/aivision-ai-inference:${TAG}" aivision-ai-inference:latest
docker tag "${REGISTRY}/aivision-frontend:${TAG}" aivision-frontend:latest
docker tag "${REGISTRY}/aivision-backend:${TAG}" aivision-backend:latest
docker tag "${REGISTRY}/aivision-model-agent:${TAG}" aivision-model-agent:latest

# --- 3. 记录升级前的模型运行状态，升级后用来核对没有被顶掉 ---
# model_store/model_active 是具名卷，理论上镜像升级不会碰它们；这里实测确认一下，
# 而不是假设"理论上"成立。
AI_INFERENCE_PORT=$(grep -E '^AI_INFERENCE_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2)
AI_INFERENCE_PORT=${AI_INFERENCE_PORT:-8100}
MODEL_ADMIN_TOKEN=$(grep -E '^MODEL_ADMIN_TOKEN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)
ENV_INFERENCE_VERSION=$(grep -E '^INFERENCE_VERSION=' "$ENV_FILE" 2>/dev/null | cut -d= -f2)

# TAG 是镜像发布批次标识（可以是日期等任意格式），跟 INFERENCE_VERSION 是两回事：
# 后者必须是严格 semver（X.Y.Z），是模型包 minimum_inference_version 比较的基准，
# production 模式下推理服务启动时也会校验这一点，格式不对会直接拒绝启动。
# 这里只保证 .env 里现有的 INFERENCE_VERSION 没有被手滑改成非法格式，不再要求它和 TAG 相同。
if [ -n "$ENV_INFERENCE_VERSION" ]; then
  core="${ENV_INFERENCE_VERSION%%[-+]*}"
  IFS=. read -r major minor patch extra <<< "$core"
  if [ -z "$major" ] || [ -z "$minor" ] || [ -z "$patch" ] || [ -n "$extra" ] \
     || ! [[ "$major$minor$patch" =~ ^[0-9]+$ ]]; then
    echo "WARNING: deploy/.env 里的 INFERENCE_VERSION ($ENV_INFERENCE_VERSION) 不是合法 semver（X.Y.Z）。"
    echo "         production 模式下推理服务会因此拒绝启动，模型包的 minimum_inference_version 比较也会失败。"
  fi
fi

model_snapshot() {
  [ -z "$MODEL_ADMIN_TOKEN" ] && { echo '{}'; return; }
  curl -sS --noproxy '*' --max-time 5 \
    -H "X-Model-Admin-Token: ${MODEL_ADMIN_TOKEN}" \
    "http://127.0.0.1:${AI_INFERENCE_PORT}/models" 2>/dev/null || echo '{}'
}

json_get() {
  python3 -c "import json,sys; print(json.loads(sys.argv[1]).get(sys.argv[2], ''))" "$1" "$2" 2>/dev/null
}

BEFORE_JSON=$(model_snapshot)
BEFORE_SET_ID=$(json_get "$BEFORE_JSON" set_id)
BEFORE_GENERATION=$(json_get "$BEFORE_JSON" generation)

# --- 4. 重启服务 ---
echo "Restarting services..."
cd "$DEPLOY_DIR" || exit 1
docker compose down
docker compose up -d

# --- 5. 等待容器变健康 ---
echo "Waiting for containers to become healthy..."
DEADLINE=$((SECONDS + 300))
while true; do
  ALL_OK=1
  for name in "${CONTAINERS[@]}"; do
    status=$(docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null)
    if [ "$status" != "running" ]; then
      ALL_OK=0
      break
    fi
    health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name" 2>/dev/null)
    if [ "$health" != "none" ] && [ "$health" != "healthy" ]; then
      ALL_OK=0
      break
    fi
  done
  [ "$ALL_OK" -eq 1 ] && break
  if [ "$SECONDS" -ge "$DEADLINE" ]; then
    break
  fi
  sleep 5
done

echo
echo "=== docker compose ps ==="
docker compose ps

# --- 6. 核对结果 ---
FAILED=0
echo
echo "=== 容器健康检查 ==="
for name in "${CONTAINERS[@]}"; do
  status=$(docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null)
  health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name" 2>/dev/null)
  if [ -z "$status" ]; then
    echo "  $name: MISSING"
    FAILED=1
  elif [ "$status" != "running" ]; then
    echo "  $name: NOT RUNNING (status=$status)"
    FAILED=1
  elif [ "$health" != "none" ] && [ "$health" != "healthy" ]; then
    echo "  $name: UNHEALTHY (health=$health)"
    FAILED=1
  else
    echo "  $name: OK"
  fi
done

echo
echo "=== 模型运行状态核对 ==="
AFTER_JSON=$(model_snapshot)
AFTER_STATE=$(json_get "$AFTER_JSON" runtime_state)
AFTER_SET_ID=$(json_get "$AFTER_JSON" set_id)
AFTER_GENERATION=$(json_get "$AFTER_JSON" generation)

if [ -z "$MODEL_ADMIN_TOKEN" ]; then
  echo "  跳过：deploy/.env 里没找到 MODEL_ADMIN_TOKEN"
elif [ "$AFTER_STATE" != "active" ]; then
  echo "  runtime_state=$AFTER_STATE（不是 active，模型没能在镜像升级后自动恢复，需要看 docker compose logs ai-inference 排查）"
  FAILED=1
else
  echo "  runtime_state=active"
  if [ -n "$BEFORE_SET_ID" ]; then
    if [ "$BEFORE_SET_ID" = "$AFTER_SET_ID" ] && [ "$BEFORE_GENERATION" = "$AFTER_GENERATION" ]; then
      echo "  set_id/generation 升级前后一致（$AFTER_SET_ID @ $AFTER_GENERATION），模型状态没有被镜像升级顶掉。"
    else
      echo "  WARNING: set_id/generation 变了：升级前 $BEFORE_SET_ID@$BEFORE_GENERATION -> 升级后 $AFTER_SET_ID@$AFTER_GENERATION"
      echo "           镜像升级本不应该改变已激活的模型版本，出现变化要确认是不是预期之外的回滚/重置。"
    fi
  else
    echo "  升级前没有采集到基线（可能是本来就没在跑），本次不做前后比对。"
  fi
fi

echo
if [ "$FAILED" -eq 0 ]; then
  echo "Done. 部署机所有容器健康，模型状态正常。"
else
  echo "Done, 但上面有失败项，请检查后再确认这次发布是否可用。"
  exit 1
fi
