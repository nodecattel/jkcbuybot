#!/usr/bin/env python3
"""
NonKYC Integration Template for Bitcoin Classic (XBT) Bot
Ready-to-implement functions for when XBT becomes available on NonKYC
"""

import requests
import asyncio
import logging
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

# NonKYC API Configuration
NONKYC_BASE_URL = "https://api.nonkyc.io/api/v2"
XBT_USDT_MARKET = "XBT_USDT"
XBT_BTC_MARKET = "XBT_BTC"

class NonKYCIntegration:
    """NonKYC API integration for XBT market data."""
    
    def __init__(self):
        self.xbt_available = False
        self.available_markets = []
        self.last_availability_check = 0
    
    async def check_xbt_availability(self) -> Tuple[bool, List[Dict]]:
        """Check if XBT markets are available on NonKYC."""
        try:
            url = f"{NONKYC_BASE_URL}/markets"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                markets = response.json()
                xbt_markets = [m for m in markets if m.get('base') == 'XBT']
                
                if xbt_markets:
                    logger.info(f"XBT now available on NonKYC! Found {len(xbt_markets)} markets")
                    for market in xbt_markets:
                        logger.info(f"  - {market.get('base')}_{market.get('quote')}")
                
                self.xbt_available = len(xbt_markets) > 0
                self.available_markets = xbt_markets
                return self.xbt_available, xbt_markets
            else:
                logger.warning(f"NonKYC markets endpoint returned {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Error checking XBT availability: {e}")
        
        return False, []
    
    async def get_ticker_data(self, market: str = XBT_USDT_MARKET) -> Optional[Dict]:
        """Get ticker data for XBT market."""
        try:
            url = f"{NONKYC_BASE_URL}/market/ticker"
            params = {"market": market}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 404:
                logger.debug(f"XBT market {market} not yet available on NonKYC")
                return None
            elif response.status_code == 200:
                data = response.json()
                logger.debug(f"NonKYC ticker data for {market}: ${data.get('lastPriceNumber', 'N/A')}")
                return data
            else:
                logger.warning(f"NonKYC ticker API returned {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"Error getting NonKYC ticker for {market}: {e}")
            return None
    
    async def get_recent_trades(self, market: str = XBT_USDT_MARKET, limit: int = 100) -> Optional[List[Dict]]:
        """Get recent trades for XBT market."""
        try:
            url = f"{NONKYC_BASE_URL}/market/trades"
            params = {"market": market, "limit": limit}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                trades = response.json()
                logger.debug(f"Retrieved {len(trades)} recent trades for {market}")
                return trades
            elif response.status_code == 404:
                logger.debug(f"Trades for {market} not available yet")
                return None
            else:
                logger.warning(f"NonKYC trades API returned {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"Error getting NonKYC trades for {market}: {e}")
            return None
    
    async def get_orderbook(self, market: str = XBT_USDT_MARKET, limit: int = 50) -> Optional[Dict]:
        """Get orderbook data for XBT market."""
        try:
            url = f"{NONKYC_BASE_URL}/market/orderbook"
            params = {"market": market, "limit": limit}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                orderbook = response.json()
                asks_count = len(orderbook.get('asks', []))
                bids_count = len(orderbook.get('bids', []))
                logger.debug(f"Retrieved orderbook for {market}: {asks_count} asks, {bids_count} bids")
                return orderbook
            elif response.status_code == 404:
                logger.debug(f"Orderbook for {market} not available yet")
                return None
            else:
                logger.warning(f"NonKYC orderbook API returned {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"Error getting NonKYC orderbook for {market}: {e}")
            return None
    
    def extract_price_data(self, ticker_data: Dict) -> Dict:
        """Extract price data in standardized format."""
        if not ticker_data:
            return {}
        
        return {
            'current_price': ticker_data.get('lastPriceNumber', 0),
            'change_percent': ticker_data.get('changePercentNumber', 0),
            'volume_24h_xbt': ticker_data.get('volumeNumber', 0),
            'volume_24h_usd': ticker_data.get('volumeUsdNumber', 0),
            'market_cap': ticker_data.get('marketcapNumber', 0),
            'best_bid': ticker_data.get('bestBidNumber', 0),
            'best_ask': ticker_data.get('bestAskNumber', 0),
            'spread_percent': ticker_data.get('spreadPercentNumber', 0),
            'high_24h': ticker_data.get('highPriceNumber', 0),
            'low_24h': ticker_data.get('lowPriceNumber', 0),
            'yesterday_price': ticker_data.get('yesterdayPriceNumber', 0),
        }
    
    async def get_comprehensive_market_data(self) -> Tuple[Optional[Dict], str]:
        """Get comprehensive market data with fallback logic."""
        # Check availability first
        if not self.xbt_available:
            available, markets = await self.check_xbt_availability()
            if not available:
                return None, "XBT not available on NonKYC"
        
        # Try to get USDT pair data
        usdt_data = await self.get_ticker_data(XBT_USDT_MARKET)
        if usdt_data:
            extracted_data = self.extract_price_data(usdt_data)
            extracted_data['trading_pair'] = 'XBT/USDT'
            extracted_data['source'] = 'NonKYC Exchange'
            return extracted_data, "NonKYC Exchange"
        
        # Try BTC pair as fallback
        btc_data = await self.get_ticker_data(XBT_BTC_MARKET)
        if btc_data:
            extracted_data = self.extract_price_data(btc_data)
            extracted_data['trading_pair'] = 'XBT/BTC'
            extracted_data['source'] = 'NonKYC Exchange'
            return extracted_data, "NonKYC Exchange"
        
        return None, "NonKYC data unavailable"

# Integration functions for existing bot
async def get_nonkyc_data_with_fallback():
    """Integration function for existing bot - get NonKYC data with LiveCoinWatch fallback."""
    nonkyc = NonKYCIntegration()
    
    # Try NonKYC first
    market_data, source = await nonkyc.get_comprehensive_market_data()
    if market_data:
        return market_data, source
    
    # Fallback to LiveCoinWatch (existing function)
    try:
        from telebot_fixed import get_livecoinwatch_data
        lcw_data = await get_livecoinwatch_data()
        if lcw_data:
            # Convert LiveCoinWatch format to standardized format
            standardized_data = {
                'current_price': lcw_data.get('rate', 0),
                'volume_24h_usd': lcw_data.get('volume', 0),
                'market_cap': lcw_data.get('cap', 0),
                'total_supply': lcw_data.get('totalSupply', 0),
                'trading_pair': 'XBT/USD',
                'source': 'LiveCoinWatch'
            }
            
            # Calculate 24h change from delta
            delta = lcw_data.get('delta', {})
            standardized_data['change_percent'] = delta.get('day', 0) if delta else 0
            
            return standardized_data, "LiveCoinWatch"
    except Exception as e:
        logger.warning(f"LiveCoinWatch fallback failed: {e}")
    
    return None, "All data sources unavailable"

# Example usage and testing
async def test_nonkyc_integration():
    """Test NonKYC integration."""
    nonkyc = NonKYCIntegration()
    
    print("🧪 Testing NonKYC Integration")
    print("=" * 40)
    
    # Test availability check
    available, markets = await nonkyc.check_xbt_availability()
    print(f"XBT Available: {available}")
    if markets:
        for market in markets:
            print(f"  - {market.get('base')}_{market.get('quote')}")
    
    if available:
        # Test ticker data
        ticker = await nonkyc.get_ticker_data()
        if ticker:
            data = nonkyc.extract_price_data(ticker)
            print(f"Price: ${data['current_price']}")
            print(f"24h Change: {data['change_percent']}%")
            print(f"Volume: ${data['volume_24h_usd']:,.0f}")
        
        # Test trades
        trades = await nonkyc.get_recent_trades(limit=5)
        if trades:
            print(f"Recent trades: {len(trades)}")
    
    # Test fallback logic
    data, source = await get_nonkyc_data_with_fallback()
    print(f"Final data source: {source}")
    if data:
        print(f"Final price: ${data['current_price']}")

if __name__ == "__main__":
    asyncio.run(test_nonkyc_integration())
