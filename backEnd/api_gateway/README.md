# AI Vision API Gateway

🚀 基于 Spring Boot 3.2 的 AI 视觉检测系统 API 网关，提供完整的项目管理、文件上传、任务处理和AI检测功能。

## 📋 目录

- [1. 项目背景和代码架构](#1-项目背景和代码架构)
- [2. 接口说明](#2-接口说明)
- [3. 打包部署说明](#3-打包部署说明)

---

## 1. 项目背景和代码架构

### 🎯 项目背景

AI Vision Detection System 是一个工业缺陷检测系统，原本基于 n8n 工作流实现。为了提供更好的性能、可维护性和扩展性，我们使用 Spring Boot 重新实现了核心功能。

**核心功能**:
- 📁 项目和目录管理
- 📤 多文件上传和存储
- 🔍 AI 视觉缺陷检测 (YOLOv8)
- 🤖 LLM 智能报告生成 (DeepSeek/Qwen)
- 📊 任务管理和进度跟踪
- 📈 检测结果可视化

### 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend UI   │───▶│  API Gateway    │───▶│   PostgreSQL    │
│                 │    │  (Spring Boot)  │    │   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │     MinIO       │
                    │ Object Storage  │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │   Vision AI     │    │    LLM AI       │
                    │   (YOLOv8)      │    │ (DeepSeek/Qwen) │
                    └─────────────────┘    └─────────────────┘
```

### 💻 技术栈

| 层级 | 技术选型 | 版本 | 说明 |
|------|----------|------|------|
| **后端框架** | Spring Boot | 3.2+ | 主应用框架 |
| **数据访问** | Spring Data JPA | 3.2+ | ORM框架 |
| **数据库** | PostgreSQL | 14+ | 关系型数据库 |
| **对象存储** | MinIO | Latest | 文件存储 |
| **HTTP客户端** | WebFlux WebClient | 3.2+ | 异步HTTP调用 |
| **API文档** | SpringDoc OpenAPI | 2.0+ | Swagger集成 |
| **构建工具** | Maven | 3.6+ | 项目构建 |
| **容器化** | Docker | Latest | 容器部署 |

### 📁 代码架构

```
src/main/java/com/aivision/gateway/
├── controller/                 # REST API控制器层
│   ├── ProjectController.java     # 项目管理API
│   ├── DirectoryController.java   # 目录管理API
│   ├── FileController.java        # 文件上传API
│   └── TaskController.java        # 任务管理API
├── service/                    # 业务逻辑服务层
│   ├── ProjectService.java        # 项目业务逻辑
│   ├── DirectoryService.java      # 目录业务逻辑
│   ├── FileService.java           # 文件处理逻辑
│   ├── TaskService.java           # 任务管理逻辑
│   ├── TaskProcessService.java    # 异步任务处理
│   └── AiServiceClient.java       # AI服务调用客户端
├── repository/                 # 数据访问层
│   ├── ProjectRepository.java     # 项目数据访问
│   ├── DirectoryRepository.java   # 目录数据访问
│   ├── FileRepository.java        # 文件数据访问
│   ├── TaskRepository.java        # 任务数据访问
│   └── TaskFileRepository.java    # 任务文件关联
├── model/                      # 数据模型层
│   ├── entity/                    # JPA实体类
│   │   ├── Project.java
│   │   ├── Directory.java
│   │   ├── File.java
│   │   ├── Task.java
│   │   └── TaskFile.java
│   ├── request/                   # 请求模型
│   └── response/                  # 响应模型
├── config/                     # 配置类
│   ├── AsyncConfig.java           # 异步处理配置
│   ├── FileUploadProperties.java  # 文件上传配置
│   ├── DefaultUserProperties.java # 默认用户配置
│   └── SwaggerConfig.java         # API文档配置
└── ApiGatewayApplication.java  # 主启动类
```

### 🗄️ 数据库设计

**核心表结构**:
- `project` - 项目信息
- `directory` - 目录层级结构 (最多5层)
- `file` - 文件元数据
- `task` - 检测任务
- `task_file` - 任务文件关联和结果

**关系设计**:
```
Project (1:N) Directory (1:N) File
   │                              │
   └─────────── Task (1:N) TaskFile
```

---

## 2. 接口说明

### 📚 API文档访问

启动应用后，可通过以下地址访问完整的API文档：

- **Swagger UI**: http://localhost:8080/swagger-ui.html
- **OpenAPI JSON**: http://localhost:8080/v3/api-docs

### 🔑 通用说明

**请求头参数**:
- `project-id`: 项目ID (UUID格式)
- `user-id`: 用户ID (字符串)
- `directory-id`: 目录ID (文件上传时需要)

**响应格式**:
```json
{
  "Code": 200,
  "Message": "操作成功",
  "Data": { ... },
  "Total": 10
}
```

### 🏗️ 项目管理 API

#### 创建项目
```http
POST /api/v1/projects/create
Headers: user-id: string
Content-Type: application/json

{
  "ProjectName": "我的AI检测项目",
  "Description": "PCB板自动化检测项目"
}
```

#### 获取项目列表
```http
GET /api/v1/projects/list
Headers: user-id: string
```

#### 获取项目文件树
```http
GET /api/v1/projects/{project_id}/files
```

### 📁 目录管理 API

#### 创建目录
```http
POST /api/v1/directories/create
Headers: project-id: string, user-id: string
Content-Type: application/json

{
  "Name": "测试目录",
  "ParentDirectoryId": "parent-uuid" // null为根目录
}
```

### 📤 文件管理 API

#### 多文件上传
```http
POST /api/v1/files/upload
Headers: 
  project-id: string
  user-id: string
  directory-id: string
Content-Type: multipart/form-data

Form Data:
  File: [file1, file2, ...] // 支持 jpg,jpeg,png,gif,bmp,webp
```

**功能说明**: 
- 支持单文件和多文件同时上传
- 支持的图片格式：jpg, jpeg, png, gif, bmp, webp
- 单文件最大 200MB，总文件大小最大 10GB
- 文件会自动存储到 MinIO 对象存储中
- 返回每个文件的上传结果（成功/失败）

**curl 测试示例**:
```bash
# 单文件上传
curl -X POST "http://localhost:8080/api/v1/files/upload" \
  -H "project-id: your-project-id" \
  -H "user-id: user001" \
  -H "directory-id: your-directory-id" \
  -F "File=@image1.jpg"

# 多文件上传
curl -X POST "http://localhost:8080/api/v1/files/upload" \
  -H "project-id: your-project-id" \
  -H "user-id: user001" \
  -H "directory-id: your-directory-id" \
  -F "File=@image1.jpg" \
  -F "File=@image2.png"
```

**Swagger UI 使用说明**: 
- 在 Swagger UI 中，文件上传界面会显示文件选择按钮
- 可以点击"选择文件"按钮选择多个文件
- 填写必要的 Header 参数后点击"Execute"执行上传

**响应示例**:
```json
{
  "Code": 200,
  "Message": "文件上传处理完成",
  "Data": {
    "SuccessCount": 2,
    "FailedCount": 0,
    "SuccessFiles": [
      {
        "FileId": "uuid-1",
        "OriginalName": "image1.jpg",
        "FileSize": 1024000,
        "FilePath": "/project/user/dir/uuid-1.jpg"
      }
    ],
    "FailedFiles": []
  }
}
```

### 🔍 任务管理 API

#### 提交检测任务
```http
POST /api/v1/tasks/submit
Headers: project-id: string, user-id: string
Content-Type: application/json

{
  "Name": "PCB缺陷检测任务",
  "Description": "检测PCB板上的焊接缺陷",
  "AlgorithmType": "object-detection",
  "SelectedFiles": [
    {"FileId": "file-uuid-1"},
    {"FileId": "file-uuid-2"}
  ]
}
```

#### 获取任务列表
```http
GET /api/v1/tasks/list
Headers: project-id: string, user-id: string
```

**功能说明**: 获取指定项目和用户的所有检测任务列表，按创建时间倒序排列，包含每个任务的详细信息和所有文件的处理结果。

**响应示例**:
```json
{
  "Code": 200,
  "Message": "获取成功", 
  "Data": {
    "tasks": [
      {
        "id": "16548faa-43d2-4a9d-975b-50a36af9cbac",
        "name": "PCB缺陷检测任务2",
        "description": "检测PCB板上的元器件缺失",
        "projectId": "c6f4c9b9-a12e-4b11-9792-24993a69497a",
        "userId": "user001",
        "algorithmType": "object-detection",
        "status": "completed",
        "progress": 100,
        "fileCount": 1,
        "processedFiles": 1,
        "successFiles": 1,
        "failedFiles": 0,
        "createTime": "2025-06-26 11:08:12",
        "updateTime": "2025-06-26 11:08:15",
        "errorMessage": null,
        "taskFiles": [
          {
            "taskFileId": "4f49da5a-3b4b-48c2-86ac-da0c37d712ef",
            "fileId": "986ab6fd-f80a-4e39-bf14-3203e81041e8",
            "fileName": "001.jpg",
            "logicalPath": "/test-images/001.jpg",
            "status": "completed",
            "visionResult": "{\"detection_count\":1,\"results\":[...]}",
            "llmResult": "【检测报告】详细的检测分析报告内容...",
            "reportPath": "reports/task-uuid/report.html",
            "errorMessage": null,
            "processingStartTime": "2025-06-26 11:08:12",
            "processingEndTime": "2025-06-26 11:08:15"
          }
        ]
      }
    ],
    "totalCount": 1
  }
}
```

#### 获取任务状态
```http
GET /api/v1/tasks/{task_id}/status
Headers: project-id: string, user-id: string
```

**响应示例**:
```json
{
  "Code": 200,
  "Message": "获取成功",
  "Data": {
    "Id": "task-uuid",
    "Name": "检测任务",
    "Status": "completed",
    "Progress": 100,
    "FileCount": 2,
    "ProcessedFiles": 2,
    "SuccessFiles": 2,
    "FailedFiles": 0,
    "ProcessingFiles": 0,
    "InQueueFiles": 0,
    "SelectedFiles": [
      {
        "TaskFileId": "task-file-uuid",
        "FileId": "file-uuid",
        "FileName": "001.jpg",
        "Status": "completed",
        "VisionResult": "{\"detections\": [...]}",
        "LlmResult": "检测分析报告内容...",
        "ProcessingStartTime": "2025-06-25 12:31:45",
        "ProcessingEndTime": "2025-06-25 12:31:59"
      }
    ]
  }
}
```

### 🔄 任务处理流程

1. **任务提交** → 创建任务记录，状态为 `pending`
2. **文件处理** → 并行处理所有文件，状态变为 `processing`
3. **Vision AI检测** → 调用YOLOv8进行缺陷检测
4. **LLM报告生成** → 调用DeepSeek/Qwen生成分析报告
5. **任务完成** → 状态变为 `completed`，进度100%

### 📊 任务状态字段说明

任务状态接口 `/api/v1/tasks/{task_id}/status` 返回的关键字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `FileCount` | Integer | 任务包含的文件总数 |
| `ProcessedFiles` | Integer | 已处理完成的文件数量 (成功+失败) |
| `SuccessFiles` | Integer | 处理成功的文件数量 |
| `FailedFiles` | Integer | 处理失败的文件数量 |
| `ProcessingFiles` | Integer | 正在处理中的文件数量 |
| `InQueueFiles` | Integer | 等待处理的文件数量 |
| `Progress` | Integer | 任务整体进度百分比 (0-100) |
| `Status` | String | 任务状态: `pending`, `processing`, `completed`, `failed` |

**计算关系**:
```
FileCount = ProcessedFiles + ProcessingFiles + InQueueFiles
ProcessedFiles = SuccessFiles + FailedFiles
Progress = (ProcessedFiles / FileCount) * 100
```

---

## 3. 打包部署说明

### 🛠️ 本地开发环境

#### 环境要求
- **Java**: 17+
- **Maven**: 3.6+
- **PostgreSQL**: 14+
- **MinIO**: Latest
- **Docker**: 20.10+ (可选)

#### 启动步骤

1. **克隆项目**
```bash
cd backEnd/api_gateway
```

2. **配置数据库**
```bash
# 启动PostgreSQL (使用Docker)
docker run -d \
  --name postgres-dev \
  -p 5432:5432 \
  -e POSTGRES_DB=ai_detection \
  -e POSTGRES_USER=aiuser \
  -e POSTGRES_PASSWORD=aipass123 \
  postgres:14

# 初始化数据库
psql -h localhost -U aiuser -d ai_detection -f src/main/resources/sql/init_database.sql
```

3. **启动MinIO**
```bash
docker run -d \
  --name minio-dev \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin123 \
  minio/minio server /data --console-address ":9001"
```

4. **编译和运行**
```bash
# 编译项目
./mvnw clean compile

# 运行测试
./mvnw test

# 启动应用
./mvnw spring-boot:run
```

5. **验证服务**
- API服务: http://localhost:8080
- Swagger文档: http://localhost:8080/swagger-ui.html
- MinIO控制台: http://localhost:9001

### 🐳 Docker容器化部署

#### 单服务部署

1. **构建镜像**
```bash
# 构建应用镜像
docker build -t ai-vision-gateway:latest .
```

2. **运行容器**
```bash
docker run -d \
  --name ai-vision-gateway \
  -p 8080:8080 \
  -e SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/ai_detection \
  -e SPRING_DATASOURCE_USERNAME=aiuser \
  -e SPRING_DATASOURCE_PASSWORD=aipass123 \
  ai-vision-gateway:latest
```

#### 完整环境部署

**推荐方式：分离式部署**

1. **启动存储服务**（PostgreSQL + MinIO）：
```bash
cd ../storage
docker-compose up -d
```

2. **启动API Gateway**：
```bash
cd ../api_gateway
docker-compose up -d
```

3. **查看服务状态**：
```bash
# 查看存储服务
cd ../storage && docker-compose ps

# 查看API Gateway
cd ../api_gateway && docker-compose ps

# 查看日志
docker-compose logs -f api-gateway
```

4. **停止服务**：
```bash
# 停止API Gateway
docker-compose down

# 停止存储服务
cd ../storage && docker-compose down
```

**服务端口映射**:
- API Gateway: 8080
- PostgreSQL: 5432 (来自storage服务)
- MinIO: 9000 (API), 9001 (Console) (来自storage服务)

### 🏭 生产环境部署

#### 环境配置

1. **创建生产配置文件** `application-prod.yml`:
```yaml
server:
  port: 8080

spring:
  datasource:
    url: jdbc:postgresql://prod-postgres:5432/ai_detection
    username: ${DB_USERNAME}
    password: ${DB_PASSWORD}
  
  jpa:
    hibernate:
      ddl-auto: validate  # 生产环境不自动更新表结构
    show-sql: false       # 关闭SQL日志

logging:
  level:
    com.aivision.gateway: INFO
    org.springframework.web: WARN
    org.hibernate.SQL: WARN
```

2. **构建生产镜像**
```bash
# 多阶段构建优化镜像大小
docker build -f Dockerfile.prod -t ai-vision-gateway:prod .
```

3. **使用环境变量**
```bash
# 设置环境变量
export DB_USERNAME=prod_user
export DB_PASSWORD=secure_password
export MINIO_ACCESS_KEY=prod_access_key
export MINIO_SECRET_KEY=secure_secret_key

# 启动生产服务
docker-compose -f docker-compose.prod.yml up -d
```

#### 健康检查

应用提供以下健康检查端点：

- **应用状态**: `GET /actuator/health`
- **数据库连接**: `GET /actuator/health/db`
- **MinIO连接**: `GET /actuator/health/minio`

#### 监控和日志

1. **日志配置**
```yaml
logging:
  file:
    name: /app/logs/application.log
  pattern:
    file: "%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n"
  level:
    com.aivision.gateway: INFO
```

2. **性能监控**
- JVM指标: `/actuator/metrics`
- HTTP指标: `/actuator/metrics/http.server.requests`
- 数据库连接池: `/actuator/metrics/hikaricp`

#### 备份策略

1. **数据库备份**
```bash
# 定期备份PostgreSQL
pg_dump -h postgres-host -U aiuser ai_detection > backup_$(date +%Y%m%d).sql
```

2. **MinIO数据备份**
```bash
# 使用mc客户端备份
mc mirror minio/ai-detection-bucket /backup/minio/
```

### 🔧 配置说明

#### 核心配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `server.port` | 8080 | 服务端口 |
| `spring.datasource.url` | localhost:5432 | 数据库连接 |
| `minio.endpoint` | localhost:9000 | MinIO地址 |
| `ai-services.vision-ai.url` | localhost:8001 | Vision AI服务 |
| `ai-services.llm-ai.url` | localhost:11434 | LLM AI服务 |
| `file-upload.max-file-size` | 200MB | 单文件大小限制 |

#### 性能调优

```yaml
# 数据库连接池
spring:
  datasource:
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 30000

# 异步处理线程池
async:
  task-executor:
    core-pool-size: 5
    max-pool-size: 20
    queue-capacity: 100
```

### 🚀 部署检查清单

- [ ] 数据库连接正常
- [ ] MinIO存储可访问
- [ ] AI服务连接正常
- [ ] 健康检查端点响应
- [ ] 日志输出正常
- [ ] 文件上传功能测试
- [ ] 任务提交和处理测试
- [ ] API文档可访问

---

## 📞 技术支持

如有问题，请联系开发团队或查看项目文档：

- **项目地址**: [GitHub Repository]
- **问题反馈**: [Issues]
- **API文档**: http://localhost:8080/swagger-ui.html
- **技术文档**: `src/main/resources/sql/README.md` 