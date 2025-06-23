# XBT (Bitcoin Classic) Telegram Bot Dockerfile
# Optimized for production deployment with complete isolation

FROM python:3.11-slim

# Set metadata
LABEL maintainer="XBT Bot Team"
LABEL description="Bitcoin Classic (XBT) Telegram Alert Bot with animated GIF alerts"
LABEL version="1.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=UTC

# Create app user for security (non-root)
RUN groupadd -r xbtbot && useradd -r -g xbtbot xbtbot

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/logs /app/images && \
    chown -R xbtbot:xbtbot /app

# Copy application files
COPY telebot_fixed.py .
COPY config.json .
COPY xbt_buy_alert.gif .
COPY nonkyc_integration_template.py .

# Copy pre-populated image collection
COPY --chown=xbtbot:xbtbot images/ ./images/

# Copy test files (useful for health checks)
COPY test_*.py ./

# Set proper permissions including image collection
RUN chown -R xbtbot:xbtbot /app && \
    chmod 644 /app/*.py /app/*.json /app/*.gif && \
    chmod 755 /app/logs /app/images && \
    find /app/images -type f -exec chmod 644 {} \; && \
    find /app/images -type f -exec chown xbtbot:xbtbot {} \;

# Switch to non-root user
USER xbtbot

# Health check to ensure bot is responsive
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import requests; requests.get('https://api.telegram.org/bot$(grep -o '\"bot_token\": \"[^\"]*\"' config.json | cut -d'\"' -f4)/getMe', timeout=5)" || exit 1

# Expose no ports (bot uses Telegram polling, not webhooks)
# This ensures no port conflicts with JKC bot

# Default command
CMD ["python3", "telebot_fixed.py"]
