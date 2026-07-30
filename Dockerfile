# Dockerfile — UAEK 开发环境
# 基于 Python 3.11 精简镜像

FROM python:3.11-slim

# 创建非 root 用户
RUN groupadd -r uaek && useradd -r -g uaek -m uaek

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件（利用 Docker 缓存层）
COPY pyproject.toml README.md ./

# 安装项目依赖（包含 dev 可选依赖）
RUN pip install --no-cache-dir -e ".[dev]"

# 复制源码
COPY src/ ./src/
COPY tests/ ./tests/

# 切换到非 root 用户
RUN chown -R uaek:uaek /app
USER uaek

# 默认命令
CMD ["python", "-m", "pytest", "tests/"]