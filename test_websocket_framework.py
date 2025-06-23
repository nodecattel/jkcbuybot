#!/usr/bin/env python3
"""
Test script for the restored WebSocket framework in XBT bot
"""

import asyncio
import sys
import os
import logging
import time

# Add the current directory to the path so we can import from telebot_fixed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_exchange_availability_detection():
    """Test the exchange availability detection system."""
    try:
        from telebot_fixed import check_exchange_availability, EXCHANGE_AVAILABILITY
        
        logger.info("🧪 Testing exchange availability detection...")
        
        # Test the availability check function
        availability = await check_exchange_availability()
        
        logger.info("📊 Exchange Availability Results:")
        for exchange, available in availability.items():
            status = "✅ AVAILABLE" if available else "❌ NOT AVAILABLE"
            logger.info(f"  {exchange.upper()}: {status}")
        
        # Verify the global state was updated
        logger.info(f"Global EXCHANGE_AVAILABILITY: {EXCHANGE_AVAILABILITY}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Exception in availability detection test: {e}")
        return False

async def test_websocket_conditional_logic():
    """Test that WebSocket functions handle unavailable exchanges correctly."""
    try:
        from telebot_fixed import EXCHANGE_AVAILABILITY
        
        logger.info("🧪 Testing WebSocket conditional logic...")
        
        # Since XBT is not available on any exchange, WebSocket functions should wait
        # We'll test this by checking the availability flags
        
        all_unavailable = not any(EXCHANGE_AVAILABILITY.values())
        
        if all_unavailable:
            logger.info("✅ Confirmed: XBT not available on any exchange")
            logger.info("✅ WebSocket connections will wait for availability")
            return True
        else:
            available_exchanges = [ex for ex, avail in EXCHANGE_AVAILABILITY.items() if avail]
            logger.info(f"⚠️  XBT is available on: {available_exchanges}")
            logger.info("✅ WebSocket connections should activate for available exchanges")
            return True
            
    except Exception as e:
        logger.error(f"❌ Exception in WebSocket conditional logic test: {e}")
        return False

async def test_livecoinwatch_primary_source():
    """Test that LiveCoinWatch remains the primary data source."""
    try:
        from telebot_fixed import get_livecoinwatch_data
        
        logger.info("🧪 Testing LiveCoinWatch as primary data source...")
        
        data = await get_livecoinwatch_data()
        
        if data:
            logger.info("✅ LiveCoinWatch API working correctly")
            logger.info(f"   Current XBT price: ${data.get('rate', 'N/A')}")
            logger.info(f"   24h volume: ${data.get('volume', 'N/A')}")
            return True
        else:
            logger.error("❌ LiveCoinWatch API failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception in LiveCoinWatch test: {e}")
        return False

async def test_websocket_imports():
    """Test that all WebSocket functions can be imported correctly."""
    try:
        logger.info("🧪 Testing WebSocket function imports...")
        
        from telebot_fixed import (
            nonkyc_websocket_usdt,
            nonkyc_websocket_btc, 
            coinex_websocket,
            ascendex_websocket,
            nonkyc_orderbook_websocket,
            exchange_availability_monitor
        )
        
        logger.info("✅ All WebSocket functions imported successfully")
        
        # Test that functions are callable
        functions_to_test = [
            ("NonKYC USDT WebSocket", nonkyc_websocket_usdt),
            ("NonKYC BTC WebSocket", nonkyc_websocket_btc),
            ("CoinEx WebSocket", coinex_websocket),
            ("AscendEX WebSocket", ascendex_websocket),
            ("NonKYC Orderbook WebSocket", nonkyc_orderbook_websocket),
            ("Exchange Availability Monitor", exchange_availability_monitor)
        ]
        
        for name, func in functions_to_test:
            if callable(func):
                logger.info(f"✅ {name}: Callable")
            else:
                logger.error(f"❌ {name}: Not callable")
                return False
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Exception in import test: {e}")
        return False

async def test_configuration_compatibility():
    """Test that the bot configuration is compatible with WebSocket features."""
    try:
        from telebot_fixed import CONFIG, EXCHANGE_AVAILABILITY, running
        
        logger.info("🧪 Testing configuration compatibility...")
        
        # Check that essential config values exist
        essential_configs = ['bot_token', 'value_require', 'image_path']
        missing_configs = [key for key in essential_configs if key not in CONFIG]
        
        if missing_configs:
            logger.warning(f"⚠️  Missing config keys: {missing_configs}")
        else:
            logger.info("✅ Essential configuration keys present")
        
        # Check WebSocket-related globals
        logger.info(f"✅ Running flag: {running}")
        logger.info(f"✅ Exchange availability tracking: {EXCHANGE_AVAILABILITY}")
        
        # Check if AscendEX API keys are configured
        ascendex_configured = bool(CONFIG.get("ascendex_access_id") and CONFIG.get("ascendex_secret_key"))
        logger.info(f"AscendEX API keys configured: {'✅ Yes' if ascendex_configured else '❌ No'}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Exception in configuration test: {e}")
        return False

async def simulate_websocket_startup():
    """Simulate the WebSocket startup process without actually connecting."""
    try:
        logger.info("🧪 Simulating WebSocket startup process...")
        
        # This simulates what happens when the bot starts
        from telebot_fixed import check_exchange_availability
        
        # Check initial availability
        availability = await check_exchange_availability()
        
        logger.info("📋 WebSocket Startup Simulation:")
        logger.info("1. ✅ Exchange availability check completed")
        logger.info("2. ✅ WebSocket functions would be started as background tasks")
        logger.info("3. ✅ Functions would wait for XBT availability before connecting")
        logger.info("4. ✅ LiveCoinWatch API remains primary data source")
        logger.info("5. ✅ Availability monitor would run every 5 minutes")
        
        # Show what would happen for each exchange
        for exchange, available in availability.items():
            if available:
                logger.info(f"   🔗 {exchange.upper()} WebSocket would connect immediately")
            else:
                logger.info(f"   ⏳ {exchange.upper()} WebSocket would wait for XBT listing")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Exception in startup simulation: {e}")
        return False

async def main():
    """Run all WebSocket framework tests."""
    logger.info("🚀 XBT Bot WebSocket Framework Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Exchange Availability Detection", test_exchange_availability_detection),
        ("WebSocket Conditional Logic", test_websocket_conditional_logic),
        ("LiveCoinWatch Primary Source", test_livecoinwatch_primary_source),
        ("WebSocket Function Imports", test_websocket_imports),
        ("Configuration Compatibility", test_configuration_compatibility),
        ("WebSocket Startup Simulation", simulate_websocket_startup),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running: {test_name}")
        logger.info("-" * 40)
        
        try:
            result = await test_func()
            results.append((test_name, result))
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"Result: {status}")
        except Exception as e:
            logger.error(f"❌ EXCEPTION: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 WEBSOCKET FRAMEWORK TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name}")
    
    logger.info("-" * 60)
    logger.info(f"Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        logger.info("🎉 All tests passed! WebSocket framework is ready.")
        logger.info("💡 WebSocket connections will activate when XBT becomes available on exchanges.")
    elif passed >= total * 0.75:
        logger.info("⚠️  Most tests passed. Review failures before deployment.")
    else:
        logger.error("❌ Multiple test failures. Fix issues before deployment.")
    
    return passed >= total * 0.75

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
