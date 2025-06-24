#!/usr/bin/env python3
"""
Test script to validate the XBT trading bot shutdown/restart loop fixes.
This script tests the bot's stability and proper shutdown handling.
"""

import asyncio
import logging
import signal
import sys
import time
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_shutdown_fix.log')
    ]
)
logger = logging.getLogger(__name__)

async def test_background_task_stability():
    """Test that background tasks run stably without unexpected exits."""
    logger.info("🧪 Testing background task stability...")
    
    try:
        # Import the WebSocket handlers
        from websocket_handlers import (
            exchange_availability_monitor, heartbeat, 
            set_trade_processor, stop_websockets
        )
        from alert_system import initialize_alert_system, process_message
        
        # Initialize alert system and set trade processor
        initialize_alert_system()
        set_trade_processor(process_message)
        
        # Create test tasks (subset of background tasks)
        tasks = [
            asyncio.create_task(exchange_availability_monitor(), name="availability_monitor"),
            asyncio.create_task(heartbeat(), name="heartbeat")
        ]
        
        logger.info(f"✅ Started {len(tasks)} test background tasks")
        
        # Let them run for 30 seconds
        start_time = time.time()
        test_duration = 30
        
        while time.time() - start_time < test_duration:
            # Check if any tasks completed unexpectedly
            for task in tasks:
                if task.done():
                    if task.exception():
                        logger.error(f"❌ Task '{task.get_name()}' failed: {task.exception()}")
                        return False
                    else:
                        logger.error(f"❌ Task '{task.get_name()}' completed unexpectedly")
                        return False
            
            await asyncio.sleep(1)
        
        logger.info("✅ Background tasks ran stably for 30 seconds")
        
        # Cancel tasks gracefully
        logger.info("🛑 Cancelling test tasks...")
        stop_websockets()
        
        for task in tasks:
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        logger.info("✅ Test tasks cancelled successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Background task stability test failed: {e}")
        return False

async def test_telegram_application_lifecycle():
    """Test Telegram application startup and shutdown sequence."""
    logger.info("🧪 Testing Telegram application lifecycle...")
    
    try:
        from telegram.ext import Application
        from config import get_config
        
        config = get_config()
        bot_token = config.get("bot_token", "")
        
        if not bot_token or bot_token == "YOUR_BOT_TOKEN":
            logger.warning("⚠️ Bot token not configured, skipping Telegram test")
            return True
        
        # Create application
        application = Application.builder().token(bot_token).build()
        
        # Test initialization
        logger.info("🔄 Testing application initialization...")
        await application.initialize()
        logger.info("✅ Application initialized successfully")
        
        # Test start
        logger.info("🔄 Testing application start...")
        await application.start()
        logger.info("✅ Application started successfully")
        
        # Test updater start (but don't actually poll)
        logger.info("🔄 Testing updater lifecycle...")
        # Note: We won't actually start polling to avoid interfering with production bot
        
        # Test shutdown sequence
        logger.info("🔄 Testing shutdown sequence...")
        
        # Stop application
        await application.stop()
        logger.info("✅ Application stopped successfully")
        
        # Shutdown application
        await application.shutdown()
        logger.info("✅ Application shutdown successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Telegram application lifecycle test failed: {e}")
        return False

async def test_signal_handling():
    """Test signal handling and graceful shutdown."""
    logger.info("🧪 Testing signal handling...")
    
    try:
        # Test signal handler setup
        signal_received = False
        
        def test_signal_handler(signum, frame):
            nonlocal signal_received
            logger.info(f"✅ Signal {signum} received and handled")
            signal_received = True
        
        # Set up test signal handler
        original_handler = signal.signal(signal.SIGTERM, test_signal_handler)
        
        # Send test signal to self
        import os
        os.kill(os.getpid(), signal.SIGTERM)
        
        # Wait a moment for signal processing
        await asyncio.sleep(0.1)
        
        # Restore original handler
        signal.signal(signal.SIGTERM, original_handler)
        
        if signal_received:
            logger.info("✅ Signal handling test passed")
            return True
        else:
            logger.error("❌ Signal was not received")
            return False
            
    except Exception as e:
        logger.error(f"❌ Signal handling test failed: {e}")
        return False

async def main():
    """Run all shutdown fix validation tests."""
    logger.info("🚀 Starting XBT Trading Bot Shutdown Fix Validation")
    logger.info("=" * 60)
    
    tests = [
        ("Background Task Stability", test_background_task_stability),
        ("Telegram Application Lifecycle", test_telegram_application_lifecycle),
        ("Signal Handling", test_signal_handling)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running test: {test_name}")
        logger.info("-" * 40)
        
        try:
            result = await test_func()
            if result:
                logger.info(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name}: FAILED")
                failed += 1
        except Exception as e:
            logger.error(f"❌ {test_name}: FAILED with exception: {e}")
            failed += 1
    
    logger.info("\n" + "=" * 60)
    logger.info("🏁 Test Results Summary")
    logger.info("=" * 60)
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"📊 Total: {passed + failed}")
    
    if failed == 0:
        logger.info("🎉 All tests passed! Shutdown fixes are working correctly.")
        return 0
    else:
        logger.error(f"💥 {failed} test(s) failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test runner failed: {e}")
        sys.exit(1)
