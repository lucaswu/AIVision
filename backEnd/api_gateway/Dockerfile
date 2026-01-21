# 多阶段构建 - 构建阶段
FROM ubuntu:22.04 AS builder

# 设置环境变量避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 替换为阿里云镜像源 (同时兼容 x86 和 ARM)
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/ports.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list

# 安装Java和必要工具
RUN apt-get update && \
    apt-get install -y openjdk-17-jdk maven curl locales && \
    locale-gen zh_CN.UTF-8 && \
    rm -rf /var/lib/apt/lists/*

# 配置 Maven 使用阿里云镜像
RUN mkdir -p ~/.m2 && \
    echo '<?xml version="1.0" encoding="UTF-8"?>\n\
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"\n\
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n\
          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 http://maven.apache.org/xsd/settings-1.0.0.xsd">\n\
  <mirrors>\n\
    <mirror>\n\
      <id>aliyunmaven</id>\n\
      <mirrorOf>*</mirrorOf>\n\
      <name>阿里云公共仓库</name>\n\
      <url>https://maven.aliyun.com/repository/public</url>\n\
    </mirror>\n\
  </mirrors>\n\
</settings>' > ~/.m2/settings.xml

# 设置语言环境
ENV LANG zh_CN.UTF-8
ENV LANGUAGE zh_CN:zh
ENV LC_ALL zh_CN.UTF-8

WORKDIR /app

# 复制Maven包装器和依赖文件
COPY backEnd/api_gateway/pom.xml ./

# 下载依赖
RUN mvn dependency:go-offline -B

# 复制源代码
COPY backEnd/api_gateway/src ./src

# 构建应用程序
RUN mvn clean package -DskipTests -B

# 运行阶段 - 最小化运行时镜像
# 注意：Python 推理已移至独立容器，这里只需要 Java 运行时
FROM ubuntu:22.04 AS runtime

# 设置环境变量避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 替换为阿里云镜像源
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/ports.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list

# 只安装 Java 运行时（Python 推理已移至独立容器）
RUN apt-get update && \
    apt-get install -y openjdk-17-jre-headless curl locales && \
    locale-gen zh_CN.UTF-8 && \
    rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 设置语言环境
ENV LANG zh_CN.UTF-8
ENV LANGUAGE zh_CN:zh
ENV LC_ALL zh_CN.UTF-8

WORKDIR /app

# 从构建阶段复制JAR文件
COPY --from=builder /app/target/api-gateway-*.jar app.jar

# 创建日志和数据目录
RUN mkdir -p /app/logs /app/data/files /app/data/results && \
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
