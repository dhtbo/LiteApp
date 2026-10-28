# ==========================================
# LiteApp Studio - Dockerfile
# ==========================================

FROM python:3.11-slim

# 设置环境变量，确保 Python 输出无缓冲且不生成字节码文件
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# 安装基础依赖工具（curl 用于健康检查）
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装 Python 依赖（支持快速安装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/

# 预先创建持久化数据目录
RUN mkdir -p /app/data

# 声明持久化数据卷
VOLUME ["/app/data"]

# 暴露服务端口
EXPOSE 8000

# 容器健康检查指令
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 启动服务
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
