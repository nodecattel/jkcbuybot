"""
WebSocket Handlers Module for XBT Trading Bot

This module handles all WebSocket connections to various exchanges including
NonKYC, CoinEx, and AscendEX. It processes real-time trade data and manages
connection lifecycle with proper error handling and reconnection logic.
"""

import asyncio
import json
import logging
import time
import websockets
from typing import Optional, Dict, Any

from api_clients import check_exchange_availability, get_exchange_availability, get_btc_usdt_rate, convert_btc_to_usdt
from config import get_config_value

# Set up module logger
logger = logging.getLogger(__name__)

# Global state for WebSocket management
running = True
DEBUG_MODE = False

# Global variables for orderbook state
CURRENT_ORDERBOOK = None
ORDERBOOK_SEQUENCE = 0

# Import alert processing function (will be set by main module)
process_trade_message = None

def set_trade_processor(processor_func):
    """
    Set the trade processing function from the alert system.
    
    Args:
        processor_func: Function to process trade messages
    """
    global process_trade_message
    process_trade_message = processor_func

def stop_websockets():
    """Stop all WebSocket connections."""
    global running
    running = False
    logger.info("WebSocket shutdown initiated")

async def nonkyc_orderbook_websocket():
    """Subscribe to NonKYC orderbook updates for real-time sweep detection."""
    global running, CURRENT_ORDERBOOK, ORDERBOOK_SEQUENCE
    uri = "wss://ws.nonkyc.io"

    # Wait for XBT to become available on NonKYC
    while running:
        await check_exchange_availability()
        exchange_availability = get_exchange_availability()
        if exchange_availability["nonkyc"]:
            logger.info("XBT detected on NonKYC - starting orderbook WebSocket for sweep detection")
            break
        else:
            logger.debug("XBT not yet available on NonKYC for orderbook - waiting...")
            await asyncio.sleep(60)  # Check every minute
            continue

    # For exponential backoff
    retry_delay = 5
    max_retry_delay = 60

    while running:
        websocket = None
        try:
            websocket = await websockets.connect(uri, ping_interval=30)
            logger.debug(f"Connected to NonKYC orderbook WebSocket at {uri}")

            # Subscribe to XBT/USDT orderbook
            subscribe_msg = {
                "method": "subscribeOrderbook",
                "params": {
                    "symbol": "XBT/USDT"
                },
                "id": 4
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.debug("Subscribed to XBT/USDT orderbook on NonKYC")

            # Reset retry delay on successful connection
            retry_delay = 5

            # Process messages
            while running:
                try:
                    response = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))

                    # Log all messages in debug mode
                    if DEBUG_MODE:
                        logger.info(f"NonKYC orderbook message: {response}")

                    # Process orderbook updates
                    if "method" in response and response["method"] == "snapshotOrderbook":
                        # Full orderbook snapshot
                        CURRENT_ORDERBOOK = response["params"]
                        ORDERBOOK_SEQUENCE = response["params"].get("sequence", 0)
                        logger.debug(f"Received orderbook snapshot, sequence: {ORDERBOOK_SEQUENCE}")

                    elif "method" in response and response["method"] == "updateOrderbook":
                        # Incremental orderbook update
                        update_data = response["params"]
                        new_sequence = update_data.get("sequence", 0)

                        if new_sequence > ORDERBOOK_SEQUENCE:
                            CURRENT_ORDERBOOK = update_data
                            ORDERBOOK_SEQUENCE = new_sequence
                            logger.debug(f"Updated orderbook, sequence: {ORDERBOOK_SEQUENCE}")

                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    try:
                        await websocket.ping()
                    except Exception:
                        logger.warning("Failed to ping NonKYC orderbook WebSocket")
                        break
                except Exception as e:
                    logger.error(f"Error processing NonKYC orderbook message: {e}")
                    break

        except Exception as e:
            logger.error(f"NonKYC orderbook WebSocket error: {e}")

        finally:
            if websocket:
                try:
                    await websocket.close()
                except Exception:
                    pass

        if running:
            logger.info(f"Reconnecting to NonKYC orderbook WebSocket in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)

async def nonkyc_websocket_usdt():
    """Connect to NonKYC WebSocket API and process XBT/USDT trade data."""
    global running
    uri = "wss://ws.nonkyc.io"

    # Wait for XBT to become available on NonKYC
    while running:
        await check_exchange_availability()
        exchange_availability = get_exchange_availability()
        if exchange_availability["nonkyc"]:
            logger.info("XBT detected on NonKYC - starting USDT WebSocket connection")
            break
        else:
            logger.debug("XBT not yet available on NonKYC - waiting...")
            await asyncio.sleep(60)  # Check every minute
            continue

    # For exponential backoff
    retry_delay = 5
    max_retry_delay = 60

    while running:
        websocket = None
        try:
            websocket = await websockets.connect(uri, ping_interval=30)
            logger.debug(f"Connected to NonKYC WebSocket at {uri}")

            # Subscribe to XBT/USDT trades
            subscribe_msg = {
                "method": "subscribeTrades",
                "params": {
                    "symbol": "XBT/USDT"
                },
                "id": 1
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.debug("Subscribed to XBT/USDT trades on NonKYC")

            # Reset retry delay on successful connection
            retry_delay = 5

            # Process messages
            while running:
                try:
                    response = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))

                    # Log all messages in debug mode
                    if DEBUG_MODE:
                        logger.info(f"NonKYC message: {response}")

                    # Process trade messages
                    if "method" in response and response["method"] == "updateTrades":
                        trades = response["params"]["data"]
                        for trade in trades:
                            if process_trade_message:
                                price = float(trade["price"])
                                quantity = float(trade["quantity"])
                                sum_value = price * quantity
                                timestamp = int(trade["timestamp"])
                                trade_side = trade.get("side", "unknown")

                                await process_trade_message(
                                    price, quantity, sum_value, "NonKYC", timestamp,
                                    "https://nonkyc.io/market/XBT_USDT", trade_side, "XBT/USDT"
                                )

                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    try:
                        await websocket.ping()
                    except Exception:
                        logger.warning("Failed to ping NonKYC WebSocket")
                        break
                except Exception as e:
                    logger.error(f"Error processing NonKYC message: {e}")
                    break

        except Exception as e:
            logger.error(f"NonKYC WebSocket error: {e}")

        finally:
            if websocket:
                try:
                    await websocket.close()
                except Exception:
                    pass

        if running:
            logger.info(f"Reconnecting to NonKYC WebSocket in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)

async def nonkyc_websocket_btc():
    """Connect to NonKYC WebSocket API and process XBT/BTC trade data with BTC-to-USDT conversion."""
    global running
    uri = "wss://ws.nonkyc.io"

    # Wait for XBT to become available on NonKYC
    while running:
        await check_exchange_availability()
        exchange_availability = get_exchange_availability()
        if exchange_availability["nonkyc"]:
            logger.info("XBT detected on NonKYC - starting BTC WebSocket connection")
            break
        else:
            logger.debug("XBT not yet available on NonKYC for BTC pair - waiting...")
            await asyncio.sleep(60)  # Check every minute
            continue

    # For exponential backoff
    retry_delay = 5
    max_retry_delay = 60

    # Track last transaction timestamp for BTC pair
    last_trans_btc = int(time.time() * 1000)

    # Cache BTC/USDT rate and refresh periodically
    btc_rate = None
    last_rate_update = 0
    rate_update_interval = 300  # Update BTC rate every 5 minutes

    while running:
        websocket = None
        try:
            websocket = await websockets.connect(uri, ping_interval=30)
            logger.debug(f"Connected to NonKYC WebSocket for XBT/BTC at {uri}")

            # Subscribe to XBT/BTC trades
            subscribe_msg = {
                "method": "subscribeTrades",
                "params": {
                    "symbol": "XBT/BTC"
                },
                "id": 3
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.debug("Subscribed to XBT/BTC trades on NonKYC")

            # Reset retry delay on successful connection
            retry_delay = 5

            # Process messages
            while running:
                try:
                    # Update BTC rate periodically
                    current_time = time.time()
                    if current_time - last_rate_update > rate_update_interval or btc_rate is None:
                        btc_rate = await get_btc_usdt_rate()
                        last_rate_update = current_time
                        if btc_rate:
                            logger.debug(f"Updated BTC/USDT rate: ${btc_rate:.2f}")
                        else:
                            logger.warning("Failed to update BTC/USDT rate")

                    response = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))

                    # Log all messages in debug mode
                    if DEBUG_MODE:
                        logger.info(f"NonKYC BTC message: {response}")

                    # Process trade messages
                    if "method" in response and response["method"] == "updateTrades":
                        trades = response["params"]["data"]
                        for trade in trades:
                            timestamp = int(trade["timestamp"])
                            if timestamp > last_trans_btc:
                                last_trans_btc = timestamp

                                if process_trade_message:
                                    btc_price = float(trade["price"])
                                    quantity = float(trade["quantity"])
                                    btc_sum_value = btc_price * quantity
                                    trade_side = trade.get("side", "unknown")

                                    # Convert BTC price to USDT equivalent
                                    if btc_rate:
                                        usdt_price, _ = await convert_btc_to_usdt(btc_price, btc_rate)
                                        usdt_sum_value = usdt_price * quantity

                                        logger.debug(f"XBT/BTC trade: {quantity:.4f} XBT at {btc_price:.8f} BTC (${usdt_price:.6f} USDT equivalent)")

                                        # Pass both BTC and USDT values to process_message
                                        await process_trade_message(
                                            btc_price, quantity, btc_sum_value, "NonKYC (BTC)", timestamp,
                                            "https://nonkyc.io/market/XBT_BTC", trade_side, "XBT/BTC",
                                            usdt_price, usdt_sum_value, btc_rate
                                        )
                                    else:
                                        logger.warning("Cannot process XBT/BTC trade: BTC/USDT rate unavailable")

                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    try:
                        await websocket.ping()
                    except Exception:
                        logger.warning("Failed to ping NonKYC BTC WebSocket")
                        break
                except Exception as e:
                    logger.error(f"Error processing NonKYC BTC message: {e}")
                    break

        except Exception as e:
            logger.error(f"NonKYC BTC WebSocket error: {e}")

        finally:
            if websocket:
                try:
                    await websocket.close()
                except Exception:
                    pass

        if running:
            logger.info(f"Reconnecting to NonKYC BTC WebSocket in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)

async def coinex_websocket():
    """Connect to CoinEx WebSocket API and process trade data."""
    global running
    uri = "wss://socket.coinex.com/"

    # Wait for XBT to become available on CoinEx
    while running:
        await check_exchange_availability()
        exchange_availability = get_exchange_availability()
        if exchange_availability["coinex"]:
            logger.info("XBT detected on CoinEx - starting WebSocket connection")
            break
        else:
            logger.debug("XBT not yet available on CoinEx - waiting...")
            await asyncio.sleep(60)  # Check every minute
            continue

    # For exponential backoff
    retry_delay = 5
    max_retry_delay = 60

    # CoinEx public websocket doesn't require API keys for trade data
    logger.info("Starting CoinEx WebSocket connection for public trade data")

    while running:
        websocket = None
        try:
            websocket = await websockets.connect(uri, ping_interval=30)
            logger.debug(f"Connected to CoinEx WebSocket at {uri}")

            # Subscribe to XBT/USDT trades
            subscribe_msg = {
                "method": "deals.subscribe",
                "params": ["XBTUSDT"],
                "id": 2
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.debug("Subscribed to XBT/USDT trades on CoinEx")

            # Reset retry delay on successful connection
            retry_delay = 5

            # Process messages
            while running:
                try:
                    response = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))

                    # Log all messages in debug mode
                    if DEBUG_MODE:
                        logger.info(f"CoinEx message: {response}")

                    # Process trade messages
                    if "method" in response and response["method"] == "deals.update":
                        trades = response["params"][1]
                        for trade in trades:
                            if process_trade_message:
                                price = float(trade["price"])
                                quantity = float(trade["amount"])
                                sum_value = price * quantity
                                timestamp = int(trade["date_ms"])
                                trade_side = trade.get("type", "unknown")

                                await process_trade_message(
                                    price, quantity, sum_value, "CoinEx", timestamp,
                                    "https://www.coinex.com/exchange/XBT-USDT", trade_side, "XBT/USDT"
                                )

                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    try:
                        await websocket.ping()
                    except Exception:
                        logger.warning("Failed to ping CoinEx WebSocket")
                        break
                except Exception as e:
                    logger.error(f"Error processing CoinEx message: {e}")
                    break

        except Exception as e:
            logger.error(f"CoinEx WebSocket error: {e}")

        finally:
            if websocket:
                try:
                    await websocket.close()
                except Exception:
                    pass

        if running:
            logger.info(f"Reconnecting to CoinEx WebSocket in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)

async def ascendex_websocket():
    """Connect to AscendEX WebSocket API and process trade data."""
    global running
    uri = "wss://ascendex.com/0/api/pro/v1/stream"

    logger.info("🔄 Starting AscendEX WebSocket handler...")

    # Wait for XBT to become available on AscendEX
    while running:
        try:
            await check_exchange_availability()
            exchange_availability = get_exchange_availability()
            if exchange_availability["ascendex"]:
                logger.info("XBT detected on AscendEX - starting WebSocket connection")
                break
            else:
                logger.debug("XBT not yet available on AscendEX - waiting...")
                await asyncio.sleep(60)  # Check every minute
                continue
        except Exception as e:
            logger.error(f"Error checking AscendEX availability: {e}")
            await asyncio.sleep(60)
            continue

    # For exponential backoff
    retry_delay = 5
    max_retry_delay = 60

    while running:
        websocket = None
        try:
            logger.debug(f"Attempting to connect to AscendEX WebSocket at {uri}")
            websocket = await websockets.connect(uri, ping_interval=30)
            logger.info(f"✅ Connected to AscendEX WebSocket at {uri}")

            # Subscribe to XBT/USDT trades
            subscribe_msg = {
                "op": "sub",
                "ch": "trades:XBT/USDT"
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.info("✅ Subscribed to XBT/USDT trades on AscendEX")

            # Reset retry delay on successful connection
            retry_delay = 5

            # Process messages
            while running:
                try:
                    response = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))

                    # Log all messages in debug mode
                    if DEBUG_MODE:
                        logger.info(f"AscendEX message: {response}")

                    # Process trade messages
                    if "m" in response and response["m"] == "trades":
                        trades = response.get("data", [])
                        for trade in trades:
                            if process_trade_message:
                                price = float(trade["p"])
                                quantity = float(trade["q"])
                                sum_value = price * quantity
                                timestamp = int(trade["ts"])
                                trade_side = trade.get("bm", False)  # True for buy, False for sell
                                side_str = "buy" if trade_side else "sell"

                                await process_trade_message(
                                    price, quantity, sum_value, "AscendEX", timestamp,
                                    "https://ascendex.com/en/cashtrade-spottrading/usdt/xbt", side_str, "XBT/USDT"
                                )

                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    try:
                        await websocket.ping()
                        logger.debug("Sent ping to AscendEX WebSocket")
                    except Exception as e:
                        logger.warning(f"Failed to ping AscendEX WebSocket: {e}")
                        break
                except Exception as e:
                    logger.error(f"Error processing AscendEX message: {e}")
                    break

        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limited = "429" in error_msg or "rate limit" in error_msg

            if is_rate_limited:
                logger.warning(f"AscendEX rate limit hit: {e}")
                # Use longer delay for rate limiting
                rate_limit_delay = min(retry_delay * 3, 300)  # Max 5 minutes
                logger.info(f"⏳ Rate limited - waiting {rate_limit_delay} seconds before retry...")
                if running:
                    await asyncio.sleep(rate_limit_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
            else:
                logger.error(f"AscendEX WebSocket connection error: {e}")

        finally:
            if websocket:
                try:
                    await websocket.close()
                    logger.debug("AscendEX WebSocket connection closed")
                except Exception as e:
                    logger.debug(f"Error closing AscendEX WebSocket: {e}")

        if running:
            # Only sleep and log if we didn't already handle rate limiting above
            try:
                # Check if we had a rate limiting error in this iteration
                if 'is_rate_limited' in locals() and not is_rate_limited:
                    logger.info(f"🔄 Reconnecting to AscendEX WebSocket in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_retry_delay)
            except NameError:
                # If is_rate_limited is not defined, it means no exception occurred
                logger.info(f"🔄 Reconnecting to AscendEX WebSocket in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
        else:
            logger.info("🛑 AscendEX WebSocket handler stopping due to running=False")
            break

    logger.info("👋 AscendEX WebSocket handler finished")

# Monitoring functions
async def exchange_availability_monitor():
    """Monitor exchange availability and log changes."""
    global running
    previous_availability = {}

    logger.info("🔄 Starting exchange availability monitor...")

    while running:
        try:
            # Check availability every 5 minutes
            current_availability = await check_exchange_availability()

            # Log any changes in availability
            for exchange, available in current_availability.items():
                if available != previous_availability.get(exchange, False):
                    if available:
                        logger.info(f"🎉 XBT is now available on {exchange.upper()}!")
                    else:
                        logger.info(f"❌ XBT is no longer available on {exchange.upper()}")

            previous_availability = current_availability.copy()

        except Exception as e:
            logger.error(f"Error in exchange availability monitor: {e}")

        # Wait 5 minutes before next check
        try:
            await asyncio.sleep(300)
        except asyncio.CancelledError:
            logger.info("🛑 Exchange availability monitor cancelled")
            break

    logger.info("👋 Exchange availability monitor finished")

async def heartbeat():
    """Send periodic heartbeat messages to show the bot is running."""
    global running
    from config import get_value_require

    logger.info("🔄 Starting heartbeat monitor...")
    counter = 0

    while running:
        try:
            counter += 1
            if counter % 60 == 0:  # Log every minute
                exchange_availability = get_exchange_availability()
                available_exchanges = [ex for ex, available in exchange_availability.items() if available]
                value_require = get_value_require()

                if available_exchanges:
                    logger.info(f"💓 Bot running - Monitoring XBT on: {', '.join(available_exchanges)} | Threshold: {value_require} USDT")
                else:
                    logger.info(f"💓 Bot running - Using LiveCoinWatch API | Threshold: {value_require} USDT")

            await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("🛑 Heartbeat monitor cancelled")
            break
        except Exception as e:
            logger.error(f"Error in heartbeat monitor: {e}")
            await asyncio.sleep(1)

    logger.info("👋 Heartbeat monitor finished")
