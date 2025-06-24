"""
API Clients Module for XBT Trading Bot

This module handles all external API integrations including LiveCoinWatch,
NonKYC Exchange, and other market data providers. It provides a clean interface
for fetching market data with proper error handling and fallback mechanisms.
"""

import logging
import time
import requests
import asyncio
from typing import Optional, Dict, Any, Tuple

# Set up module logger
logger = logging.getLogger(__name__)

# API configuration
LIVECOINWATCH_API_KEY = "4646e0ac-da16-4526-b196-c0cd70d84501"
LIVECOINWATCH_BASE_URL = "https://api.livecoinwatch.com"

# Exchange availability tracking
EXCHANGE_AVAILABILITY = {
    "nonkyc": False,
    "coinex": False,
    "ascendex": False
}

LAST_AVAILABILITY_CHECK = 0
AVAILABILITY_CHECK_INTERVAL = 300  # 5 minutes

async def get_livecoinwatch_data() -> Optional[Dict[str, Any]]:
    """
    Get Bitcoin Classic data from LiveCoinWatch API with comprehensive error handling.
    
    Returns:
        Optional[Dict]: Market data from LiveCoinWatch or None if failed
    """
    try:
        url = f"{LIVECOINWATCH_BASE_URL}/coins/single"
        headers = {
            "content-type": "application/json",
            "x-api-key": LIVECOINWATCH_API_KEY
        }
        payload = {"currency": "USD", "code": "_XBT", "meta": True}

        logger.debug("Making request to LiveCoinWatch API for XBT data")
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        # Log API usage for rate limiting awareness
        logger.debug(f"LiveCoinWatch API response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            logger.debug("Successfully retrieved LiveCoinWatch data")
            
            # Validate essential fields
            if 'rate' in data and 'volume' in data:
                return data
            else:
                logger.warning("LiveCoinWatch response missing essential fields")
                return None
        elif response.status_code == 429:
            logger.warning("LiveCoinWatch API rate limit exceeded")
            return None
        elif response.status_code == 401:
            logger.error("LiveCoinWatch API authentication failed - check API key")
            return None
        else:
            logger.warning(f"LiveCoinWatch API returned status {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        logger.warning("LiveCoinWatch API request timed out after 10 seconds")
        return None
    except requests.exceptions.ConnectionError:
        logger.warning("Failed to connect to LiveCoinWatch API")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"LiveCoinWatch API request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting LiveCoinWatch data: {e}")
        return None

async def get_nonkyc_ticker(pair: str = "XBT_USDT") -> Optional[Dict[str, Any]]:
    """
    Get ticker data from NonKYC Exchange API for specified trading pair.

    Args:
        pair: Trading pair (e.g., "XBT_USDT", "BTC_USDT")

    Returns:
        Optional[Dict]: Ticker data from NonKYC or None if failed
    """
    try:
        url = f"https://api.nonkyc.io/api/v2/market/ticker/{pair}"

        logger.debug(f"Making request to NonKYC API for {pair} ticker")
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            logger.debug(f"Successfully retrieved NonKYC {pair} ticker data")
            return data
        else:
            logger.warning(f"NonKYC API returned status {response.status_code} for {pair}")
            return None

    except requests.exceptions.Timeout:
        logger.warning(f"NonKYC API request timed out after 10 seconds for {pair}")
        return None
    except requests.exceptions.ConnectionError:
        logger.warning(f"Failed to connect to NonKYC API for {pair}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"NonKYC API request failed for {pair}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting NonKYC {pair} data: {e}")
        return None

async def get_btc_usdt_rate() -> Optional[float]:
    """
    Get current BTC/USDT rate from NonKYC Exchange for XBT/BTC price conversion.

    Returns:
        Optional[float]: BTC/USDT rate or None if failed
    """
    try:
        btc_ticker = await get_nonkyc_ticker("BTC_USDT")

        if btc_ticker and "lastPriceNumber" in btc_ticker:
            btc_rate = float(btc_ticker["lastPriceNumber"])
            logger.debug(f"Retrieved BTC/USDT rate: ${btc_rate:.2f}")
            return btc_rate
        else:
            logger.warning("Failed to get BTC/USDT rate from NonKYC")
            return None

    except Exception as e:
        logger.error(f"Error getting BTC/USDT rate: {e}")
        return None

async def convert_btc_to_usdt(btc_price: float, btc_rate: Optional[float] = None) -> Tuple[float, float]:
    """
    Convert XBT/BTC price to USDT equivalent.

    Args:
        btc_price: Price in BTC
        btc_rate: BTC/USDT rate (fetched if not provided)

    Returns:
        Tuple[float, float]: (usdt_equivalent_price, btc_usdt_rate_used)
    """
    try:
        if btc_rate is None:
            btc_rate = await get_btc_usdt_rate()

        if btc_rate is None:
            logger.error("Cannot convert BTC to USDT: BTC rate unavailable")
            return 0.0, 0.0

        usdt_equivalent = btc_price * btc_rate
        logger.debug(f"Converted {btc_price:.8f} BTC to ${usdt_equivalent:.6f} USDT (rate: ${btc_rate:.2f})")

        return usdt_equivalent, btc_rate

    except Exception as e:
        logger.error(f"Error converting BTC to USDT: {e}")
        return 0.0, 0.0

async def get_nonkyc_trades() -> Optional[Dict[str, Any]]:
    """
    Get recent trades from NonKYC Exchange API.
    
    Returns:
        Optional[Dict]: Recent trades data from NonKYC or None if failed
    """
    try:
        url = "https://api.nonkyc.io/api/v2/market/trades/XBT_USDT"
        
        logger.debug("Making request to NonKYC API for XBT/USDT trades")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            logger.debug("Successfully retrieved NonKYC trades data")
            return data
        else:
            logger.warning(f"NonKYC trades API returned status {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting NonKYC trades: {e}")
        return None

async def get_coinex_trades() -> Optional[Dict[str, Any]]:
    """
    Get recent trades from CoinEx API.
    
    Returns:
        Optional[Dict]: Recent trades data from CoinEx or None if failed
    """
    try:
        url = "https://api.coinex.com/v1/market/deals?market=XBTUSDT&limit=100"
        
        logger.debug("Making request to CoinEx API for XBT/USDT trades")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:  # CoinEx success code
                logger.debug("Successfully retrieved CoinEx trades data")
                return data.get('data', [])
            else:
                logger.warning(f"CoinEx API returned error code: {data.get('code')}")
                return None
        else:
            logger.warning(f"CoinEx API returned status {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting CoinEx trades: {e}")
        return None

async def check_exchange_availability() -> Dict[str, bool]:
    """
    Check if XBT is available on various exchanges and update availability flags.
    
    Returns:
        Dict[str, bool]: Exchange availability status
    """
    global EXCHANGE_AVAILABILITY, LAST_AVAILABILITY_CHECK

    current_time = time.time()
    if current_time - LAST_AVAILABILITY_CHECK < AVAILABILITY_CHECK_INTERVAL:
        return EXCHANGE_AVAILABILITY

    logger.debug("Checking exchange availability for XBT")

    # Check NonKYC availability
    try:
        nonkyc_data = await get_nonkyc_ticker()
        EXCHANGE_AVAILABILITY["nonkyc"] = nonkyc_data is not None
    except Exception as e:
        logger.debug(f"NonKYC availability check failed: {e}")
        EXCHANGE_AVAILABILITY["nonkyc"] = False

    # Check CoinEx availability
    try:
        coinex_url = "https://api.coinex.com/v1/market/ticker?market=XBTUSDT"
        response = requests.get(coinex_url, timeout=5)
        EXCHANGE_AVAILABILITY["coinex"] = response.status_code == 200
    except Exception as e:
        logger.debug(f"CoinEx availability check failed: {e}")
        EXCHANGE_AVAILABILITY["coinex"] = False

    # Check AscendEX availability
    try:
        ascendex_url = "https://ascendex.com/api/pro/v1/ticker?symbol=XBT/USDT"
        response = requests.get(ascendex_url, timeout=5)
        EXCHANGE_AVAILABILITY["ascendex"] = response.status_code == 200
    except Exception as e:
        logger.debug(f"AscendEX availability check failed: {e}")
        EXCHANGE_AVAILABILITY["ascendex"] = False

    LAST_AVAILABILITY_CHECK = current_time
    
    available_exchanges = [ex for ex, available in EXCHANGE_AVAILABILITY.items() if available]
    logger.debug(f"Exchange availability check complete. Available: {available_exchanges}")
    
    return EXCHANGE_AVAILABILITY

async def calculate_volume_periods(trades: list) -> Dict[str, float]:
    """
    Calculate volume for different time periods from trades data.
    
    Args:
        trades: List of trade data
        
    Returns:
        Dict[str, float]: Volume for different periods (15m, 1h, 4h, 24h)
    """
    if not trades:
        return {"15m": 0, "1h": 0, "4h": 0, "24h": 0}

    current_time = time.time()
    periods = {
        "15m": 15 * 60,
        "1h": 60 * 60,
        "4h": 4 * 60 * 60,
        "24h": 24 * 60 * 60
    }
    
    volumes = {}
    
    for period_name, period_seconds in periods.items():
        cutoff_time = current_time - period_seconds
        period_volume = 0
        
        for trade in trades:
            # Handle different timestamp formats
            trade_time = trade.get('timestamp', trade.get('date_ms', 0))
            if isinstance(trade_time, str):
                try:
                    trade_time = float(trade_time)
                except ValueError:
                    continue
            
            # Convert milliseconds to seconds if needed
            if trade_time > 10**10:
                trade_time = trade_time / 1000
            
            if trade_time >= cutoff_time:
                volume = trade.get('amount', trade.get('volume', 0))
                period_volume += float(volume) if volume else 0
        
        volumes[period_name] = round(period_volume, 2)
    
    return volumes

async def calculate_combined_volume_periods() -> Dict[str, Any]:
    """
    Calculate combined volume from both NonKYC and CoinEx exchanges.
    
    Returns:
        Dict containing combined and individual exchange volumes
    """
    try:
        # Get trades from both exchanges
        nonkyc_trades = await get_nonkyc_trades()
        coinex_trades = await get_coinex_trades()

        # Calculate volumes for each exchange
        nonkyc_volumes = await calculate_volume_periods(nonkyc_trades or [])
        coinex_volumes = await calculate_volume_periods(coinex_trades or [])

        # Combine volumes
        combined_volumes = {}
        for period in ["15m", "1h", "4h", "24h"]:
            combined_volumes[period] = round(
                nonkyc_volumes.get(period, 0) + coinex_volumes.get(period, 0), 2
            )

        # Also return individual exchange volumes for detailed display
        return {
            "combined": combined_volumes,
            "nonkyc": nonkyc_volumes,
            "coinex": coinex_volumes
        }

    except Exception as e:
        logger.error(f"Error calculating combined volume periods: {e}")
        return {
            "combined": {"15m": 0, "1h": 0, "4h": 0, "24h": 0},
            "nonkyc": {"15m": 0, "1h": 0, "4h": 0, "24h": 0},
            "coinex": {"15m": 0, "1h": 0, "4h": 0, "24h": 0}
        }

def get_exchange_availability() -> Dict[str, bool]:
    """
    Get current exchange availability status.
    
    Returns:
        Dict[str, bool]: Current exchange availability
    """
    return EXCHANGE_AVAILABILITY.copy()
