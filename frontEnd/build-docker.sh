#!/bin/bash

# 前端容器化构建脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
IMAGE_NAME="aivision-frontend"
TAG="latest"
CONTAINER_NAME="aivision-frontend-container"
PORT="3000"

echo -e "${GREEN}=== AIVision 前端容器化构建脚本 ===${NC}"

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}错误: Docker 未运行，请先启动 Docker${NC}"
    exit 1
fi

# 构建镜像
echo -e "${YELLOW}正在构建前端镜像...${NC}"
docker build -t ${IMAGE_NAME}:${TAG} .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 镜像构建成功: ${IMAGE_NAME}:${TAG}${NC}"
else
    echo -e "${RED}❌ 镜像构建失败${NC}"
    exit 1
fi

# 停止并删除现有容器（如果存在）
if [ "$(docker ps -aq -f name=${CONTAINER_NAME})" ]; then
    echo -e "${YELLOW}停止并删除现有容器...${NC}"
    docker stop ${CONTAINER_NAME} > /dev/null 2>&1 || true
    docker rm ${CONTAINER_NAME} > /dev/null 2>&1 || true
fi

# 运行容器
echo -e "${YELLOW}启动前端容器...${NC}"
docker run -d \
    --name ${CONTAINER_NAME} \
    -p ${PORT}:80 \
    ${IMAGE_NAME}:${TAG}

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 容器启动成功${NC}"
    echo -e "${GREEN}🌐 前端应用访问地址: http://localhost:${PORT}${NC}"
    echo -e "${GREEN}📊 容器状态: docker ps | grep ${CONTAINER_NAME}${NC}"
    echo -e "${GREEN}📝 查看日志: docker logs ${CONTAINER_NAME}${NC}"
    echo -e "${GREEN}🛑 停止容器: docker stop ${CONTAINER_NAME}${NC}"
else
    echo -e "${RED}❌ 容器启动失败${NC}"
    exit 1
fi

echo -e "${GREEN}=== 构建完成 ===${NC}"

