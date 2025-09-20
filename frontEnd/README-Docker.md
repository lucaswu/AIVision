# AIVision 前端容器化部署指南

本文档说明如何将 AIVision 前端应用容器化部署。

## 📁 容器化文件说明

- `Dockerfile` - Docker 镜像构建文件
- `nginx.conf` - Nginx 配置文件，处理前端路由和 API 代理
- `.dockerignore` - Docker 构建时忽略的文件
- `build-docker.sh` - 构建脚本（推荐使用）
- `docker-compose.yml` - Docker Compose 配置文件

## 🚀 快速开始

### 方法一：使用构建脚本（推荐）

```bash
# 进入前端目录
cd frontEnd

# 运行构建脚本
./build-docker.sh
```

构建完成后，访问 http://localhost:3000

### 方法二：手动构建

```bash
# 进入前端目录
cd frontEnd

# 构建镜像
docker build -t aivision-frontend:latest .

# 运行容器
docker run -d \
  --name aivision-frontend \
  -p 3000:80 \
  aivision-frontend:latest
```

### 方法三：使用 Docker Compose

```bash
# 进入前端目录
cd frontEnd

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 🔧 配置说明

### Nginx 配置特性

- **前端路由支持**: 支持 React Router，刷新页面不会 404
- **API 代理**: 自动代理 `/api/*` 请求到后端服务（8080 端口）
- **静态资源缓存**: JS、CSS、图片等静态资源缓存 1 年
- **Gzip 压缩**: 自动压缩文本资源
- **CORS 处理**: 处理跨域请求
- **健康检查**: 提供 `/health` 端点用于健康检查

### 端口配置

- **容器内部**: 80 端口（Nginx）
- **映射到主机**: 3000 端口
- **后端 API**: 8080 端口（通过 proxy 代理）

## 🔍 常用命令

```bash
# 查看容器状态
docker ps | grep aivision-frontend

# 查看容器日志
docker logs aivision-frontend

# 进入容器内部
docker exec -it aivision-frontend /bin/sh

# 停止容器
docker stop aivision-frontend

# 删除容器
docker rm aivision-frontend

# 删除镜像
docker rmi aivision-frontend:latest

# 查看镜像大小
docker images | grep aivision-frontend
```

## 🐛 故障排除

### 1. 构建失败

```bash
# 查看构建日志
docker build -t aivision-frontend:latest . --no-cache

# 检查 Node.js 版本兼容性
# 如果失败，可以尝试修改 Dockerfile 中的 Node.js 版本
```

### 2. 容器无法启动

```bash
# 查看详细错误日志
docker logs aivision-frontend

# 检查端口是否被占用
lsof -i :3000
```

### 3. API 请求失败

- 检查后端服务是否运行在 8080 端口
- 检查 `nginx.conf` 中的代理配置
- 确认网络连接正常

### 4. 前端路由 404

- 确认 `nginx.conf` 中有正确的 `try_files` 配置
- 检查 React Router 配置

## 📊 性能优化

### 镜像大小优化

当前配置使用了多阶段构建：
- 构建阶段：使用 `node:18-alpine` 
- 运行阶段：使用 `nginx:alpine`
- 最终镜像大小约：~50MB

### 启动速度优化

- 使用 `.dockerignore` 减少构建上下文
- 分层缓存：先复制 `package.json`，再安装依赖
- 静态资源缓存策略

## 🔗 集成部署

如果需要与现有的后端服务集成：

1. 修改 `docker-compose.yml` 中的网络配置
2. 确保所有服务在同一网络中
3. 更新 `nginx.conf` 中的代理地址

## 📝 注意事项

1. **环境变量**: 如果前端需要环境变量，请在构建时通过 `--build-arg` 传入
2. **API 地址**: 生产环境需要修改 `nginx.conf` 中的后端服务地址
3. **HTTPS**: 生产环境建议配置 HTTPS 和 SSL 证书
4. **监控**: 建议添加日志收集和监控配置

