# AI Detection N8N 工作流部署指南

## 前置条件

确保以下服务已启动：
- PostgreSQL (端口: 5432)
- MinIO (端口: 9000)
- Vision AI 服务 (端口: 8001)
- LLM AI 服务 (端口: 11434)

## 启动 N8N

```bash
cd backEnd/workflow
docker-compose up -d
```

访问 N8N 控制台：http://localhost:5678

## 配置步骤

### 1. 配置数据库凭据

在 N8N 界面中创建 PostgreSQL 凭据：
- 名称: `AI Detection PostgreSQL`
- 主机: `ai-detection-postgres`
- 端口: `5432`
- 数据库: `ai_detection`
- 用户名: `aiuser`
- 密码: `aipass123`

### 2. 配置 MinIO 凭据

创建 AWS S3 兼容凭据：
- 名称: `AI Detection MinIO`
- Access Key ID: `minioadmin`
- Secret Access Key: `minioadmin123`
- 区域: `us-east-1`
- 自定义端点: `http://ai-detection-minio:9000`
- 强制路径样式: `True`

### 3. 导入工作流

1. **导入任务提交工作流**：
   - 在 N8N 中点击 "Import from file"
   - 选择 `ai-detection-submit.json`
   - 工作流名称：`AI Detection Submit`

2. **导入结果查询工作流**：
   - 在 N8N 中点击 "Import from file"
   - 选择 `ai-detection-result.json`
   - 工作流名称：`AI Detection Result`

### 4. 激活工作流

在每个工作流页面点击 "Active" 开关以激活工作流。

## API 端点

工作流激活后，将提供以下 API 端点：

### 提交检测任务
```bash
POST http://localhost:5678/api/v1/task/submit
Content-Type: multipart/form-data

参数：
- project_id: 项目ID
- user_id: 用户ID
- image: 图片文件
```

### 获取任务结果
```bash
GET http://localhost:5678/api/v1/task/result?task_id={task_id}
```

## 测试示例

### 提交任务
```bash
curl -X POST http://localhost:5678/api/v1/task/submit \
  -F "project_id=test_project" \
  -F "user_id=test_user" \
  -F "image=@test_image.jpg"
```

响应：
```json
{
  "success": true,
  "task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "message": "任务提交成功，正在后台处理"
}
```

### 查询结果
```bash
curl "http://localhost:5678/api/v1/task/result?task_id=f47ac10b-58cc-4372-a567-0e02b2c3d479"
```

## 故障排除

### 常见问题

1. **连接数据库失败**
   - 检查 PostgreSQL 服务是否运行
   - 确认凭据配置正确
   - 使用 `host.docker.internal` 而不是 `localhost`

2. **MinIO 连接失败**
   - 检查 MinIO 服务状态
   - 确认存储桶 `ai-detection-bucket` 已创建
   - 验证 S3 凭据配置

3. **AI 服务调用失败**
   - 确认 Vision AI 和 LLM AI 服务正常运行
   - 检查端口 8001 和 11434 是否可访问

### 日志查看

```bash
# 查看 N8N 容器日志
docker-compose logs -f n8n

# 查看工作流执行日志
# 在 N8N 界面的 "Executions" 页面查看
```

## 监控和维护

- 定期检查工作流执行状态
- 监控数据库和存储空间使用情况
- 备份 N8N 工作流配置和数据 