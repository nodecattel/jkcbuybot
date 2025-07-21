# JKC (JunkCoin) Telegram Bot Dockerfile
# Optimized for production deployment with complete isolation

FROM python:3.11-slim

# Set metadata
LABEL maintainer="JKC Bot Team"
LABEL description="JunkCoin (JKC) Telegram Alert Bot with animated GIF alerts"
LABEL version="1.0"
LABEL project="JKC-TeleBot"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=UTC

# Create app user for security (non-root) with host-compatible UID/GID
ARG USER_ID=1007
ARG GROUP_ID=1007
RUN groupadd -g ${GROUP_ID} jkcbot && useradd -u ${USER_ID} -g jkcbot -m jkcbot

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

# Create necessary directories with proper ownership
RUN mkdir -p /app/logs /app/images && \
    chown -R jkcbot:jkcbot /app && \
    chmod 755 /app/logs /app/images

# Copy application files
COPY telebot_fixed.py .
COPY alert_system.py .
COPY api_clients.py .
COPY config.py .
COPY image_manager.py .
COPY permissions.py .
COPY telegram_handlers.py .
COPY utils.py .
COPY websocket_handlers.py .
COPY config.json .
COPY jkc_buy_alert.gif .
COPY jkcbuy.GIF .

# Copy pre-populated image collection
COPY --chown=jkcbot:jkcbot images/ ./images/

# Set proper permissions including image collection and logs
RUN chown -R jkcbot:jkcbot /app && \
    chmod 644 /app/*.py /app/*.json /app/*.gif && \
    chmod 755 /app/logs /app/images && \
    chmod 775 /app/logs && \
    find /app/images -type f -exec chmod 644 {} \; && \
    find /app/images -type f -exec chown jkcbot:jkcbot {} \;

# Switch to non-root user
USER jkcbot

# Health check to ensure bot is responsive
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import requests; requests.get('https://api.telegram.org/bot$(grep -o '\"bot_token\": \"[^\"]*\"' config.json | cut -d'\"' -f4)/getMe', timeout=5)" || exit 1

# Expose no ports (bot uses Telegram polling, not webhooks)
# This ensures no port conflicts with JKC bot

# Default command
CMD ["python3", "telebot_fixed.py"]
