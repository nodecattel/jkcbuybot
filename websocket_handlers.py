"""
WebSocket Handlers Module for JKC Trading Bot

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

from api_clients import check_exchange_availability, get_exchange_availability
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

    # Wait for JKC to become available on NonKYC
    while running:
        await check_exchange_availability()
        exchange_availability = get_exchange_availability()
        if exchange_availability["nonkyc"]:
            logger.info("JKC detected on NonKYC - starting orderbook WebSocket for sweep detection")
            break
        else:
            logger.debug("JKC not yet available on NonKYC for orderbook - waiting...")
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

            # Subscribe to JKC/USDT orderbook
            subscribe_msg = {
                "method": "subscribeOrderbook",
                "params": {
                    "symbol": "JKC/USDT"
                },
                "id": 4
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.debug("Subscribed to JKC/USDT orderbook on NonKYC")

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
    """Connect to NonKYC WebSocket API and process JKC/USDT trade data."""
    global running
    uri = "wss://ws.nonkyc.io"

    # Wait for JKC to become available on NonKYC
    while running:
        await check_exchange_availability()
        exchange_availability = get_exchange_availability()
        if exchange_availability["nonkyc"]:
            logger.info("JKC detected on NonKYC - starting USDT WebSocket connection")
            break
        else:
            logger.debug("JKC not yet available on NonKYC - waiting...")
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

            # Subscribe to JKC/USDT trades
            subscribe_msg = {
                "method": "subscribeTrades",
                "params": {
                    "symbol": "JKC/USDT"
                },
                "id": 1
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.debug("Subscribed to JKC/USDT trades on NonKYC")

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
                                    "https://nonkyc.io/market/JKC_USDT", trade_side, "JKC/USDT"
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

# BTC pair functionality removed - JKC only trades against USDT

async def coinex_websocket():
    """Connect to CoinEx WebSocket API and process trade data."""
    global running
    uri = "wss://socket.coinex.com/"

    # Wait for JKC to become available on CoinEx
    while running:
        await check_exchange_availability()
        exchange_availability = get_exchange_availability()
        if exchange_availability["coinex"]:
            logger.info("JKC detected on CoinEx - starting WebSocket connection")
            break
        else:
            logger.debug("JKC not yet available on CoinEx - waiting...")
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

            # Subscribe to JKC/USDT trades
            subscribe_msg = {
                "method": "deals.subscribe",
                "params": ["JKCUSDT"],
                "id": 2
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.debug("Subscribed to JKC/USDT trades on CoinEx")

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
                                    "https://www.coinex.com/exchange/JKC-USDT", trade_side, "JKC/USDT"
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

    # Wait for JKC to become available on AscendEX
    while running:
        try:
            await check_exchange_availability()
            exchange_availability = get_exchange_availability()
            if exchange_availability["ascendex"]:
                logger.info("JKC detected on AscendEX - starting WebSocket connection")
                break
            else:
                logger.debug("JKC not yet available on AscendEX - waiting...")
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

            # Subscribe to JKC/USDT trades
            subscribe_msg = {
                "op": "sub",
                "ch": "trades:JKC/USDT"
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.info("✅ Subscribed to JKC/USDT trades on AscendEX")

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
                                    "https://ascendex.com/en/cashtrade-spottrading/usdt/JKC", side_str, "JKC/USDT"
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
                        logger.info(f"🎉 JKC is now available on {exchange.upper()}!")
                    else:
                        logger.info(f"❌ JKC is no longer available on {exchange.upper()}")

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
                    logger.info(f"💓 Bot running - Monitoring JKC on: {', '.join(available_exchanges)} | Threshold: {value_require} USDT")
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
