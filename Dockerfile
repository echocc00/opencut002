FROM python:3.10-slim

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg nodejs npm && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# 应用代码
COPY . .

# Remotion 依赖
WORKDIR /app/remotion
RUN npm install --production || true
WORKDIR /app

EXPOSE 8000

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
