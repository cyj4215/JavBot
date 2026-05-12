#!/bin/bash
set -e

# Playwright persistent installation path
PW_CACHE_DIR="/app/data/playwright"
export PLAYWRIGHT_BROWSERS_PATH="$PW_CACHE_DIR"

echo "=== JavBot Entrypoint ==="

# Check if Playwright is already installed
if [ -d "$PW_CACHE_DIR/chromium-"* ] && python3 -c "import playwright" 2>/dev/null; then
    echo "Playwright already installed at $PW_CACHE_DIR, skipping..."
else
    echo "Installing Playwright..."
    pip install playwright

    echo "Installing Chromium browser..."
    playwright install chromium

    echo "Playwright installation complete!"
fi

# Check system dependencies
if ! ldconfig -p | grep -q "libglib-2.0"; then
    echo "Installing system dependencies..."
    apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
        libatspi2.0-0 libx11-6 libxext6 libxi6 libxrender1 libxtst6 libxss1 \
        fonts-liberation fonts-wqy-zenhei fonts-ipafont-gothic xvfb \
        2>/dev/null || true
fi

echo "Starting JavBot..."
exec python -m app.main "$@"
