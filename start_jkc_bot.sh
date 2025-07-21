#!/bin/bash

# JKC Bot Startup Script with Conflict Prevention
# This script ensures only one instance of the JKC bot runs at a time

set -e

# Configuration
BOT_NAME="jkc-telebot"
SCRIPT_NAME="telebot_fixed.py"
LOCKFILE="/tmp/jkc_bot.lock"
LOGFILE="logs/startup.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOGFILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOGFILE"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOGFILE"
}

success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS:${NC} $1" | tee -a "$LOGFILE"
}

# Function to check if bot is already running
check_running_instances() {
    log "🔍 Checking for existing JKC bot instances..."
    
    # Check for Python processes
    PYTHON_PIDS=$(pgrep -f "$SCRIPT_NAME" 2>/dev/null || true)
    if [ ! -z "$PYTHON_PIDS" ]; then
        warning "Found Python JKC bot processes: $PYTHON_PIDS"
        return 1
    fi
    
    # Check for Docker containers
    DOCKER_CONTAINERS=$(docker ps --filter "name=$BOT_NAME" --format "{{.ID}}" 2>/dev/null || true)
    if [ ! -z "$DOCKER_CONTAINERS" ]; then
        warning "Found Docker JKC bot containers: $DOCKER_CONTAINERS"
        return 1
    fi
    
    # Check lockfile
    if [ -f "$LOCKFILE" ]; then
        LOCK_PID=$(cat "$LOCKFILE" 2>/dev/null || echo "")
        if [ ! -z "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
            warning "Lockfile exists with active PID: $LOCK_PID"
            return 1
        else
            warning "Stale lockfile found, removing..."
            rm -f "$LOCKFILE"
        fi
    fi
    
    success "No conflicting JKC bot instances found"
    return 0
}

# Function to stop conflicting instances
stop_conflicting_instances() {
    log "🛑 Stopping conflicting JKC bot instances..."
    
    # Stop Python processes
    PYTHON_PIDS=$(pgrep -f "$SCRIPT_NAME" 2>/dev/null || true)
    if [ ! -z "$PYTHON_PIDS" ]; then
        log "Stopping Python processes: $PYTHON_PIDS"
        echo "$PYTHON_PIDS" | xargs -r kill -TERM
        sleep 3
        
        # Force kill if still running
        REMAINING_PIDS=$(pgrep -f "$SCRIPT_NAME" 2>/dev/null || true)
        if [ ! -z "$REMAINING_PIDS" ]; then
            warning "Force killing remaining processes: $REMAINING_PIDS"
            echo "$REMAINING_PIDS" | xargs -r kill -KILL
        fi
    fi
    
    # Stop Docker containers
    DOCKER_CONTAINERS=$(docker ps --filter "name=$BOT_NAME" --format "{{.ID}}" 2>/dev/null || true)
    if [ ! -z "$DOCKER_CONTAINERS" ]; then
        log "Stopping Docker containers: $DOCKER_CONTAINERS"
        echo "$DOCKER_CONTAINERS" | xargs -r docker stop
    fi
    
    # Remove lockfile
    rm -f "$LOCKFILE"
    
    # Wait for Telegram API to clear
    log "⏳ Waiting 10 seconds for Telegram API to clear previous sessions..."
    sleep 10
    
    success "Conflicting instances stopped"
}

# Function to clear Telegram webhook
clear_telegram_webhook() {
    log "🔧 Clearing Telegram webhook to prevent conflicts..."
    
    if [ -f "clear_webhook.py" ]; then
        python3 clear_webhook.py || warning "Failed to clear webhook"
    else
        warning "clear_webhook.py not found, skipping webhook clearing"
    fi
}

# Function to create lockfile
create_lockfile() {
    echo $$ > "$LOCKFILE"
    log "🔒 Created lockfile with PID: $$"
}

# Function to cleanup on exit
cleanup() {
    log "🧹 Cleaning up..."
    rm -f "$LOCKFILE"
    exit 0
}

# Set up signal handlers
trap cleanup EXIT INT TERM

# Main execution
main() {
    log "🚀 Starting JKC Bot with conflict prevention..."
    
    # Create logs directory if it doesn't exist
    mkdir -p logs
    
    # Check for running instances
    if ! check_running_instances; then
        if [ "$1" = "--force" ]; then
            stop_conflicting_instances
        else
            error "Conflicting JKC bot instances found!"
            error "Use '$0 --force' to stop them automatically"
            exit 1
        fi
    fi
    
    # Clear Telegram webhook
    clear_telegram_webhook
    
    # Create lockfile
    create_lockfile
    
    # Start the bot
    if [ "$1" = "--docker" ] || [ "$2" = "--docker" ]; then
        log "🐳 Starting JKC bot via Docker..."
        docker compose up -d --build
        success "JKC bot started in Docker container"
        
        # Follow logs
        log "📋 Following container logs (Ctrl+C to stop following)..."
        docker logs -f "$BOT_NAME-container" 2>&1 || true
    else
        log "🐍 Starting JKC bot directly with Python..."
        python3 "$SCRIPT_NAME"
    fi
}

# Help function
show_help() {
    echo "JKC Bot Startup Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --force     Stop any conflicting bot instances automatically"
    echo "  --docker    Start the bot using Docker Compose"
    echo "  --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Start bot (fail if conflicts exist)"
    echo "  $0 --force           # Start bot (stop conflicts first)"
    echo "  $0 --docker --force  # Start via Docker (stop conflicts first)"
}

# Parse command line arguments
case "$1" in
    --help|-h)
        show_help
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
