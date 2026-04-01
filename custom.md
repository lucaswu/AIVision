# AI Vision Custom Deployment Notes

本文档用于记录 AI Vision 在客户环境中的打包、部署和初始化方式，重点覆盖：

- 前端、后端、AI 推理镜像如何打包
- PostgreSQL 数据库如何初始化
- `docker-compose.yml` 如何编写
- 当前客户环境使用的 PostgreSQL / MinIO 参数

## 1. 目录说明

- 项目根目录：`AIVision/`
- 部署目录：[`deploy`](/Users/Dylan.Min/Documents/Code/work/huodian/AIVision/deploy)
- 升级包目录：[`deploy/3-15-upgrade`](/Users/Dylan.Min/Documents/Code/work/huodian/deploy/3-15-upgrade)
- 数据库初始化脚本：[`deploy/sql/init_database.sql`](/Users/Dylan.Min/Documents/Code/work/huodian/AIVision/deploy/sql/init_database.sql)

## 2. 三个镜像的打包方式

### 2.1 后端镜像

Dockerfile：
[`backEnd/api_gateway/Dockerfile`](/Users/Dylan.Min/Documents/Code/work/huodian/AIVision/backEnd/api_gateway/Dockerfile)

在项目根目录执行：

```bash
cd /Users/Dylan.Min/Documents/Code/work/huodian/AIVision

docker buildx build \
  --platform linux/amd64 \
  --load \
  -t aivision-backend:latest \
  -f backEnd/api_gateway/Dockerfile \
  .
```

### 2.2 前端镜像

Dockerfile：
[`frontEnd/Dockerfile`](/Users/Dylan.Min/Documents/Code/work/huodian/AIVision/frontEnd/Dockerfile)

在前端目录执行：

```bash
cd /Users/Dylan.Min/Documents/Code/work/huodian/AIVision/frontEnd

docker buildx build \
  --platform linux/amd64 \
  --load \
  -t aivision-frontend:latest \
  -f Dockerfile \
  .
```

### 2.3 AI 推理镜像

基础推理镜像 Dockerfile：
[`model/weld/Dockerfile.ai`](/Users/Dylan.Min/Documents/Code/work/huodian/AIVision/model/weld/Dockerfile.ai)

打包版推理镜像 Dockerfile：
[`model/weld/Dockerfile.pack`](/Users/Dylan.Min/Documents/Code/work/huodian/AIVision/model/weld/Dockerfile.pack)

先构建基础推理镜像：

```bash
cd /Users/Dylan.Min/Documents/Code/work/huodian/AIVision/model

docker buildx build \
  --platform linux/amd64 \
  --load \
  -t aivision-ai-inference:latest \
  -f weld/Dockerfile.ai \
  .
```

如果交付使用的是带模型文件的 packed 镜像，再执行：

```bash
cd /Users/Dylan.Min/Documents/Code/work/huodian/deploy/3-15-upgrade

./build-inference-packed-amd64.sh
```

默认会产出：

- `aivision-ai-inference:latest`
- `aivision-ai-inference:packed`

### 2.4 一键构建脚本

升级包目录中已有统一构建脚本：
[`build-images-amd64.sh`](/Users/Dylan.Min/Documents/Code/work/huodian/deploy/3-15-upgrade/build-images-amd64.sh)

执行方式：

```bash
cd /Users/Dylan.Min/Documents/Code/work/huodian/deploy/3-15-upgrade
./build-images-amd64.sh
```

说明：

- 该脚本会构建 `linux/amd64`
- 会构建后端、前端、基础推理镜像
- 如需 packed 推理镜像，再补执行 `./build-inference-packed-amd64.sh`

### 2.5 导出镜像

升级包目录中已有导出脚本：
[`export-images.sh`](/Users/Dylan.Min/Documents/Code/work/huodian/deploy/3-15-upgrade/export-images.sh)

执行方式：

```bash
cd /Users/Dylan.Min/Documents/Code/work/huodian/deploy/3-15-upgrade
./export-images.sh
```

导出结果位于：

- `deploy/images/backend.tar`
- `deploy/images/frontend.tar`
- `deploy/images/inference.tar`

## 3. 数据库初始化

初始化脚本：
[`deploy/sql/init_database.sql`](/Users/Dylan.Min/Documents/Code/work/huodian/AIVision/deploy/sql/init_database.sql)

该脚本会：

- 创建全部业务表
- 创建索引
- 初始化默认管理员用户

默认管理员：

- 用户名：`Admin`
- 密码：`password`

### 3.1 手工初始化 PostgreSQL

如果客户数据库为空库，建议先手工执行：

```bash
psql -h <PG_HOST> -p <PG_PORT> -U <PG_USER> -d <PG_DB> -f /path/to/init_database.sql
```

例如按当前客户环境：

```bash
psql -h 192.168.203.98 -p 5432 -U root -d hjpp -f deploy/sql/init_database.sql
```

### 3.2 自动初始化

升级包 `.env` 中支持：

```bash
INIT_DB_ON_START=true
```

但要求宿主机已安装 `psql`。默认配置是 `false`，即不自动初始化。

## 4. docker-compose 编写方式

客户环境推荐基于：
[`deploy/3-15-upgrade/docker-compose.yml`](/Users/Dylan.Min/Documents/Code/work/huodian/deploy/3-15-upgrade/docker-compose.yml)
和
[`deploy/3-15-upgrade/docker-compose.gpu.yml`](/Users/Dylan.Min/Documents/Code/work/huodian/deploy/3-15-upgrade/docker-compose.gpu.yml)

核心思路：

- PostgreSQL 使用客户外部数据库
- MinIO 使用客户外部对象存储
- `api-gateway` 和 `ai-inference` 共享 `files_data:/app/data/files`
- 后端使用 `storage.type=minio`
- 后端会在任务执行前把 MinIO 文件同步到本地共享目录供推理容器读取

推荐 compose 模板如下：

```yaml
services:
  api-gateway:
    image: aivision-backend:latest
    container_name: ai-detection-gateway
    restart: unless-stopped
    user: root
    ports:
      - "9541:8080"
    environment:
      - SERVER_PORT=8080
      - SPRING_PROFILES_ACTIVE=docker
      - JAVA_OPTS=-Xmx1g -Xms512m -XX:+UseG1GC -XX:+UseContainerSupport
      - SPRING_JPA_HIBERNATE_DDL_AUTO=update
      - SPRING_DATASOURCE_URL=jdbc:postgresql://${PG_HOST}:${PG_PORT}/${PG_DB}
      - SPRING_DATASOURCE_USERNAME=${PG_USER}
      - SPRING_DATASOURCE_PASSWORD=${PG_PASSWORD}
      - SPRING_DATASOURCE_DRIVER_CLASS_NAME=org.postgresql.Driver
      - AI_SERVICES_INFERENCE_URL=http://ai-inference:8000
      - AI_SERVICES_OCR_INFERENCE_URL=http://ai-inference:8000
      - STORAGE_TYPE=minio
      - STORAGE_LOCAL_BASE_DIR=/app/data/files
      - STORAGE_RESULT_DIR=/app/data/results
      - STORAGE_EXTERNAL_BASE_DIR=/app/data/files
      - MINIO_ENDPOINT=http://${MINIO_HOST}:${MINIO_PORT}
      - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
      - MINIO_BUCKET=${MINIO_BUCKET}
    depends_on:
      ai-inference:
        condition: service_healthy
    volumes:
      - files_data:/app/data/files
      - results_data:/app/data/results
    networks:
      - ai-services

  ai-inference:
    image: aivision-ai-inference:packed
    container_name: ai-detection-inference
    restart: unless-stopped
    environment:
      - USE_GPU=true
      - NVIDIA_VISIBLE_DEVICES=all
      - CUDA_VISIBLE_DEVICES=0,1,2,3
      - PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
      - ROI_WEIGHTS=/app/model/weights/weldROI4.pt
      - PRIMARY_WEIGHTS=/app/model/weights/0208primary.pth
      - LOCATION_MODEL=/app/model/weights/location_0.pt
      - LOCATION2_MODEL=/app/model/weights/location_1.pt
      - CORRECTION_MODEL=/app/model/weights/weld_orientation_model.pth
    ports:
      - "8000:8000"
    volumes:
      - files_data:/app/data/files
      - results_data:/app/data/results
    networks:
      - ai-services

  frontend:
    image: aivision-frontend:latest
    container_name: ai-detection-frontend
    restart: unless-stopped
    ports:
      - "3000:80"
    depends_on:
      api-gateway:
        condition: service_healthy
    networks:
      - ai-services

volumes:
  files_data:
    driver: local
    name: ai-detection-files-data
  results_data:
    driver: local
    name: ai-detection-results-data

networks:
  ai-services:
    name: ai-services
    driver: bridge
```

GPU 机器如果需要 `deploy.resources.reservations.devices`，可额外合并：

[`deploy/3-15-upgrade/docker-compose.gpu.yml`](/Users/Dylan.Min/Documents/Code/work/huodian/deploy/3-15-upgrade/docker-compose.gpu.yml)

## 5. 当前客户环境参数

客户环境参数来源：
[`deploy/3-15-upgrade/.env`](/Users/Dylan.Min/Documents/Code/work/huodian/deploy/3-15-upgrade/.env)

### 5.1 PostgreSQL

- `PG_HOST=192.168.203.98`
- `PG_PORT=5432`
- `PG_DB=hjpp`
- `PG_USER=root`
- `PG_PASSWORD=hjpp@135!A`

### 5.2 MinIO

- `MINIO_HOST=192.168.203.98`
- `MINIO_PORT=9000`
- `MINIO_CONSOLE_PORT=9001`
- `MINIO_ACCESS_KEY=minioadmin`
- `MINIO_SECRET_KEY=minio123456@!`
- `MINIO_BUCKET=ai-vision-files`

### 5.3 镜像默认值

- `BACKEND_IMAGE=aivision-backend:latest`
- `FRONTEND_IMAGE=aivision-frontend:latest`
- `AI_INFERENCE_BASE_IMAGE=aivision-ai-inference:latest`
- `AI_INFERENCE_IMAGE=aivision-ai-inference:packed`

### 5.4 VPN 与堡垒机

VPN 地址：

- [https://vpn.ztpc.com](https://vpn.ztpc.com)

VPN 账户：

- 用户名：`shenguohua`
- 密码：`ovalab00Test!123`

堡垒机账户：

- 用户名：`shenguohua`
- 密码：`12345678.Com`

## 6. 推荐部署顺序

```bash
cd deploy/3-15-upgrade
```

1. 构建镜像

```bash
./build-images-amd64.sh
./build-inference-packed-amd64.sh
```

2. 导出镜像

```bash
./export-images.sh
```

3. 在客户机器加载镜像

```bash
docker load -i backend.tar
docker load -i frontend.tar
docker load -i inference.tar
```

4. 确保客户 PostgreSQL 空库时已执行初始化脚本

5. 启动服务

```bash
./start.sh
```

## 7. 当前部署要点

- 后端已支持 `MinIO -> /app/data/files` 的任务前同步逻辑
- 因此客户环境可以继续使用外部 MinIO
- 推理容器仍按本地共享目录读取待检测文件
- `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` 建议保留，避免首次推理时卡在模型源连通性检查
