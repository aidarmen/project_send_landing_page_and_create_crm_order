# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# OS deps (pandas/openpyxl need build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install -r requirements.txt

# App code
COPY . .

# Non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    mkdir -p /app/data /app/uploads && \
    chown -R appuser:appuser /app
USER appuser

# Defaults (override in compose/.env as needed)
ENV FLASK_ENV=production \
    ORDER_API_URL=http://10.8.219.66:8501 \
    TOKEN_MAX_AGE_SECONDS=2592000 \
    DB_PATH=/app/data/app.db \
    TZ=Asia/Almaty

EXPOSE 5000
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
