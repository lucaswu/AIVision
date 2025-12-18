# 多阶段构建 - 构建阶段
FROM ubuntu:20.04 AS builder

# 设置环境变量避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 替换为阿里云镜像源 (同时兼容 x86 和 ARM)
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/ports.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list

# 安装Java和必要工具
RUN apt-get update && \
    apt-get install -y openjdk-17-jdk maven curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制Maven包装器和依赖文件
COPY pom.xml ./

# 下载依赖（利用Docker缓存层优化）
# 直接使用系统安装的 maven，避免 mvnw 下载 maven 时的 SSL 问题
RUN mvn dependency:go-offline -B -Dmaven.wagon.http.ssl.insecure=true -Dmaven.wagon.http.ssl.allowall=true -Dmaven.wagon.http.ssl.ignore.validity.dates=true

# 复制源代码
COPY src ./src

# 构建应用程序
RUN mvn clean package -DskipTests -B -Dmaven.wagon.http.ssl.insecure=true -Dmaven.wagon.http.ssl.allowall=true -Dmaven.wagon.http.ssl.ignore.validity.dates=true

# 运行阶段 - 最小化运行时镜像
FROM ubuntu:20.04 AS runtime

# 设置环境变量避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 替换为阿里云镜像源 (同时兼容 x86 和 ARM)
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/ports.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list

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
