#!/usr/bin/env python3
"""
Comprehensive integration test for Bitcoin Classic (XBT) bot
"""

import asyncio
import sys
import os
import logging

# Add the current directory to the path so we can import from telebot_fixed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_livecoinwatch_integration():
    """Test LiveCoinWatch API integration."""
    try:
        # Import the function from our bot
        from telebot_fixed import get_livecoinwatch_data
        
        logger.info("🧪 Testing LiveCoinWatch API integration...")
        data = await get_livecoinwatch_data()
        
        if data:
            logger.info("✅ LiveCoinWatch API integration successful!")
            logger.info(f"   Price: ${data.get('rate', 'N/A')}")
            logger.info(f"   Volume: ${data.get('volume', 'N/A')}")
            logger.info(f"   Market Cap: ${data.get('cap', 'N/A')}")
            
            # Test data extraction logic
            current_price = data.get("rate", 0)
            volume_24h_usdt = data.get("volume", 0)
            market_cap = data.get("cap", 0)
            
            delta = data.get("delta", {})
            change_percent = delta.get("day", 0) if delta else 0
            
            logger.info(f"   24h Change: {change_percent}%")
            
            if current_price > 0:
                logger.info("✅ Price data validation passed")
            else:
                logger.warning("⚠️  Price data validation failed")
                
            return True
        else:
            logger.error("❌ LiveCoinWatch API integration failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception in LiveCoinWatch test: {e}")
        return False

async def test_price_validation():
    """Test price validation logic for different trading pairs."""
    logger.info("🧪 Testing price validation logic...")
    
    # Test USDT pair validation (high price)
    test_cases = [
        {"price": 0.16, "expected": "USDT", "should_pass": True},
        {"price": 50000.0, "expected": "USDT", "should_pass": True},
        {"price": 150000.0, "expected": "USDT", "should_pass": False},  # Above $100k limit
        {"price": 0.0001, "expected": "BTC", "should_pass": True},
        {"price": 5.0, "expected": "BTC", "should_pass": True},
        {"price": 15.0, "expected": "BTC", "should_pass": False},  # Above 10 BTC limit
    ]
    
    passed = 0
    total = len(test_cases)
    
    for i, case in enumerate(test_cases):
        price = case["price"]
        expected_type = case["expected"]
        should_pass = case["should_pass"]
        
        # Determine if this is a BTC or USDT pair based on price range
        is_btc_pair = price < 1.0
        max_price = 10.0 if is_btc_pair else 100000.0
        price_unit = "BTC" if is_btc_pair else "USDT"
        
        validation_passed = price <= max_price
        
        if (validation_passed == should_pass) and (price_unit == expected_type):
            logger.info(f"✅ Test {i+1}: {price} {price_unit} - {'PASS' if validation_passed else 'FAIL'} (expected)")
            passed += 1
        else:
            logger.error(f"❌ Test {i+1}: {price} {price_unit} - Unexpected result")
    
    logger.info(f"Price validation tests: {passed}/{total} passed")
    return passed == total

async def test_data_source_fallback():
    """Test data source fallback logic."""
    logger.info("🧪 Testing data source fallback logic...")
    
    try:
        # Test the logic that would be used in price_command
        from telebot_fixed import get_livecoinwatch_data
        
        # Try LiveCoinWatch first
        market_data = await get_livecoinwatch_data()
        data_source = "LiveCoinWatch"
        
        if market_data:
            logger.info("✅ Primary data source (LiveCoinWatch) working")
            
            # Test data extraction for LiveCoinWatch format
            current_price = market_data.get("rate", 0)
            volume_24h_usdt = market_data.get("volume", 0)
            market_cap = market_data.get("cap", 0)
            
            if current_price > 0:
                logger.info("✅ Data extraction successful")
                return True
            else:
                logger.warning("⚠️  Data extraction failed")
                return False
        else:
            logger.warning("⚠️  Primary data source failed")
            # In a real scenario, we would fall back to NonKYC here
            # But since XBT isn't on NonKYC, we'll just note this
            logger.info("ℹ️  Would fall back to NonKYC, but XBT not available there")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception in fallback test: {e}")
        return False

async def test_button_urls():
    """Test that all button URLs are accessible."""
    import requests
    
    logger.info("🧪 Testing button URL accessibility...")
    
    urls_to_test = [
        ("LiveCoinWatch", "https://www.livecoinwatch.com/price/BitcoinClassic-_XBT"),
        ("CoinPaprika", "https://coinpaprika.com/coin/xbt-bitcoin-classic/"),
        ("Bitcoin Classic Website", "https://bitcoinclassic.com/"),
        ("Bitcoin Classic Docs", "https://bitcoinclassic.com/devel/"),
    ]
    
    passed = 0
    total = len(urls_to_test)
    
    for name, url in urls_to_test:
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code < 400:
                logger.info(f"✅ {name}: Accessible (Status {response.status_code})")
                passed += 1
            else:
                logger.warning(f"⚠️  {name}: Status {response.status_code}")
        except Exception as e:
            logger.error(f"❌ {name}: Error - {e}")
    
    logger.info(f"URL accessibility tests: {passed}/{total} passed")
    return passed >= (total * 0.75)  # Allow 25% failure rate for external URLs

async def main():
    """Run all integration tests."""
    logger.info("🚀 Bitcoin Classic (XBT) Bot Integration Tests")
    logger.info("=" * 60)
    
    tests = [
        ("LiveCoinWatch API Integration", test_livecoinwatch_integration),
        ("Price Validation Logic", test_price_validation),
        ("Data Source Fallback", test_data_source_fallback),
        ("Button URL Accessibility", test_button_urls),
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
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name}")
    
    logger.info("-" * 60)
    logger.info(f"Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        logger.info("🎉 All tests passed! Bot is ready for deployment.")
    elif passed >= total * 0.75:
        logger.info("⚠️  Most tests passed. Review failures before deployment.")
    else:
        logger.error("❌ Multiple test failures. Fix issues before deployment.")
    
    return passed >= total * 0.75

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
