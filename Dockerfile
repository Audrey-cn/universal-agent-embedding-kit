# Dockerfile — UAEK 开发环境
# 基于 Python 3.11 精简镜像

FROM python:3.11-slim

# 创建非 root 用户
RUN groupadd -r uaek && useradd -r -g uaek -m uaek

# 设置工作目录
WORKDIR /app

# 复制经过 .dockerignore 过滤的仓库，确保 CLI/API/MCP 与测试夹具同构
COPY . .

# 安装项目及开发门禁依赖
RUN pip install --no-cache-dir ".[dev]"

# 切换到非 root 用户
RUN chown -R uaek:uaek /app
USER uaek

# 默认命令
CMD ["python", "-m", "pytest", "tests/"]
