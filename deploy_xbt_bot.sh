#!/bin/bash

# XBT Bot Docker Deployment Script
# Complete automated deployment with validation and monitoring

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="xbt-telebot-container"
IMAGE_NAME="xbt-telebot"
IMAGE_TAG="latest"
COMPOSE_FILE="docker-compose.xbt.yml"

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
    
    # Check if we're in the right directory
    if [[ ! -f "telebot_fixed.py" ]]; then
        log_error "telebot_fixed.py not found. Are you in the XBT bot directory?"
        exit 1
    fi
    
    # Check if GIF file exists
    if [[ ! -f "xbt_buy_alert.gif" ]]; then
        log_error "xbt_buy_alert.gif not found"
        exit 1
    fi
    
    # Check if config exists
    if [[ ! -f "config.json" ]]; then
        log_error "config.json not found"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

validate_configuration() {
    log_info "Validating configuration..."
    
    # Run configuration tests
    if python3 test_config_loading.py > /dev/null 2>&1; then
        log_success "Configuration validation passed"
    else
        log_error "Configuration validation failed"
        log_info "Run: python3 test_config_loading.py for details"
        exit 1
    fi
    
    # Run GIF integration tests
    if python3 test_gif_integration.py > /dev/null 2>&1; then
        log_success "GIF integration validation passed"
    else
        log_error "GIF integration validation failed"
        log_info "Run: python3 test_gif_integration.py for details"
        exit 1
    fi
}

stop_existing_container() {
    log_info "Checking for existing container..."
    
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        log_warning "Stopping existing container: $CONTAINER_NAME"
        docker stop $CONTAINER_NAME
    fi
    
    if docker ps -aq -f name=$CONTAINER_NAME | grep -q .; then
        log_warning "Removing existing container: $CONTAINER_NAME"
        docker rm $CONTAINER_NAME
    fi
}

build_image() {
    log_info "Building Docker image: $IMAGE_NAME:$IMAGE_TAG"
    
    # Build the image
    docker build -t $IMAGE_NAME:$IMAGE_TAG .
    
    # Also tag with version
    docker tag $IMAGE_NAME:$IMAGE_TAG $IMAGE_NAME:v1.0
    
    log_success "Docker image built successfully"
    
    # Show image info
    docker images $IMAGE_NAME
}

create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p logs images backups
    
    # Set proper permissions
    chmod 755 logs images backups
    
    log_success "Directories created"
}

deploy_container() {
    log_info "Deploying container using Docker Compose..."
    
    # Deploy using docker-compose
    docker-compose -f $COMPOSE_FILE up -d
    
    log_success "Container deployed successfully"
}

wait_for_startup() {
    log_info "Waiting for bot to start up..."
    
    # Wait up to 60 seconds for the container to be healthy
    for i in {1..60}; do
        if docker ps --filter "name=$CONTAINER_NAME" --filter "health=healthy" | grep -q $CONTAINER_NAME; then
            log_success "Bot started successfully and is healthy"
            return 0
        fi
        
        if docker ps --filter "name=$CONTAINER_NAME" --filter "health=unhealthy" | grep -q $CONTAINER_NAME; then
            log_error "Bot health check failed"
            return 1
        fi
        
        echo -n "."
        sleep 1
    done
    
    log_warning "Health check timeout, but container may still be starting"
    return 0
}

show_status() {
    log_info "Container status:"
    docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    log_info "Recent logs:"
    docker logs --tail 20 $CONTAINER_NAME
}

run_tests() {
    log_info "Running post-deployment tests..."
    
    # Test if the bot process is running
    if docker exec $CONTAINER_NAME pgrep -f "python3 telebot_fixed.py" > /dev/null; then
        log_success "Bot process is running"
    else
        log_error "Bot process not found"
        return 1
    fi
    
    # Test if config is loaded correctly
    if docker exec $CONTAINER_NAME python3 -c "import json; config=json.load(open('config.json')); print('Config loaded')" > /dev/null 2>&1; then
        log_success "Configuration loads correctly in container"
    else
        log_error "Configuration loading failed in container"
        return 1
    fi
    
    # Test if GIF file is accessible
    if docker exec $CONTAINER_NAME test -f xbt_buy_alert.gif; then
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
    echo "🚀 XBT Bot Docker Deployment"
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
    
    echo ""
    echo "🎉 XBT Bot Deployment Complete!"
    echo "================================"
    log_success "Container: $CONTAINER_NAME"
    log_success "Image: $IMAGE_NAME:$IMAGE_TAG"
    log_success "Status: Running with animated GIF alerts"
    echo ""
    log_info "Next steps:"
    echo "  1. Test bot in Telegram with /start command"
    echo "  2. Use /test command to verify GIF alerts"
    echo "  3. Monitor logs: docker logs -f $CONTAINER_NAME"
    echo "  4. Check status: docker ps | grep xbt"
    echo ""
    log_info "Management commands:"
    echo "  Stop:    docker stop $CONTAINER_NAME"
    echo "  Start:   docker start $CONTAINER_NAME"
    echo "  Restart: docker restart $CONTAINER_NAME"
    echo "  Logs:    docker logs -f $CONTAINER_NAME"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "stop")
        log_info "Stopping XBT bot container..."
        docker stop $CONTAINER_NAME 2>/dev/null || log_warning "Container not running"
        ;;
    "start")
        log_info "Starting XBT bot container..."
        docker start $CONTAINER_NAME 2>/dev/null || log_error "Container not found"
        ;;
    "restart")
        log_info "Restarting XBT bot container..."
        docker restart $CONTAINER_NAME 2>/dev/null || log_error "Container not found"
        ;;
    "logs")
        docker logs -f $CONTAINER_NAME
        ;;
    "status")
        show_status
        ;;
    *)
        echo "Usage: $0 [deploy|stop|start|restart|logs|status]"
        echo "  deploy  - Full deployment (default)"
        echo "  stop    - Stop the container"
        echo "  start   - Start the container"
        echo "  restart - Restart the container"
        echo "  logs    - Show container logs"
        echo "  status  - Show container status"
        exit 1
        ;;
esac
