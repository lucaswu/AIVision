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

echo "Restarting services..."

# 释放 8000 端口（宿主机上可能有推理服务在运行）
PORT_8000_PID=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$PORT_8000_PID" ]; then
  echo "Stopping process on port 8000 (PID: $PORT_8000_PID)..."
  kill -9 "$PORT_8000_PID" 2>/dev/null || true
  # 等端口真正释放
  for i in $(seq 1 10); do
    ss -tlnp | grep -q ':8000 ' || break
    sleep 1
  done
fi

cd deploy
# 注意: docker compose down 不会删除 named volumes（数据库数据安全）
# 只有 docker compose down -v 才会删除卷
docker compose down 
docker compose up -d

echo "Done!"
