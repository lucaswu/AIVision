# 多阶段构建 - 构建阶段
FROM ubuntu:20.04 AS builder

# 设置环境变量避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 安装Java和必要工具
RUN apt-get update && \
    apt-get install -y openjdk-17-jdk maven curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制Maven包装器和依赖文件
COPY .mvn/ .mvn/
COPY mvnw pom.xml ./
RUN chmod +x ./mvnw

# 下载依赖（利用Docker缓存层优化）
RUN ./mvnw dependency:go-offline -B

# 复制源代码
COPY src ./src

# 构建应用程序
RUN ./mvnw clean package -DskipTests -B

# 运行阶段 - 最小化运行时镜像
FROM ubuntu:20.04 AS runtime

# 设置环境变量避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 安装Java运行时环境和必要的工具
RUN apt-get update && \
    apt-get install -y openjdk-17-jre-headless curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从构建阶段复制JAR文件
COPY --from=builder /app/target/api-gateway-*.jar app.jar

# 创建日志目录
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/actuator/health || exit 1

# JVM优化参数
ENV JAVA_OPTS="-Xmx1g -Xms512m -XX:+UseG1GC -XX:+UseContainerSupport -Djava.security.egd=file:/dev/./urandom"

# 启动应用
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"] 
