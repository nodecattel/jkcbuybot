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
import random
import glob
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

# Image collection constants
IMAGES_DIR = "images"
SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".gif"]

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
PENDING_TRADES = {}  # {exchange: {buyer_id: [trades]}}
LAST_AGGREGATION_CHECK = time.time()

# Add a debug mode to log all incoming messages
DEBUG_MODE = True

# Add a function to check if a user is an admin
async def is_admin(update: Update, context: CallbackContext) -> bool:
    """Check if the user is an admin or bot owner."""
    # Get user ID with multiple fallback methods to ensure we get the correct one
    user_id = None

    # Try different methods to get the user ID, prioritizing message.from_user
    if update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id
    elif update.effective_user:
        user_id = update.effective_user.id

    if user_id is None:
        logger.error("Could not extract user ID from update")
        return False

    chat_id = update.effective_chat.id

    # Debug logging with more detail
    logger.info(f"Admin check - User ID: {user_id}, Chat ID: {chat_id}, BOT_OWNER: {BOT_OWNER}, BY_PASS: {BY_PASS}")

    # Additional debug info
    if update.message and update.message.from_user:
        logger.info(f"Message from_user ID: {update.message.from_user.id}")
    if update.effective_user:
        logger.info(f"Effective user ID: {update.effective_user.id}")
    if update.callback_query and update.callback_query.from_user:
        logger.info(f"Callback query from_user ID: {update.callback_query.from_user.id}")

    # Bot owner always has admin rights - ensure both are integers for comparison
    if int(user_id) == int(BOT_OWNER) or int(user_id) == int(BY_PASS):
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

def ensure_images_directory():
    """Ensure the images directory exists."""
    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)
        logger.info(f"Created images directory: {IMAGES_DIR}")

def get_image_collection():
    """Get list of all images in the collection."""
    ensure_images_directory()
    images = []
    for ext in SUPPORTED_IMAGE_FORMATS:
        pattern = os.path.join(IMAGES_DIR, f"*{ext}")
        images.extend(glob.glob(pattern))
        # Also check uppercase extensions
        pattern = os.path.join(IMAGES_DIR, f"*{ext.upper()}")
        images.extend(glob.glob(pattern))
    return images

def get_random_image():
    """Get a random image from the collection."""
    images = get_image_collection()

    # If no images in collection, try to use the default image
    if not images:
        if os.path.exists(IMAGE_PATH):
            return IMAGE_PATH
        else:
            logger.warning("No images found in collection and default image doesn't exist")
            return None

    # Return random image from collection
    return random.choice(images)

def load_random_image():
    """Load a random image as InputFile for Telegram."""
    image_path = get_random_image()
    if not image_path:
        return None

    try:
        with open(image_path, 'rb') as photo:
            img = photo.read()
            filename = os.path.basename(image_path)
            return InputFile(io.BytesIO(img), filename=filename)
    except Exception as e:
        logger.error(f"Error loading image {image_path}: {e}")
        return None

# Load image (now using random selection)
try:
    PHOTO = load_random_image()
    if PHOTO is None:
        logger.warning("No images available for alerts")
except Exception as e:
    logger.error(f"Error loading image: {e}")
    PHOTO = None

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

async def get_coinex_trades():
    """Get historical trades from CoinEx API v2."""
    try:
        import requests
        # CoinEx v2 API for historical trades
        url = "https://api.coinex.com/v2/spot/deals"
        params = {
            "market": "JKCUSDT",
            "limit": 1000  # Get last 1000 trades
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and "data" in data:
                # Convert CoinEx v2 format to our standard format
                trades = []
                for trade in data["data"]:
                    trades.append({
                        "id": trade.get("id", ""),
                        "price": trade.get("price", "0"),
                        "quantity": trade.get("amount", "0"),  # CoinEx uses 'amount' for quantity
                        "timestamp": trade.get("created_at", 0),  # CoinEx uses 'created_at' timestamp
                        "side": trade.get("type", "unknown")  # buy/sell
                    })
                return trades
        return []
    except Exception as e:
        logger.warning(f"Error getting CoinEx trades: {e}")
        return []

async def get_coinex_ticker():
    """Get ticker data from CoinEx API v2."""
    try:
        import requests
        # CoinEx v2 API for ticker data
        url = "https://api.coinex.com/v2/spot/ticker"
        params = {
            "market": "JKCUSDT"
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and "data" in data and len(data["data"]) > 0:
                return data["data"][0]  # Return first (and only) market data
        return None
    except Exception as e:
        logger.warning(f"Error getting CoinEx ticker: {e}")
        return None

async def calculate_volume_periods(trades_data):
    """Calculate volume for different time periods from trades data."""
    if not trades_data:
        return {
            "15m": 0,
            "1h": 0,
            "4h": 0,
            "24h": 0
        }

    current_time = time.time() * 1000  # Convert to milliseconds

    # Time periods in milliseconds
    periods = {
        "15m": 15 * 60 * 1000,      # 15 minutes
        "1h": 60 * 60 * 1000,       # 1 hour
        "4h": 4 * 60 * 60 * 1000,   # 4 hours
        "24h": 24 * 60 * 60 * 1000  # 24 hours
    }

    volumes = {}

    for period_name, period_ms in periods.items():
        cutoff_time = current_time - period_ms
        period_volume = 0

        for trade in trades_data:
            # Handle different timestamp formats
            trade_time_ms = 0
            timestamp = trade.get("timestamp", 0)

            if isinstance(timestamp, str):
                # Handle ISO format like '2025-06-21T11:03:23.862Z'
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    trade_time_ms = int(dt.timestamp() * 1000)
                except (ValueError, AttributeError):
                    # If ISO parsing fails, try to extract timestampms
                    trade_time_ms = int(trade.get("timestampms", 0))
            elif isinstance(timestamp, (int, float)):
                # Handle numeric timestamp (assume milliseconds if > 1e10, else seconds)
                if timestamp > 1e10:
                    trade_time_ms = int(timestamp)
                else:
                    trade_time_ms = int(timestamp * 1000)
            else:
                # Fallback to timestampms field or time field
                timestampms = trade.get("timestampms", 0)
                time_field = trade.get("time", 0)
                created_at = trade.get("created_at", 0)

                if timestampms > 0:
                    trade_time_ms = int(timestampms)
                elif time_field > 0:
                    # CoinEx v1 format (seconds)
                    trade_time_ms = int(time_field * 1000)
                elif created_at > 0:
                    # CoinEx v2 format (milliseconds)
                    trade_time_ms = int(created_at)
                else:
                    trade_time_ms = 0

            if trade_time_ms >= cutoff_time:
                # Calculate volume in USDT (price * quantity)
                price = float(trade.get("price", 0))
                # Handle different quantity field names
                quantity = float(trade.get("quantity", trade.get("amount", 0)))
                period_volume += price * quantity

        volumes[period_name] = round(period_volume, 2)

    return volumes

async def calculate_combined_volume_periods():
    """Calculate combined volume from both NonKYC and CoinEx exchanges."""
    try:
        # Get trades from both exchanges
        nonkyc_trades = await get_nonkyc_trades()
        coinex_trades = await get_coinex_trades()

        # Calculate volumes for each exchange
        nonkyc_volumes = await calculate_volume_periods(nonkyc_trades)
        coinex_volumes = await calculate_volume_periods(coinex_trades)

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
        logger.warning(f"Error calculating combined volumes: {e}")
        # Fallback to NonKYC only
        nonkyc_trades = await get_nonkyc_trades()
        nonkyc_volumes = await calculate_volume_periods(nonkyc_trades)
        return {
            "combined": nonkyc_volumes,
            "nonkyc": nonkyc_volumes,
            "coinex": {"15m": 0, "1h": 0, "4h": 0, "24h": 0}
        }

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

    # Get aggregation settings from config
    aggregation_enabled = CONFIG.get("trade_aggregation", {}).get("enabled", True)
    aggregation_window = CONFIG.get("trade_aggregation", {}).get("window_seconds", 8)

    if not aggregation_enabled or aggregation_window <= 0:
        # If aggregation is disabled, apply threshold check and send alert immediately if it passes
        if sum_value >= VALUE_REQUIRE:
            logger.info(f"Sending immediate alert for trade: {sum_value} USDT (threshold: {VALUE_REQUIRE})")
            await send_alert(price, quantity, sum_value, exchange, timestamp, exchange_url)
        else:
            logger.info(f"Trade below threshold: {sum_value} USDT < {VALUE_REQUIRE} USDT")
        return

    # For aggregation, we'll use a simpler approach - just aggregate by exchange within the time window
    # Use a single aggregation key per exchange to catch all trades together
    current_time = int(time.time())
    buyer_id = f"{exchange}_current"  # Use a simple key per exchange

    # Initialize exchange dict if not exists
    if exchange not in PENDING_TRADES:
        PENDING_TRADES[exchange] = {}

    # Add trade to pending trades (regardless of individual threshold)
    if buyer_id not in PENDING_TRADES[exchange]:
        PENDING_TRADES[exchange][buyer_id] = {
            'trades': [],
            'window_start': current_time
        }

    PENDING_TRADES[exchange][buyer_id]['trades'].append({
        'price': price,
        'quantity': quantity,
        'sum_value': sum_value,
        'timestamp': timestamp,
        'exchange': exchange,
        'exchange_url': exchange_url,
        'received_time': current_time
    })

    # Log the pending trades for this buyer
    total_pending = sum(t['sum_value'] for t in PENDING_TRADES[exchange][buyer_id]['trades'])
    trade_count = len(PENDING_TRADES[exchange][buyer_id]['trades'])
    logger.info(f"Added to pending trades: {buyer_id} - {trade_count} trades, Total: {total_pending:.2f} USDT (threshold: {VALUE_REQUIRE} USDT)")

    # Check if we should process this aggregation immediately
    window_start = PENDING_TRADES[exchange][buyer_id]['window_start']
    time_in_window = current_time - window_start

    # Process if either threshold is met OR window time has elapsed
    should_process = (total_pending >= VALUE_REQUIRE) or (time_in_window >= aggregation_window)

    if should_process:
        trades = PENDING_TRADES[exchange][buyer_id]['trades']

        if total_pending >= VALUE_REQUIRE:
            logger.info(f"Aggregated trades exceed threshold: {total_pending:.2f} USDT >= {VALUE_REQUIRE} USDT")

            # Calculate aggregated values
            total_quantity = sum(trade['quantity'] for trade in trades)
            avg_price = total_pending / total_quantity if total_quantity > 0 else 0
            latest_timestamp = max(trade['timestamp'] for trade in trades)

            # Send the alert
            await send_alert(
                avg_price,
                total_quantity,
                total_pending,
                f"{exchange} (Aggregated)",
                latest_timestamp,
                trades[0]['exchange_url'],
                len(trades)
            )
        else:
            logger.info(f"Aggregation window expired: {time_in_window}s >= {aggregation_window}s, total: {total_pending:.2f} USDT < {VALUE_REQUIRE} USDT")

        # Clear the processed trades
        del PENDING_TRADES[exchange][buyer_id]

        # If the exchange dict is now empty, remove it
        if not PENDING_TRADES[exchange]:
            del PENDING_TRADES[exchange]

        return  # Don't process individual window below
    
    # Check if it's time to process other aggregated trades
    if current_time - LAST_AGGREGATION_CHECK >= 2:  # Check every 2 seconds (less frequent)
        LAST_AGGREGATION_CHECK = current_time
        await process_aggregated_trades()

async def process_aggregated_trades():
    """Process any pending aggregated trades that are ready."""
    global PENDING_TRADES

    # Get aggregation window from config
    aggregation_window = CONFIG.get("trade_aggregation", {}).get("window_seconds", 8)
    current_time = int(time.time())

    # Make a copy of the exchanges to avoid modification during iteration
    exchanges = list(PENDING_TRADES.keys())

    for exchange in exchanges:
        # Make a copy of the buyer_ids to avoid modification during iteration
        buyer_ids = list(PENDING_TRADES[exchange].keys())

        for buyer_id in buyer_ids:
            # Check if this aggregation window has expired
            aggregation_data = PENDING_TRADES[exchange][buyer_id]
            window_start = aggregation_data['window_start']
            time_in_window = current_time - window_start

            if time_in_window >= aggregation_window:
                # This window has expired, process the trades
                trades = aggregation_data['trades']

                # Calculate total value
                total_value = sum(trade['sum_value'] for trade in trades)

                # If the total exceeds the threshold, send an alert
                if total_value >= VALUE_REQUIRE:
                    # Calculate aggregated values
                    total_quantity = sum(trade['quantity'] for trade in trades)
                    avg_price = total_value / total_quantity if total_quantity > 0 else 0
                    latest_timestamp = max(trade['timestamp'] for trade in trades)

                    logger.info(f"Processing expired aggregated trades: {len(trades)} trades, {total_quantity} JKC, {total_value} USDT")

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
                    logger.info(f"Expired aggregated trades below threshold: {total_value} USDT < {VALUE_REQUIRE} USDT")

                # Remove these trades
                del PENDING_TRADES[exchange][buyer_id]

                # If the exchange dict is now empty, remove it
                if not PENDING_TRADES[exchange]:
                    del PENDING_TRADES[exchange]

async def send_alert(price, quantity, sum_value, exchange, timestamp, exchange_url, num_trades=1):
    """Send an alert to all active chats."""
    global PHOTO

    # Get a random image for this alert
    random_photo = load_random_image()
    if random_photo is None:
        random_photo = PHOTO  # Fallback to global PHOTO if no random image available

    # Get market data for additional context
    try:
        market_data = await get_nonkyc_ticker()
        volume_data = await calculate_combined_volume_periods()
        volume_periods = volume_data["combined"]

        market_cap = market_data.get("marketcapNumber", 0) if market_data else 0
        current_price = market_data.get("lastPriceNumber", price) if market_data else price
    except Exception as e:
        logger.warning(f"Could not fetch market data for alert: {e}")
        market_cap = 0
        current_price = price
        volume_periods = {"15m": 0, "1h": 0, "4h": 0, "24h": 0}

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

    # Add market data if available
    if market_cap > 0:
        message += f"\n🏦 <b>Market Cap:</b> ${market_cap:,}\n"

    # Add volume data
    if any(v > 0 for v in volume_periods.values()):
        message += (
            f"📈 <b>Combined Volume:</b>\n"
            f"🕐 15m: ${volume_periods['15m']:,.0f} | 1h: ${volume_periods['1h']:,.0f}\n"
            f"🕐 4h: ${volume_periods['4h']:,.0f} | 24h: ${volume_periods['24h']:,.0f}\n"
        )
    
    # Create inline button to exchange
    button = InlineKeyboardButton(text=f"Trade on {exchange.split(' ')[0]}", url=exchange_url)
    keyboard = InlineKeyboardMarkup([[button]])
    
    # Send to all active chats
    bot = Bot(token=BOT_TOKEN)
    for chat_id in ACTIVE_CHAT_IDS:
        try:
            if random_photo:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=random_photo,
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

    try:
        # Get the highest resolution photo
        photo = update.message.photo[-1]
        file = await photo.get_file()

        logger.info(f"Processing image upload: file_id={file.file_id}, file_size={file.file_size}")

        # Download the image
        image_data = await file.download_as_bytearray()
        logger.info(f"Downloaded image data: {len(image_data)} bytes")

        # Ensure images directory exists
        ensure_images_directory()

        # Generate unique filename with timestamp
        timestamp = int(time.time())
        file_extension = ".jpg"  # Default to jpg for Telegram photos
        filename = f"alert_image_{timestamp}{file_extension}"
        image_path = os.path.join(IMAGES_DIR, filename)

        # Save to collection
        try:
            with open(image_path, 'wb') as f:
                f.write(image_data)
            logger.info(f"Successfully saved image to: {image_path}")
        except Exception as e:
            logger.error(f"Error saving image to collection: {e}")
            await update.message.reply_text(f"❌ Error saving image to collection: {e}")
            return ConversationHandler.END

        # Also update the default image path for backward compatibility
        try:
            await file.download_to_drive(IMAGE_PATH)
            logger.info(f"Successfully saved default image to: {IMAGE_PATH}")
        except Exception as e:
            logger.warning(f"Error saving default image: {e}")
            # Don't fail the whole operation if this fails

        # Update the global PHOTO variable with a new random image
        PHOTO = load_random_image()

        # Get collection count
        collection_count = len(get_image_collection())

        await update.message.reply_text(
            f"✅ Image added to collection successfully!\n"
            f"📁 Collection now has {collection_count} images\n"
            f"🎲 Images will be randomly selected for alerts\n"
            f"📄 Saved as: {filename}"
        )
        logger.info(f"Image upload completed successfully. Collection now has {collection_count} images")

    except Exception as e:
        logger.error(f"Error in set_image_input: {e}")
        await update.message.reply_text(f"❌ Error processing image: {e}")

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

    # Get combined volume data from both exchanges
    volume_data = await calculate_combined_volume_periods()
    volume_periods = volume_data["combined"]

    # Extract data from NonKYC API
    current_price = market_data.get("lastPriceNumber", 0)
    yesterday_price = market_data.get("yesterdayPriceNumber", 0)
    high_24h = market_data.get("highPriceNumber", 0)
    low_24h = market_data.get("lowPriceNumber", 0)
    volume_24h_jkc = market_data.get("volumeNumber", 0)
    volume_24h_usdt = market_data.get("volumeUsdNumber", 0)
    change_percent = market_data.get("changePercentNumber", 0)
    market_cap_nonkyc = market_data.get("marketcapNumber", 0)
    best_bid = market_data.get("bestBidNumber", 0)
    best_ask = market_data.get("bestAskNumber", 0)
    spread_percent = market_data.get("spreadPercentNumber", 0)

    # Calculate additional metrics
    price_change_usdt = current_price - yesterday_price if yesterday_price > 0 else 0

    # Determine momentum emoji
    if change_percent > 5:
        momentum_emoji = "🚀🚀🚀"
        momentum_text = "BULLISH"
    elif change_percent > 2:
        momentum_emoji = "🚀🚀"
        momentum_text = "Strong Up"
    elif change_percent > 0:
        momentum_emoji = "🚀"
        momentum_text = "Up"
    elif change_percent == 0:
        momentum_emoji = "➡️"
        momentum_text = "Neutral"
    elif change_percent > -2:
        momentum_emoji = "📉"
        momentum_text = "Down"
    elif change_percent > -5:
        momentum_emoji = "📉📉"
        momentum_text = "Strong Down"
    else:
        momentum_emoji = "📉📉📉"
        momentum_text = "BEARISH"

    # Format change with appropriate emoji
    change_emoji = "📈" if change_percent >= 0 else "📉"
    change_sign = "+" if change_percent >= 0 else ""

    # Create buttons
    button1 = InlineKeyboardButton(
        text="📊 NonKYC", url="https://nonkyc.io/market/JKC_USDT")
    button2 = InlineKeyboardButton(
        text="🏦 CoinEx", url="https://www.coinex.com/en/exchange/jkc-usdt")
    button3 = InlineKeyboardButton(
        text="🦎 CoinGecko", url="https://www.coingecko.com/en/coins/junkcoin")
    button4 = InlineKeyboardButton(
        text="📈 CoinMarketCap", url="https://coinmarketcap.com/currencies/junkcoin")
    keyboard = InlineKeyboardMarkup([
        [button1, button2],
        [button3, button4]
    ])

    # Format the message with rich data including volume periods
    message = (
        f"⛵️ <b>JunkCoin (JKC) Market Data</b> ⛵️\n\n"
        f"� <b>Price:</b> ${current_price:.6f} USDT\n"
        f"{change_emoji} <b>24h Change:</b> {change_sign}{change_percent:.2f}% "
        f"({change_sign}${price_change_usdt:.6f})\n"
        f"{momentum_emoji} <b>Momentum:</b> {momentum_text}\n\n"

        f"🏦 <b>Market Cap:</b> ${market_cap_nonkyc:,}\n\n"

        f"📊 <b>24h Statistics:</b>\n"
        f"📈 <b>High:</b> ${high_24h:.6f}\n"
        f"📉 <b>Low:</b> ${low_24h:.6f}\n"
        f"💹 <b>Volume:</b> {volume_24h_jkc:,.0f} JKC (${volume_24h_usdt:,.0f})\n\n"

        f"📈 <b>Combined Volume (NonKYC + CoinEx):</b>\n"
        f"🕐 <b>15m:</b> ${volume_periods['15m']:,.0f}\n"
        f"🕐 <b>1h:</b> ${volume_periods['1h']:,.0f}\n"
        f"🕐 <b>4h:</b> ${volume_periods['4h']:,.0f}\n"
        f"🕐 <b>24h:</b> ${volume_periods['24h']:,.0f}\n\n"

        f"📋 <b>Order Book:</b>\n"
        f"🟢 <b>Best Bid:</b> ${best_bid:.6f}\n"
        f"🔴 <b>Best Ask:</b> ${best_ask:.6f}\n"
        f"📏 <b>Spread:</b> {spread_percent:.2f}%\n\n"

        f"📡 <b>Data Source:</b> NonKYC Exchange"
    )

    await update.message.reply_text(
        message,
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
        "🤖⛵️ <b>JunkCoin Alert Bot</b> ⛵️🤖\n\n"
        "🚨 <b>Real-time monitoring of JKC transactions across multiple exchanges</b>\n"
        "🎯 <b>Smart alerts with sweep detection and trade aggregation</b>\n"
        "🎨 <b>Random image collection for varied alert visuals</b>\n\n"

        "📊 <b>Information Commands:</b>\n"
        "/price - Check current JKC price and market cap\n"
        "/chart - Generate and send a price chart\n"
        "/debug - Show user ID, chat info, and admin status\n"
        "/help - Show this help message\n\n"

        "🛑 <b>Control Commands:</b>\n"
        "/start - Start receiving alerts in this chat\n"
        "/stop - Stop receiving alerts in this chat\n\n"

        "⚙️ <b>Admin Configuration:</b>\n"
        "/config - Interactive configuration menu\n"
        "/setmin [value] - Set minimum transaction value (e.g. /setmin 150)\n"
        "/toggle_aggregation - Enable/disable trade aggregation\n\n"

        "🎨 <b>Image Management (Admin):</b>\n"
        "/setimage - Add image to collection (send image after command)\n"
        "/list_images - View all images in your collection\n"
        "/clear_images - Remove all images from collection\n\n"

        "🔐 <b>Owner Only Commands:</b>\n"
        "/setapikey - Configure exchange API keys\n"
        "/ipwan - Get server's public IP address\n\n"

        "🚨 <b>Alert Types:</b>\n"
        "🚨 Standard (1x threshold) | 💥 Significant (2x)\n"
        "🔥 Major (3x) | 🔥🔥 Huge (5x) | 🐋🐋🐋 Whale (10x+)\n\n"

        "📈 <b>Monitored Exchanges:</b>\n"
        "• NonKYC (Real-time orderbook + sweep detection)\n"
        "• CoinEx (Live trade monitoring)\n"
        "• AscendEX (With API keys)\n\n"

        "💡 <b>Pro Tips:</b>\n"
        "• Use /setimage multiple times to build a varied collection\n"
        "• Enable trade aggregation to catch coordinated buying\n"
        "• Set threshold based on your preferred alert frequency\n"
        "• Use /debug to verify your admin permissions"
    )
    
    # Create buttons for quick access to common commands
    user_id = update.effective_user.id
    is_user_admin = await is_admin(update, context)

    # Basic buttons for all users
    keyboard = [
        [
            InlineKeyboardButton("📊 Check Price", callback_data="cmd_price"),
            InlineKeyboardButton("📈 View Chart", callback_data="cmd_chart")
        ],
        [
            InlineKeyboardButton("🔍 Debug Info", callback_data="cmd_debug"),
            InlineKeyboardButton("🛑 Stop Bot", callback_data="cmd_stop")
        ]
    ]

    # Add admin buttons if user is admin
    if is_user_admin:
        keyboard.insert(1, [
            InlineKeyboardButton("⚙️ Configuration", callback_data="cmd_config"),
            InlineKeyboardButton("🎨 List Images", callback_data="cmd_list_images")
        ])

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

    # Create a new update object for command execution
    new_update = Update(
        update_id=update.update_id,
        message=query.message,
        callback_query=None
    )

    if query.data == "cmd_price":
        await check_price(new_update, context)
    elif query.data == "cmd_chart":
        await chart_command(new_update, context)
    elif query.data == "cmd_debug":
        await debug_command(new_update, context)
    elif query.data == "cmd_config":
        if await is_admin(update, context):
            await config_command(new_update, context)
        else:
            await query.edit_message_text("❌ You don't have permission to access configuration.")
    elif query.data == "cmd_list_images":
        if await is_admin(update, context):
            await list_images_command(new_update, context)
        else:
            await query.edit_message_text("❌ You don't have permission to list images.")
    elif query.data == "cmd_stop":
        await stop_bot(new_update, context)
    elif query.data == "cmd_help":
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
            CONFIG["trade_aggregation"] = {"enabled": True, "window_seconds": 8}

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

async def list_images_command(update: Update, context: CallbackContext) -> None:
    """List all images in the collection - admin only command."""
    # Get user ID with multiple fallback methods to ensure we get the correct one
    user_id = None
    if update.effective_user:
        user_id = update.effective_user.id
    elif update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id

    logger.info(f"list_images command called by user {user_id}")

    if await is_admin(update, context):
        images = get_image_collection()
        if not images:
            await update.message.reply_text(
                "📁 Image collection is empty.\n"
                "Use /setimage to add images to the collection."
            )
        else:
            image_list = []
            for i, img_path in enumerate(images, 1):
                filename = os.path.basename(img_path)
                size = os.path.getsize(img_path)
                size_kb = size / 1024
                image_list.append(f"{i}. {filename} ({size_kb:.1f} KB)")

            message = (
                f"📁 <b>Image Collection ({len(images)} images)</b>\n\n"
                + "\n".join(image_list) +
                "\n\n🎲 Images are randomly selected for alerts"
            )
            await update.message.reply_text(message, parse_mode="HTML")
    else:
        logger.warning(f"User {user_id} tried to use list_images command without admin permissions")
        await update.message.reply_text("You do not have permission to use this command.")

async def clear_images_command(update: Update, context: CallbackContext) -> None:
    """Clear all images from the collection - admin only command."""
    user_id = update.effective_user.id
    logger.info(f"clear_images command called by user {user_id}")

    if await is_admin(update, context):
        images = get_image_collection()
        if not images:
            await update.message.reply_text("📁 Image collection is already empty.")
        else:
            # Delete all images in the collection
            deleted_count = 0
            for img_path in images:
                try:
                    os.remove(img_path)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting image {img_path}: {e}")

            await update.message.reply_text(
                f"🗑️ Cleared {deleted_count} images from collection.\n"
                f"Default image will be used for alerts."
            )
    else:
        logger.warning(f"User {user_id} tried to use clear_images command without admin permissions")
        await update.message.reply_text("You do not have permission to use this command.")

async def debug_command(update: Update, context: CallbackContext) -> None:
    """Debug command to show user and chat IDs."""
    # Get user ID with multiple fallback methods to ensure we get the correct one
    user_id = None
    if update.effective_user:
        user_id = update.effective_user.id
    elif update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id

    chat_id = update.effective_chat.id

    # Get chat type
    chat_type = update.effective_chat.type

    # Check if user is admin using centralized function
    is_user_admin = await is_admin(update, context)

    # Get bot info
    bot_info = await context.bot.get_me()

    # Additional debug info to help troubleshoot
    debug_sources = []
    if update.effective_user:
        debug_sources.append(f"effective_user: {update.effective_user.id}")
    if update.message and update.message.from_user:
        debug_sources.append(f"message.from_user: {update.message.from_user.id}")
    if update.callback_query and update.callback_query.from_user:
        debug_sources.append(f"callback_query.from_user: {update.callback_query.from_user.id}")

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
        f"- Bypass ID: {BY_PASS}\n\n"
        f"🔧 <b>Debug Sources:</b>\n"
        f"{chr(10).join(debug_sources)}\n"
    )

    await update.message.reply_text(debug_info, parse_mode="HTML")

async def test_command(update: Update, context: CallbackContext) -> None:
    """Test command to show current data format and simulate alert."""
    if not await is_admin(update, context):
        await update.message.reply_text("You do not have permission to use this command.")
        return

    await update.message.reply_text("🧪 <b>Testing Data Sources...</b>", parse_mode="HTML")

    try:
        # Test NonKYC data
        await update.message.reply_text("📊 <b>Testing NonKYC API...</b>", parse_mode="HTML")
        nonkyc_ticker = await get_nonkyc_ticker()
        nonkyc_trades = await get_nonkyc_trades()

        nonkyc_info = "📊 <b>NonKYC Data:</b>\n"
        if nonkyc_ticker:
            nonkyc_info += f"✅ Ticker: Price ${nonkyc_ticker.get('lastPriceNumber', 'N/A')}\n"
            nonkyc_info += f"✅ Market Cap: ${nonkyc_ticker.get('marketcapNumber', 'N/A'):,}\n"
        else:
            nonkyc_info += "❌ Ticker: Failed to fetch\n"

        if nonkyc_trades:
            nonkyc_info += f"✅ Trades: {len(nonkyc_trades)} trades fetched\n"
            if len(nonkyc_trades) > 0:
                latest_trade = nonkyc_trades[0]
                nonkyc_info += f"   Latest: {latest_trade.get('quantity', 'N/A')} JKC at ${latest_trade.get('price', 'N/A')}\n"
        else:
            nonkyc_info += "❌ Trades: Failed to fetch\n"

        await update.message.reply_text(nonkyc_info, parse_mode="HTML")

        # Test CoinEx data
        await update.message.reply_text("🏦 <b>Testing CoinEx API...</b>", parse_mode="HTML")
        coinex_ticker = await get_coinex_ticker()
        coinex_trades = await get_coinex_trades()

        coinex_info = "🏦 <b>CoinEx Data:</b>\n"
        if coinex_ticker:
            coinex_info += f"✅ Ticker: Price ${coinex_ticker.get('last', 'N/A')}\n"
            coinex_info += f"✅ Volume: {coinex_ticker.get('volume', 'N/A')} JKC\n"
            coinex_info += f"✅ Value: ${coinex_ticker.get('value', 'N/A')}\n"
        else:
            coinex_info += "❌ Ticker: Failed to fetch\n"

        if coinex_trades:
            coinex_info += f"✅ Trades: {len(coinex_trades)} trades fetched\n"
            if len(coinex_trades) > 0:
                latest_trade = coinex_trades[0]
                coinex_info += f"   Latest: {latest_trade.get('quantity', 'N/A')} JKC at ${latest_trade.get('price', 'N/A')}\n"
        else:
            coinex_info += "❌ Trades: Failed to fetch\n"

        await update.message.reply_text(coinex_info, parse_mode="HTML")

        # Test combined volume calculation
        await update.message.reply_text("📈 <b>Testing Combined Volume...</b>", parse_mode="HTML")
        volume_data = await calculate_combined_volume_periods()

        volume_info = (
            "📈 <b>Combined Volume Data:</b>\n"
            f"🕐 15m: ${volume_data['combined']['15m']:,.0f}\n"
            f"🕐 1h: ${volume_data['combined']['1h']:,.0f}\n"
            f"🕐 4h: ${volume_data['combined']['4h']:,.0f}\n"
            f"🕐 24h: ${volume_data['combined']['24h']:,.0f}\n\n"
            f"<b>NonKYC:</b> 15m: ${volume_data['nonkyc']['15m']:,.0f}, 24h: ${volume_data['nonkyc']['24h']:,.0f}\n"
            f"<b>CoinEx:</b> 15m: ${volume_data['coinex']['15m']:,.0f}, 24h: ${volume_data['coinex']['24h']:,.0f}"
        )

        await update.message.reply_text(volume_info, parse_mode="HTML")

        # Simulate an alert
        await update.message.reply_text("🚨 <b>Simulating Alert...</b>", parse_mode="HTML")

        # Create a simulated trade that meets threshold
        simulated_price = 0.027500
        simulated_quantity = VALUE_REQUIRE / simulated_price + 100  # Ensure it exceeds threshold
        simulated_value = simulated_price * simulated_quantity
        simulated_timestamp = int(time.time() * 1000)

        await send_alert(
            price=simulated_price,
            quantity=simulated_quantity,
            sum_value=simulated_value,
            exchange="Test Exchange (Simulated)",
            timestamp=simulated_timestamp,
            exchange_url="https://www.coinex.com/en/exchange/jkc-usdt"
        )

        await update.message.reply_text(
            f"✅ <b>Test Complete!</b>\n\n"
            f"Simulated trade:\n"
            f"💰 Amount: {simulated_quantity:.2f} JKC\n"
            f"💵 Price: ${simulated_price:.6f}\n"
            f"💲 Value: ${simulated_value:.2f} USDT\n"
            f"🎯 Threshold: ${VALUE_REQUIRE} USDT",
            parse_mode="HTML"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ <b>Test Error:</b> {str(e)}", parse_mode="HTML")

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
    application.add_handler(CommandHandler("test", test_command))  # Test command for simulating alerts
    application.add_handler(CommandHandler("list_images", list_images_command))
    application.add_handler(CommandHandler("clear_images", clear_images_command))
    
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






