#!/bin/bash
set -uo pipefail

# 客户交付包升级脚本模板。
# 使用场景：脚本与 .env、docker-compose.yml/.gpu.yml/.infra.yml 放在同一目录下
# （例如客户机器上的 /opt/huodian/infra/3-15-upgrade），.env 里的
# BACKEND_IMAGE / FRONTEND_IMAGE / AI_INFERENCE_IMAGE 都通过 ${IMAGE_TAG} 拼接镜像名，
# 所以只要把 IMAGE_TAG 改掉，compose 就会解析到新镜像，不需要本地 retag。
#
# 用法: ./pull.sh <tag>
# 例如: ./pull.sh 7-8

if [ $# -lt 1 ]; then
  echo "用法: $0 <tag>"
  echo "例如: $0 7-8"
  exit 1
fi

TAG="$1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

ENV_FILE="$SCRIPT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "未找到 .env: $ENV_FILE"
  exit 1
fi

CURRENT_TAG=$(grep -E '^IMAGE_TAG=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)
echo "当前 IMAGE_TAG: ${CURRENT_TAG:-<未设置>}"
echo "目标 IMAGE_TAG: ${TAG}"

# --- 1. 备份并更新 .env 中的 IMAGE_TAG ---
BACKUP_FILE="$ENV_FILE.bak-$(date +%Y%m%d-%H%M%S)"
cp "$ENV_FILE" "$BACKUP_FILE"
echo ".env 已备份到: $BACKUP_FILE"

if grep -q '^IMAGE_TAG=' "$ENV_FILE"; then
  sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${TAG}/" "$ENV_FILE"
else
  echo "IMAGE_TAG=${TAG}" >> "$ENV_FILE"
fi

# --- 2. 应用服务清单（与 docker-compose.yml 中的 service 名对应） ---
APP_SERVICES=(api-gateway ai-inference frontend)

# 对应的容器名，用于后面的健康检查（docker-compose.yml / docker-compose.infra.yml 中固定写死）
CONTAINERS=(ai-detection-gateway ai-detection-inference ai-detection-frontend)
# 若当前 COMPOSE_FILE 中包含 postgres/minio（即基础设施跟应用一起用 compose 管），一并纳入检查；
# 若客户使用外部 PostgreSQL/MinIO（compose 配置里没有这两个 service），则跳过。
if docker compose config --services 2>/dev/null | grep -q '^postgres$'; then
  CONTAINERS+=(ai-detection-postgres)
fi
if docker compose config --services 2>/dev/null | grep -q '^minio$'; then
  CONTAINERS+=(ai-detection-minio)
fi
# 若 compose 中已接入模型交付的 model-agent（跟 ai-inference 之间走 mTLS 管理通道），
# 一并纳入拉取/重启/健康检查；旧版没有该 service 时自动跳过，脚本对两种状态都兼容。
HAS_MODEL_AGENT=0
if docker compose config --services 2>/dev/null | grep -q '^model-agent$'; then
  HAS_MODEL_AGENT=1
  APP_SERVICES+=(model-agent)
  CONTAINERS+=(ai-detection-model-agent)
fi

# --- 3. 拉取新 tag 对应的镜像 ---
# BACKEND_IMAGE/FRONTEND_IMAGE/AI_INFERENCE_IMAGE 已经在 .env 里通过 ${IMAGE_TAG} 拼好完整镜像名，
# docker compose 会自动读取当前目录的 .env 做变量替换，所以这里直接对 service 名 pull 即可。
echo
echo "拉取镜像 (tag=${TAG})..."
docker compose pull "${APP_SERVICES[@]}" || {
  echo "镜像拉取失败，请检查 tag 是否存在于仓库中；.env 已保留改动，如需回滚执行："
  echo "  cp $BACKUP_FILE $ENV_FILE"
  exit 1
}

# --- 4. 重启应用服务（不动 postgres/minio） ---
if [ "$HAS_MODEL_AGENT" -eq 1 ]; then
  # model-volume-init 是一次性任务，重复执行是幂等的（mkdir -p + chown -R），
  # 每次升级都跑一遍，确保 model_store/model_active/model_inbox 等卷权限始终正确。
  echo
  echo "校验模型卷权限 (model-volume-init)..."
  docker compose up -d model-volume-init
fi

echo
echo "重启应用服务: ${APP_SERVICES[*]}..."
docker compose up -d --no-deps "${APP_SERVICES[@]}"

# --- 5. 等待容器变健康 ---
# 等待时长不能写死：ai-inference 的健康检查 start_period 由 docker-compose.yml
# 决定（TensorRT engine 缓存卷是空的时候——比如第一次部署，或者换了GPU型号——
# 首次启动要把所有模型的engine现场编译一遍，耗时比start_period本身还长很多，
# 这里从容器实际的健康检查配置里读start_period，再加一点余量，而不是硬编码
# 一个可能跟compose配置脱节的秒数。
INFERENCE_START_PERIOD_NS=$(docker inspect -f '{{if .Config.Healthcheck}}{{.Config.Healthcheck.StartPeriod}}{{else}}0{{end}}' ai-detection-inference 2>/dev/null || echo 0)
INFERENCE_START_PERIOD_S=$((INFERENCE_START_PERIOD_NS / 1000000000))
WAIT_SECONDS=$((INFERENCE_START_PERIOD_S > 300 ? INFERENCE_START_PERIOD_S + 60 : 300))
echo
echo "等待容器变健康（最长 ${WAIT_SECONDS}s，ai-inference 健康检查 start_period=${INFERENCE_START_PERIOD_S}s）..."
DEADLINE=$((SECONDS + WAIT_SECONDS))
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
if [ "$FAILED" -eq 0 ]; then
  echo "Done. IMAGE_TAG 已更新为 ${TAG}，所有容器健康。"
else
  echo "Done, 但上面有失败项。如需回滚 .env 执行："
  echo "  cp $BACKUP_FILE $ENV_FILE && docker compose pull ${APP_SERVICES[*]} && docker compose up -d --no-deps ${APP_SERVICES[*]}"
  exit 1
fi
