#!/usr/bin/env python3
"""
Test script to validate Telegram bot connection and configuration.
This script tests the bot token and basic Telegram API connectivity.
"""

import asyncio
import logging
import sys
from telegram import Bot
from telegram.error import TelegramError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_telegram_connection():
    """Test Telegram bot connection and configuration."""
    try:
        # Import config
        from config import get_config
        
        config = get_config()
        bot_token = config.get("bot_token", "")
        bot_owner = config.get("bot_owner", 0)
        
        if not bot_token or bot_token == "YOUR_BOT_TOKEN":
            logger.error("❌ Bot token not configured in config.json")
            return False
        
        logger.info("🧪 Testing Telegram bot connection...")
        
        # Create bot instance
        bot = Bot(token=bot_token)
        
        # Test 1: Get bot info
        logger.info("🔄 Testing bot authentication...")
        try:
            bot_info = await bot.get_me()
            logger.info(f"✅ Bot authenticated successfully:")
            logger.info(f"   • Username: @{bot_info.username}")
            logger.info(f"   • Name: {bot_info.first_name}")
            logger.info(f"   • ID: {bot_info.id}")
        except TelegramError as e:
            logger.error(f"❌ Bot authentication failed: {e}")
            return False
        
        # Test 2: Test bot owner configuration
        if bot_owner:
            logger.info(f"🔄 Testing bot owner configuration (ID: {bot_owner})...")
            try:
                # Try to get chat info (this will fail if bot can't access the chat)
                chat = await bot.get_chat(bot_owner)
                logger.info(f"✅ Bot owner chat accessible: {chat.first_name or chat.title}")
            except TelegramError as e:
                logger.warning(f"⚠️ Cannot access bot owner chat: {e}")
                logger.warning("   This may be normal if the bot hasn't been started by the owner yet")
        else:
            logger.warning("⚠️ Bot owner not configured in config.json")
        
        # Test 3: Test webhook info (should be empty for polling)
        logger.info("🔄 Checking webhook configuration...")
        try:
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url:
                logger.warning(f"⚠️ Webhook is set: {webhook_info.url}")
                logger.warning("   This may interfere with polling. Consider removing webhook.")
            else:
                logger.info("✅ No webhook configured (good for polling)")
        except TelegramError as e:
            logger.warning(f"⚠️ Could not check webhook info: {e}")
        
        logger.info("🎉 Telegram connection test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Telegram connection test failed: {e}")
        return False

async def test_telegram_application():
    """Test Telegram Application startup and shutdown."""
    try:
        logger.info("🧪 Testing Telegram Application lifecycle...")
        
        from telegram.ext import Application
        from config import get_config
        
        config = get_config()
        bot_token = config.get("bot_token", "")
        
        # Create application
        application = Application.builder().token(bot_token).build()
        
        # Test initialization
        logger.info("🔄 Testing application initialization...")
        await application.initialize()
        logger.info("✅ Application initialized")
        
        # Test start
        logger.info("🔄 Testing application start...")
        await application.start()
        logger.info("✅ Application started")
        
        # Test bot info through application
        bot_info = await application.bot.get_me()
        logger.info(f"✅ Application bot info: @{bot_info.username}")
        
        # Test shutdown sequence
        logger.info("🔄 Testing shutdown sequence...")
        await application.stop()
        logger.info("✅ Application stopped")
        
        await application.shutdown()
        logger.info("✅ Application shutdown complete")
        
        logger.info("🎉 Telegram Application test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Telegram Application test failed: {e}")
        return False

async def main():
    """Run all Telegram connection tests."""
    logger.info("🚀 Starting Telegram Connection Tests")
    logger.info("=" * 50)
    
    tests = [
        ("Basic Telegram Connection", test_telegram_connection),
        ("Telegram Application Lifecycle", test_telegram_application)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running test: {test_name}")
        logger.info("-" * 30)
        
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
    
    logger.info("\n" + "=" * 50)
    logger.info("🏁 Test Results Summary")
    logger.info("=" * 50)
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"📊 Total: {passed + failed}")
    
    if failed == 0:
        logger.info("🎉 All Telegram tests passed! Bot should work correctly.")
        return 0
    else:
        logger.error(f"💥 {failed} test(s) failed. Please fix the issues above.")
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
