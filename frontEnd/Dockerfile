# 多阶段构建
# 第一阶段：构建前端应用
FROM hub.rat.dev/library/node:18-alpine AS builder

# 设置工作目录
WORKDIR /app

# 复制package.json和yarn.lock文件
COPY package.json yarn.lock ./

# 设置国内镜像源并安装依赖
RUN yarn config set registry https://registry.npmmirror.com && \
    yarn config set strict-ssl false && \
    yarn install --frozen-lockfile

# 复制源代码
COPY . .

# 构建应用
RUN yarn build

# 第二阶段：生产环境
FROM hub.rat.dev/library/nginx:alpine

# 删除默认的nginx配置和文件
RUN rm -rf /usr/share/nginx/html/*

# 从构建阶段复制构建产物到nginx目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制nginx配置
COPY nginx.conf /etc/nginx/nginx.conf

# 暴露端口
EXPOSE 80

# 启动nginx
CMD ["nginx", "-g", "daemon off;"] 