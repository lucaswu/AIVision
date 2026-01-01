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
    apt-get install -y openjdk-17-jdk maven curl locales && \
    locale-gen zh_CN.UTF-8 && \
    rm -rf /var/lib/apt/lists/*

# 设置语言环境
ENV LANG zh_CN.UTF-8
ENV LANGUAGE zh_CN:zh
ENV LC_ALL zh_CN.UTF-8

WORKDIR /app

# 复制Maven包装器和依赖文件
# 注意：上下文现在是根目录 AIVision，所以路径需要调整
COPY backEnd/api_gateway/pom.xml ./

# 下载依赖
RUN mvn dependency:go-offline -B -Dmaven.wagon.http.ssl.insecure=true -Dmaven.wagon.http.ssl.allowall=true -Dmaven.wagon.http.ssl.ignore.validity.dates=true

# 复制源代码
COPY backEnd/api_gateway/src ./src

# 构建应用程序
RUN mvn clean package -DskipTests -B -Dmaven.wagon.http.ssl.insecure=true -Dmaven.wagon.http.ssl.allowall=true -Dmaven.wagon.http.ssl.ignore.validity.dates=true

# 运行阶段 - 最小化运行时镜像
FROM ubuntu:20.04 AS runtime

# 设置环境变量避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 替换为阿里云镜像源
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/ports.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list

# 安装Java、Python和必要工具
# libgl1-mesa-glx 是 OpenCV 需要的
# python3-dev 和 build-essential 用于编译某些 Python 包
RUN apt-get update && \
    apt-get install -y openjdk-17-jre-headless curl locales python3 python3-pip libgl1-mesa-glx python3-dev build-essential && \
    locale-gen zh_CN.UTF-8 && \
    rm -rf /var/lib/apt/lists/*

# 创建非root用户 (恢复此重要步骤)
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 设置 pip 超时时间
ENV PIP_DEFAULT_TIMEOUT=1000
# 设置 Matplotlib 后端为非交互式，避免在 Docker 中报错
ENV MPLBACKEND=Agg

# 升级 pip 并分步安装依赖，使用清华源提高稳定性
RUN pip3 install --no-cache-dir --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# 1. 基础科学计算库
RUN pip3 install --no-cache-dir numpy tqdm opencv-python-headless numba matplotlib mlflow scikit-learn pydicom PyYAML Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# 2. Ultralytics (YOLO)
RUN pip3 install --no-cache-dir ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# 3. PyTorch (CPU版)
RUN pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# 设置语言环境
ENV LANG zh_CN.UTF-8
ENV LANGUAGE zh_CN:zh
ENV LC_ALL zh_CN.UTF-8

WORKDIR /app

# 从构建阶段复制JAR文件
COPY --from=builder /app/target/api-gateway-*.jar app.jar

# 复制算法模型代码
COPY model /app/model

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
