# AI图片探伤平台 - 存储服务

本目录包含AI图片探伤平台的基础存储服务，**完全自包含**，无需任何外部文件。

## 服务组件

- **MinIO**: 对象存储 (v2023-07-07)，用于存储图片和报告文件
- **PostgreSQL**: 关系型数据库 (v14.12-alpine)，用于存储业务数据和元数据
- **MinIO-Init**: 自动初始化MinIO的一次性服务
- **PostgreSQL-Init**: 自动初始化数据库的一次性服务

## 版本信息

| 服务 | 版本 | 说明 |
|------|------|------|
| MinIO | RELEASE.2023-07-07T07-13-57Z | 保守稳定版本，经过1.5年+生产验证 |
| MinIO Client | RELEASE.2023-07-07T05-25-51Z | 对应的mc客户端版本 |
| PostgreSQL | 14.12-alpine | 成熟稳定版本，3年+企业验证，支持到2026年 |

## 🚀 一键启动

```bash
# 在storage目录下执行
cd storage
docker-compose up -d
```

**就这么简单！** 服务会自动完成：
1. ✅ 启动PostgreSQL数据库
2. ✅ 启动MinIO对象存储服务
3. ✅ 等待服务健康检查通过
4. ✅ 自动创建数据库表结构和索引
5. ✅ 自动创建MinIO存储桶和目录结构
6. ✅ 设置访问策略和权限
7. ✅ 插入测试数据

### 查看初始化状态

```bash
# 查看所有服务状态
docker-compose ps

# 查看MinIO初始化日志
docker-compose logs minio-init

# 查看数据库初始化日志  
docker-compose logs postgres-init

# 查看实时日志
docker-compose logs -f
```

## 访问信息

### MinIO对象存储
- **Web控制台**: http://localhost:9001
- **API端点**: http://localhost:9000
- **用户名**: minioadmin
- **密码**: minioadmin123

### PostgreSQL数据库
- **主机**: localhost
- **端口**: 5432
- **数据库**: ai_detection
- **用户名**: aiuser
- **密码**: aipass123

## 自动创建的资源

### MinIO存储桶结构
```
ai-detection-bucket/
├── images/
│   ├── original/        # 原始图片
│   ├── processed/       # 处理后图片
│   └── thumbnails/      # 缩略图
├── reports/
│   ├── markdown/        # Markdown报告
│   ├── pdf/            # PDF报告
│   └── attachments/    # 附件
├── models/
│   ├── pytorch/        # PyTorch模型文件
│   └── versions/       # 模型版本
└── standards/
    ├── documents/      # 标准文档
    └── parsed/         # 解析后内容
```

### 数据库表结构
- `detection_tasks`: 检测任务主表
- `image_files`: 图片文件信息
- `ai_detection_results`: AI检测结果
- `customer_standards`: 客户标准文档
- `detection_reports`: 检测报告
- `task_status_logs`: 任务状态日志

包含完整的索引和测试数据！

## 常用操作

### 快速验证

```bash
# 验证MinIO存储桶
curl http://localhost:9000/ai-detection-bucket/

# 验证数据库连接和表结构
docker exec -it ai-detection-postgres psql -U aiuser -d ai_detection -c '\dt'
```

### 使用mc客户端操作MinIO

```bash
# 安装mc客户端（如果需要）
# macOS: brew install minio/stable/mc
# Linux: wget https://dl.min.io/client/mc/release/linux-amd64/mc && chmod +x mc

# 配置mc客户端（已经自动配置好）
mc alias set local http://localhost:9000 minioadmin minioadmin123

# 上传文件
mc cp ./example.jpg local/ai-detection-bucket/images/original/

# 列出文件
mc ls local/ai-detection-bucket/images/original/

# 下载文件
mc cp local/ai-detection-bucket/images/original/example.jpg ./downloaded.jpg
```

### 连接PostgreSQL数据库

```bash
# 使用psql连接
psql -h localhost -p 5432 -U aiuser -d ai_detection

# 或者使用Docker exec
docker exec -it ai-detection-postgres psql -U aiuser -d ai_detection

# 查看表结构
\dt

# 查看测试数据
SELECT * FROM customer_standards;
```

## 数据持久化

数据存储在Docker volumes中：
- `minio_data`: MinIO数据
- `postgres_data`: PostgreSQL数据

即使容器重启，数据也会保持不变。

## 服务管理

### 启动服务
```bash
docker-compose up -d
```

### 停止服务
```bash
# 停止服务但保留数据
docker-compose down

# 停止服务并删除数据（谨慎操作！）
docker-compose down -v
```

### 重启服务
```bash
docker-compose restart
```

### 查看服务状态
```bash
docker-compose ps
```

### 重新初始化（如果需要）
```bash
# 重新初始化MinIO
docker-compose up minio-init

# 重新初始化数据库
docker-compose up postgres-init
```

## 故障排除

### MinIO相关问题
1. 检查端口占用：`lsof -i :9000,9001`
2. 查看MinIO日志：`docker-compose logs minio`
3. 查看初始化日志：`docker-compose logs minio-init`
4. 重新初始化：`docker-compose up minio-init`

### PostgreSQL相关问题
1. 检查端口占用：`lsof -i :5432`
2. 查看数据库日志：`docker-compose logs postgres`
3. 查看初始化日志：`docker-compose logs postgres-init`
4. 验证表创建：
   ```bash
   docker exec -it ai-detection-postgres psql -U aiuser -d ai_detection -c "\dt"
   ```

### 服务无法启动
1. 确保Docker服务正在运行：`docker version`
2. 检查Docker Compose版本：`docker-compose version`
3. 查看所有服务日志：`docker-compose logs`

### 完全重置
如果需要完全重置所有数据：
```bash
# 停止并删除所有数据
docker-compose down -v

# 重新启动
docker-compose up -d
```

## 健康检查

服务包含健康检查机制：
- **MinIO**: 每30秒检查一次服务健康状态
- **PostgreSQL**: 每30秒检查一次数据库连接

可以通过以下命令查看健康状态：
```bash
docker-compose ps
```

## 网络配置

所有服务运行在同一个Docker网络中，服务间可以通过服务名进行通信：
- MinIO: `http://minio:9000`
- PostgreSQL: `postgres:5432`

## 特性

✅ **完全自包含** - 无需任何外部配置文件  
✅ **一键启动** - 单个命令完成所有设置  
✅ **保守稳定** - 使用经过长期验证的稳定版本  
✅ **自动初始化** - 数据库和存储自动配置  
✅ **健康检查** - 确保服务正常启动  
✅ **依赖管理** - 正确的服务启动顺序  
✅ **错误处理** - 优雅处理初始化失败  
✅ **幂等操作** - 可以安全重复运行 