"""
Utility Functions Module for XBT Trading Bot

This module contains utility functions, formatting helpers, validation logic,
and other support functions used throughout the bot application.
"""

import logging
import time
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timezone

# Set up module logger
logger = logging.getLogger(__name__)

def validate_price_calculation(price: float, quantity: float, sum_value: float, context: str = "Unknown", pair_type: str = "USDT") -> Tuple[bool, float]:
    """
    Validate that price * quantity = sum_value within acceptable tolerance.

    Args:
        price: Price per unit
        quantity: Quantity of units
        sum_value: Total value to validate
        context: Context for logging purposes
        pair_type: Trading pair type for appropriate formatting

    Returns:
        Tuple of (is_valid, corrected_value)
    """
    expected_value = price * quantity

    # Use appropriate tolerance based on trading pair
    if pair_type.upper() == "BTC":
        # For BTC pairs, use much smaller tolerance due to 8-decimal precision
        tolerance = max(0.00000001, expected_value * 0.0001)  # 0.01% tolerance or 1 satoshi minimum
    else:
        # For USDT pairs, use standard tolerance
        tolerance = max(0.01, expected_value * 0.001)  # 0.1% tolerance or 0.01 minimum

    if abs(sum_value - expected_value) > tolerance:
        price_formatted = format_price(price, pair_type)
        currency_symbol = "BTC" if pair_type.upper() == "BTC" else "USDT"

        logger.error(f"❌ PRICE CALCULATION VALIDATION FAILED in {context}:")
        logger.error(f"  💵 Price: {price_formatted} {currency_symbol}")
        logger.error(f"  📊 Quantity: {format_quantity(quantity)} XBT")
        expected_formatted = f"{expected_value:.8f}" if pair_type.upper() == "BTC" else f"{expected_value:.2f}"
        actual_formatted = f"{sum_value:.8f}" if pair_type.upper() == "BTC" else f"{sum_value:.2f}"
        diff_formatted = f"{sum_value - expected_value:.8f}" if pair_type.upper() == "BTC" else f"{sum_value - expected_value:.2f}"
        tolerance_formatted = f"{tolerance:.8f}" if pair_type.upper() == "BTC" else f"{tolerance:.2f}"

        logger.error(f"  ✅ Expected Value: {expected_formatted} {currency_symbol}")
        logger.error(f"  ❌ Actual Value: {actual_formatted} {currency_symbol}")
        logger.error(f"  📉 Difference: {diff_formatted} {currency_symbol}")
        logger.error(f"  🎯 Tolerance: {tolerance_formatted} {currency_symbol}")
        return False, expected_value
    else:
        price_formatted = format_price(price, pair_type)
        currency_symbol = "BTC" if pair_type.upper() == "BTC" else "USDT"
        value_formatted = f"{sum_value:.8f}" if pair_type.upper() == "BTC" else f"{sum_value:.2f}"
        logger.debug(f"✅ Price calculation validated in {context}: {price_formatted} * {format_quantity(quantity)} = {value_formatted} {currency_symbol}")
        return True, sum_value

def format_momentum(value: float) -> str:
    """
    Format momentum/percentage values with proper signs and formatting.
    
    Args:
        value: Percentage value to format
        
    Returns:
        Formatted string with sign and percentage
    """
    if value > 0:
        return f"+{value:.2f}%"
    elif value < 0:
        return f"{value:.2f}%"
    else:
        return "0.00%"

def get_change_emoji(change_percent: float) -> str:
    """
    Get appropriate emoji based on price change percentage.
    
    Args:
        change_percent: Percentage change value
        
    Returns:
        Emoji string representing the change magnitude
    """
    if change_percent >= 10:
        return "🚀"
    elif change_percent >= 5:
        return "📈"
    elif change_percent > 0:
        return "⬆️"
    elif change_percent >= -5:
        return "➡️"
    elif change_percent >= -10:
        return "⬇️"
    elif change_percent >= -20:
        return "📉"
    else:
        return "💀"

def format_price(price: float, pair_type: str = "USDT") -> str:
    """
    Format price with appropriate decimal places based on trading pair.

    Args:
        price: Price value to format
        pair_type: Trading pair type ("USDT" for 6 decimals, "BTC" for 8 decimals)

    Returns:
        Formatted price string
    """
    if pair_type.upper() == "BTC":
        return f"{price:.8f}"  # 8 decimal places for BTC prices
    else:
        return f"{price:.6f}"  # 6 decimal places for USDT prices

def format_btc_price(price: float) -> str:
    """
    Format BTC price with 8 decimal places.

    Args:
        price: BTC price value to format

    Returns:
        Formatted BTC price string
    """
    return f"{price:.8f}"

def format_usdt_price(price: float) -> str:
    """
    Format USDT price with 6 decimal places.

    Args:
        price: USDT price value to format

    Returns:
        Formatted USDT price string
    """
    return f"{price:.6f}"

def format_quantity(quantity: float, decimals: int = 4) -> str:
    """
    Format quantity with specified decimal places.

    Args:
        quantity: Quantity value to format
        decimals: Number of decimal places

    Returns:
        Formatted quantity string
    """
    return f"{quantity:.{decimals}f}"

def format_currency(value: float, currency: str = "USDT") -> str:
    """
    Format currency value with appropriate formatting.
    
    Args:
        value: Currency value to format
        currency: Currency symbol
        
    Returns:
        Formatted currency string
    """
    if value >= 1000000:
        return f"${value/1000000:.2f}M {currency}"
    elif value >= 1000:
        return f"${value/1000:.2f}K {currency}"
    else:
        return f"${value:.2f} {currency}"

def get_timestamp_ms() -> int:
    """
    Get current timestamp in milliseconds.
    
    Returns:
        Current timestamp in milliseconds
    """
    return int(time.time() * 1000)

def format_timestamp(timestamp: int, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format timestamp to human-readable string.
    
    Args:
        timestamp: Timestamp in seconds or milliseconds
        format_str: Format string for datetime formatting
        
    Returns:
        Formatted timestamp string
    """
    # Handle both seconds and milliseconds timestamps
    if timestamp > 10**10:  # Milliseconds
        timestamp = timestamp / 1000
    
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(format_str)

def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Calculate percentage change between two values.
    
    Args:
        old_value: Original value
        new_value: New value
        
    Returns:
        Percentage change
    """
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100

def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float with default fallback.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert value to int with default fallback.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value or default
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate string to maximum length with optional suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def validate_buy_sell_aggregation(trades: list, context: str = "Unknown") -> Tuple[bool, float, float]:
    """
    Validate buy/sell trade aggregation and calculate volumes with proper trading pair handling.

    Args:
        trades: List of trade dictionaries
        context: Context for logging

    Returns:
        Tuple of (validation_passed, buy_volume, sell_volume)
    """
    if not trades:
        return True, 0.0, 0.0

    # Determine trading pair from first trade for consistent formatting
    pair_type = trades[0].get('pair_type', 'XBT/USDT')
    is_btc_pair = pair_type == "XBT/BTC"
    currency_symbol = "BTC" if is_btc_pair else "USDT"

    # Separate buy and sell trades
    buy_trades = [t for t in trades if t.get('side', '').lower() in ['buy', 'b']]
    sell_trades = [t for t in trades if t.get('side', '').lower() in ['sell', 's']]

    # Calculate volumes using original currency values
    buy_volume = sum(t.get('sum_value', 0) for t in buy_trades)
    sell_volume = sum(t.get('sum_value', 0) for t in sell_trades)

    total_volume = buy_volume + sell_volume
    calculated_total = sum(t.get('sum_value', 0) for t in trades)

    # Use appropriate tolerance based on trading pair
    tolerance = 0.00000001 if is_btc_pair else 0.01
    validation_passed = abs(total_volume - calculated_total) < tolerance

    # Format values for logging based on trading pair
    if is_btc_pair:
        buy_formatted = f"{buy_volume:.8f}"
        sell_formatted = f"{sell_volume:.8f}"
        total_formatted = f"{total_volume:.8f}"
        calculated_formatted = f"{calculated_total:.8f}"
        diff_formatted = f"{total_volume - calculated_total:.8f}"
    else:
        buy_formatted = f"{buy_volume:.2f}"
        sell_formatted = f"{sell_volume:.2f}"
        total_formatted = f"{total_volume:.2f}"
        calculated_formatted = f"{calculated_total:.2f}"
        diff_formatted = f"{total_volume - calculated_total:.2f}"

    if not validation_passed:
        logger.error(f"❌ BUY/SELL AGGREGATION VALIDATION FAILED in {context} ({pair_type}):")
        logger.error(f"  🟢 Buy Volume: {buy_formatted} {currency_symbol} ({len(buy_trades)} trades)")
        logger.error(f"  🔴 Sell Volume: {sell_formatted} {currency_symbol} ({len(sell_trades)} trades)")
        logger.error(f"  📊 Total Calculated: {total_formatted} {currency_symbol}")
        logger.error(f"  ✅ Expected Total: {calculated_formatted} {currency_symbol}")
        logger.error(f"  📉 Difference: {diff_formatted} {currency_symbol}")
    else:
        logger.debug(f"✅ Buy/sell aggregation validated in {context} ({pair_type}): Buy {buy_formatted} + Sell {sell_formatted} = {total_formatted} {currency_symbol}")

    if validation_passed:
        logger.info(f"✅ Buy volume aggregation validated: {buy_formatted} {currency_symbol} from {len(buy_trades)} BUY trades in {pair_type}")

    return validation_passed, buy_volume, sell_volume

def get_public_ip() -> str:
    """
    Get public IP address of the server.
    
    Returns:
        Public IP address string
    """
    try:
        import requests
        response = requests.get('https://api.ipify.org', timeout=5)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error getting public IP: {e}")
        return "Unable to determine public IP"

def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        level: Logging level
        log_file: Optional log file path
    """
    # Basic logging setup
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=level
    )
    
    # Set httpx logging to WARNING to reduce noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(file_handler)

# Constants for conversation handlers (moved from main file)
INPUT_NUMBER = 1
INPUT_IMAGE = 2
CONFIG_MENU = 3
DYNAMIC_CONFIG = 4
INPUT_API_KEYS = 5
INPUT_IMAGE_SETIMAGE = 6  # Separate state for setimage command
