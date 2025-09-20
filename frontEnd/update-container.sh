#!/bin/bash

# 更新现有容器的脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

CONTAINER_NAME="aivision-frontend-container"
IMAGE_NAME="aivision-frontend:fixed"

echo -e "${GREEN}=== 更新Frontend容器 ===${NC}"

# 检查容器是否存在并运行
if [ "$(docker ps -q -f name=${CONTAINER_NAME})" ]; then
    echo -e "${GREEN}✅ 容器 ${CONTAINER_NAME} 正在运行${NC}"
    echo -e "${GREEN}🌐 前端应用访问地址: http://localhost:3000${NC}"
    
    # 检查容器健康状态
    echo -e "${YELLOW}检查容器状态...${NC}"
    docker ps | grep ${CONTAINER_NAME}
    
    echo -e "${GREEN}📝 查看实时日志: docker logs -f ${CONTAINER_NAME}${NC}"
    echo -e "${GREEN}🛑 停止容器: docker stop ${CONTAINER_NAME}${NC}"
    echo -e "${GREEN}🔄 重启容器: docker restart ${CONTAINER_NAME}${NC}"
    
elif [ "$(docker ps -aq -f name=${CONTAINER_NAME})" ]; then
    echo -e "${YELLOW}容器存在但未运行，正在启动...${NC}"
    docker start ${CONTAINER_NAME}
    echo -e "${GREEN}✅ 容器已启动${NC}"
else
    echo -e "${YELLOW}容器不存在，正在创建新容器...${NC}"
    docker run -d \
        --name ${CONTAINER_NAME} \
        -p 3000:80 \
        ${IMAGE_NAME}
    echo -e "${GREEN}✅ 新容器已创建并启动${NC}"
fi

echo -e "${GREEN}=== 完成 ===${NC}"

