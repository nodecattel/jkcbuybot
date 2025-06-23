#!/usr/bin/env python3
"""
Test script to check what symbols are available on NonKYC
"""

import requests
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_nonkyc_symbols():
    """Test different symbol variations on NonKYC."""
    symbols_to_test = [
        "XBTUSDT",
        "XBTBTC", 
        "XBT_USDT",
        "XBT_BTC",
        "BTCUSDT",  # Test if regular BTC works
        "ETHUSDT"   # Test if ETH works
    ]
    
    base_url = "https://api.nonkyc.io/api/v2/market/ticker"
    
    logger.info("🔍 Testing NonKYC API with different symbols...")
    logger.info("=" * 50)
    
    for symbol in symbols_to_test:
        try:
            params = {"market": symbol}
            response = requests.get(base_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ {symbol}: Found - Price: ${data.get('lastPriceNumber', 'N/A')}")
            elif response.status_code == 404:
                logger.info(f"❌ {symbol}: Not found (404)")
            else:
                logger.info(f"⚠️  {symbol}: Status {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ {symbol}: Error - {e}")
    
    # Also try to get the list of available markets
    logger.info("-" * 30)
    logger.info("🔍 Trying to get list of available markets...")
    
    try:
        # Try different endpoints that might list markets
        endpoints_to_try = [
            "https://api.nonkyc.io/api/v2/markets",
            "https://api.nonkyc.io/api/v2/market/list",
            "https://api.nonkyc.io/api/v2/tickers",
            "https://api.nonkyc.io/api/v2/market/tickers"
        ]
        
        for endpoint in endpoints_to_try:
            try:
                response = requests.get(endpoint, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ {endpoint}: Success")
                    if isinstance(data, list) and len(data) > 0:
                        logger.info(f"   Found {len(data)} markets")
                        # Show first few markets
                        for i, market in enumerate(data[:5]):
                            if isinstance(market, dict):
                                market_name = market.get('market', market.get('symbol', market.get('name', str(market))))
                                logger.info(f"   - {market_name}")
                            else:
                                logger.info(f"   - {market}")
                    elif isinstance(data, dict):
                        logger.info(f"   Response keys: {list(data.keys())}")
                    break
                else:
                    logger.info(f"❌ {endpoint}: Status {response.status_code}")
            except Exception as e:
                logger.info(f"❌ {endpoint}: Error - {e}")
                
    except Exception as e:
        logger.error(f"Error getting market list: {e}")

if __name__ == "__main__":
    test_nonkyc_symbols()
