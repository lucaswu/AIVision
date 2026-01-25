# AI Vision Detection System - 统一部署文档

🚀 这是AI视觉检测系统的统一部署配置，整合了所有微服务组件。

## 📋 系统架构

### 🏗️ 服务组件

| 服务 | 端口 | 功能 | 状态 |
|------|------|------|------|
| **PostgreSQL** | 5432 | 数据库服务 | ✅ 必需 |
| **MinIO** | 9000/9001 | 对象存储 | ✅ 必需 |
| **Vision AI** | 8001 | YOLOv8缺陷检测 | ✅ 必需 |
| **LLM AI** | 11434 | DeepSeek文本生成 | ✅ 必需 |
| **API Gateway** | 9541 | 主应用服务 | ✅ 必需 |
| **N8N** | 5678 | 工作流引擎 | 🔧 可选 |

### 🔗 服务依赖关系

```
┌─────────────────────────────────────────────────────────┐
│                  ai-services 网络                       │
├─────────────────┬─────────────────┬─────────────────────┤
│  基础服务        │   AI 服务        │   应用服务           │
├─────────────────┼─────────────────┼─────────────────────┤
│ PostgreSQL      │ Vision AI       │ API Gateway         │
│ ├─ 数据持久化    │ ├─ 图像检测      │ ├─ REST API        │
│ └─ 健康检查      │ └─ 健康检查      │ ├─ 任务管理         │
│                 │                 │ ├─ 文件管理         │
│ MinIO           │ LLM AI          │ └─ Swagger UI       │
│ ├─ 文件存储      │ ├─ 文本生成      │                     │
│ ├─ 自动初始化    │ └─ 健康检查      │ N8N (可选)          │
│ └─ Web控制台     │                 │ └─ 工作流备份        │
└─────────────────┴─────────────────┴─────────────────────┘
```

## 🚀 快速启动

### 1. 前置条件
#### 1 模型文件
将模型文件primary-weights.pth和weldROI4.pt放置到model/weight目录下

```bash
# 检查Docker和Docker Compose
docker --version
docker-compose --version

# 进入部署目录
cd backEnd/deploy
```

### 2. 系统启动 (环境切换)

本项目支持双环境 (CPU / GPU) 快速切换。

**前置操作 (必选):**
进入部署目录
```bash
cd deploy
```

**方案 A: 切换到 GPU 模式 (推荐)**
```bash
cp .env.gpu .env
docker compose up -d --build
```
> 适用场景: 生产环境、NVIDIA显卡主机

**方案 B: 切换到 CPU 模式**
```bash
cp .env.cpu .env
docker compose up -d --build
```
> 适用场景: 开发测试、无显卡主机 (OCR使用百度预装镜像，速度较慢但兼容性好)

**常用命令:**
```bash
# 查看服务状态
docker compose ps

# 查看启动日志
docker compose logs -f
```

### 3. 分步启动 (推荐)

```bash
# 1. 启动基础存储服务
docker-compose up -d postgres minio minio-init

# 2. 等待基础服务就绪后启动AI服务
docker-compose up -d vision-ai deepseek-llm

# 3. 最后启动API Gateway
docker-compose up -d api-gateway
```

### 4. 启动可选服务

```bash
# 启动N8N工作流引擎 (可选)
docker-compose --profile n8n up -d n8n
```

## 📊 服务验证

### 🔍 健康检查

```bash
# 检查所有服务状态
docker-compose ps

# 检查健康状态
curl http://localhost:9541/actuator/health
curl http://localhost:8001/health
curl http://localhost:11434/api/tags
```

### 🌐 Web界面访问

| 服务 | 地址 | 说明 |
|------|------|------|
| **API Gateway** | http://localhost:9541 | 主应用 |
| **Swagger UI** | http://localhost:9541/swagger-ui.html | API文档 |
| **MinIO Console** | http://localhost:9001 | 存储管理 |
| **N8N** | http://localhost:5678 | 工作流 (可选) |

### 🔑 默认凭据

**MinIO Console:**
- 用户名: `minioadmin`
- 密码: `minioadmin123`

**PostgreSQL:**
- 数据库: `ai_detection`
- 用户名: `aiuser`
- 密码: `aipass123`

## 📝 部署配置

### 🔧 环境变量配置

创建 `.env` 文件自定义配置：

```bash
# 数据库配置
POSTGRES_PASSWORD=your_secure_password

# MinIO配置
MINIO_ROOT_PASSWORD=your_secure_minio_password

# 端口配置
API_GATEWAY_PORT=8080
POSTGRES_PORT=5432
MINIO_API_PORT=9000
MINIO_CONSOLE_PORT=9001

# 应用配置
SPRING_PROFILES_ACTIVE=docker
JAVA_OPTS=-Xmx2g -Xms1g -XX:+UseG1GC
```

### 🏗️ 构建配置

**自动构建:**
Docker Compose会自动构建以下服务的镜像：
- Vision AI (从 `../ai_services/vision_ai`)
- LLM AI (从 `../ai_services/llm_ai`)
- API Gateway (从 `../api_gateway`)

**预构建镜像:**
如果已有构建好的镜像，可以修改配置使用现有镜像：

```yaml
api-gateway:
  image: ai-vision-gateway:latest  # 使用已构建镜像
  # build: ../api_gateway          # 注释掉构建配置
```

## 🛠️ 运维管理

### 📊 监控和日志

```bash
# 查看所有服务日志
docker-compose logs

# 查看特定服务日志
docker-compose logs api-gateway
docker-compose logs vision-ai

# 实时跟踪日志
docker-compose logs -f api-gateway

# 查看服务资源使用
docker stats
```

### 🔄 服务管理

```bash
# 重启特定服务
docker-compose restart api-gateway

# 停止所有服务
docker-compose stop

# 停止并删除容器
docker-compose down

# 停止并删除容器和数据卷 (⚠️ 会删除数据)
docker-compose down -v
```

### 📈 扩容配置

```bash
# 扩展API Gateway实例
docker-compose up -d --scale api-gateway=3

# 使用负载均衡器 (需要额外配置)
# 可以添加nginx或traefik进行负载均衡
```

## 🔧 故障排除

### 常见问题

**1. 端口冲突**
```bash
# 检查端口占用
lsof -i :8080
lsof -i :5432

# 修改docker-compose.yml中的端口映射
ports:
  - "8081:8080"  # 使用其他端口
```

**2. 服务启动失败**
```bash
# 查看详细错误日志
docker-compose logs service-name

# 检查依赖服务是否就绪
docker-compose ps
```

**3. 数据持久化问题**
```bash
# 检查数据卷
docker volume ls | grep ai-detection

# 备份数据卷
docker run --rm -v ai-detection-postgres-data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-backup.tar.gz /data
```

**4. 网络连接问题**
```bash
# 检查网络
docker network ls | grep ai-services

# 重建网络
docker network rm ai-services
docker-compose up -d
```

## 🏭 生产环境部署

### 安全加固

1. **修改默认密码**
2. **使用环境变量管理敏感信息**
3. **启用HTTPS**
4. **配置防火墙规则**
5. **定期备份数据**

### 性能优化

1. **调整JVM参数**
2. **配置数据库连接池**
3. **优化MinIO性能**
4. **监控资源使用**

### 高可用配置

1. **数据库主从复制**
2. **MinIO集群**
3. **API Gateway负载均衡**
4. **健康检查和自动重启**

---

## 📞 技术支持

如有问题，请查看：
- **项目文档**: `../api_gateway/README.md`
- **API文档**: http://localhost:8080/swagger-ui.html
- **健康检查**: http://localhost:8080/actuator/health 