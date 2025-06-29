"""
Alert System Module for XBT Trading Bot

This module handles trade processing, aggregation, threshold checking, and alert delivery.
It includes the core logic for detecting significant trades and sending notifications
with comprehensive validation and error handling.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

try:
    from telegram import Bot, InputFile
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    # Handle missing telegram dependency gracefully
    Bot = None
    InputFile = None
    TelegramError = Exception
    TELEGRAM_AVAILABLE = False

from config import get_config, get_active_chat_ids, get_value_require, update_config
from utils import validate_price_calculation, format_price, format_quantity, validate_buy_sell_aggregation, format_btc_price, format_usdt_price
from image_manager import load_random_image, is_animation
from api_clients import get_nonkyc_ticker, calculate_combined_volume_periods

# Set up module logger
logger = logging.getLogger(__name__)

# Global state for trade aggregation - separated by exchange and trading pair
PENDING_TRADES: Dict[str, Dict[str, Dict[str, List[Dict]]]] = {}  # {exchange: {pair: {buyer_id: [trades]}}}
LAST_AGGREGATION_CHECK = time.time()

# Global photo variable for alerts
PHOTO = None

def initialize_alert_system():
    """Initialize the alert system with a random image."""
    global PHOTO
    try:
        PHOTO = load_random_image()
        if PHOTO is None:
            logger.warning("No images available for alerts")
    except Exception as e:
        logger.error(f"Error loading image: {e}")
        PHOTO = None

async def update_threshold():
    """Update threshold based on volume if dynamic threshold is enabled."""
    config = get_config()
    
    if not config.get("dynamic_threshold", {}).get("enabled", False):
        return
        
    try:
        # Get market data from NonKYC
        market_data = await get_nonkyc_ticker()
        
        if market_data and "volume" in market_data:
            volume_24h = float(market_data["volumeNumber"])
            
            # Calculate new threshold based on 24h volume
            dynamic_config = config["dynamic_threshold"]
            new_threshold = dynamic_config["base_value"] + (volume_24h * dynamic_config["volume_multiplier"])
            
            # Apply min/max constraints
            new_threshold = max(dynamic_config["min_threshold"], 
                               min(dynamic_config["max_threshold"], new_threshold))
            
            # Update the threshold
            new_value_require = round(new_threshold)
            if update_config({"value_require": new_value_require}):
                logger.info(f"Updated threshold to {new_value_require} based on 24h volume of {volume_24h}")
            
    except Exception as e:
        logger.error(f"Error updating dynamic threshold: {e}")

async def process_message(price: float, quantity: float, sum_value: float, exchange: str,
                         timestamp: int, exchange_url: str, trade_side: str = "buy",
                         pair_type: str = "XBT/USDT", usdt_price: Optional[float] = None,
                         usdt_sum_value: Optional[float] = None, btc_rate: Optional[float] = None):
    """
    Process a trade message and send notification if it meets criteria.

    Args:
        price: Trade price (in original currency)
        quantity: Trade quantity
        sum_value: Total trade value (in original currency)
        exchange: Exchange name
        timestamp: Trade timestamp
        exchange_url: Exchange URL
        trade_side: Trade side (buy/sell)
        pair_type: Trading pair type ("XBT/USDT" or "XBT/BTC")
        usdt_price: USDT equivalent price (for BTC pairs)
        usdt_sum_value: USDT equivalent total value (for BTC pairs)
        btc_rate: BTC/USDT rate used for conversion (for BTC pairs)
    """
    global PHOTO, PENDING_TRADES, LAST_AGGREGATION_CHECK

    # Determine the currency for logging and threshold checking
    if pair_type == "XBT/BTC":
        # For BTC pairs, use USDT equivalent for threshold checking
        threshold_price = usdt_price if usdt_price is not None else 0.0
        threshold_sum_value = usdt_sum_value if usdt_sum_value is not None else 0.0
        currency_symbol = "BTC"
        price_display = format_btc_price(price)
        logger.info(f"Processing {trade_side.upper()} trade: {exchange} {pair_type} - {format_quantity(quantity)} XBT at {price_display} BTC (${format_usdt_price(threshold_price)} USDT equivalent)")
    else:
        # For USDT pairs, use original values
        threshold_price = price
        threshold_sum_value = sum_value
        currency_symbol = "USDT"
        price_display = format_usdt_price(price)
        logger.info(f"Processing {trade_side.upper()} trade: {exchange} {pair_type} - {format_quantity(quantity)} XBT at ${price_display} USDT")

    # Additional validation: Only process buy trades for alerts
    if trade_side.lower() not in ["buy", "b", "unknown"]:
        logger.debug(f"Skipping {trade_side.upper()} trade - not counting toward buy volume threshold")
        return

    # Update threshold based on volume
    await update_threshold()

    # Get aggregation settings from config
    config = get_config()
    aggregation_enabled = config.get("trade_aggregation", {}).get("enabled", True)
    aggregation_window = config.get("trade_aggregation", {}).get("window_seconds", 8)

    value_require = get_value_require()

    if not aggregation_enabled or aggregation_window <= 0:
        # If aggregation is disabled, apply threshold check and send alert immediately if it passes
        if threshold_sum_value >= value_require:
            logger.info(f"Sending immediate alert for trade: ${threshold_sum_value:.2f} USDT equivalent (threshold: ${value_require})")
            await send_alert(price, quantity, sum_value, exchange, timestamp, exchange_url, 1, None, pair_type, usdt_price, usdt_sum_value, btc_rate)
        else:
            logger.info(f"Trade below threshold: ${threshold_sum_value:.2f} USDT equivalent < ${value_require} USDT")
        return

    # Trade aggregation is enabled - add to pending trades
    current_time = time.time()

    # Initialize exchange dict if not exists
    if exchange not in PENDING_TRADES:
        PENDING_TRADES[exchange] = {}

    # Initialize pair dict if not exists
    if pair_type not in PENDING_TRADES[exchange]:
        PENDING_TRADES[exchange][pair_type] = {}

    # Use a simple buyer ID based on price and time window
    buyer_id = f"buyer_{int(timestamp / 1000 / aggregation_window)}"

    # Initialize buyer's trade list if not exists
    if buyer_id not in PENDING_TRADES[exchange][pair_type]:
        PENDING_TRADES[exchange][pair_type][buyer_id] = []

    # Add trade to pending list
    trade_data = {
        'price': price,
        'quantity': quantity,
        'sum_value': sum_value,
        'timestamp': timestamp,
        'exchange_url': exchange_url,
        'side': trade_side,
        'received_time': current_time,
        'pair_type': pair_type,
        'usdt_price': usdt_price,
        'usdt_sum_value': usdt_sum_value,
        'btc_rate': btc_rate,
        'threshold_sum_value': threshold_sum_value  # For aggregation threshold checking
    }
    PENDING_TRADES[exchange][pair_type][buyer_id].append(trade_data)

    logger.debug(f"Added trade to aggregation: {exchange} {pair_type} buyer {buyer_id} - ${threshold_sum_value:.2f} USDT equivalent")

    # Check if we should process aggregated trades
    if current_time - LAST_AGGREGATION_CHECK >= 1:  # Check every second
        await process_aggregated_trades()
        LAST_AGGREGATION_CHECK = current_time

async def process_aggregated_trades():
    """Process and send alerts for aggregated trades that meet criteria, separated by trading pair."""
    global PENDING_TRADES

    config = get_config()
    aggregation_window = config.get("trade_aggregation", {}).get("window_seconds", 8)
    value_require = get_value_require()
    current_time = time.time()

    for exchange in list(PENDING_TRADES.keys()):
        for pair_type in list(PENDING_TRADES[exchange].keys()):
            for buyer_id in list(PENDING_TRADES[exchange][pair_type].keys()):
                trades = PENDING_TRADES[exchange][pair_type][buyer_id]

                if not trades:
                    continue

                # Check if trades have expired (older than aggregation window)
                oldest_trade_time = min(trade['received_time'] for trade in trades)
                if current_time - oldest_trade_time >= aggregation_window:

                    # Calculate aggregated values
                    total_quantity = sum(trade['quantity'] for trade in trades)
                    total_pending = sum(trade['sum_value'] for trade in trades)

                    # For threshold checking, use USDT equivalent values
                    total_threshold_value = sum(trade['threshold_sum_value'] for trade in trades)

                    # Calculate volume-weighted average price
                    if total_quantity > 0:
                        avg_price = total_pending / total_quantity
                    else:
                        avg_price = trades[0]['price']  # Fallback

                    # Get latest timestamp and pair info
                    latest_timestamp = max(trade['timestamp'] for trade in trades)
                    first_trade = trades[0]

                    # Validate buy/sell aggregation
                    validation_passed, buy_volume, sell_volume = validate_buy_sell_aggregation(trades, f"{exchange} {pair_type} aggregation")

                    # Use USDT equivalent for threshold checking - use correct field name 'trade_side'
                    buy_threshold_volume = sum(trade['threshold_sum_value'] for trade in trades if trade.get('trade_side', '').lower() in ['buy', 'b', 'unknown'])

                    if validation_passed and buy_threshold_volume >= value_require:
                        logger.info(f"Sending aggregated alert: {exchange} {pair_type} - {len(trades)} trades, {format_quantity(total_quantity)} XBT, ${buy_threshold_volume:.2f} USDT equivalent")

                        # Verification: Check if weighted average calculation is correct
                        calculated_total = avg_price * total_quantity
                        tolerance = 0.01 if pair_type == "XBT/USDT" else 0.00000001  # Different tolerance for BTC
                        if abs(calculated_total - total_pending) > tolerance:
                            pair_currency = "BTC" if pair_type == "XBT/BTC" else "USDT"
                            logger.error(f"❌ AGGREGATION PRICE CALCULATION MISMATCH for {pair_type}: {format_price(avg_price, pair_currency)} * {format_quantity(total_quantity)} = {calculated_total:.8f if pair_type == 'XBT/BTC' else calculated_total:.2f} != {total_pending:.8f if pair_type == 'XBT/BTC' else total_pending:.2f}")
                        else:
                            pair_currency = "BTC" if pair_type == "XBT/BTC" else "USDT"
                            logger.debug(f"✅ Aggregation price calculation verified for {pair_type}: {format_price(avg_price, pair_currency)} * {format_quantity(total_quantity)} = {calculated_total:.8f if pair_type == 'XBT/BTC' else calculated_total:.2f} ≈ {total_pending:.8f if pair_type == 'XBT/BTC' else total_pending:.2f}")

                        # Send the alert with trade details
                        await send_alert(
                            avg_price,
                            total_quantity,
                            total_pending,
                            f"{exchange} (Aggregated)",
                            latest_timestamp,
                            first_trade['exchange_url'],
                            len(trades),
                            trades,  # Pass trade details for breakdown
                            pair_type,
                            first_trade.get('usdt_price'),
                            sum(trade.get('usdt_sum_value', 0) for trade in trades) if pair_type == "XBT/BTC" else None,
                            first_trade.get('btc_rate')
                        )
                    else:
                        if validation_passed:
                            logger.info(f"Aggregated {pair_type} trades below threshold: ${buy_threshold_volume:.2f} USDT equivalent < ${value_require} USDT")
                        else:
                            logger.warning(f"Aggregation validation failed for {exchange} {pair_type} buyer {buyer_id}")

                    # Remove processed trades
                    del PENDING_TRADES[exchange][pair_type][buyer_id]

            # Clean up empty pair dicts
            if not PENDING_TRADES[exchange][pair_type]:
                del PENDING_TRADES[exchange][pair_type]

        # Clean up empty exchange dicts
        if not PENDING_TRADES[exchange]:
            del PENDING_TRADES[exchange]

async def send_alert(price: float, quantity: float, sum_value: float, exchange: str,
                    timestamp: int, exchange_url: str, num_trades: int = 1,
                    trade_details: Optional[List[Dict]] = None, pair_type: str = "XBT/USDT",
                    usdt_price: Optional[float] = None, usdt_sum_value: Optional[float] = None,
                    btc_rate: Optional[float] = None):
    """
    Send an alert to all active chats with robust error handling and fallback.

    Args:
        price: Trade price (in original currency)
        quantity: Trade quantity
        sum_value: Total trade value (in original currency)
        exchange: Exchange name
        timestamp: Trade timestamp
        exchange_url: Exchange URL
        num_trades: Number of trades in aggregation
        trade_details: List of individual trade details
        pair_type: Trading pair type ("XBT/USDT" or "XBT/BTC")
        usdt_price: USDT equivalent price (for BTC pairs)
        usdt_sum_value: USDT equivalent total value (for BTC pairs)
        btc_rate: BTC/USDT rate used for conversion (for BTC pairs)
    """
    global PHOTO

    # Determine currency type for validation
    currency_type = "BTC" if pair_type == "XBT/BTC" else "USDT"

    # Validate the alert calculation before sending
    is_valid, corrected_value = validate_price_calculation(price, quantity, sum_value, f"Alert from {exchange}", currency_type)
    if not is_valid:
        if pair_type == "XBT/BTC":
            logger.warning(f"Alert calculation corrected: {sum_value:.8f} -> {corrected_value:.8f} BTC")
        else:
            logger.warning(f"Alert calculation corrected: {sum_value:.2f} -> {corrected_value:.2f} USDT")
        sum_value = corrected_value  # Use corrected value for the alert

    # Format timestamp
    dt = datetime.fromtimestamp(timestamp / 1000 if timestamp > 10**10 else timestamp, tz=timezone.utc)
    time_str = dt.strftime("%H:%M:%S UTC")

    # Get comprehensive market data for additional context
    try:
        # Fetch real-time prices for both trading pairs
        market_data_usdt = await get_nonkyc_ticker()  # XBT/USDT
        volume_data = await calculate_combined_volume_periods()
        volume_periods = volume_data["combined"]

        # Get current prices for both pairs
        current_price_usdt = market_data_usdt.get("lastPriceNumber", price) if market_data_usdt else price
        market_cap = market_data_usdt.get("marketcapNumber", 0) if market_data_usdt else 0

    except Exception as e:
        logger.error(f"Error fetching market context data: {e}")
        current_price_usdt = price
        market_cap = 0
        volume_periods = {"15m": 0, "1h": 0, "4h": 0, "24h": 0}

    # Build the alert message based on trading pair
    if pair_type == "XBT/BTC":
        # XBT/BTC alert with BTC prices and USDT equivalent
        if num_trades > 1 and trade_details:
            # Aggregated BTC trade alert
            message_parts = [
                f"🚨 <b>XBT/BTC BUY ALERT - {num_trades} Orders Aggregated</b> 🚨\n",
                f"💰 <b>Total Value:</b> {format_btc_price(sum_value)} BTC",
                f"💵 <b>USDT Equivalent:</b> ≈ {format_usdt_price(usdt_sum_value)} USDT" if usdt_sum_value else "",
                f"📊 <b>Total Quantity:</b> {format_quantity(quantity)} XBT",
                f"💵 <b>Avg Price:</b> {format_btc_price(price)} BTC",
                f"💱 <b>USDT Equivalent:</b> ≈ {format_usdt_price(usdt_price)} USDT" if usdt_price else "",
                f"🏦 <b>Exchange:</b> {exchange}",
                f"⏰ <b>Time:</b> {time_str}",
                f"📈 <b>BTC Rate:</b> ${btc_rate:.2f} USDT" if btc_rate else "",
                ""
            ]

            # Add individual order breakdown (limit to first 5 for readability)
            message_parts.append("📋 <b>Individual Orders:</b>")
            for i, trade in enumerate(trade_details[:5], 1):
                trade_btc_price = trade['price']
                trade_quantity = trade['quantity']
                trade_usdt_price = trade.get('usdt_price', 0)
                if trade_usdt_price:
                    message_parts.append(f"Order {i}: {format_quantity(trade_quantity)} XBT at {format_btc_price(trade_btc_price)} BTC (≈ {format_usdt_price(trade_usdt_price)} USDT)")
                else:
                    message_parts.append(f"Order {i}: {format_quantity(trade_quantity)} XBT at {format_btc_price(trade_btc_price)} BTC")

            if len(trade_details) > 5:
                message_parts.append(f"... and {len(trade_details) - 5} more orders")

        else:
            # Single BTC trade alert
            message_parts = [
                f"🚨 <b>XBT/BTC BUY ALERT</b> 🚨\n",
                f"💰 <b>Value:</b> {format_btc_price(sum_value)} BTC",
                f"💵 <b>USDT Equivalent:</b> ≈ {format_usdt_price(usdt_sum_value)} USDT" if usdt_sum_value else "",
                f"📊 <b>Quantity:</b> {format_quantity(quantity)} XBT",
                f"💵 <b>Price:</b> {format_btc_price(price)} BTC",
                f"💱 <b>USDT Equivalent:</b> ≈ {format_usdt_price(usdt_price)} USDT" if usdt_price else "",
                f"🏦 <b>Exchange:</b> {exchange}",
                f"⏰ <b>Time:</b> {time_str}",
                f"📈 <b>BTC Rate:</b> ${btc_rate:.2f} USDT" if btc_rate else ""
            ]
    else:
        # XBT/USDT alert with USDT prices
        if num_trades > 1 and trade_details:
            # Aggregated USDT trade alert
            message_parts = [
                f"🚨 <b>XBT/USDT BUY ALERT - {num_trades} Orders Aggregated</b> 🚨\n",
                f"💰 <b>Total Value:</b> ${format_usdt_price(sum_value)} USDT",
                f"📊 <b>Total Quantity:</b> {format_quantity(quantity)} XBT",
                f"💵 <b>Avg Price:</b> ${format_usdt_price(price)} USDT",
                f"🏦 <b>Exchange:</b> {exchange}",
                f"⏰ <b>Time:</b> {time_str}\n"
            ]

            # Add individual order breakdown (limit to first 5 for readability)
            message_parts.append("📋 <b>Individual Orders:</b>")
            for i, trade in enumerate(trade_details[:5], 1):
                trade_price = trade['price']
                trade_quantity = trade['quantity']
                message_parts.append(f"Order {i}: {format_quantity(trade_quantity)} XBT at ${format_usdt_price(trade_price)} USDT")

            if len(trade_details) > 5:
                message_parts.append(f"... and {len(trade_details) - 5} more orders")

        else:
            # Single USDT trade alert
            message_parts = [
                f"🚨 <b>XBT/USDT BUY ALERT</b> 🚨\n",
                f"💰 <b>Value:</b> ${format_usdt_price(sum_value)} USDT",
                f"📊 <b>Quantity:</b> {format_quantity(quantity)} XBT",
                f"💵 <b>Price:</b> ${format_usdt_price(price)} USDT",
                f"🏦 <b>Exchange:</b> {exchange}",
                f"⏰ <b>Time:</b> {time_str}"
            ]

    # Add market context
    message_parts.extend([
        f"\n📈 <b>Current Market:</b>",
        f"💲 <b>XBT/USDT:</b> ${format_usdt_price(current_price_usdt)} USDT",
        f"🏛️ <b>Market Cap:</b> ${market_cap:,.0f}" if market_cap > 0 else "",
        f"\n📊 <b>Volume (24h periods):</b>",
        f"🕐 <b>15m:</b> {volume_periods['15m']:.2f} XBT",
        f"🕐 <b>1h:</b> {volume_periods['1h']:.2f} XBT",
        f"🕐 <b>4h:</b> {volume_periods['4h']:.2f} XBT",
        f"🕐 <b>24h:</b> {volume_periods['24h']:.2f} XBT",
        f"\n🔗 <b>Trade XBT:</b>",
        f"• <a href='https://nonkyc.io/market/XBT_USDT'>XBT/USDT on NonKYC</a>",
        f"• <a href='https://nonkyc.io/market/XBT_BTC'>XBT/BTC on NonKYC</a>"
    ])

    # Filter out empty strings and join
    message = "\n".join(filter(None, message_parts))

    # Send to all active chats
    active_chat_ids = get_active_chat_ids()
    config = get_config()
    bot_token = config.get("bot_token", "")
    
    if not bot_token:
        logger.error("Bot token not configured - cannot send alerts")
        return

    bot = Bot(token=bot_token)
    
    for chat_id in active_chat_ids:
        try:
            await send_alert_to_chat(bot, chat_id, message, PHOTO)
        except Exception as e:
            logger.error(f"Failed to send alert to chat {chat_id}: {e}")

async def send_alert_to_chat(bot: Bot, chat_id: int, message: str, photo: Optional[InputFile]):
    """
    Send alert to a specific chat with image-first approach and text fallback.
    
    Args:
        bot: Telegram bot instance
        chat_id: Target chat ID
        message: Alert message
        photo: Photo to send with alert
    """
    try:
        if photo:
            # Try to send with image first
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=message,
                    parse_mode="HTML"
                )
                logger.info(f"✅ Alert sent with image to chat {chat_id}")
                return
            except TelegramError as e:
                logger.warning(f"Failed to send image alert to {chat_id}: {e}")
        
        # Fallback to text-only message
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logger.info(f"✅ Alert sent (text-only) to chat {chat_id}")
        
    except TelegramError as e:
        logger.error(f"❌ Failed to send alert to chat {chat_id}: {e}")
        raise
