#!/bin/bash

# JKC Bot Docker Deployment Script
# Complete automated deployment with validation and monitoring

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="jkc-telebot-container"
IMAGE_NAME="jkc-telebot"
IMAGE_TAG="latest"
COMPOSE_FILE="docker-compose.jkc.yml"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check if config.json exists
    if [ ! -f "config.json" ]; then
        log_warning "config.json not found, creating from example"
        if [ -f "config.json.example" ]; then
            cp config.json.example config.json
            log_info "Created config.json from example"
        else
            log_error "config.json.example not found"
            exit 1
        fi
    fi
    
    # Check if jkc_buy_alert.gif exists
    if [ ! -f "jkc_buy_alert.gif" ]; then
        log_error "jkc_buy_alert.gif not found"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

validate_configuration() {
    log_info "Validating configuration..."
    
    # Check if bot token is set
    BOT_TOKEN=$(grep -o '"bot_token": *"[^"]*"' config.json | cut -d'"' -f4)
    if [ "$BOT_TOKEN" = "YOUR_BOT_TOKEN_HERE" ] || [ -z "$BOT_TOKEN" ]; then
        log_error "Bot token not set in config.json"
        exit 1
    fi
    
    # Check if bot owner is set
    BOT_OWNER=$(grep -o '"bot_owner": *[0-9]*' config.json | cut -d':' -f2 | tr -d ' ')
    if [ "$BOT_OWNER" = "0" ] || [ -z "$BOT_OWNER" ]; then
        log_warning "Bot owner not set in config.json"
    fi
    
    log_success "Configuration validation passed"
}

stop_existing_container() {
    log_info "Checking for existing container..."
    
    # Check if container exists and stop it
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "Stopping existing container: ${CONTAINER_NAME}"
        docker stop ${CONTAINER_NAME} > /dev/null 2>&1 || true
        docker rm ${CONTAINER_NAME} > /dev/null 2>&1 || true
        log_success "Existing container stopped and removed"
    else
        log_info "No existing container found"
    fi
}

create_directories() {
    log_info "Creating required directories..."
    
    # Create logs directory if it doesn't exist
    mkdir -p logs
    
    # Create images directory if it doesn't exist
    mkdir -p images
    
    # Create backups directory if it doesn't exist
    mkdir -p backups
    
    log_success "Directories created"
}

build_image() {
    log_info "Building Docker image..."
    
    # Build the Docker image
    docker-compose -f ${COMPOSE_FILE} build
    
    log_success "Docker image built: ${IMAGE_NAME}:${IMAGE_TAG}"
}

deploy_container() {
    log_info "Deploying container..."
    
    # Deploy the container
    docker-compose -f ${COMPOSE_FILE} up -d
    
    log_success "Container deployed: ${CONTAINER_NAME}"
}

wait_for_startup() {
    log_info "Waiting for container to start..."
    
    # Wait for container to start
    sleep 5
    
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_error "Container failed to start"
        docker logs ${CONTAINER_NAME}
        exit 1
    fi
    
    log_success "Container started successfully"
}

show_status() {
    log_info "Container status:"
    
    # Show container status
    docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    log_info "Container logs (last 10 lines):"
    docker logs --tail 10 ${CONTAINER_NAME}
}

run_tests() {
    log_info "Running post-deployment tests..."
    
    # Test if container is healthy
    HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' ${CONTAINER_NAME})
    if [ "$HEALTH_STATUS" = "healthy" ]; then
        log_success "Container health check passed"
    else
        log_warning "Container health check not passed yet, status: ${HEALTH_STATUS}"
    fi
    
    # Test if GIF file is accessible
    if docker exec $CONTAINER_NAME test -f jkc_buy_alert.gif; then
        log_success "GIF file is accessible in container"
    else
        log_error "GIF file not found in container"
        return 1
    fi
    
    log_success "All post-deployment tests passed"
}

cleanup_old_images() {
    log_info "Cleaning up old Docker images..."
    
    # Remove dangling images
    docker image prune -f > /dev/null 2>&1 || true
    
    log_success "Cleanup completed"
}

main() {
    echo "🚀 JKC Bot Docker Deployment"
    echo "============================"
    
    check_prerequisites
    validate_configuration
    stop_existing_container
    create_directories
    build_image
    deploy_container
    wait_for_startup
    run_tests
    show_status
    cleanup_old_images
    
    echo "============================"
    echo "✅ JKC Bot deployment completed successfully"
    echo "📝 Check logs with: docker logs ${CONTAINER_NAME}"
    echo "🛑 Stop bot with: docker stop ${CONTAINER_NAME}"
    echo "🔄 Restart bot with: docker restart ${CONTAINER_NAME}"
}

# Run main function
main
