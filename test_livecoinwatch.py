#!/usr/bin/env python3
"""
Test script for LiveCoinWatch API integration
"""

import asyncio
import requests
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_livecoinwatch_api():
    """Test the LiveCoinWatch API integration."""
    try:
        url = "https://api.livecoinwatch.com/coins/single"
        headers = {
            "content-type": "application/json",
            "x-api-key": "4646e0ac-da16-4526-b196-c0cd70d84501"
        }
        payload = {"currency": "USD", "code": "_XBT", "meta": True}
        
        logger.info("Testing LiveCoinWatch API for XBT...")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if "error" in data:
                logger.error(f"API Error: {data['error']}")
                return False
            
            logger.info("✅ LiveCoinWatch API Response:")
            logger.info(f"  Rate: ${data.get('rate', 'N/A')}")
            logger.info(f"  Volume: ${data.get('volume', 'N/A')}")
            logger.info(f"  Market Cap: ${data.get('cap', 'N/A')}")
            logger.info(f"  Total Supply: {data.get('totalSupply', 'N/A')}")
            
            delta = data.get('delta', {})
            if delta:
                logger.info(f"  24h Change: {delta.get('day', 'N/A')}%")
            
            return True
        else:
            logger.error(f"❌ API request failed with status {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception during API test: {e}")
        return False

async def test_nonkyc_fallback():
    """Test NonKYC API as fallback."""
    try:
        url = "https://api.nonkyc.io/api/v2/market/ticker"
        params = {"market": "XBTUSDT"}
        
        logger.info("Testing NonKYC API fallback...")
        response = requests.get(url, params=params, timeout=10)
        
        logger.info(f"NonKYC Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info("✅ NonKYC API Response:")
            logger.info(f"  Last Price: ${data.get('lastPriceNumber', 'N/A')}")
            logger.info(f"  Volume: {data.get('volumeNumber', 'N/A')} XBT")
            logger.info(f"  Market Cap: ${data.get('marketcapNumber', 'N/A')}")
            return True
        else:
            logger.error(f"❌ NonKYC API failed with status {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception during NonKYC test: {e}")
        return False

async def main():
    """Run all tests."""
    logger.info("🧪 Testing Bitcoin Classic (XBT) API Integrations")
    logger.info("=" * 50)
    
    # Test LiveCoinWatch
    lcw_success = await test_livecoinwatch_api()
    
    logger.info("-" * 30)
    
    # Test NonKYC fallback
    nonkyc_success = await test_nonkyc_fallback()
    
    logger.info("=" * 50)
    logger.info("📊 Test Results:")
    logger.info(f"  LiveCoinWatch API: {'✅ PASS' if lcw_success else '❌ FAIL'}")
    logger.info(f"  NonKYC Fallback: {'✅ PASS' if nonkyc_success else '❌ FAIL'}")
    
    if lcw_success or nonkyc_success:
        logger.info("🎉 At least one data source is working!")
    else:
        logger.error("⚠️  All data sources failed!")

if __name__ == "__main__":
    asyncio.run(main())
