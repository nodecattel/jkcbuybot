import asyncio
from datetime import datetime, timezone, timedelta
import time
import io
import json
import os
import signal
import sys
import logging
import base64
import hashlib
import hmac
import copy
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import Application, CommandHandler, CallbackContext, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
import requests
import threading
import websockets
import plotly.graph_objects as go
import pandas as pd
import gzip
import zlib
import traceback

# Set up logging with more detailed format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set httpx logging to WARNING to reduce noise
logging.getLogger("httpx").setLevel(logging.WARNING)

# Add a file handler to save logs
file_handler = logging.FileHandler("telebot.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

def setup_file_logging():
    """Set up logging to a file in addition to console"""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Create a file handler with current timestamp
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join("logs", f"telebot_{current_time}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    file_handler.setLevel(logging.INFO)
    
    # Add the file handler to the logger
    logger.addHandler(file_handler)
    
    return log_file

async def notify_owner_of_error(error_msg):
    """Send error notification to bot owner"""
    try:
        bot = Bot(token=BOT_TOKEN)
        # Escape HTML special characters
        safe_error = error_msg.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        await bot.send_message(
            chat_id=BOT_OWNER,
            text=f"⚠️ Bot crashed with error:\n\n<pre>{safe_error[:3000]}</pre>",
            parse_mode="HTML"
        )
        logger.info("Error notification sent to bot owner")
    except Exception as notify_error:
        logger.error(f"Failed to notify owner about crash: {notify_error}")

# Load configuration from file
def load_config():
    config_path = "config.json"
    if not os.path.exists(config_path):
        # Create default config if it doesn't exist
        default_config = {
            "bot_token": "YOUR_BOT_TOKEN",
            "value_require": 300,
            "active_chat_ids": [],
            "bot_owner": 0,
            "by_pass": 0,
            "image_path": "junk_resized.jpeg",
            "dynamic_threshold": {
                "enabled": True,
                "base_value": 300,
                "volume_multiplier": 0.05,
                "price_check_interval": 3600,
                "min_threshold": 100,
                "max_threshold": 1000
            },
            "coinex_access_id": "",
            "coinex_secret_key": "",
            "ascendex_access_id": "",
            "ascendex_secret_key": ""
        }
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        return default_config
    
    with open(config_path, 'r') as f:
        return json.load(f)

# Save configuration to file
def save_config(config):
    with open("config.json", 'w') as f:
        json.dump(config, f, indent=2)

# Load config
CONFIG = load_config()

# Set variables from config
BOT_TOKEN = CONFIG["bot_token"]
VALUE_REQUIRE = CONFIG["value_require"]
ACTIVE_CHAT_IDS = CONFIG["active_chat_ids"]
BOT_OWNER = int(CONFIG["bot_owner"])  # Ensure this is an integer
BY_PASS = int(CONFIG["by_pass"])      # Ensure this is an integer
IMAGE_PATH = CONFIG["image_path"]

# Constants for conversation handlers
INPUT_NUMBER = 1
INPUT_IMAGE = 2
CONFIG_MENU = 3
DYNAMIC_CONFIG = 4
INPUT_API_KEYS = 5

# Transaction timestamps
LAST_TRANS_KYC = int(time.time() * 1000)
LAST_TRANS_COINEX = LAST_TRANS_KYC
LAST_TRANS_ASENDEX = 0
PHOTO = None
USER_CHECK_PRICE = []

# Last time the threshold was updated
LAST_THRESHOLD_UPDATE = time.time()

# Flag to control websocket loops
running = True

# Add these global variables at the top of the file with other globals
TRADE_AGGREGATION_WINDOW = 5  # seconds (increased from 3)
PENDING_TRADES = {}  # {exchange: {buyer_id: [trades]}}
LAST_AGGREGATION_CHECK = time.time()

# Add a debug mode to log all incoming messages
DEBUG_MODE = True

# Add a function to check if a user is an admin
async def is_admin(update: Update, context: CallbackContext) -> bool:
    """Check if the user is an admin or bot owner."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Debug logging
    logger.info(f"Admin check - User ID: {user_id}, Chat ID: {chat_id}, BOT_OWNER: {BOT_OWNER}, BY_PASS: {BY_PASS}")

    # Bot owner always has admin rights
    if user_id == BOT_OWNER or user_id == BY_PASS:
        logger.info(f"User {user_id} is bot owner or bypass user")
        return True

    # For group chats, check if user is an admin
    if chat_id < 0:  # Group chat IDs are negative
        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            is_admin_status = chat_member.status in ["administrator", "creator"]
            logger.info(f"User {user_id} in group {chat_id} has status: {chat_member.status}, is_admin: {is_admin_status}")
            return is_admin_status
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
    else:
        # For private chats, only bot owner and bypass user have admin rights
        logger.info(f"Private chat {chat_id} - User {user_id} is not bot owner or bypass user")

    return False

# Load image
try:
    with open(IMAGE_PATH, 'rb') as photo:
        img = photo.read()
        PHOTO = InputFile(io.BytesIO(img), filename=IMAGE_PATH)
except Exception as e:
    print(f"Error loading image: {e}")

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    global running
    print("Shutting down gracefully...")
    running = False
    # Give tasks time to clean up
    time.sleep(1)
    sys.exit(0)

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def get_nonkyc_ticker():
    """Get ticker data from NonKYC WebSocket API."""
    uri = "wss://ws.nonkyc.io"
    
    try:
        async with websockets.connect(uri, ping_interval=30) as websocket:
            # Request ticker data
            ticker_msg = {
                "method": "getMarket",
                "params": {
                    "symbol": "JKC/USDT"
                },
                "id": 999
            }
            await websocket.send(json.dumps(ticker_msg))
            
            # Wait for response
            response = json.loads(await websocket.recv())
            
            if "result" in response:
                return response["result"]
            else:
                return None
                
    except Exception as e:
        print(f"Error getting NonKYC ticker: {e}")
        return None

async def get_nonkyc_trades():
    """Get historical trades from NonKYC WebSocket API."""
    uri = "wss://ws.nonkyc.io"
    
    try:
        async with websockets.connect(uri, ping_interval=30) as websocket:
            # Request trades data
            trades_msg = {
                "method": "getTrades",
                "params": {
                    "symbol": "JKC/USDT",
                    "limit": 1000,
                    "sort": "DESC"
                },
                "id": 888
            }
            await websocket.send(json.dumps(trades_msg))
            
            # Wait for response
            response = json.loads(await websocket.recv())
            
            if "result" in response and "data" in response["result"]:
                return response["result"]["data"]
            else:
                return []
                
    except Exception as e:
        print(f"Error getting NonKYC trades: {e}")
        return []

async def get_nonkyc_orderbook():
    """Get orderbook data from NonKYC WebSocket API using subscription."""
    uri = "wss://ws.nonkyc.io"

    try:
        async with websockets.connect(uri, ping_interval=30) as websocket:
            # Subscribe to orderbook data
            subscribe_msg = {
                "method": "subscribeOrderbook",
                "params": {
                    "symbol": "JKC/USDT",
                    "limit": 50  # Smaller limit for faster processing
                },
                "id": 777
            }
            await websocket.send(json.dumps(subscribe_msg))

            # Wait for snapshot response
            while True:
                response = json.loads(await websocket.recv())

                # Look for the snapshot orderbook
                if "method" in response and response["method"] == "snapshotOrderbook":
                    params = response["params"]
                    if "asks" in params and "bids" in params:
                        # Convert to the expected format
                        orderbook = {
                            "asks": [[ask["price"], ask["quantity"]] for ask in params["asks"]],
                            "bids": [[bid["price"], bid["quantity"]] for bid in params["bids"]],
                            "timestamp": params.get("timestamp"),
                            "sequence": params.get("sequence")
                        }
                        return orderbook
                elif "result" in response:
                    # Subscription confirmation
                    continue
                else:
                    break

            return None

    except Exception as e:
        logger.error(f"Error getting NonKYC orderbook: {e}")
        return None

# Add global variables to track orderbook state for real-time sweep detection
CURRENT_ORDERBOOK = None
ORDERBOOK_SEQUENCE = 0

async def nonkyc_orderbook_websocket():
    """Subscribe to NonKYC orderbook updates for real-time sweep detection."""
    global running, CURRENT_ORDERBOOK, ORDERBOOK_SEQUENCE
    uri = "wss://ws.nonkyc.io"

    # For exponential backoff
    retry_delay = 5
    max_retry_delay = 60

    logger.info("Starting NonKYC orderbook subscription for real-time sweep detection...")

    while running:
        websocket = None
        try:
            websocket = await websockets.connect(uri, ping_interval=30)
            logger.info("Connected to NonKYC orderbook WebSocket")

            # Subscribe to orderbook updates
            subscribe_msg = {
                "method": "subscribeOrderbook",
                "params": {
                    "symbol": "JKC/USDT",
                    "limit": 20  # Only need top 20 levels for sweep detection
                },
                "id": 888
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.info("Subscribed to JKC/USDT orderbook updates")

            # Reset retry delay on successful connection
            retry_delay = 5

            # Process messages
            while running:
                try:
                    response = json.loads(await asyncio.wait_for(websocket.recv(), timeout=10))

                    if "method" in response:
                        if response["method"] == "snapshotOrderbook":
                            # Initial orderbook snapshot
                            params = response["params"]
                            CURRENT_ORDERBOOK = {
                                "asks": [[ask["price"], ask["quantity"]] for ask in params["asks"]],
                                "bids": [[bid["price"], bid["quantity"]] for bid in params["bids"]],
                                "sequence": params.get("sequence", 0)
                            }
                            ORDERBOOK_SEQUENCE = int(params.get("sequence", 0))
                            logger.info(f"Received orderbook snapshot with {len(CURRENT_ORDERBOOK['asks'])} asks, sequence: {ORDERBOOK_SEQUENCE}")

                        elif response["method"] == "updateOrderbook":
                            # Orderbook update - this is where we detect sweeps
                            await process_orderbook_update(response["params"])

                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("NonKYC orderbook WebSocket connection closed")
                    break
                except Exception as e:
                    logger.error(f"Error processing NonKYC orderbook message: {e}")
                    break

        except Exception as e:
            logger.error(f"Error in NonKYC orderbook WebSocket connection: {e}")

        finally:
            # Clean up
            if websocket and websocket.close_code is None:
                await websocket.close()

            # Don't retry if we're shutting down
            if not running:
                break

            # Exponential backoff for reconnection
            logger.info(f"Reconnecting to NonKYC orderbook WebSocket in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)

async def process_orderbook_update(params):
    """Process orderbook updates to detect sweep orders."""
    global CURRENT_ORDERBOOK, ORDERBOOK_SEQUENCE

    if not CURRENT_ORDERBOOK:
        return

    # Check sequence to ensure we don't miss updates
    new_sequence = int(params.get("sequence", 0))
    if new_sequence <= ORDERBOOK_SEQUENCE:
        return  # Old or duplicate update

    # Track what was removed/reduced
    swept_asks = []
    total_swept_value = 0

    # Process ask updates (we're looking for buy sweeps that remove asks)
    if "asks" in params:
        for ask_update in params["asks"]:
            price = ask_update["price"]
            new_quantity = float(ask_update["quantity"])

            # Find this price level in current orderbook
            for i, current_ask in enumerate(CURRENT_ORDERBOOK["asks"]):
                if current_ask[0] == price:
                    old_quantity = float(current_ask[1])

                    if new_quantity == 0:
                        # Price level completely removed (swept)
                        swept_asks.append({"price": float(price), "quantity": old_quantity})
                        total_swept_value += float(price) * old_quantity
                        logger.debug(f"Ask level swept: {price} USDT, {old_quantity} JKC")
                        # Remove from current orderbook
                        CURRENT_ORDERBOOK["asks"].pop(i)

                    elif new_quantity < old_quantity:
                        # Partial fill
                        filled_quantity = old_quantity - new_quantity
                        swept_asks.append({"price": float(price), "quantity": filled_quantity})
                        total_swept_value += float(price) * filled_quantity
                        logger.debug(f"Ask level partially filled: {price} USDT, {filled_quantity} JKC")
                        # Update current orderbook
                        CURRENT_ORDERBOOK["asks"][i][1] = str(new_quantity)

                    else:
                        # Quantity increased or same - update orderbook
                        CURRENT_ORDERBOOK["asks"][i][1] = str(new_quantity)
                    break
            else:
                # New price level - add to orderbook
                if new_quantity > 0:
                    CURRENT_ORDERBOOK["asks"].append([price, str(new_quantity)])
                    # Keep asks sorted by price
                    CURRENT_ORDERBOOK["asks"].sort(key=lambda x: float(x[0]))

    # Update sequence
    ORDERBOOK_SEQUENCE = new_sequence

    # If we detected a significant sweep, process it
    if swept_asks and total_swept_value > 0:
        total_quantity = sum(ask["quantity"] for ask in swept_asks)
        avg_price = total_swept_value / total_quantity if total_quantity > 0 else 0

        logger.info(f"Orderbook sweep detected: {total_quantity:.4f} JKC at avg {avg_price:.6f} USDT (Total: {total_swept_value:.2f} USDT)")

        # Process through normal pipeline
        timestamp = int(time.time() * 1000)
        await process_message(
            price=avg_price,
            quantity=total_quantity,
            sum_value=total_swept_value,
            exchange="NonKYC (Orderbook Sweep)",
            timestamp=timestamp,
            exchange_url="https://nonkyc.io/market/JKC_USDT"
        )

# Function to update threshold dynamically based on trading volume
async def update_threshold():
    global VALUE_REQUIRE, LAST_THRESHOLD_UPDATE, CONFIG
    
    # Only update if dynamic threshold is enabled
    if not CONFIG["dynamic_threshold"]["enabled"]:
        return
        
    # Check if it's time to update
    current_time = time.time()
    if current_time - LAST_THRESHOLD_UPDATE < CONFIG["dynamic_threshold"]["price_check_interval"]:
        return
        
    try:
        # Get market data from NonKYC
        market_data = await get_nonkyc_ticker()
        
        if market_data and "volume" in market_data:
            volume_24h = float(market_data["volumeNumber"])
            
            # Calculate new threshold based on 24h volume
            new_threshold = CONFIG["dynamic_threshold"]["base_value"] + (volume_24h * CONFIG["dynamic_threshold"]["volume_multiplier"])
            
            # Apply min/max constraints
            new_threshold = max(CONFIG["dynamic_threshold"]["min_threshold"], 
                               min(CONFIG["dynamic_threshold"]["max_threshold"], new_threshold))
            
            # Update the threshold
            VALUE_REQUIRE = round(new_threshold)
            CONFIG["value_require"] = VALUE_REQUIRE
            save_config(CONFIG)
            
            print(f"Updated threshold to {VALUE_REQUIRE} based on 24h volume of {volume_24h}")
            
        LAST_THRESHOLD_UPDATE = current_time
    except Exception as e:
        print(f"Error updating threshold: {e}")

async def safe_websocket_connect(uri, timeout=10):
    """Safely connect to a WebSocket with timeout."""
    try:
        return await asyncio.wait_for(
            websockets.connect(uri, ping_interval=30), 
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.error(f"Timeout connecting to {uri}")
        raise
    except Exception as e:
        logger.error(f"Error connecting to {uri}: {e}")
        raise

async def nonkyc_websocket():
    """Connect to NonKYC WebSocket API and process trade data."""
    global LAST_TRANS_KYC, running
    uri = "wss://ws.nonkyc.io"
    
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
                        # Handle NonKYC updateTrades format
                        if "params" in response and "data" in response["params"]:
                            trades_data = response["params"]["data"]

                            for trade_data in trades_data:
                                # Extract trade details
                                price = float(trade_data["price"])
                                quantity = float(trade_data["quantity"])
                                sum_value = price * quantity
                                timestamp = int(trade_data["timestampms"])  # Use timestampms for milliseconds

                                # Only process trades newer than the last one
                                if timestamp > LAST_TRANS_KYC:
                                    LAST_TRANS_KYC = timestamp

                                    # Process the trade
                                    await process_message(
                                        price=price,
                                        quantity=quantity,
                                        sum_value=sum_value,
                                        exchange="NonKYC Exchange",
                                        timestamp=timestamp,
                                        exchange_url="https://nonkyc.io/market/JKC_USDT"
                                    )
                    
                except asyncio.TimeoutError:
                    # This is normal, just continue
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("NonKYC WebSocket connection closed")
                    break
                except Exception as e:
                    logger.error(f"Error processing NonKYC message: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Error in NonKYC WebSocket connection: {e}")
        
        finally:
            # Clean up
            if websocket and websocket.close_code is None:
                await websocket.close()
            
            # Don't retry if we're shutting down
            if not running:
                break
                
            # Exponential backoff for reconnection
            logger.info(f"Reconnecting to NonKYC WebSocket in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)

async def coinex_websocket():
    """Connect to CoinEx WebSocket API and process trade data."""
    global LAST_TRANS_COINEX, running
    uri = "wss://socket.coinex.com/"
    
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
                            # Extract trade details
                            price = float(trade["price"])
                            quantity = float(trade["amount"])
                            sum_value = price * quantity
                            timestamp = int(trade["time"] * 1000)  # Convert to milliseconds
                            
                            # Only process trades newer than the last one
                            if timestamp > LAST_TRANS_COINEX:
                                LAST_TRANS_COINEX = timestamp
                                
                                # Process the trade
                                await process_message(
                                    price=price,
                                    quantity=quantity,
                                    sum_value=sum_value,
                                    exchange="CoinEx Exchange",
                                    timestamp=timestamp,
                                    exchange_url="https://www.coinex.com/exchange/JKC-USDT"
                                )
                    
                except asyncio.TimeoutError:
                    # This is normal, just continue
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("CoinEx WebSocket connection closed")
                    break
                except Exception as e:
                    logger.error(f"Error processing CoinEx message: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Error in CoinEx WebSocket connection: {e}")
        
        finally:
            # Clean up
            if websocket and websocket.close_code is None:
                await websocket.close()
            
            # Don't retry if we're shutting down
            if not running:
                break
                
            # Exponential backoff for reconnection
            logger.info(f"Reconnecting to CoinEx WebSocket in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)

async def ascendex_websocket():
    """Connect to AscendEX WebSocket API and process trade data."""
    global LAST_TRANS_ASENDEX, running
    uri = "wss://ascendex.com/api/pro/v1/stream"
    
    # For exponential backoff
    retry_delay = 5
    max_retry_delay = 60
    
    # Check if API keys are configured
    if not CONFIG.get("ascendex_access_id") or not CONFIG.get("ascendex_secret_key"):
        logger.warning("AscendEX API keys not configured, skipping AscendEX WebSocket")
        return
    
    while running:
        websocket = None
        try:
            websocket = await websockets.connect(uri, ping_interval=30)
            logger.debug(f"Connected to AscendEX WebSocket at {uri}")
            
            # Subscribe to JKC/USDT trades
            subscribe_msg = {
                "op": "sub",
                "ch": "trades:JKC/USDT"
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.debug("Subscribed to JKC/USDT trades on AscendEX")
            
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
                        trades = response["data"]
                        
                        for trade in trades:
                            # Extract trade details
                            price = float(trade["p"])
                            quantity = float(trade["q"])
                            sum_value = price * quantity
                            timestamp = int(trade["ts"])
                            
                            # Only process trades newer than the last one
                            if timestamp > LAST_TRANS_ASENDEX:
                                LAST_TRANS_ASENDEX = timestamp
                                
                                # Process the trade
                                await process_message(
                                    price=price,
                                    quantity=quantity,
                                    sum_value=sum_value,
                                    exchange="AscendEX Exchange",
                                    timestamp=timestamp,
                                    exchange_url="https://ascendex.com/en/cashtrade-spottrading/usdt/jkc"
                                )
                    
                except asyncio.TimeoutError:
                    # This is normal, just continue
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("AscendEX WebSocket connection closed")
                    break
                except Exception as e:
                    logger.error(f"Error processing AscendEX message: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Error in AscendEX WebSocket connection: {e}")
        
        finally:
            # Clean up
            if websocket and websocket.close_code is None:
                await websocket.close()
            
            # Don't retry if we're shutting down
            if not running:
                break
                
            # Exponential backoff for reconnection
            logger.info(f"Reconnecting to AscendEX WebSocket in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)

async def process_message(price, quantity, sum_value, exchange, timestamp, exchange_url):
    """Process a trade message and send notification if it meets criteria."""
    global PHOTO, PENDING_TRADES, LAST_AGGREGATION_CHECK
    
    # Log all trades for debugging
    logger.info(f"Processing trade: {exchange} - {quantity} JKC at {price} USDT (Total: {sum_value} USDT)")

    # Update threshold based on volume
    await update_threshold()

    # Check if aggregation is enabled
    aggregation_enabled = CONFIG.get("trade_aggregation", {}).get("enabled", True)

    if not aggregation_enabled or TRADE_AGGREGATION_WINDOW <= 0:
        # If aggregation is disabled, apply threshold check and send alert immediately if it passes
        if sum_value >= VALUE_REQUIRE:
            logger.info(f"Sending immediate alert for trade: {sum_value} USDT (threshold: {VALUE_REQUIRE})")
            await send_alert(price, quantity, sum_value, exchange, timestamp, exchange_url)
        else:
            logger.info(f"Trade below threshold: {sum_value} USDT < {VALUE_REQUIRE} USDT")
        return
    
    # For aggregation, we'll use a simpler approach - just aggregate by exchange and time window
    # This should catch sweep orders better
    current_time = int(time.time())
    window_key = int(current_time / TRADE_AGGREGATION_WINDOW)
    buyer_id = f"{exchange}_{window_key}"

    # Initialize exchange dict if not exists
    if exchange not in PENDING_TRADES:
        PENDING_TRADES[exchange] = {}

    # Add trade to pending trades (regardless of individual threshold)
    if buyer_id not in PENDING_TRADES[exchange]:
        PENDING_TRADES[exchange][buyer_id] = []

    PENDING_TRADES[exchange][buyer_id].append({
        'price': price,
        'quantity': quantity,
        'sum_value': sum_value,
        'timestamp': timestamp,
        'exchange': exchange,
        'exchange_url': exchange_url
    })

    # Log the pending trades for this buyer
    total_pending = sum(t['sum_value'] for t in PENDING_TRADES[exchange][buyer_id])
    logger.info(f"Added to pending trades: {buyer_id} - Total now: {total_pending:.2f} USDT (threshold: {VALUE_REQUIRE} USDT)")
    
    # If the total already exceeds the threshold, process it immediately
    if total_pending >= VALUE_REQUIRE:
        logger.info(f"Pending trades exceed threshold, processing immediately: {total_pending} USDT")
        trades = PENDING_TRADES[exchange][buyer_id]
        
        # Calculate aggregated values
        total_quantity = sum(trade['quantity'] for trade in trades)
        avg_price = total_pending / total_quantity if total_quantity > 0 else 0
        latest_timestamp = max(trade['timestamp'] for trade in trades)
        
        # Send the alert
        await send_alert(
            avg_price, 
            total_quantity, 
            total_pending, 
            exchange, 
            latest_timestamp, 
            trades[0]['exchange_url'],
            len(trades)
        )
        
        # Clear these trades
        del PENDING_TRADES[exchange][buyer_id]
        
        # If the exchange dict is now empty, remove it
        if not PENDING_TRADES[exchange]:
            del PENDING_TRADES[exchange]
    
    # Check if it's time to process other aggregated trades
    if current_time - LAST_AGGREGATION_CHECK >= 1:  # Check every second
        LAST_AGGREGATION_CHECK = current_time
        await process_aggregated_trades()

async def process_aggregated_trades():
    """Process any pending aggregated trades that are ready."""
    global PENDING_TRADES
    
    current_time = int(time.time())
    current_window = int(current_time / TRADE_AGGREGATION_WINDOW)
    
    # Make a copy of the exchanges to avoid modification during iteration
    exchanges = list(PENDING_TRADES.keys())
    
    for exchange in exchanges:
        # Make a copy of the buyer_ids to avoid modification during iteration
        buyer_ids = list(PENDING_TRADES[exchange].keys())
        
        for buyer_id in buyer_ids:
            # Check if this window has expired
            window_key = int(buyer_id.split('_')[1])
            
            if window_key < current_window:
                # This window has expired, process the trades
                trades = PENDING_TRADES[exchange][buyer_id]
                
                # Calculate total value
                total_value = sum(trade['sum_value'] for trade in trades)
                
                # If the total exceeds the threshold, send an alert
                if total_value >= VALUE_REQUIRE:
                    # Calculate aggregated values
                    total_quantity = sum(trade['quantity'] for trade in trades)
                    avg_price = total_value / total_quantity if total_quantity > 0 else 0
                    latest_timestamp = max(trade['timestamp'] for trade in trades)
                    
                    logger.info(f"Processing aggregated trades: {len(trades)} trades, {total_quantity} JKC, {total_value} USDT")
                    
                    # Send the alert
                    await send_alert(
                        avg_price, 
                        total_quantity, 
                        total_value, 
                        f"{exchange} (Aggregated)", 
                        latest_timestamp, 
                        trades[0]['exchange_url'],
                        len(trades)
                    )
                else:
                    logger.info(f"Aggregated trades below threshold: {total_value} USDT < {VALUE_REQUIRE} USDT")
                
                # Remove these trades
                del PENDING_TRADES[exchange][buyer_id]
                
                # If the exchange dict is now empty, remove it
                if not PENDING_TRADES[exchange]:
                    del PENDING_TRADES[exchange]

async def send_alert(price, quantity, sum_value, exchange, timestamp, exchange_url, num_trades=1):
    """Send an alert to all active chats."""
    global PHOTO
    
    # Format the message
    dt_object = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
    vietnam_tz = timezone(timedelta(hours=7))
    dt_vietnam = dt_object.astimezone(vietnam_tz)
    formatted_time = dt_vietnam.strftime("%H:%M:%S %d/%m/%Y")
    
    # Calculate magnitude ratio for scaling
    magnitude_ratio = sum_value / VALUE_REQUIRE
    
    # Calculate magnitude indicator (number of green square emojis)
    magnitude_count = min(100, max(1, int(magnitude_ratio * 10)))
    
    # Create rows of emojis (10 per row for readability)
    magnitude_rows = []
    for i in range(0, magnitude_count, 10):
        row_count = min(10, magnitude_count - i)
        magnitude_rows.append("🟩" * row_count)
    
    magnitude_indicator = "\n".join(magnitude_rows)
    
    # Dynamic alert text based on transaction size
    if magnitude_ratio >= 10:
        alert_text = "🐋🐋🐋 <b>MASSIVE WHALE TRANSACTION DETECTED!!!</b> 🐋🐋🐋"
    elif magnitude_ratio >= 5:
        alert_text = "🔥🔥 <b>HUGE Transaction LFG!!!</b> 🔥🔥"
    elif magnitude_ratio >= 3:
        alert_text = "🔥 <b>MAJOR Buy Ahoy Junkies!</b> 🔥"
    elif magnitude_ratio >= 2:
        alert_text = "💥 <b>SIGNIFICANT Transaction Alert!</b> 💥"
    else:
        alert_text = "🚨 <b>Buy Transaction Detected</b> 🚨"
    
    # Add special emoji for sweep orders
    if "Sweep" in exchange and "Sweep Buy" in exchange:
        alert_text = alert_text.replace("TRANSACTION", "SWEEP BUY")
        alert_text = alert_text.replace("Transaction", "Sweep Buy")
        alert_text = alert_text.replace("Buy", "Sweep Buy")
    
    message = (
        f"{magnitude_indicator}\n\n"
        f"{alert_text}\n\n"
        f"💰 <b>Amount:</b> {quantity:.2f} JKC\n"
        f"💵 <b>Price:</b> {price:.6f} USDT\n"
        f"💲 <b>Total Value:</b> {sum_value:.2f} USDT\n"
        f"🏦 <b>Exchange:</b> {exchange}\n"
    )
    
    # Add number of trades if it's an aggregated alert
    if num_trades > 1:
        message += f"🔄 <b>Trades:</b> {num_trades}\n"
    
    message += f"⏰ <b>Time:</b> {formatted_time}\n"
    
    # Create inline button to exchange
    button = InlineKeyboardButton(text=f"Trade on {exchange.split(' ')[0]}", url=exchange_url)
    keyboard = InlineKeyboardMarkup([[button]])
    
    # Send to all active chats
    bot = Bot(token=BOT_TOKEN)
    for chat_id in ACTIVE_CHAT_IDS:
        try:
            if PHOTO:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=PHOTO,
                    caption=message,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        except Exception as e:
            print(f"Error sending message to chat {chat_id}: {e}")

async def chart_command(update: Update, context: CallbackContext) -> None:
    """Generate and send a price chart."""
    await update.message.reply_text("Generating chart, please wait...")
    
    try:
        # Get historical trades
        trades = await get_nonkyc_trades()
        
        if not trades:
            await update.message.reply_text("No trade data available to generate chart.")
            return
            
        # Convert to DataFrame
        df = pd.DataFrame(trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['price'] = df['price'].astype(float)
        df['quantity'] = df['quantity'].astype(float)
        
        # Sort by timestamp
        df = df.sort_values('timestamp')
        
        # Create figure
        fig = go.Figure(data=[go.Scatter(
            x=df['timestamp'],
            y=df['price'],
            mode='lines',
            name='JKC/USDT',
            line=dict(color='green', width=2)
        )])
        
        # Update layout
        fig.update_layout(
            title='JKC/USDT Price Chart (NonKYC)',
            xaxis_title='Time',
            yaxis_title='Price (USDT)',
            template='plotly_dark',
            autosize=True,
            width=1000,
            height=600
        )
        
        # Save to temporary file
        chart_path = 'temp_chart.png'
        fig.write_image(chart_path)
        
        # Send chart
        with open(chart_path, 'rb') as f:
            await update.message.reply_photo(photo=f)
            
        # Clean up
        os.remove(chart_path)
        
    except Exception as e:
        await update.message.reply_text(f"Error generating chart: {str(e)}")

def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org')
        return response.text
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"

async def get_ipwan_command(update: Update, context: CallbackContext) -> None:
    """Get public IP address - admin only command."""
    user_id = update.effective_user.id
    logger.info(f"ipwan command called by user {user_id}")

    if await is_admin(update, context):
        logger.info(f"User {user_id} has admin permissions, getting IP address")
        await update.message.reply_text(get_public_ip())
    else:
        logger.warning(f"User {user_id} tried to use ipwan command without admin permissions")
        await update.message.reply_text("You do not have permission to use this command.")

async def set_minimum_command(update: Update, context: CallbackContext) -> int:
    """Command to set the minimum transaction value to alert on."""
    user_id = update.effective_user.id
    logger.info(f"setmin command called by user {user_id}")

    if not await is_admin(update, context):
        logger.warning(f"User {user_id} tried to use setmin command without admin permissions")
        await update.message.reply_text("You do not have permission to set the minimum value.")
        return ConversationHandler.END

    logger.info(f"User {user_id} has admin permissions, proceeding with setmin command")
    await update.message.reply_text(
        "Please enter the new minimum value in USDT.\n"
        f"Current value: {VALUE_REQUIRE} USDT"
    )
    return INPUT_NUMBER

async def set_minimum_input(update: Update, context: CallbackContext) -> int:
    global VALUE_REQUIRE, CONFIG
    try:
        value = float(update.message.text)
        if value <= 0:
            await update.message.reply_text("Value must be greater than 0. Please try again.")
            return INPUT_NUMBER
            
        VALUE_REQUIRE = value
        CONFIG["value_require"] = value
        save_config(CONFIG)
        await update.message.reply_text(f"Minimum value set to {value} USDT")
    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number.")
        return INPUT_NUMBER
    return ConversationHandler.END

async def set_image_command(update: Update, context: CallbackContext) -> int:
    """Command to set the image used in alerts."""
    user_id = update.effective_user.id
    logger.info(f"setimage command called by user {user_id}")

    if not await is_admin(update, context):
        logger.warning(f"User {user_id} tried to use setimage command without admin permissions")
        await update.message.reply_text("You do not have permission to set the image.")
        return ConversationHandler.END

    logger.info(f"User {user_id} has admin permissions, proceeding with setimage command")
    await update.message.reply_text(
        "Please send the image you want to use for alerts.\n"
        "The image should be clear and appropriate."
    )
    return INPUT_IMAGE

async def set_image_input(update: Update, context: CallbackContext) -> int:
    global PHOTO, CONFIG
    photo = update.message.photo[-1]
    file = await photo.get_file()
    PHOTO = InputFile(io.BytesIO(await file.download_as_bytearray()), filename=IMAGE_PATH)
    await file.download_to_drive(IMAGE_PATH)
    await update.message.reply_text("Image updated successfully!")
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel and end the conversation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def start_bot(update: Update, context: CallbackContext) -> None:
    global ACTIVE_CHAT_IDS, CONFIG

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Log the IDs for debugging
    logger.info(f"Start command - User ID: {user_id}, Chat ID: {chat_id}")

    # Check if user is admin or bot owner
    is_user_admin = False
    try:
        if user_id == BOT_OWNER or user_id == BY_PASS:
            is_user_admin = True
        elif chat_id < 0:  # Group chat
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            is_user_admin = chat_member.status in ["administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        is_user_admin = False

    if is_user_admin:
        if chat_id not in ACTIVE_CHAT_IDS:
            ACTIVE_CHAT_IDS.append(chat_id)
            CONFIG["active_chat_ids"] = ACTIVE_CHAT_IDS
            save_config(CONFIG)
            
            # Get aggregation status
            aggregation_enabled = CONFIG.get("trade_aggregation", {}).get("enabled", True)
            aggregation_window = CONFIG.get("trade_aggregation", {}).get("window_seconds", 3)
            
            # Send welcome message with commands
            welcome_text = (
                "🎉 <b>JunkCoin Alert Bot Started!</b> 🎉\n\n"
                "You will now receive alerts for significant JKC transactions.\n\n"
                "<b>Current threshold:</b> {:.2f} USDT\n"
                "<b>Dynamic threshold:</b> {}\n"
                "<b>Trade aggregation:</b> {} (window: {}s)\n\n"
                "Type /help to see all available commands."
            ).format(
                VALUE_REQUIRE,
                "Enabled" if CONFIG['dynamic_threshold']['enabled'] else "Disabled",
                "Enabled" if aggregation_enabled else "Disabled",
                aggregation_window
            )
            
            # Create buttons for quick access
            keyboard = [
                [
                    InlineKeyboardButton("📊 Check Price", callback_data="cmd_price"),
                    InlineKeyboardButton("📈 View Chart", callback_data="cmd_chart")
                ],
                [
                    InlineKeyboardButton("⚙️ Configuration", callback_data="cmd_config"),
                    InlineKeyboardButton("❓ Help", callback_data="cmd_help")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "Bot already running! Type /help to see available commands.",
                parse_mode="HTML"
            )
    else:
        await update.message.reply_text("You need to be an admin to start the bot.")

async def stop_bot(update: Update, context: CallbackContext) -> None:
    global ACTIVE_CHAT_IDS, CONFIG
    
    # Make sure we're getting the correct user ID
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None and update.message and update.message.from_user:
        user_id = update.message.from_user.id
    
    chat_id = update.effective_chat.id
    
    # Debug log
    logger.info(f"Stop command accessed by user ID: {user_id}, BOT_OWNER: {BOT_OWNER}")

    # Always allow the bot owner to stop the bot
    if int(user_id) == int(BOT_OWNER):
        if chat_id in ACTIVE_CHAT_IDS:
            ACTIVE_CHAT_IDS.remove(chat_id)
            CONFIG["active_chat_ids"] = ACTIVE_CHAT_IDS
            save_config(CONFIG)
            await update.message.reply_text("Bot stopped")
        else:
            await update.message.reply_text("Bot not running")
        return

    # For non-owners, check if they're an admin
    chat_member = await context.bot.get_chat_member(chat_id, user_id)
    if chat_member.status in ["administrator", "creator"]:
        if chat_id in ACTIVE_CHAT_IDS:
            ACTIVE_CHAT_IDS.remove(chat_id)
            CONFIG["active_chat_ids"] = ACTIVE_CHAT_IDS
            save_config(CONFIG)
            await update.message.reply_text("Bot stopped")
        else:
            await update.message.reply_text("Bot not running")
    else:
        await update.message.reply_text("You need to be an admin to stop the bot.")

async def check_price(update: Update, context: CallbackContext) -> None:
    global USER_CHECK_PRICE

    exist = False
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    for item in USER_CHECK_PRICE:
        if item.get('user_id') == user_id:
            exist = True
            if int(item["time"]) > int(time.time() * 1000):
                await update.message.reply_text("Request limit within 30sec")
                return
            else:
                item["time"] = int(time.time() * 1000) + 30000

    if not exist:
        USER_CHECK_PRICE.append(
            {'user_id': user_id, 'time': (int(time.time() * 1000) + 30000)})

    # Get market data for current price
    market_data = await get_nonkyc_ticker()
    if not market_data:
        await update.message.reply_text("Error fetching market data. Please try again later.")
        return
        
    current_price = market_data.get("lastPrice", "0")
    
    # Get market cap
    response = requests.get(
        "https://api-junkpool.blockraid.io/list/summary/mainnet")
    marketcap = int(float(current_price) *
                    float(response.json()['data']['supply']))

    button1 = InlineKeyboardButton(
        text="CoinMarketCap", url="https://coinmarketcap.com/currencies/junkcoin")
    button2 = InlineKeyboardButton(
        text="CoinGecko", url="https://www.coingecko.com/en/coins/junkcoin")
    keyboard = InlineKeyboardMarkup([
        [button1, button2]
    ])

    await update.message.reply_text(
        f"⛵️ <b>JunkCoin (JKC) Price</b> ⛵️\n\n"
        f"💵 <b>Price:</b> {current_price} USDT\n"
        f"📈 <b>Market Cap:</b> <b>${marketcap:,}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

async def config_command(update: Update, context: CallbackContext) -> int:
    """Command to access the configuration menu."""
    if not await is_admin(update, context):
        await update.message.reply_text("You do not have permission to access configuration.")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("Set Minimum Value", callback_data="set_min")],
        [InlineKeyboardButton("Set Image", callback_data="set_img")],
        [InlineKeyboardButton("Dynamic Threshold Settings", callback_data="dynamic_config")],
        [InlineKeyboardButton("Trade Aggregation Settings", callback_data="aggregation_config")],
        [InlineKeyboardButton("Show Current Settings", callback_data="show_config")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Bot Configuration Menu:", reply_markup=reply_markup)
    return CONFIG_MENU

async def button_callback(update: Update, context: CallbackContext) -> int:
    """Handle button presses in the configuration menu."""
    query = update.callback_query
    await query.answer()
    
    # Check if user is admin
    if not await is_admin(update, context):
        await query.edit_message_text("You do not have permission to access configuration.")
        return ConversationHandler.END
    
    if query.data == "set_min":
        await query.edit_message_text("Please enter the new minimum value in USDT:")
        return INPUT_NUMBER
    elif query.data == "set_img":
        await query.edit_message_text("Please send the image you want to use for alerts:")
        return INPUT_IMAGE
    elif query.data == "dynamic_config":
        # Show dynamic threshold configuration options
        keyboard = [
            [InlineKeyboardButton("Enable/Disable", callback_data="toggle_dynamic")],
            [InlineKeyboardButton("Set Base Value", callback_data="set_base_value")],
            [InlineKeyboardButton("Set Volume Multiplier", callback_data="set_volume_mult")],
            [InlineKeyboardButton("Set Min Threshold", callback_data="set_min_threshold")],
            [InlineKeyboardButton("Set Max Threshold", callback_data="set_max_threshold")],
            [InlineKeyboardButton("Back to Main Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Show current settings
        dynamic_config = CONFIG.get("dynamic_threshold", {})
        enabled = dynamic_config.get("enabled", False)
        base_value = dynamic_config.get("base_value", 300)
        volume_mult = dynamic_config.get("volume_multiplier", 0.05)
        min_threshold = dynamic_config.get("min_threshold", 100)
        max_threshold = dynamic_config.get("max_threshold", 1000)
        
        message = (
            "Dynamic Threshold Configuration:\n\n"
            f"Status: {'Enabled' if enabled else 'Disabled'}\n"
            f"Base Value: {base_value} USDT\n"
            f"Volume Multiplier: {volume_mult}\n"
            f"Minimum Threshold: {min_threshold} USDT\n"
            f"Maximum Threshold: {max_threshold} USDT\n\n"
            "Select an option to modify:"
        )
        
        await query.edit_message_text(message, reply_markup=reply_markup)
        return DYNAMIC_CONFIG
    elif query.data == "aggregation_config":
        # Show trade aggregation configuration options
        keyboard = [
            [InlineKeyboardButton("Enable/Disable", callback_data="toggle_aggregation")],
            [InlineKeyboardButton("Set Window (seconds)", callback_data="set_window_seconds")],
            [InlineKeyboardButton("Back to Main Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Show current settings
        agg_config = CONFIG.get("trade_aggregation", {})
        enabled = agg_config.get("enabled", True)
        window = agg_config.get("window_seconds", 3)
        
        message = (
            "Trade Aggregation Configuration:\n\n"
            f"Status: {'Enabled' if enabled else 'Disabled'}\n"
            f"Window: {window} seconds\n\n"
            "Select an option to modify:"
        )
        
        await query.edit_message_text(message, reply_markup=reply_markup)
        return DYNAMIC_CONFIG  # Reuse the same state
    elif query.data == "show_config":
        # Show current configuration
        dynamic_config = CONFIG.get("dynamic_threshold", {})
        agg_config = CONFIG.get("trade_aggregation", {})
        
        message = (
            "Current Bot Configuration:\n\n"
            f"Minimum Value: {VALUE_REQUIRE} USDT\n"
            f"Bot Owner ID: {BOT_OWNER}\n"
            f"Bypass ID: {BY_PASS}\n"
            f"Active Chats: {len(ACTIVE_CHAT_IDS)}\n\n"
            "Dynamic Threshold:\n"
            f"- Enabled: {'Yes' if dynamic_config.get('enabled', False) else 'No'}\n"
            f"- Base Value: {dynamic_config.get('base_value', 300)} USDT\n"
            f"- Volume Multiplier: {dynamic_config.get('volume_multiplier', 0.05)}\n"
            f"- Min Threshold: {dynamic_config.get('min_threshold', 100)} USDT\n"
            f"- Max Threshold: {dynamic_config.get('max_threshold', 1000)} USDT\n\n"
            "Trade Aggregation:\n"
            f"- Enabled: {'Yes' if agg_config.get('enabled', True) else 'No'}\n"
            f"- Window: {agg_config.get('window_seconds', 3)} seconds\n"
        )
        
        keyboard = [[InlineKeyboardButton("Back to Main Menu", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
        return CONFIG_MENU
    elif query.data == "back_to_main":
        # Return to main config menu
        keyboard = [
            [InlineKeyboardButton("Set Minimum Value", callback_data="set_min")],
            [InlineKeyboardButton("Set Image", callback_data="set_img")],
            [InlineKeyboardButton("Dynamic Threshold Settings", callback_data="dynamic_config")],
            [InlineKeyboardButton("Trade Aggregation Settings", callback_data="aggregation_config")],
            [InlineKeyboardButton("Show Current Settings", callback_data="show_config")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Bot Configuration Menu:", reply_markup=reply_markup)
        return CONFIG_MENU
    
    # Handle dynamic threshold configuration options
    elif query.data == "toggle_dynamic":
        CONFIG["dynamic_threshold"]["enabled"] = not CONFIG["dynamic_threshold"].get("enabled", False)
        save_config(CONFIG)
        await query.edit_message_text(
            f"Dynamic threshold {'enabled' if CONFIG['dynamic_threshold']['enabled'] else 'disabled'}. "
            "Returning to configuration menu..."
        )
        # Return to config menu after a short delay
        await asyncio.sleep(2)
        return await button_callback(update, context)
    
    # Handle other dynamic config options...
    
    return CONFIG_MENU

async def handle_dynamic_config(update: Update, context: CallbackContext, data: str) -> int:
    query = update.callback_query
    global CONFIG
    
    if data == "dynamic_enable":
        CONFIG["dynamic_threshold"]["enabled"] = True
        save_config(CONFIG)
        await query.edit_message_text("Dynamic threshold enabled. Returning to config menu...")
        await asyncio.sleep(2)
        return await config_command(update, context)
    elif data == "dynamic_disable":
        CONFIG["dynamic_threshold"]["enabled"] = False
        save_config(CONFIG)
        await query.edit_message_text("Dynamic threshold disabled. Returning to config menu...")
        await asyncio.sleep(2)
        return await config_command(update, context)
    elif data == "dynamic_base":
        await query.edit_message_text("Please enter the new base value for dynamic threshold:")
        context.user_data["config_type"] = "base_value"
        return DYNAMIC_CONFIG
    elif data == "dynamic_mult":
        await query.edit_message_text("Please enter the new volume multiplier for dynamic threshold:")
        context.user_data["config_type"] = "volume_multiplier"
        return DYNAMIC_CONFIG
    
    return DYNAMIC_CONFIG

async def dynamic_config_input(update: Update, context: CallbackContext) -> int:
    try:
        global CONFIG
        config_type = context.user_data.get("config_type")
        
        if config_type == "base_value":
            value = int(update.message.text)
            CONFIG["dynamic_threshold"]["base_value"] = value
        elif config_type == "volume_multiplier":
            value = float(update.message.text)
            CONFIG["dynamic_threshold"]["volume_multiplier"] = value
        
        save_config(CONFIG)
        await update.message.reply_text(f"Updated {config_type} to {value}. Use /config to continue configuration.")
    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a valid number.")
        return DYNAMIC_CONFIG
    
    return ConversationHandler.END

async def set_api_keys_command(update: Update, context: CallbackContext) -> int:
    """Command to set API keys for exchanges - bot owner only."""
    user_id = update.effective_user.id
    if user_id != BOT_OWNER:  # Only bot owner can set API keys (not even BY_PASS for security)
        await update.message.reply_text("You do not have permission to set API keys.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("Set CoinEx API Keys", callback_data="set_coinex_keys")],
        [InlineKeyboardButton("Set Ascendex API Keys", callback_data="set_ascendex_keys")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select which API keys to set:", reply_markup=reply_markup)
    return CONFIG_MENU

async def set_api_key_command(update: Update, context: CallbackContext) -> int:
    """Alias for set_api_keys_command (singular form)."""
    return await set_api_keys_command(update, context)

async def api_keys_callback(update: Update, context: CallbackContext) -> int:
    """Handle API key selection."""
    query = update.callback_query
    await query.answer()
    
    # Only bot owner can set API keys
    if update.effective_user.id != BOT_OWNER:
        await query.edit_message_text("You do not have permission to set API keys.")
        return ConversationHandler.END
    
    # Store which exchange we're setting keys for
    context.user_data["exchange"] = query.data.replace("set_", "").replace("_keys", "")
    
    await query.edit_message_text(
        f"Please enter your {context.user_data['exchange'].upper()} API keys in the format:\n\n"
        "access_id:secret_key\n\n"
        "For example: ABC123:XYZ456\n\n"
        "Type /cancel to abort."
    )
    return INPUT_API_KEYS

async def set_api_keys_input(update: Update, context: CallbackContext) -> int:
    """Process API key input."""
    global CONFIG
    
    # Only bot owner can set API keys
    if update.effective_user.id != BOT_OWNER:
        await update.message.reply_text("You do not have permission to set API keys.")
        return ConversationHandler.END
    
    # Get the exchange from user_data
    exchange = context.user_data.get("exchange", "")
    if not exchange:
        await update.message.reply_text("Error: Exchange not specified. Please try again.")
        return ConversationHandler.END
    
    # Parse the input
    text = update.message.text
    try:
        access_id, secret_key = text.strip().split(":", 1)
        
        # Update the config
        CONFIG[f"{exchange}_access_id"] = access_id
        CONFIG[f"{exchange}_secret_key"] = secret_key
        save_config(CONFIG)
        
        # Delete the message containing the API keys for security
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete message with API keys: {e}")
        
        await update.message.reply_text(
            f"{exchange.upper()} API keys updated successfully.\n\n"
            "⚠️ For security, your message with the API keys has been deleted."
        )
    except ValueError:
        await update.message.reply_text(
            "Invalid format. Please use the format: access_id:secret_key\n"
            "Try again or type /cancel to abort."
        )
        return INPUT_API_KEYS
    
    return ConversationHandler.END

async def help_command(update: Update, context: CallbackContext) -> None:
    """Show help information and available commands."""
    help_text = (
        "🤖 <b>JunkCoin Alert Bot Commands</b> 🤖\n\n"
        "<b>Basic Commands:</b>\n"
        "/start - Start receiving alerts in this chat\n"
        "/stop - Stop receiving alerts in this chat\n"
        "/price - Check current JKC price\n"
        "/chart - Generate and send a price chart\n"
        "/help - Show this help message\n\n"
        
        "<b>Admin Commands:</b>\n"
        "/config - Access bot configuration menu\n"
        "/setmin - Set minimum transaction value\n"
        "/setimage - Set image for alerts\n"
        "/toggle_aggregation - Toggle trade aggregation\n"
        "/setapikey - Set exchange API keys (owner only)\n"
        "/setapikeys - Set exchange API keys (owner only)\n"
        "/ipwan - Get server's public IP (owner only)\n\n"
        
        "<b>About:</b>\n"
        "This bot monitors JKC transactions across exchanges and sends alerts for significant trades."
    )
    
    # Create buttons for quick access to common commands
    keyboard = [
        [
            InlineKeyboardButton("📊 Price", callback_data="cmd_price"),
            InlineKeyboardButton("📈 Chart", callback_data="cmd_chart")
        ],
        [
            InlineKeyboardButton("⚙️ Config", callback_data="cmd_config"),
            InlineKeyboardButton("🛑 Stop Bot", callback_data="cmd_stop")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def button_command_callback(update: Update, context: CallbackContext) -> None:
    """Handle button commands from the help menu."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cmd_price":
        # Create a new update object with the message from the callback query
        new_update = Update(
            update_id=update.update_id,
            message=query.message,
            callback_query=None
        )
        await check_price(new_update, context)
    elif query.data == "cmd_chart":
        new_update = Update(
            update_id=update.update_id,
            message=query.message,
            callback_query=None
        )
        await chart_command(new_update, context)
    elif query.data == "cmd_config":
        if update.effective_user.id in (BY_PASS, BOT_OWNER):
            new_update = Update(
                update_id=update.update_id,
                message=query.message,
                callback_query=None
            )
            await config_command(new_update, context)
        else:
            await query.edit_message_text("You don't have permission to access configuration.")
    elif query.data == "cmd_stop":
        new_update = Update(
            update_id=update.update_id,
            message=query.message,
            callback_query=None
        )
        await stop_bot(new_update, context)
    elif query.data == "cmd_help":
        new_update = Update(
            update_id=update.update_id,
            message=query.message,
            callback_query=None
        )
        await help_command(new_update, context)

async def toggle_aggregation(update: Update, context: CallbackContext) -> None:
    """Toggle trade aggregation on/off - admin only command."""
    global CONFIG
    user_id = update.effective_user.id
    logger.info(f"toggle_aggregation command called by user {user_id}")

    if await is_admin(update, context):
        logger.info(f"User {user_id} has admin permissions, toggling aggregation")
        # Initialize trade_aggregation if it doesn't exist
        if "trade_aggregation" not in CONFIG:
            CONFIG["trade_aggregation"] = {"enabled": True, "window": TRADE_AGGREGATION_WINDOW}

        # Toggle the enabled state
        CONFIG["trade_aggregation"]["enabled"] = not CONFIG["trade_aggregation"]["enabled"]

        # Save the config
        save_config(CONFIG)

        # Inform the user
        state = "enabled" if CONFIG["trade_aggregation"]["enabled"] else "disabled"
        logger.info(f"Trade aggregation toggled to: {state}")
        await update.message.reply_text(f"Trade aggregation is now {state}.")
    else:
        logger.warning(f"User {user_id} tried to use toggle_aggregation command without admin permissions")
        await update.message.reply_text("You do not have permission to use this command.")

async def debug_command(update: Update, context: CallbackContext) -> None:
    """Debug command to show user and chat IDs."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Get chat type
    chat_type = update.effective_chat.type

    # Check if user is admin using centralized function
    is_user_admin = await is_admin(update, context)

    # Get bot info
    bot_info = await context.bot.get_me()

    debug_info = (
        "🔍 <b>Debug Information</b>\n\n"
        f"👤 <b>Your User ID:</b> {user_id}\n"
        f"💬 <b>Chat ID:</b> {chat_id}\n"
        f"💬 <b>Chat Type:</b> {chat_type}\n"
        f"👑 <b>Admin Status:</b> {'Yes' if is_user_admin else 'No'}\n\n"
        f"🤖 <b>Bot ID:</b> {bot_info.id}\n"
        f"🤖 <b>Bot Username:</b> @{bot_info.username}\n\n"
        f"⚙️ <b>Config Values:</b>\n"
        f"- Bot Owner ID: {BOT_OWNER}\n"
        f"- Bypass ID: {BY_PASS}\n"
    )

    await update.message.reply_text(debug_info, parse_mode="HTML")

async def heartbeat():
    """Send periodic heartbeat messages to show the bot is running."""
    global running
    counter = 0
    while running:
        counter += 1
        if counter % 60 == 0:  # Log every minute
            logger.info(f"Bot running - Monitoring trades with threshold: {VALUE_REQUIRE} USDT")
        await asyncio.sleep(1)

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # Add debug logging for startup
    logger.info(f"Starting bot with token: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]}")
    logger.info(f"Bot owner ID: {BOT_OWNER}")
    logger.info(f"Bypass ID: {BY_PASS}")
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_bot))
    application.add_handler(CommandHandler("stop", stop_bot))
    application.add_handler(CommandHandler("price", check_price))
    application.add_handler(CommandHandler("chart", chart_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ipwan", get_ipwan_command))
    application.add_handler(CommandHandler("toggle_aggregation", toggle_aggregation))
    application.add_handler(CommandHandler("debug", debug_command))  # This should now be defined
    
    # Add conversation handlers for admin commands
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setmin", set_minimum_command)],
        states={
            INPUT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_minimum_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setimage", set_image_command)],
        states={
            INPUT_IMAGE: [MessageHandler(filters.PHOTO, set_image_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    
    # Add the config conversation handler
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("config", config_command)],
        states={
            CONFIG_MENU: [
                CallbackQueryHandler(button_callback)
            ],
            INPUT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_minimum_input)],
            INPUT_IMAGE: [MessageHandler(filters.PHOTO, set_image_input)],
            DYNAMIC_CONFIG: [
                CallbackQueryHandler(button_callback)
            ],
            INPUT_API_KEYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_api_keys_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    
    # Add the API keys conversation handler
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setapikeys", set_api_keys_command)],
        states={
            CONFIG_MENU: [CallbackQueryHandler(api_keys_callback, pattern='^set_coinex_keys$|^set_ascendex_keys$')],
            INPUT_API_KEYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_api_keys_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    # Add the API key conversation handler (singular form)
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setapikey", set_api_key_command)],
        states={
            CONFIG_MENU: [CallbackQueryHandler(api_keys_callback, pattern='^set_coinex_keys$|^set_ascendex_keys$')],
            INPUT_API_KEYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_api_keys_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    
    # Add callback query handler for button commands
    application.add_handler(CallbackQueryHandler(button_command_callback, pattern="^cmd_"))
    
    # Start the websocket listeners in separate tasks
    loop = asyncio.get_event_loop()
    
    # Start all background tasks
    try:
        loop.create_task(nonkyc_websocket())
        loop.create_task(coinex_websocket())
        loop.create_task(ascendex_websocket())
        loop.create_task(nonkyc_orderbook_websocket())
        loop.create_task(heartbeat())
        logger.info("Started all background tasks including real-time orderbook sweep detection")
    except Exception as e:
        logger.warning(f"Could not start some background tasks: {e}")
    
    logger.info("Bot started and ready to receive commands!")
    logger.info(f"Monitoring trades with threshold: {VALUE_REQUIRE} USDT")
    logger.info(f"Active in {len(ACTIVE_CHAT_IDS)} chats")
    logger.info("Press Ctrl+C to stop the bot")
    
    # Start the Bot
    application.run_polling()  # Removed the while True loop

if __name__ == "__main__":
    try:
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)

        # Set up file logging
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join("logs", f"telebot_{current_time}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)

        logger.info(f"Logging to file: {log_file}")
        logger.info("Starting JunkCoin Alert Bot...")

        # Configuration is already loaded at module level
        logger.info(f"Configuration loaded: {json.dumps({k: v for k, v in CONFIG.items() if k not in ['bot_token', 'coinex_secret_key', 'ascendex_secret_key']})}")
        
        # Log important startup information
        logger.info(f"Bot owner ID: {BOT_OWNER}")
        logger.info(f"Minimum value threshold: {VALUE_REQUIRE} USDT")
        logger.info(f"Active in {len(ACTIVE_CHAT_IDS)} chats")
        
        # Start the main bot function
        main()
    except Exception as e:
        error_msg = f"Critical error: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        
        # Keep the container running instead of exiting
        logger.info("Bot crashed. Sleeping for 60 seconds before exit to allow container restart...")
        time.sleep(60)
        sys.exit(1)  # Exit with error code so container will restart






