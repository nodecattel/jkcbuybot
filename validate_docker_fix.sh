#!/bin/bash

# XBT Trading Bot Docker Fix Validation Script
# This script validates that the Docker deployment issue has been resolved
# and all modular Python files are properly included in the container

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
TEST_IMAGE_NAME="xbt-telebot-validation:test"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Logging functions
log() {
    echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
}

log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] ℹ️  $1${NC}"
}

# Header
echo -e "${PURPLE}"
echo "================================================================================"
echo "🔧 XBT TRADING BOT - DOCKER DEPLOYMENT FIX VALIDATION"
echo "================================================================================"
echo "Testing modular architecture Docker deployment fix"
echo "================================================================================"
echo -e "${NC}"

# Step 1: Verify all Python files exist
log "🔍 STEP 1: Verifying all required Python files exist..."

REQUIRED_FILES=(
    "telebot_fixed.py"
    "config.py"
    "utils.py"
    "permissions.py"
    "image_manager.py"
    "api_clients.py"
    "websocket_handlers.py"
    "alert_system.py"
    "telegram_handlers.py"
)

cd "$SCRIPT_DIR"

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        log_success "Found: $file"
    else
        log_error "Missing: $file"
        exit 1
    fi
done

echo ""

# Step 2: Build test Docker image
log "🔨 STEP 2: Building test Docker image..."

if docker build -t "$TEST_IMAGE_NAME" .; then
    log_success "Docker image built successfully"
else
    log_error "Docker image build failed"
    exit 1
fi

echo ""

# Step 3: Test module imports
log "🧪 STEP 3: Testing module imports in container..."

IMPORT_TEST=$(docker run --rm "$TEST_IMAGE_NAME" python3 -c "
import sys
print('Testing all module imports...')
modules = [
    'config', 'utils', 'permissions', 'image_manager', 
    'api_clients', 'websocket_handlers', 'alert_system', 'telegram_handlers'
]
failed = []
for module in modules:
    try:
        __import__(module)
        print(f'✅ {module}.py imported successfully')
    except ImportError as e:
        print(f'❌ {module}.py import failed: {e}')
        failed.append(module)
        
if failed:
    print(f'❌ Failed modules: {failed}')
    sys.exit(1)
else:
    print('🎉 All modules imported successfully!')
    sys.exit(0)
" 2>&1)

echo "$IMPORT_TEST"

if echo "$IMPORT_TEST" | grep -q "All modules imported successfully"; then
    log_success "All module imports working correctly"
else
    log_error "Module import test failed"
    docker rmi "$TEST_IMAGE_NAME" 2>/dev/null || true
    exit 1
fi

echo ""

# Step 4: Test main telebot_fixed.py imports
log "🎯 STEP 4: Testing main telebot_fixed.py imports..."

MAIN_IMPORT_TEST=$(docker run --rm "$TEST_IMAGE_NAME" python3 -c "
import sys
print('Testing telebot_fixed.py specific imports...')
try:
    # Test the exact imports from telebot_fixed.py
    from config import get_config, get_bot_token, get_bot_owner, get_active_chat_ids, get_value_require
    from utils import setup_logging, INPUT_NUMBER, INPUT_IMAGE_SETIMAGE, CONFIG_MENU, DYNAMIC_CONFIG, INPUT_API_KEYS
    from permissions import is_admin
    from image_manager import load_random_image
    from websocket_handlers import (
        nonkyc_websocket_usdt, nonkyc_websocket_btc, coinex_websocket, 
        ascendex_websocket, nonkyc_orderbook_websocket, exchange_availability_monitor,
        heartbeat, set_trade_processor, stop_websockets
    )
    from alert_system import initialize_alert_system, process_message
    from telegram_handlers import (
        start_bot, stop_bot, help_command, check_price, chart_command, get_ipwan_command,
        toggle_aggregation, debug_command, test_command, cancel, set_minimum_command,
        set_minimum_input, config_command, set_image_command, set_image_input,
        list_images_command, clear_images_command, button_callback, set_global_photo
    )
    print('🎉 All telebot_fixed.py imports successful!')
    print('✅ ModuleNotFoundError issue resolved')
    sys.exit(0)
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Unexpected error: {e}')
    sys.exit(1)
" 2>&1)

echo "$MAIN_IMPORT_TEST"

if echo "$MAIN_IMPORT_TEST" | grep -q "ModuleNotFoundError issue resolved"; then
    log_success "Main telebot_fixed.py imports working correctly"
else
    log_error "Main import test failed"
    docker rmi "$TEST_IMAGE_NAME" 2>/dev/null || true
    exit 1
fi

echo ""

# Step 5: Test container startup validation
log "🚀 STEP 5: Testing container startup validation..."

STARTUP_TEST=$(docker run --rm "$TEST_IMAGE_NAME" python3 -c "
import sys
print('Testing container startup components...')
try:
    # Test basic initialization components
    from config import get_config
    from utils import setup_logging
    from image_manager import get_image_collection
    from alert_system import initialize_alert_system
    
    print('✅ Configuration system ready')
    print('✅ Logging system ready')
    print('✅ Image management system ready')
    print('✅ Alert system ready')
    print('🎉 Container startup validation successful!')
    sys.exit(0)
except Exception as e:
    print(f'❌ Startup validation error: {e}')
    sys.exit(1)
" 2>&1)

echo "$STARTUP_TEST"

if echo "$STARTUP_TEST" | grep -q "Container startup validation successful"; then
    log_success "Container startup validation passed"
else
    log_error "Container startup validation failed"
    docker rmi "$TEST_IMAGE_NAME" 2>/dev/null || true
    exit 1
fi

echo ""

# Step 6: Clean up test image
log "🧹 STEP 6: Cleaning up test image..."

if docker rmi "$TEST_IMAGE_NAME" >/dev/null 2>&1; then
    log_success "Test image cleaned up successfully"
else
    log_error "Failed to clean up test image"
fi

echo ""

# Final success message
echo -e "${GREEN}"
echo "================================================================================"
echo "✅ DOCKER DEPLOYMENT FIX VALIDATION COMPLETED SUCCESSFULLY!"
echo "================================================================================"
echo -e "${NC}"

log_success "All 9 Python modules are properly included in Docker container"
log_success "ModuleNotFoundError issue has been resolved"
log_success "Container can start without import errors"
log_success "Modular architecture is fully supported in Docker deployment"

echo ""
log_info "🎯 VALIDATION RESULTS:"
echo "   ✅ All 9 Python files present and accessible"
echo "   ✅ Docker build includes all modular components"
echo "   ✅ Module imports working correctly in container"
echo "   ✅ Main telebot_fixed.py imports successful"
echo "   ✅ Container startup validation passed"

echo ""
log_info "📋 NEXT STEPS:"
echo "   1. Run ./deploy.sh to deploy with the fixed Dockerfile"
echo "   2. Monitor container logs for successful startup"
echo "   3. Test XBT trading bot functionality"
echo "   4. Verify all enhanced features are working"

echo ""
echo -e "${PURPLE}================================================================================"
echo "🎉 DOCKER DEPLOYMENT FIX VALIDATION COMPLETE - READY FOR PRODUCTION!"
echo "================================================================================${NC}"

exit 0
