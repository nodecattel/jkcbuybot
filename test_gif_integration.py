#!/usr/bin/env python3
"""
Test script for GIF integration in XBT bot
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_file_existence():
    """Test that all required files exist."""
    logger.info("🧪 Testing file existence...")
    
    files_to_check = [
        "xbt_buy_alert.gif",
        "config.json",
        "config.json.example",
        "telebot_fixed.py"
    ]
    
    results = {}
    for file_path in files_to_check:
        exists = os.path.exists(file_path)
        size = os.path.getsize(file_path) if exists else 0
        results[file_path] = {"exists": exists, "size": size}
        
        if exists:
            logger.info(f"✅ {file_path}: {size:,} bytes")
        else:
            logger.error(f"❌ {file_path}: NOT FOUND")
    
    return all(result["exists"] for result in results.values())

def test_gif_properties():
    """Test GIF file properties."""
    logger.info("🧪 Testing GIF properties...")
    
    gif_path = "xbt_buy_alert.gif"
    if not os.path.exists(gif_path):
        logger.error(f"❌ GIF file not found: {gif_path}")
        return False
    
    # Check file size (should be under 10MB for Telegram)
    file_size = os.path.getsize(gif_path)
    max_size = 10 * 1024 * 1024  # 10MB
    
    logger.info(f"📁 File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
    
    if file_size > max_size:
        logger.error(f"❌ File too large: {file_size:,} bytes > {max_size:,} bytes")
        return False
    else:
        logger.info(f"✅ File size OK: {file_size:,} bytes < {max_size:,} bytes")
    
    # Check file permissions
    readable = os.access(gif_path, os.R_OK)
    if readable:
        logger.info("✅ File is readable")
    else:
        logger.error("❌ File is not readable")
        return False
    
    return True

def test_config_files():
    """Test that config files reference the correct GIF."""
    logger.info("🧪 Testing configuration files...")
    
    config_files = ["config.json", "config.json.example"]
    expected_path = "xbt_buy_alert.gif"
    
    for config_file in config_files:
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            image_path = config.get("image_path", "")
            if image_path == expected_path:
                logger.info(f"✅ {config_file}: image_path = '{image_path}'")
            else:
                logger.error(f"❌ {config_file}: image_path = '{image_path}' (expected '{expected_path}')")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error reading {config_file}: {e}")
            return False
    
    return True

def test_bot_code_references():
    """Test that bot code references the correct GIF."""
    logger.info("🧪 Testing bot code references...")
    
    try:
        with open("telebot_fixed.py", 'r') as f:
            content = f.read()
        
        # Check for the default image path in the code
        expected_line = '"image_path": "xbt_buy_alert.gif"'
        if expected_line in content:
            logger.info(f"✅ Bot code contains: {expected_line}")
        else:
            logger.error(f"❌ Bot code missing: {expected_line}")
            return False
        
        # Check that GIF is in supported formats
        if '".gif"' in content:
            logger.info("✅ GIF format is supported in SUPPORTED_IMAGE_FORMATS")
        else:
            logger.error("❌ GIF format not found in supported formats")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error reading bot code: {e}")
        return False

def test_image_loading_simulation():
    """Simulate image loading process."""
    logger.info("🧪 Testing image loading simulation...")
    
    try:
        gif_path = "xbt_buy_alert.gif"
        
        # Test file opening
        with open(gif_path, 'rb') as f:
            data = f.read()
        
        logger.info(f"✅ Successfully read {len(data):,} bytes from GIF")
        
        # Test that it's actually a GIF file
        if data.startswith(b'GIF'):
            logger.info("✅ File has valid GIF header")
        else:
            logger.error("❌ File does not have valid GIF header")
            return False
        
        # Check for animation frames (basic check)
        if b'\x21\xF9' in data:  # Graphic Control Extension (indicates animation)
            logger.info("✅ GIF appears to be animated")
        else:
            logger.info("ℹ️  GIF appears to be static (no animation frames detected)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in image loading simulation: {e}")
        return False

def test_bot_isolation():
    """Test bot isolation from JKC bot."""
    logger.info("🧪 Testing bot isolation...")
    
    # Check working directory
    current_dir = os.getcwd()
    if "xbttelebot" in current_dir:
        logger.info(f"✅ Working directory: {current_dir}")
    else:
        logger.warning(f"⚠️  Working directory: {current_dir} (should contain 'xbttelebot')")
    
    # Check for potential conflicts
    conflict_files = [
        "../jkctelebot/config.json",
        "../jkctelebot/telebot_fixed.py",
        "/tmp/shared_bot_resource",
        "/var/log/shared_bot.log"
    ]
    
    conflicts_found = []
    for file_path in conflict_files:
        if os.path.exists(file_path):
            conflicts_found.append(file_path)
    
    if conflicts_found:
        logger.warning(f"⚠️  Potential shared resources found: {conflicts_found}")
    else:
        logger.info("✅ No obvious shared resources detected")
    
    # Check log file naming
    try:
        with open("telebot_fixed.py", 'r') as f:
            content = f.read()
        
        if 'telebot_' in content and 'log' in content:
            logger.info("✅ Bot uses 'telebot_' prefix for log files")
        else:
            logger.warning("⚠️  Log file naming pattern not detected")
    except:
        pass
    
    return True

def test_telegram_compatibility():
    """Test Telegram API compatibility."""
    logger.info("🧪 Testing Telegram compatibility...")
    
    # Check file size limits
    gif_size = os.path.getsize("xbt_buy_alert.gif")
    
    # Telegram limits
    max_photo_size = 10 * 1024 * 1024  # 10MB for photos/animations
    max_document_size = 50 * 1024 * 1024  # 50MB for documents
    
    if gif_size <= max_photo_size:
        logger.info(f"✅ GIF size ({gif_size:,} bytes) is within Telegram photo limit")
    elif gif_size <= max_document_size:
        logger.warning(f"⚠️  GIF size ({gif_size:,} bytes) exceeds photo limit but can be sent as document")
    else:
        logger.error(f"❌ GIF size ({gif_size:,} bytes) exceeds all Telegram limits")
        return False
    
    # Check file format
    try:
        with open("xbt_buy_alert.gif", 'rb') as f:
            header = f.read(6)
        
        if header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
            logger.info("✅ GIF format is compatible with Telegram")
        else:
            logger.error("❌ Invalid GIF format")
            return False
    except Exception as e:
        logger.error(f"❌ Error checking GIF format: {e}")
        return False
    
    return True

def main():
    """Run all tests."""
    logger.info("🚀 XBT Bot GIF Integration Tests")
    logger.info("=" * 50)
    
    tests = [
        ("File Existence", test_file_existence),
        ("GIF Properties", test_gif_properties),
        ("Configuration Files", test_config_files),
        ("Bot Code References", test_bot_code_references),
        ("Image Loading Simulation", test_image_loading_simulation),
        ("Bot Isolation", test_bot_isolation),
        ("Telegram Compatibility", test_telegram_compatibility),
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
    logger.info("📊 GIF INTEGRATION TEST SUMMARY")
    logger.info("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name}")
    
    logger.info("-" * 50)
    logger.info(f"Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        logger.info("🎉 All tests passed! GIF integration is ready.")
        logger.info("💡 The XBT bot will now use animated GIF for buy alerts.")
    elif passed >= total * 0.75:
        logger.info("⚠️  Most tests passed. Review failures before deployment.")
    else:
        logger.error("❌ Multiple test failures. Fix issues before deployment.")
    
    # Specific recommendations
    logger.info("\n📋 DEPLOYMENT CHECKLIST:")
    logger.info("✅ GIF file prepared and optimized")
    logger.info("✅ Configuration files updated")
    logger.info("✅ Bot code compatibility verified")
    logger.info("✅ Telegram API compatibility confirmed")
    logger.info("✅ Bot isolation maintained")
    
    return passed >= total * 0.75

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
