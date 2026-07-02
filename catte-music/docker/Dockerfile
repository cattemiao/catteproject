# ===== 后端 Dockerfile =====
FROM python:3.11-slim

# 系统依赖：librosa 需要 ffmpeg + libsndfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 uv（复用缓存层）
RUN pip install --no-cache-dir uv

# 先拷依赖文件，利用缓存
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# 拷贝源码
COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
