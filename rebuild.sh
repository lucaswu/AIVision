#!/bin/bash
set -e

# 预下载 OCR 模型（如果尚未存在）
# echo "Checking OCR model weights..."
# bash model/weld/scripts/download_ocr_models.sh

echo "Building backend..."
docker build -t aivision-backend:latest -f backEnd/api_gateway/Dockerfile .

echo "Building frontend..."
docker build  -t aivision-frontend:latest ./frontEnd

echo "Building AI inference (weld)..."
# 构建上下文为 model/ 目录，以便同时访问 weld/ 和 OCR/ 子目录
docker build -t aivision-ai-inference:latest -f model/weld/Dockerfile.ai model/

echo "Building model-agent..."
# model-agent 与推理服务分离部署，独占模型库写权限；构建上下文同样是 model/ 目录
docker build -t aivision-model-agent:latest -f model/weld/Dockerfile.model-agent model/

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
docker compose up -d

echo "Done!"
