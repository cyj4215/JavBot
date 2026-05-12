FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CALLBACK_DB_PATH=/app/data/callbacks.json

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app /app/app
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Run as non-root user
RUN groupadd -r javbot && useradd -r -g javbot -d /app -s /sbin/nologin javbot && \
    chown -R javbot:javbot /app
USER javbot

ENTRYPOINT ["/app/docker-entrypoint.sh"]
