FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FAVORITES_DB_PATH=/app/data/favorites.db \
    CALLBACK_DB_PATH=/app/data/callbacks.json \
    PLAYWRIGHT_BROWSERS_PATH=/app/data/playwright

# Install Playwright browser dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libatspi2.0-0 libx11-6 libxext6 libxi6 libxrender1 libxtst6 libxss1 \
    fonts-liberation fonts-wqy-zenhei fonts-ipafont-gothic xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app /app/app
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Install Chromium browser for Playwright (will be cached in volume)
RUN playwright install chromium

# Run as non-root user
RUN groupadd -r javbot && useradd -r -g javbot -d /app -s /sbin/nologin javbot && \
    chown -R javbot:javbot /app
USER javbot

ENTRYPOINT ["/app/docker-entrypoint.sh"]
