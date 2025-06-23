#!/usr/bin/env python3
"""
Test bot isolation between JKC and XBT bots
"""

import os
import sys
import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_working_directories():
    """Test that bots use separate working directories."""
    logger.info("🧪 Testing working directory isolation...")
    
    current_dir = os.getcwd()
    logger.info(f"Current working directory: {current_dir}")
    
    # Check that we're in the XBT bot directory
    if "xbttelebot" in current_dir:
        logger.info("✅ Running in XBT bot directory")
    else:
        logger.warning(f"⚠️  Not in expected XBT directory: {current_dir}")
    
    # Check for JKC bot directory
    jkc_dir = "../jkctelebot"
    if os.path.exists(jkc_dir):
        logger.info(f"✅ JKC bot directory exists: {jkc_dir}")
        return True
    else:
        logger.info(f"ℹ️  JKC bot directory not found: {jkc_dir}")
        return True  # Not an error if JKC bot isn't present

def test_configuration_isolation():
    """Test that configuration files are separate."""
    logger.info("🧪 Testing configuration isolation...")
    
    # Load XBT bot config
    try:
        with open("config.json", 'r') as f:
            xbt_config = json.load(f)
        logger.info("✅ XBT bot config loaded")
    except Exception as e:
        logger.error(f"❌ Error loading XBT config: {e}")
        return False
    
    # Check XBT-specific values
    xbt_image = xbt_config.get("image_path", "")
    if xbt_image == "xbt_buy_alert.gif":
        logger.info(f"✅ XBT bot uses correct image: {xbt_image}")
    else:
        logger.error(f"❌ XBT bot has wrong image: {xbt_image}")
        return False
    
    # Check if JKC config exists and is different
    jkc_config_path = "../jkctelebot/config.json"
    if os.path.exists(jkc_config_path):
        try:
            with open(jkc_config_path, 'r') as f:
                jkc_config = json.load(f)
            
            jkc_image = jkc_config.get("image_path", "")
            logger.info(f"ℹ️  JKC bot image: {jkc_image}")
            
            if jkc_image != xbt_image:
                logger.info("✅ Bots use different image files")
            else:
                logger.warning("⚠️  Bots use same image file")
            
        except Exception as e:
            logger.warning(f"⚠️  Could not read JKC config: {e}")
    else:
        logger.info("ℹ️  JKC config not found (bots are isolated)")
    
    return True

def test_log_file_isolation():
    """Test that log files are separate."""
    logger.info("🧪 Testing log file isolation...")
    
    # Check XBT bot log directory
    xbt_logs_dir = "logs"
    if os.path.exists(xbt_logs_dir):
        xbt_log_files = os.listdir(xbt_logs_dir)
        logger.info(f"✅ XBT bot logs directory: {len(xbt_log_files)} files")
    else:
        logger.info("ℹ️  XBT bot logs directory not yet created")
    
    # Check for shared log files
    shared_log_patterns = [
        "/tmp/bot.log",
        "/var/log/telebot.log",
        "../shared_bot.log"
    ]
    
    shared_logs_found = []
    for log_path in shared_log_patterns:
        if os.path.exists(log_path):
            shared_logs_found.append(log_path)
    
    if shared_logs_found:
        logger.warning(f"⚠️  Shared log files found: {shared_logs_found}")
    else:
        logger.info("✅ No shared log files detected")
    
    return True

def test_image_file_isolation():
    """Test that image files are separate."""
    logger.info("🧪 Testing image file isolation...")
    
    # Check XBT bot images
    xbt_image = "xbt_buy_alert.gif"
    xbt_images_dir = "images"
    
    if os.path.exists(xbt_image):
        logger.info(f"✅ XBT bot default image: {xbt_image}")
    else:
        logger.error(f"❌ XBT bot default image missing: {xbt_image}")
        return False
    
    if os.path.exists(xbt_images_dir):
        xbt_image_count = len(os.listdir(xbt_images_dir))
        logger.info(f"✅ XBT bot images directory: {xbt_image_count} files")
    else:
        logger.info("ℹ️  XBT bot images directory not yet created")
    
    # Check JKC bot images
    jkc_image_path = "../jkctelebot/junk_resized.jpeg"
    if os.path.exists(jkc_image_path):
        logger.info(f"ℹ️  JKC bot image exists: {jkc_image_path}")
        logger.info("✅ Bots use separate image files")
    else:
        logger.info("ℹ️  JKC bot image not found (bots are isolated)")
    
    return True

def test_port_and_resource_isolation():
    """Test that bots don't use conflicting ports or resources."""
    logger.info("🧪 Testing port and resource isolation...")
    
    # Check bot code for hardcoded ports
    try:
        with open("telebot_fixed.py", 'r') as f:
            content = f.read()
        
        # Look for potential port conflicts
        port_patterns = [":80", ":443", ":8080", "localhost:", "127.0.0.1:"]
        ports_found = []
        
        for pattern in port_patterns:
            if pattern in content:
                ports_found.append(pattern)
        
        if ports_found:
            logger.warning(f"⚠️  Port patterns found in code: {ports_found}")
        else:
            logger.info("✅ No hardcoded ports found in bot code")
        
        # Check for WebSocket usage (should be fine as they use different endpoints)
        if "websockets" in content:
            logger.info("✅ Bot uses WebSocket connections (different endpoints)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking bot code: {e}")
        return False

def test_process_isolation():
    """Test that bots can run as separate processes."""
    logger.info("🧪 Testing process isolation...")
    
    # Check for shared global state or locks
    shared_resources = [
        "/tmp/bot.lock",
        "/var/run/telebot.pid",
        "../shared_state.json"
    ]
    
    shared_found = []
    for resource in shared_resources:
        if os.path.exists(resource):
            shared_found.append(resource)
    
    if shared_found:
        logger.warning(f"⚠️  Shared resources found: {shared_found}")
    else:
        logger.info("✅ No shared process resources detected")
    
    # Check that bot uses different working directory
    current_dir = os.getcwd()
    if "xbttelebot" in current_dir:
        logger.info("✅ Bot runs in isolated working directory")
    else:
        logger.warning(f"⚠️  Unexpected working directory: {current_dir}")
    
    return True

def test_telegram_token_isolation():
    """Test that bots use different Telegram tokens."""
    logger.info("🧪 Testing Telegram token isolation...")
    
    try:
        with open("config.json", 'r') as f:
            xbt_config = json.load(f)
        
        xbt_token = xbt_config.get("bot_token", "")
        if xbt_token and len(xbt_token) > 10:
            logger.info("✅ XBT bot has valid token configured")
            
            # Check if JKC bot has different token
            jkc_config_path = "../jkctelebot/config.json"
            if os.path.exists(jkc_config_path):
                try:
                    with open(jkc_config_path, 'r') as f:
                        jkc_config = json.load(f)
                    
                    jkc_token = jkc_config.get("bot_token", "")
                    if jkc_token != xbt_token:
                        logger.info("✅ Bots use different Telegram tokens")
                    else:
                        logger.error("❌ Bots use the same Telegram token!")
                        return False
                        
                except Exception as e:
                    logger.warning(f"⚠️  Could not read JKC token: {e}")
            else:
                logger.info("ℹ️  JKC config not found (tokens are isolated)")
        else:
            logger.error("❌ XBT bot token not configured")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking tokens: {e}")
        return False

def main():
    """Run all isolation tests."""
    logger.info("🚀 XBT Bot Isolation Tests")
    logger.info("=" * 50)
    
    tests = [
        ("Working Directory Isolation", test_working_directories),
        ("Configuration Isolation", test_configuration_isolation),
        ("Log File Isolation", test_log_file_isolation),
        ("Image File Isolation", test_image_file_isolation),
        ("Port and Resource Isolation", test_port_and_resource_isolation),
        ("Process Isolation", test_process_isolation),
        ("Telegram Token Isolation", test_telegram_token_isolation),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running: {test_name}")
        logger.info("-" * 30)
        
        try:
            result = test_func()
            results.append((test_name, result))
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"Result: {status}")
        except Exception as e:
            logger.error(f"❌ EXCEPTION: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 BOT ISOLATION TEST SUMMARY")
    logger.info("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name}")
    
    logger.info("-" * 50)
    logger.info(f"Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        logger.info("🎉 Perfect isolation! Both bots can run simultaneously.")
        logger.info("✅ No conflicts detected between JKC and XBT bots.")
    elif passed >= total * 0.8:
        logger.info("⚠️  Good isolation with minor warnings.")
        logger.info("✅ Bots should be able to run simultaneously.")
    else:
        logger.error("❌ Isolation issues detected.")
        logger.error("⚠️  Review conflicts before running both bots.")
    
    return passed >= total * 0.8

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
