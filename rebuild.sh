#!/bin/bash
set -e

# 推理服务起不来时给出可操作的诊断信息，而不是让脚本停在一行 compose 报错上。
# 注意：这里只做检测和提示，不自动打包/签名/激活模型——签名私钥不应该被自动化
# 流程碰，"是否要发布一个模型组合"也必须是人做的决定，不能由 rebuild.sh 替你决定。
diagnose_inference_not_ready() {
  echo
  echo "============================================================"
  echo "ai-detection-inference 没有变成 healthy，服务栈没有完全起来。"
  echo "============================================================"

  local build_flavor
  build_flavor=$(grep -E '^BUILD_FLAVOR=' .env 2>/dev/null | cut -d= -f2)

  if [ "$build_flavor" = "production" ]; then
    local runtime_state
    runtime_state=$(curl -sS --noproxy '*' --max-time 5 "http://127.0.0.1:${AI_PORT}/models" 2>/dev/null \
      | python3 -c "import json,sys; print(json.load(sys.stdin).get('runtime_state',''))" 2>/dev/null)
    if [ "$runtime_state" != "active" ]; then
      echo "生产模式（BUILD_FLAVOR=production）下，推理服务必须先有一个已激活的模型组合才能就绪，"
      echo "而这台机器的 model_store/model_active 卷里目前没有——大概率是全新部署，或者卷被清空了。"
      echo
      echo "需要手动打包签名并激活一次模型（不会自动执行）："
      echo "  1. python3 model/weld/scripts/build_model_bundle.py --help   查看打包/签名用法"
      echo "  2. 装好后调用 /models/install + /models/activate 激活，具体步骤见 docs/release-runbook.md 第 4-5 节"
      echo
    fi
  fi

  echo "也可以先看日志排查其他原因：docker compose logs ai-inference --tail 100"
  echo "============================================================"
}

# 预下载 OCR 模型（如果尚未存在）
# echo "Checking OCR model weights..."
# bash model/weld/scripts/download_ocr_models.sh

echo "Building backend..."
docker build --provenance=false --sbom=false -t aivision-backend:latest -f backEnd/api_gateway/Dockerfile .

echo "Building frontend..."
docker build --provenance=false --sbom=false -t aivision-frontend:latest ./frontEnd

echo "Building AI inference (weld)..."
# 构建上下文为 model/ 目录，以便同时访问 weld/ 和 OCR/ 子目录
docker build --provenance=false --sbom=false -t aivision-ai-inference:latest -f model/weld/Dockerfile.ai model/

echo "Building model-agent..."
# model-agent 与推理服务分离部署，独占模型库写权限；构建上下文同样是 model/ 目录
docker build --provenance=false --sbom=false -t aivision-model-agent:latest -f model/weld/Dockerfile.model-agent model/

echo "Restarting services..."

# 释放推理服务端口（宿主机上可能有裸跑的推理进程）。
# 注意：这里必须是推理端口而不是 8000 —— 训练平台后端占用宿主机 8000，
# 误杀它会连带停掉训练平台。
AI_PORT="${AI_INFERENCE_PORT:-8100}"
PORT_PID=$(lsof -ti ":${AI_PORT}" 2>/dev/null || true)
if [ -n "$PORT_PID" ]; then
  echo "Stopping process on port ${AI_PORT} (PID: $PORT_PID)..."
  kill -9 "$PORT_PID" 2>/dev/null || true
  for i in $(seq 1 10); do
    ss -tlnp | grep -q ":${AI_PORT} " || break
    sleep 1
  done
fi

cd deploy
# 注意: docker compose down 不会删除 named volumes（数据库数据安全）
# 只有 docker compose down -v 才会删除卷
docker compose down 
# gateway/frontend 依赖 ai-inference healthy 才会启动；ai-inference 起不来时
# compose 自己也会返回非零码，这里先不让 set -e 直接掐断脚本，改成走下面的诊断分支。
set +e
docker compose up -d
UP_STATUS=$?
set -e

INFERENCE_STATUS=$(docker inspect -f '{{.State.Status}}' ai-detection-inference 2>/dev/null)
INFERENCE_HEALTH=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' ai-detection-inference 2>/dev/null)

if [ "$UP_STATUS" -ne 0 ] || [ "$INFERENCE_STATUS" != "running" ] || [ "$INFERENCE_HEALTH" = "unhealthy" ]; then
  diagnose_inference_not_ready
  exit 1
fi

echo "Done!"
echo
echo "Frontend:        http://127.0.0.1:3000"
echo "API Gateway:     http://127.0.0.1:9541"
echo "Swagger:         http://127.0.0.1:9541/swagger-ui.html"
echo "Health check:    http://127.0.0.1:9541/actuator/health"
echo "AI Inference:    http://127.0.0.1:${AI_PORT}"
