# 使用官方 Python 3.12 slim 镜像（稳定版）
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖清单（默认 requirements.txt）
COPY requirements.txt .

# 复制应用代码
COPY . .

# 安装 Python 依赖：优先使用导出的锁定文件（requirements.lock.txt）
# 通过 `poetry export -f requirements.txt -o requirements.lock.txt --without-hashes` 生成
RUN if [ -f requirements.lock.txt ]; then \
      echo "Using requirements.lock.txt" && pip install --no-cache-dir -r requirements.lock.txt; \
    else \
      echo "Using requirements.txt" && pip install --no-cache-dir -r requirements.txt; \
    fi

# 复制并设置 init 脚本权限
COPY init-logs.sh /init-logs.sh
RUN chmod +x /init-logs.sh

# 创建非 root 用户和必要目录
RUN useradd --create-home --shell /bin/bash app \
    && mkdir -p /app/logs /app/data_analysis \
    && chown -R app:app /app \
    && chmod 755 /app/data_analysis
USER app

# 暴露端口
EXPOSE 8000

# 健康检查（需要 curl）
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "main_fastapi:app", "--host", "0.0.0.0", "--port", "8000"]

