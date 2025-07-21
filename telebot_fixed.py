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
from utils import validate_price_calculation

# Set up logging with more detailed format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set httpx logging to WARNING to reduce noise
logging.getLogger("httpx").setLevel(logging.WARNING)

# Add a file handler to save logs
file_handler = logging.FileHandler("jkc_telebot.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

def setup_file_logging():
    """Set up logging to a file in addition to console"""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Create a file handler with current timestamp
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join("logs", f"jkc_telebot_{current_time}.log")
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
            "image_path": "jkc_buy_alert.gif",
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

# Save configuration to file with enhanced error handling and atomic operations
def save_config(config_data):
    """Save configuration to file with enhanced error handling and atomic operations."""
    import shutil
    import tempfile
    import stat

    CONFIG_FILE = "config.json"

    try:
        # Log current state for debugging
        logger.info(f"💾 Attempting to save config to: {CONFIG_FILE}")

        # Check file permissions and ownership
        try:
            file_stat = os.stat(CONFIG_FILE)
            logger.info(f"📊 Current file permissions: {oct(file_stat.st_mode)[-3:]}")
            logger.info(f"👤 File owner: UID {file_stat.st_uid}, GID {file_stat.st_gid}")
            logger.info(f"🔧 Container user: UID {os.getuid()}, GID {os.getgid()}")
        except Exception as e:
            logger.warning(f"⚠️ Could not check file stats: {e}")

        # Validate configuration data
        if not isinstance(config_data, dict):
            raise ValueError("Configuration data must be a dictionary")

        # Validate critical fields
        required_fields = ['bot_token', 'bot_owner', 'value_require', 'active_chat_ids', 'by_pass', 'image_path']
        for field in required_fields:
            if field not in config_data:
                raise ValueError(f"Missing required field: {field}")

        # Validate optional but important nested configurations
        if 'dynamic_threshold' not in config_data:
            config_data['dynamic_threshold'] = {
                "enabled": False,
                "base_value": 300,
                "volume_multiplier": 0.05,
                "price_check_interval": 3600,
                "min_threshold": 100,
                "max_threshold": 1000
            }

        if 'trade_aggregation' not in config_data:
            config_data['trade_aggregation'] = {
                "enabled": True,
                "window_seconds": 8
            }

        if 'sweep_orders' not in config_data:
            config_data['sweep_orders'] = {
                "enabled": True,
                "min_value": 50,
                "check_interval": 2,
                "min_orders_filled": 2
            }

        # Ensure API keys exist (can be empty)
        if 'coinex_access_id' not in config_data:
            config_data['coinex_access_id'] = ""
        if 'coinex_secret_key' not in config_data:
            config_data['coinex_secret_key'] = ""
        if 'ascendex_access_id' not in config_data:
            config_data['ascendex_access_id'] = ""
        if 'ascendex_secret_key' not in config_data:
            config_data['ascendex_secret_key'] = ""

        # Validate bot_token format
        bot_token = config_data.get('bot_token', '')
        if not bot_token or bot_token == "YOUR_BOT_TOKEN":
            raise ValueError("bot_token must be set to a valid Telegram bot token")
        if not bot_token.count(':') == 1 or len(bot_token.split(':')[0]) < 8:
            raise ValueError("bot_token format appears invalid (should be like '123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11')")

        # Validate bot_owner
        bot_owner = config_data.get('bot_owner', 0)
        if not isinstance(bot_owner, int) or bot_owner <= 0:
            raise ValueError("bot_owner must be a positive integer (Telegram user ID)")

        # Validate value_require range
        value_require = config_data.get('value_require', 100.0)
        if not isinstance(value_require, (int, float)) or value_require < 1 or value_require > 10000:
            raise ValueError(f"value_require must be between 1 and 10000, got: {value_require}")

        # Validate active_chat_ids
        active_chat_ids = config_data.get('active_chat_ids', [])
        if not isinstance(active_chat_ids, list):
            raise ValueError("active_chat_ids must be a list")

        # Validate image_path
        image_path = config_data.get('image_path', '')
        if not image_path:
            raise ValueError("image_path must be specified")

        # Create backup of current config
        backup_path = f"{CONFIG_FILE}.backup"
        try:
            if os.path.exists(CONFIG_FILE):
                shutil.copy2(CONFIG_FILE, backup_path)
                logger.info(f"📋 Created backup: {backup_path}")
        except Exception as e:
            logger.warning(f"⚠️ Could not create backup: {e}")

        # Direct write approach (since atomic rename fails with mounted files)
        # Write directly to the config file with proper error handling
        logger.info(f"💾 Writing configuration directly to {CONFIG_FILE}")

        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        logger.info(f"✅ Configuration written successfully")

        # Verify the write was successful
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved_data = json.load(f)

            # Verify critical fields match
            if saved_data.get('value_require') != config_data.get('value_require'):
                raise ValueError("Configuration verification failed: value_require mismatch")

            logger.info(f"✅ Configuration saved and verified successfully")
            logger.info(f"💰 New threshold: ${config_data.get('value_require', 'unknown')} USDT")

        except Exception as e:
            logger.error(f"❌ Configuration verification failed: {e}")
            # Restore backup if verification fails
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, CONFIG_FILE)
                logger.info(f"🔄 Restored backup configuration")
            raise

    except PermissionError as e:
        logger.error(f"❌ Permission denied saving config: {e}")
        logger.error(f"💡 Check if config.json is mounted read-only or has incorrect permissions")
        logger.error(f"💡 Container user: UID {os.getuid()}, file needs to be writable by this user")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decoding error: {e}")
        raise
    except ValueError as e:
        logger.error(f"❌ Configuration validation error: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error saving configuration: {e}")
        logger.error(f"💡 File path: {CONFIG_FILE}")
        logger.error(f"💡 Working directory: {os.getcwd()}")
        logger.error(f"💡 Directory writable: {os.access(os.path.dirname(CONFIG_FILE) or '.', os.W_OK)}")
        raise

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
INPUT_IMAGE_SETIMAGE = 6  # Separate state for setimage command

# Image collection constants
IMAGES_DIR = "images"
SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webp"]

# Transaction timestamps
LAST_TRANS_JKC = int(time.time() * 1000)
LAST_TRANS_COINEX = LAST_TRANS_JKC
LAST_TRANS_ASENDEX = 0
PHOTO = None
USER_CHECK_PRICE = []

# Last time the threshold was updated
LAST_THRESHOLD_UPDATE = time.time()

# Flag to control websocket loops
running = True

# Exchange availability flags - updated by periodic checks
EXCHANGE_AVAILABILITY = {
    "nonkyc": False,
    "coinex": False,
    "ascendex": False
}

# Last time exchange availability was checked
LAST_AVAILABILITY_CHECK = 0
AVAILABILITY_CHECK_INTERVAL = 300  # Check every 5 minutes

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

async def is_owner_only(update: Update, context: CallbackContext) -> bool:
    """Check if the user is the bot owner (stricter than admin check)."""
    user_id = None

    if update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id
    elif update.effective_user:
        user_id = update.effective_user.id

    if user_id is None:
        return False

    return int(user_id) == int(BOT_OWNER)

async def can_use_public_commands(update: Update, context: CallbackContext) -> bool:
    """Check if user can use public commands (always true for basic info commands)."""
    # Public commands like /help, /price, /chart are available to everyone
    return True

async def can_use_admin_commands(update: Update, context: CallbackContext) -> bool:
    """Check if user can use admin commands (owner in private chat or admin in groups)."""
    chat_id = update.effective_chat.id
    user_id = None

    if update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id
    elif update.effective_user:
        user_id = update.effective_user.id

    if user_id is None:
        return False

    # Bot owner always has admin rights
    if int(user_id) == int(BOT_OWNER):
        return True

    # For public supergroups, restrict admin commands to owner only
    public_supergroups = CONFIG.get("public_supergroups", [])
    if chat_id in public_supergroups:
        logger.info(f"Public supergroup access: User {user_id} requesting admin command - denied (owner only)")
        return False

    # For other chats, use standard admin check
    return await is_admin(update, context)

async def can_start_stop_bot(update: Update, context: CallbackContext) -> bool:
    """Check if user can start/stop bot alerts (owner only for security)."""
    chat_id = update.effective_chat.id
    user_id = None

    if update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id
    elif update.effective_user:
        user_id = update.effective_user.id

    if user_id is None:
        return False

    # Only bot owner can start/stop alerts for security
    if int(user_id) == int(BOT_OWNER):
        return True

    # For private chats (not the public supergroup), allow bypass user
    if chat_id > 0 and int(user_id) == int(BY_PASS):
        return True

    logger.info(f"Start/stop denied: User {user_id} in chat {chat_id} (owner: {BOT_OWNER})")
    return False

def ensure_images_directory():
    """Ensure the images directory exists."""
    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)
        logger.info(f"Created images directory: {IMAGES_DIR}")

def detect_file_type(file_path):
    """Detect the actual file type based on content and extension."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)

        # Check file signatures
        if header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
            return 'gif'
        elif header.startswith(b'\xff\xd8\xff'):
            return 'jpeg'
        elif header.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'png'
        elif header[4:12] == b'ftypmp4' or header[4:8] == b'ftyp':
            return 'mp4'
        elif header.startswith(b'RIFF') and header[8:12] == b'WEBP':
            return 'webp'
        else:
            # Fallback to extension
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.jpg', '.jpeg']:
                return 'jpeg'
            elif ext == '.png':
                return 'png'
            elif ext == '.gif':
                return 'gif'
            elif ext == '.mp4':
                return 'mp4'
            elif ext == '.webp':
                return 'webp'
            else:
                return 'unknown'
    except Exception as e:
        logger.warning(f"Error detecting file type for {file_path}: {e}")
        # Fallback to extension
        ext = os.path.splitext(file_path)[1].lower()
        return ext.replace('.', '') if ext else 'unknown'

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
        # Try multiple possible default image paths
        default_paths = [
            IMAGE_PATH,  # From config
            "jkcbuy.GIF",  # Actual file name
            "jkc_buy_alert.gif",  # Config file name
            os.path.join(os.getcwd(), "jkcbuy.GIF"),  # Full path
        ]

        for path in default_paths:
            if os.path.exists(path):
                logger.info(f"Using default image: {path}")
                return path

        logger.warning("No images found in collection and no default image exists")
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
    """Get ticker data from NonKYC WebSocket API with timeout handling."""
    uri = "wss://ws.nonkyc.io"

    try:
        # Add timeout to connection and operations
        async with websockets.connect(uri, ping_interval=30, close_timeout=10) as websocket:
            # Request ticker data
            ticker_msg = {
                "method": "getMarket",
                "params": {
                    "symbol": "JKC/USDT"
                },
                "id": 999
            }
            await asyncio.wait_for(websocket.send(json.dumps(ticker_msg)), timeout=5)

            # Wait for response with timeout
            response_text = await asyncio.wait_for(websocket.recv(), timeout=10)
            response = json.loads(response_text)

            if "result" in response:
                logger.debug(f"NonKYC ticker data received: ${response['result'].get('lastPriceNumber', 'N/A')}")
                return response["result"]
            else:
                logger.warning("NonKYC ticker response missing 'result' field")
                return None

    except asyncio.TimeoutError:
        logger.warning("NonKYC API request timed out after 10 seconds")
        return None
    except websockets.exceptions.ConnectionClosed:
        logger.warning("NonKYC WebSocket connection closed unexpectedly")
        return None
    except Exception as e:
        logger.warning(f"Error getting NonKYC ticker: {e}")
        return None

async def get_nonkyc_trades():
    """Get historical trades from NonKYC WebSocket API with timeout handling."""
    uri = "wss://ws.nonkyc.io"

    try:
        async with websockets.connect(uri, ping_interval=30, close_timeout=10) as websocket:
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
            await asyncio.wait_for(websocket.send(json.dumps(trades_msg)), timeout=5)

            # Wait for response with timeout
            response_text = await asyncio.wait_for(websocket.recv(), timeout=15)
            response = json.loads(response_text)

            if "result" in response and "data" in response["result"]:
                trades_count = len(response["result"]["data"])
                logger.debug(f"NonKYC trades data received: {trades_count} trades")
                return response["result"]["data"]
            else:
                logger.warning("NonKYC trades response missing 'result' or 'data' field")
                return []

    except asyncio.TimeoutError:
        logger.warning("NonKYC trades API request timed out after 15 seconds")
        return []
    except websockets.exceptions.ConnectionClosed:
        logger.warning("NonKYC WebSocket connection closed unexpectedly during trades request")
        return []
    except Exception as e:
        logger.warning(f"Error getting NonKYC trades: {e}")
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

async def get_livecoinwatch_data():
    """Get JunkCoin data from LiveCoinWatch API with comprehensive error handling."""
    try:
        import requests
        url = "https://api.livecoinwatch.com/coins/single"
        headers = {
            "content-type": "application/json",
            "x-api-key": "4646e0ac-da16-4526-b196-c0cd70d84501"
        }
        payload = {"currency": "USD", "code": "JKC", "meta": True}

        logger.debug("Making request to LiveCoinWatch API for JKC data")
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        # Log API usage for rate limiting awareness
        logger.debug(f"LiveCoinWatch API response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Check for API error response format
            if "error" in data:
                error_code = data['error'].get('code', 'unknown')
                error_desc = data['error'].get('description', 'No description provided')
                logger.error(f"LiveCoinWatch API error {error_code}: {error_desc}")

                # Handle specific error codes
                if error_code == 429:
                    logger.warning("LiveCoinWatch API rate limit exceeded (10,000 daily credits)")
                elif error_code == 401:
                    logger.error("LiveCoinWatch API authentication failed - check API key")
                elif error_code == 404:
                    logger.error("LiveCoinWatch API: JKC coin not found")

                return None

            # Validate required fields are present
            required_fields = ['rate', 'volume', 'cap']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                logger.warning(f"LiveCoinWatch API response missing fields: {missing_fields}")

            logger.info(f"Successfully fetched JKC data from LiveCoinWatch: ${data.get('rate', 'N/A')}")
            return data

        elif response.status_code == 429:
            logger.warning("LiveCoinWatch API rate limit exceeded - falling back to NonKYC")
            return None
        elif response.status_code == 401:
            logger.error("LiveCoinWatch API authentication failed - check API key")
            return None
        elif response.status_code == 404:
            logger.error("LiveCoinWatch API: JKC coin not found")
            return None
        else:
            logger.warning(f"LiveCoinWatch API returned unexpected status {response.status_code}: {response.text[:200]}")
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

async def check_exchange_availability():
    """Check if JKC is available on various exchanges and update availability flags."""
    global EXCHANGE_AVAILABILITY, LAST_AVAILABILITY_CHECK

    current_time = time.time()
    if current_time - LAST_AVAILABILITY_CHECK < AVAILABILITY_CHECK_INTERVAL:
        return EXCHANGE_AVAILABILITY

    logger.debug("Checking JKC availability across exchanges...")

    # Check NonKYC
    try:
        response = requests.get("https://api.nonkyc.io/api/v2/markets", timeout=10)
        if response.status_code == 200:
            markets = response.json()
            jkc_markets = [m for m in markets if m.get('base') == 'JKC']
            EXCHANGE_AVAILABILITY["nonkyc"] = len(jkc_markets) > 0
            if EXCHANGE_AVAILABILITY["nonkyc"]:
                logger.info(f"JKC now available on NonKYC! Found {len(jkc_markets)} markets")
        else:
            EXCHANGE_AVAILABILITY["nonkyc"] = False
    except Exception as e:
        logger.debug(f"Error checking NonKYC availability: {e}")
        EXCHANGE_AVAILABILITY["nonkyc"] = False

    # Check CoinEx
    try:
        response = requests.get("https://api.coinex.com/v1/market/ticker?market=JKCUSDT", timeout=10)
        EXCHANGE_AVAILABILITY["coinex"] = response.status_code == 200
        if EXCHANGE_AVAILABILITY["coinex"]:
            logger.info("JKC now available on CoinEx!")
    except Exception as e:
        logger.debug(f"Error checking CoinEx availability: {e}")
        EXCHANGE_AVAILABILITY["coinex"] = False

    # Check AscendEX
    try:
        response = requests.get("https://ascendex.com/api/pro/v1/ticker?symbol=JKC/USDT", timeout=10)
        EXCHANGE_AVAILABILITY["ascendex"] = response.status_code == 200
        if EXCHANGE_AVAILABILITY["ascendex"]:
            logger.info("JKC now available on AscendEX!")
    except Exception as e:
        logger.debug(f"Error checking AscendEX availability: {e}")
        EXCHANGE_AVAILABILITY["ascendex"] = False

    LAST_AVAILABILITY_CHECK = current_time

    # Log availability status
    available_exchanges = [ex for ex, available in EXCHANGE_AVAILABILITY.items() if available]
    if available_exchanges:
        logger.info(f"JKC available on: {', '.join(available_exchanges)}")
    else:
        logger.debug("JKC not yet available on any monitored exchanges")

    return EXCHANGE_AVAILABILITY

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

                # Check if this trade has side information for buy/sell filtering
                trade_side = trade.get("side", trade.get("type", "unknown")).lower()

                # Only count BUY volume for accurate volume calculations
                if trade_side in ["buy", "b"]:
                    trade_value = price * quantity
                    period_volume += trade_value
                    logger.debug(f"Including BUY trade in {period_name} volume: {quantity:.4f} JKC @ {price:.6f} = {trade_value:.2f} USDT")
                elif trade_side in ["sell", "s"]:
                    logger.debug(f"Excluding SELL trade from {period_name} volume: {quantity:.4f} JKC @ {price:.6f}")
                else:
                    # For unknown trades, include them but log warning
                    trade_value = price * quantity
                    period_volume += trade_value
                    logger.debug(f"Including UNKNOWN side trade in {period_name} volume: {quantity:.4f} JKC @ {price:.6f} = {trade_value:.2f} USDT")

        volumes[period_name] = round(period_volume, 2)

    return volumes

async def calculate_momentum_periods(trades_data, current_price):
    """Calculate price momentum for different time periods from trades data."""
    if not trades_data or not current_price:
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

    momentum = {}

    for period_name, period_ms in periods.items():
        cutoff_time = current_time - period_ms
        period_prices = []

        for trade in trades_data:
            # Handle different timestamp formats
            trade_time_ms = 0
            timestamp = trade.get("timestamp", 0)

            if isinstance(timestamp, str):
                try:
                    # Parse ISO format timestamp
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    trade_time_ms = dt.timestamp() * 1000
                except:
                    # Try parsing as milliseconds
                    try:
                        trade_time_ms = float(timestamp)
                    except:
                        continue
            else:
                trade_time_ms = float(timestamp)

            # Check if trade is within the time period
            if trade_time_ms >= cutoff_time:
                try:
                    price = float(trade.get("price", 0))
                    if price > 0:
                        period_prices.append(price)
                except (ValueError, TypeError):
                    continue

        # Calculate momentum (percentage change from period start to current)
        if period_prices:
            # Get the oldest price in the period (first trade chronologically)
            oldest_price = period_prices[-1]  # Trades are sorted DESC, so last is oldest
            if oldest_price > 0:
                momentum_percent = ((current_price - oldest_price) / oldest_price) * 100
                momentum[period_name] = round(momentum_percent, 2)
            else:
                momentum[period_name] = 0
        else:
            momentum[period_name] = 0

    return momentum

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
    global running, CURRENT_ORDERBOOK, ORDERBOOK_SEQUENCE, EXCHANGE_AVAILABILITY
    uri = "wss://ws.nonkyc.io"

    # Wait for JKC to become available on NonKYC
    while running:
        await check_exchange_availability()
        if EXCHANGE_AVAILABILITY["nonkyc"]:
            logger.info("JKC detected on NonKYC - starting orderbook WebSocket for sweep detection")
            break
        else:
            logger.debug("JKC not yet available on NonKYC for orderbook - waiting...")
            await asyncio.sleep(60)  # Check every minute
            continue

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
                                "asks": [[str(ask["price"]), str(ask["quantity"])] for ask in params["asks"]],
                                "bids": [[str(bid["price"]), str(bid["quantity"])] for bid in params["bids"]],
                                "sequence": params.get("sequence", 0)
                            }
                            ORDERBOOK_SEQUENCE = int(params.get("sequence", 0))
                            logger.info(f"Received orderbook snapshot with {len(CURRENT_ORDERBOOK['asks'])} asks, sequence: {ORDERBOOK_SEQUENCE}")

                            # Log sample of orderbook data for debugging
                            if len(CURRENT_ORDERBOOK['asks']) > 0:
                                sample_ask = CURRENT_ORDERBOOK['asks'][0]
                                logger.debug(f"Sample ask: price={sample_ask[0]}, quantity={sample_ask[1]}")

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
            # Convert price to string for comparison (orderbook stores as strings)
            price_str = str(ask_update["price"])
            price_float = float(ask_update["price"])
            new_quantity = float(ask_update["quantity"])

            # Find this price level in current orderbook
            for i, current_ask in enumerate(CURRENT_ORDERBOOK["asks"]):
                # Compare prices as strings since that's how they're stored
                if current_ask[0] == price_str:
                    old_quantity = float(current_ask[1])

                    if new_quantity == 0:
                        # Price level completely removed (swept)
                        individual_value = price_float * old_quantity
                        swept_asks.append({"price": price_float, "quantity": old_quantity, "value": individual_value})
                        total_swept_value += individual_value
                        logger.debug(f"Ask level swept: {price_float:.6f} USDT, {old_quantity:.4f} JKC")
                        # Remove from current orderbook
                        CURRENT_ORDERBOOK["asks"].pop(i)

                    elif new_quantity < old_quantity:
                        # Partial fill
                        filled_quantity = old_quantity - new_quantity
                        individual_value = price_float * filled_quantity
                        swept_asks.append({"price": price_float, "quantity": filled_quantity, "value": individual_value})
                        total_swept_value += individual_value
                        logger.debug(f"Ask level partially filled: {price_float:.6f} USDT, {filled_quantity:.4f} JKC")
                        # Update current orderbook
                        CURRENT_ORDERBOOK["asks"][i][1] = str(new_quantity)

                    else:
                        # Quantity increased or same - update orderbook
                        CURRENT_ORDERBOOK["asks"][i][1] = str(new_quantity)
                    break
            else:
                # New price level - add to orderbook
                if new_quantity > 0:
                    CURRENT_ORDERBOOK["asks"].append([price_str, str(new_quantity)])
                    # Keep asks sorted by price
                    CURRENT_ORDERBOOK["asks"].sort(key=lambda x: float(x[0]))

    # Update sequence
    ORDERBOOK_SEQUENCE = new_sequence

    # If we detected a significant sweep, process it
    if swept_asks and total_swept_value > 0:
        total_quantity = sum(ask["quantity"] for ask in swept_asks)
        avg_price = total_swept_value / total_quantity if total_quantity > 0 else 0

        # Add minimum threshold check to avoid false positives from tiny sweeps
        min_sweep_threshold = 5.0  # Minimum $5 USDT value to consider as a sweep

        # Enhanced logging for debugging
        logger.info(f"Potential sweep detected: {total_quantity:.4f} JKC, avg price: {avg_price:.6f} USDT, total value: {total_swept_value:.2f} USDT")

        # Debug logging for price calculation verification
        logger.debug(f"Sweep calculation details:")
        for i, ask in enumerate(swept_asks):
            stored_value = ask.get("value", ask["price"] * ask["quantity"])  # Use stored value if available
            calculated_value = ask["price"] * ask["quantity"]
            logger.debug(f"  Ask {i+1}: {ask['quantity']:.4f} JKC @ {ask['price']:.6f} USDT = {stored_value:.2f} USDT")
            if abs(stored_value - calculated_value) > 0.01:
                logger.warning(f"    Value mismatch: stored={stored_value:.2f}, calculated={calculated_value:.2f}")
        logger.debug(f"  Total: {total_quantity:.4f} JKC, Total Value: {total_swept_value:.2f} USDT")
        logger.debug(f"  Weighted Avg: {total_swept_value:.2f} / {total_quantity:.4f} = {avg_price:.6f} USDT per JKC")

        # Verification: Check if weighted average calculation is correct
        calculated_total = avg_price * total_quantity
        if abs(calculated_total - total_swept_value) > 0.01:  # Allow small floating point differences
            logger.error(f"PRICE CALCULATION MISMATCH: {avg_price:.6f} * {total_quantity:.4f} = {calculated_total:.2f} != {total_swept_value:.2f}")
        else:
            logger.debug(f"Price calculation verified: {avg_price:.6f} * {total_quantity:.4f} = {calculated_total:.2f} ≈ {total_swept_value:.2f}")

        # Validate price is reasonable for JKC (JunkCoin)
        # For USDT pairs: max $100k, for BTC pairs: max 10 BTC
        max_price_usdt = 100000.0
        max_price_btc = 10.0

        # Determine if this is a BTC or USDT pair based on price range
        is_btc_pair = avg_price < 1.0  # BTC prices are typically < 1 BTC
        max_price = max_price_btc if is_btc_pair else max_price_usdt
        price_unit = "BTC" if is_btc_pair else "USDT"

        if avg_price > max_price:
            logger.error(f"INVALID PRICE DETECTED in sweep: {avg_price:.6f} {price_unit} - this suggests a data parsing error")
            logger.error(f"Swept asks data: {swept_asks}")
            return  # Don't process this sweep

        if total_swept_value >= min_sweep_threshold and avg_price <= max_price:
            logger.info(f"Valid orderbook sweep detected: {total_quantity:.4f} JKC at avg {avg_price:.6f} USDT (Total: {total_swept_value:.2f} USDT)")

            # Process through normal pipeline
            timestamp = int(time.time() * 1000)
            await process_message(
                price=avg_price,
                quantity=total_quantity,
                sum_value=total_swept_value,
                exchange="NonKYC (Orderbook Sweep)",
                timestamp=timestamp,
                exchange_url="https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3",
                trade_side="buy"  # Orderbook sweeps removing asks are buy orders
            )
        else:
            if total_swept_value < min_sweep_threshold:
                logger.debug(f"Small sweep ignored: {total_swept_value:.2f} USDT < {min_sweep_threshold} USDT threshold")
            if avg_price > 100000.0:
                logger.debug(f"Invalid price sweep ignored: {avg_price:.6f} {price_unit} > {max_price} {price_unit}")

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

async def nonkyc_websocket_usdt():
    """Connect to NonKYC WebSocket API and process JKC/USDT trade data."""
    global LAST_TRANS_JKC, running, EXCHANGE_AVAILABILITY
    uri = "wss://ws.nonkyc.io"

    # Wait for JKC to become available on NonKYC
    while running:
        await check_exchange_availability()
        if EXCHANGE_AVAILABILITY["nonkyc"]:
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
                        # Handle NonKYC updateTrades format
                        if "params" in response and "data" in response["params"]:
                            trades_data = response["params"]["data"]

                            for trade_data in trades_data:
                                # Extract trade details
                                price = float(trade_data["price"])
                                quantity = float(trade_data["quantity"])
                                sum_value = price * quantity
                                timestamp = int(trade_data["timestampms"])  # Use timestampms for milliseconds

                                # Extract trade side (buy/sell) - check multiple possible field names
                                trade_side = trade_data.get("side", trade_data.get("type", trade_data.get("takerSide", "unknown"))).lower()

                                # Log trade details for debugging
                                logger.debug(f"NonKYC USDT trade: {quantity:.4f} JKC at {price:.6f} USDT, side: {trade_side}, value: {sum_value:.2f} USDT")

                                # Only process BUY trades newer than the last one
                                if timestamp > LAST_TRANS_JKC and trade_side in ["buy", "b"]:
                                    LAST_TRANS_JKC = timestamp

                                    logger.info(f"✅ Processing BUY trade: {quantity:.4f} JKC at {price:.6f} USDT = {sum_value:.2f} USDT")

                                    # Process the trade with side information
                                    await process_message(
                                        price=price,
                                        quantity=quantity,
                                        sum_value=sum_value,
                                        exchange="NonKYC Exchange (JKC/USDT)",
                                        timestamp=timestamp,
                                        exchange_url="https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3",
                                        trade_side=trade_side
                                    )
                                elif timestamp > LAST_TRANS_JKC and trade_side in ["sell", "s"]:
                                    # Update timestamp but don't process sell trades for alerts
                                    LAST_TRANS_JKC = timestamp
                                    logger.debug(f"⏭️ Skipping SELL trade: {quantity:.4f} JKC at {price:.6f} USDT = {sum_value:.2f} USDT")
                                elif trade_side == "unknown":
                                    logger.warning(f"⚠️ Unknown trade side for NonKYC USDT trade: {trade_data}")
                                    # Process unknown trades to maintain backward compatibility, but log warning
                                    if timestamp > LAST_TRANS_JKC:
                                        LAST_TRANS_JKC = timestamp
                                        await process_message(
                                            price=price,
                                            quantity=quantity,
                                            sum_value=sum_value,
                                            exchange="NonKYC Exchange (JKC/USDT)",
                                            timestamp=timestamp,
                                            exchange_url="https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3",
                                            trade_side="unknown"
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

# BTC WebSocket functionality removed - JKC only trades against USDT

async def coinex_websocket():
    """Connect to CoinEx WebSocket API and process trade data."""
    global LAST_TRANS_COINEX, running, EXCHANGE_AVAILABILITY
    uri = "wss://socket.coinex.com/"

    # Wait for JKC to become available on CoinEx
    while running:
        await check_exchange_availability()
        if EXCHANGE_AVAILABILITY["coinex"]:
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
                            # Extract trade details
                            price = float(trade["price"])
                            quantity = float(trade["amount"])
                            sum_value = price * quantity
                            timestamp = int(trade["time"] * 1000)  # Convert to milliseconds

                            # Extract trade side (buy/sell) - CoinEx uses "type" field
                            trade_side = trade.get("type", trade.get("side", "unknown")).lower()

                            # Log trade details for debugging
                            logger.debug(f"CoinEx trade: {quantity:.4f} JKC at {price:.6f} USDT, side: {trade_side}, value: {sum_value:.2f} USDT")

                            # Only process BUY trades newer than the last one
                            if timestamp > LAST_TRANS_COINEX and trade_side in ["buy", "b"]:
                                LAST_TRANS_COINEX = timestamp

                                logger.info(f"✅ Processing CoinEx BUY trade: {quantity:.4f} JKC at {price:.6f} USDT = {sum_value:.2f} USDT")

                                # Process the trade with side information
                                await process_message(
                                    price=price,
                                    quantity=quantity,
                                    sum_value=sum_value,
                                    exchange="CoinEx Exchange",
                                    timestamp=timestamp,
                                    exchange_url="https://www.coinex.com/en/exchange/jkc-usdt",
                                    trade_side=trade_side
                                )
                            elif timestamp > LAST_TRANS_COINEX and trade_side in ["sell", "s"]:
                                # Update timestamp but don't process sell trades for alerts
                                LAST_TRANS_COINEX = timestamp
                                logger.debug(f"⏭️ Skipping CoinEx SELL trade: {quantity:.4f} JKC at {price:.6f} USDT = {sum_value:.2f} USDT")
                            elif trade_side == "unknown":
                                logger.warning(f"⚠️ Unknown trade side for CoinEx trade: {trade}")
                                # Process unknown trades to maintain backward compatibility, but log warning
                                if timestamp > LAST_TRANS_COINEX:
                                    LAST_TRANS_COINEX = timestamp
                                    await process_message(
                                        price=price,
                                        quantity=quantity,
                                        sum_value=sum_value,
                                        exchange="CoinEx Exchange",
                                        timestamp=timestamp,
                                        exchange_url="https://www.coinex.com/en/exchange/jkc-usdt",
                                        trade_side="unknown"
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
    global LAST_TRANS_ASENDEX, running, EXCHANGE_AVAILABILITY
    uri = "wss://ascendex.com/api/pro/v1/stream"

    # Check if API keys are configured
    if not CONFIG.get("ascendex_access_id") or not CONFIG.get("ascendex_secret_key"):
        logger.warning("AscendEX API keys not configured, skipping AscendEX WebSocket")
        return

    # Wait for JKC to become available on AscendEX
    while running:
        await check_exchange_availability()
        if EXCHANGE_AVAILABILITY["ascendex"]:
            logger.info("JKC detected on AscendEX - starting WebSocket connection")
            break
        else:
            logger.debug("JKC not yet available on AscendEX - waiting...")
            await asyncio.sleep(60)  # Check every minute
            continue

    # For exponential backoff
    retry_delay = 5
    max_retry_delay = 60
    
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

                            # Extract trade side (buy/sell) - AscendEX uses "bm" field (true=buy, false=sell)
                            is_buy_maker = trade.get("bm", None)
                            if is_buy_maker is True:
                                trade_side = "buy"
                            elif is_buy_maker is False:
                                trade_side = "sell"
                            else:
                                # Fallback to other possible field names
                                trade_side = trade.get("side", trade.get("type", "unknown")).lower()

                            # Log trade details for debugging
                            logger.debug(f"AscendEX trade: {quantity:.4f} JKC at {price:.6f} USDT, side: {trade_side}, value: {sum_value:.2f} USDT")

                            # Only process BUY trades newer than the last one
                            if timestamp > LAST_TRANS_ASENDEX and trade_side in ["buy", "b"]:
                                LAST_TRANS_ASENDEX = timestamp

                                logger.info(f"✅ Processing AscendEX BUY trade: {quantity:.4f} JKC at {price:.6f} USDT = {sum_value:.2f} USDT")

                                # Process the trade with side information
                                await process_message(
                                    price=price,
                                    quantity=quantity,
                                    sum_value=sum_value,
                                    exchange="AscendEX Exchange",
                                    timestamp=timestamp,
                                    exchange_url="https://ascendex.com/en/cashtrade-spottrading/usdt/jkc",
                                    trade_side=trade_side
                                )
                            elif timestamp > LAST_TRANS_ASENDEX and trade_side in ["sell", "s"]:
                                # Update timestamp but don't process sell trades for alerts
                                LAST_TRANS_ASENDEX = timestamp
                                logger.debug(f"⏭️ Skipping AscendEX SELL trade: {quantity:.4f} JKC at {price:.6f} USDT = {sum_value:.2f} USDT")
                            elif trade_side == "unknown":
                                logger.warning(f"⚠️ Unknown trade side for AscendEX trade: {trade}")
                                # Process unknown trades to maintain backward compatibility, but log warning
                                if timestamp > LAST_TRANS_ASENDEX:
                                    LAST_TRANS_ASENDEX = timestamp
                                    await process_message(
                                        price=price,
                                        quantity=quantity,
                                        sum_value=sum_value,
                                        exchange="AscendEX Exchange",
                                        timestamp=timestamp,
                                        exchange_url="https://ascendex.com/en/cashtrade-spottrading/usdt/jkc",
                                        trade_side="unknown"
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

async def process_message(price, quantity, sum_value, exchange, timestamp, exchange_url, trade_side="buy",
                         pair_type="JKC/USDT", usdt_price=None, usdt_sum_value=None, btc_rate=None):
    """Process a trade message and send notification if it meets criteria."""
    global PHOTO, PENDING_TRADES, LAST_AGGREGATION_CHECK

    # Determine if this is a BTC pair and format logging appropriately
    is_btc_pair = pair_type == "JKC/BTC"

    if is_btc_pair:
        # For BTC pairs, log both BTC and USDT equivalent values
        usdt_equiv_text = f" (≈ ${usdt_price:.6f} USDT)" if usdt_price else ""
        logger.info(f"Processing {trade_side.upper()} trade: {exchange} - {quantity} JKC at {price:.8f} BTC{usdt_equiv_text} (Total: {sum_value:.8f} BTC)")
    else:
        # For USDT pairs, use standard logging
        logger.info(f"Processing {trade_side.upper()} trade: {exchange} - {quantity} JKC at ${price:.6f} USDT (Total: ${sum_value:.2f} USDT)")

    # Additional validation: Only process buy trades for alerts
    if trade_side.lower() not in ["buy", "b", "unknown"]:
        logger.debug(f"Skipping {trade_side.upper()} trade - not counting toward buy volume threshold")
        return

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

    # For aggregation, separate by trading pair to prevent mixing JKC/USDT and JKC/BTC
    current_time = int(time.time())
    buyer_id = f"{exchange}_{pair_type}_current"  # Include pair type in key

    # Initialize exchange dict if not exists
    if exchange not in PENDING_TRADES:
        PENDING_TRADES[exchange] = {}

    # Initialize pair dict if not exists
    if pair_type not in PENDING_TRADES[exchange]:
        PENDING_TRADES[exchange][pair_type] = {}

    # Add trade to pending trades (regardless of individual threshold)
    if buyer_id not in PENDING_TRADES[exchange][pair_type]:
        PENDING_TRADES[exchange][pair_type][buyer_id] = {
            'trades': [],
            'window_start': current_time
        }

    # Validate individual trade calculation before adding to pending trades
    expected_sum_value = price * quantity
    if abs(sum_value - expected_sum_value) > 0.01:  # Allow small floating point differences
        logger.error(f"TRADE VALUE CALCULATION MISMATCH: {price:.6f} * {quantity:.4f} = {expected_sum_value:.2f} != {sum_value:.2f}")
        logger.error(f"Using corrected value: {expected_sum_value:.2f} USDT")
        sum_value = expected_sum_value  # Use the corrected value

    PENDING_TRADES[exchange][pair_type][buyer_id]['trades'].append({
        'price': price,
        'quantity': quantity,
        'sum_value': sum_value,
        'timestamp': timestamp,
        'exchange': exchange,
        'exchange_url': exchange_url,
        'trade_side': trade_side,
        'received_time': current_time,
        'validated': True,  # Mark as validated
        'pair_type': pair_type,
        'usdt_price': usdt_price,
        'usdt_sum_value': usdt_sum_value,
        'btc_rate': btc_rate
    })

    # Log the pending trades for this buyer with enhanced validation
    trades_list = PENDING_TRADES[exchange][pair_type][buyer_id]['trades']
    total_pending = sum(t['sum_value'] for t in trades_list)
    trade_count = len(trades_list)

    # Validate buy volume aggregation
    buy_trades = [t for t in trades_list if t.get('trade_side', 'buy').lower() in ['buy', 'b', 'unknown']]
    sell_trades = [t for t in trades_list if t.get('trade_side', 'buy').lower() in ['sell', 's']]

    buy_volume = sum(t['sum_value'] for t in buy_trades)
    sell_volume = sum(t['sum_value'] for t in sell_trades)

    # Format logging based on pair type
    if is_btc_pair:
        currency_symbol = "BTC"
        buy_formatted = f"{buy_volume:.8f}"
        sell_formatted = f"{sell_volume:.8f}"
        total_formatted = f"{total_pending:.8f}"
        threshold_formatted = f"{VALUE_REQUIRE:.2f}"  # Threshold is always in USDT
    else:
        currency_symbol = "USDT"
        buy_formatted = f"{buy_volume:.2f}"
        sell_formatted = f"{sell_volume:.2f}"
        total_formatted = f"{total_pending:.2f}"
        threshold_formatted = f"{VALUE_REQUIRE:.2f}"

    logger.info(f"📊 Pending trades for {buyer_id} ({pair_type}): {trade_count} total trades")
    logger.info(f"  🟢 BUY trades: {len(buy_trades)} trades = {buy_formatted} {currency_symbol}")
    if sell_trades:
        logger.warning(f"  🔴 SELL trades detected: {len(sell_trades)} trades = {sell_formatted} {currency_symbol} (should be filtered out!)")

    # For threshold comparison, always use USDT equivalent
    if is_btc_pair and usdt_sum_value:
        total_usdt_equivalent = sum(t.get('usdt_sum_value', 0) for t in buy_trades)
        logger.info(f"  💰 Total pending: {total_formatted} {currency_symbol} (≈ ${total_usdt_equivalent:.2f} USDT equivalent)")
        logger.info(f"  🎯 Threshold: ${threshold_formatted} USDT")
        threshold_sum_value = total_usdt_equivalent
    else:
        logger.info(f"  💰 Total pending: ${total_formatted} {currency_symbol} (threshold: ${threshold_formatted} USDT)")
        threshold_sum_value = total_pending

    # Mathematical validation of aggregation
    calculated_total = sum(t['price'] * t['quantity'] for t in trades_list)
    if abs(calculated_total - total_pending) > 0.01:
        logger.error(f"❌ AGGREGATION CALCULATION MISMATCH: Sum of stored values ${total_pending:.2f} != calculated total ${calculated_total:.2f}")
    else:
        logger.debug(f"✅ Aggregation calculation verified: ${total_pending:.2f} USDT")

    # Check if we should process this aggregation immediately
    window_start = PENDING_TRADES[exchange][pair_type][buyer_id]['window_start']
    time_in_window = current_time - window_start

    # Process if either threshold is met OR window time has elapsed
    should_process = (threshold_sum_value >= VALUE_REQUIRE) or (time_in_window >= aggregation_window)

    if should_process:
        trades = PENDING_TRADES[exchange][pair_type][buyer_id]['trades']

        if threshold_sum_value >= VALUE_REQUIRE:
            # Enhanced threshold validation logging
            threshold_ratio = threshold_sum_value / VALUE_REQUIRE
            logger.info(f"🎯 THRESHOLD EXCEEDED: ${threshold_sum_value:.2f} USDT equivalent >= ${VALUE_REQUIRE:.2f} USDT")
            logger.info(f"📊 Threshold ratio: {threshold_ratio:.2f}x ({threshold_ratio*100:.1f}%)")
            logger.info(f"🔢 Trade composition: {len(trades)} BUY trades over {time_in_window}s window ({pair_type})")

            # Comprehensive validation of aggregated trades FIRST
            from utils import validate_buy_sell_aggregation
            validation_passed, buy_volume, sell_volume = validate_buy_sell_aggregation(
                trades, f"{exchange} {pair_type} aggregated alert"
            )

            # Use corrected volume if validation failed
            if not validation_passed:
                logger.error(f"❌ VALIDATION FAILED for aggregated alert - using only BUY volume")
                corrected_total_value = buy_volume  # Use only buy volume
            else:
                corrected_total_value = total_pending  # Use original total

            # Calculate aggregated values using corrected total
            total_quantity = sum(trade['quantity'] for trade in trades)
            avg_price = corrected_total_value / total_quantity if total_quantity > 0 else 0
            latest_timestamp = max(trade['timestamp'] for trade in trades)

            # For BTC pairs, also calculate USDT equivalent aggregated values
            if is_btc_pair:
                total_usdt_sum = sum(trade.get('usdt_sum_value', 0) for trade in trades)
                avg_usdt_price = total_usdt_sum / total_quantity if total_quantity > 0 else 0
                btc_rate_used = trades[0].get('btc_rate') if trades else None
            else:
                total_usdt_sum = corrected_total_value
                avg_usdt_price = avg_price
                btc_rate_used = None

            # Debug logging for aggregation calculation verification
            logger.debug(f"📊 Aggregation calculation details for {len(trades)} trades:")
            for i, trade in enumerate(trades):
                trade_side = trade.get('trade_side', 'unknown').upper()
                logger.debug(f"  Trade {i+1}: {trade['quantity']:.4f} JKC @ {trade['price']:.6f} USDT = {trade['sum_value']:.2f} USDT ({trade_side})")
            logger.debug(f"  Total: {total_quantity:.4f} JKC, Corrected Value: {corrected_total_value:.2f} USDT")
            logger.debug(f"  Weighted Avg: {corrected_total_value:.2f} / {total_quantity:.4f} = {avg_price:.6f} USDT per JKC")

            # Verification: Check if weighted average calculation is correct
            calculated_total = avg_price * total_quantity
            if abs(calculated_total - corrected_total_value) > 0.01:  # Allow small floating point differences
                logger.error(f"❌ AGGREGATION PRICE CALCULATION MISMATCH: {avg_price:.6f} * {total_quantity:.4f} = {calculated_total:.2f} != {corrected_total_value:.2f}")
            else:
                logger.debug(f"✅ Aggregation price calculation verified: {avg_price:.6f} * {total_quantity:.4f} = {calculated_total:.2f} ≈ {corrected_total_value:.2f}")

            # Send the alert with trade details using corrected values
            if is_btc_pair:
                # For BTC pairs, pass both BTC and USDT values
                await send_alert(
                    avg_price,  # BTC price
                    total_quantity,
                    corrected_total_value,  # Corrected BTC sum value
                    f"{exchange} (Aggregated)",
                    latest_timestamp,
                    trades[0]['exchange_url'],
                    len(trades),
                    trades,  # Pass trade details for breakdown
                    pair_type="JKC/BTC",
                    usdt_price=avg_usdt_price,
                    usdt_sum_value=total_usdt_sum,
                    btc_rate=btc_rate_used
                )
            else:
                # For USDT pairs, use standard call
                await send_alert(
                    avg_price,
                    total_quantity,
                    corrected_total_value,  # Corrected USDT sum value
                    f"{exchange} (Aggregated)",
                    latest_timestamp,
                    trades[0]['exchange_url'],
                    len(trades),
                    trades  # Pass trade details for breakdown
                )
        else:
            logger.info(f"Aggregation window expired: {time_in_window}s >= {aggregation_window}s, total: {total_pending:.2f} USDT < {VALUE_REQUIRE} USDT")

        # Clear the processed trades
        del PENDING_TRADES[exchange][pair_type][buyer_id]

        # If the pair dict is now empty, remove it
        if not PENDING_TRADES[exchange][pair_type]:
            del PENDING_TRADES[exchange][pair_type]

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
        # Make a copy of the pair_types to avoid modification during iteration
        pair_types = list(PENDING_TRADES[exchange].keys())

        for pair_type in pair_types:
            # Make a copy of the buyer_ids to avoid modification during iteration
            buyer_ids = list(PENDING_TRADES[exchange][pair_type].keys())

            for buyer_id in buyer_ids:
                # Check if this aggregation window has expired
                aggregation_data = PENDING_TRADES[exchange][pair_type][buyer_id]
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

                    # Debug logging for expired aggregation calculation verification
                    logger.debug(f"Expired aggregation calculation details for {len(trades)} trades:")
                    for i, trade in enumerate(trades):
                        logger.debug(f"  Trade {i+1}: {trade['quantity']:.4f} JKC @ {trade['price']:.6f} USDT = {trade['sum_value']:.2f} USDT")
                    logger.debug(f"  Total: {total_quantity:.4f} JKC, Total Value: {total_value:.2f} USDT")
                    logger.debug(f"  Weighted Avg: {total_value:.2f} / {total_quantity:.4f} = {avg_price:.6f} USDT per JKC")

                    # Verification: Check if weighted average calculation is correct
                    calculated_total = avg_price * total_quantity
                    if abs(calculated_total - total_value) > 0.01:  # Allow small floating point differences
                        logger.error(f"EXPIRED AGGREGATION PRICE CALCULATION MISMATCH: {avg_price:.6f} * {total_quantity:.4f} = {calculated_total:.2f} != {total_value:.2f}")
                    else:
                        logger.debug(f"Expired aggregation price calculation verified: {avg_price:.6f} * {total_quantity:.4f} = {calculated_total:.2f} ≈ {total_value:.2f}")

                    logger.info(f"Processing expired aggregated trades: {len(trades)} trades, {total_quantity} JKC, {total_value} USDT")

                    # Send the alert with trade details
                    await send_alert(
                        avg_price,
                        total_quantity,
                        total_value,
                        f"{exchange} (Aggregated)",
                        latest_timestamp,
                        trades[0]['exchange_url'],
                        len(trades),
                        trades  # Pass trade details for breakdown
                    )
                else:
                    logger.info(f"Expired aggregated trades below threshold: {total_value} USDT < {VALUE_REQUIRE} USDT")

                # Remove these trades
                del PENDING_TRADES[exchange][pair_type][buyer_id]

                # If the pair_type dict is now empty, remove it
                if not PENDING_TRADES[exchange][pair_type]:
                    del PENDING_TRADES[exchange][pair_type]

                # If the exchange dict is now empty, remove it
                if not PENDING_TRADES[exchange]:
                    del PENDING_TRADES[exchange]

# validate_price_calculation function is imported from utils.py

def validate_buy_volume_aggregation(trades_list, expected_total, context="Unknown"):
    """Validate that buy volume aggregation is correct and excludes sell trades."""
    buy_trades = []
    sell_trades = []
    unknown_trades = []

    for trade in trades_list:
        trade_side = trade.get('trade_side', 'unknown').lower()
        if trade_side in ['buy', 'b']:
            buy_trades.append(trade)
        elif trade_side in ['sell', 's']:
            sell_trades.append(trade)
        else:
            unknown_trades.append(trade)

    # Calculate volumes
    buy_volume = sum(t['sum_value'] for t in buy_trades)
    sell_volume = sum(t['sum_value'] for t in sell_trades)
    unknown_volume = sum(t['sum_value'] for t in unknown_trades)
    total_volume = buy_volume + sell_volume + unknown_volume

    # Log detailed breakdown
    logger.info(f"📊 BUY VOLUME VALIDATION for {context}:")
    logger.info(f"  🟢 BUY trades: {len(buy_trades)} trades = ${buy_volume:.2f} USDT")
    logger.info(f"  🔴 SELL trades: {len(sell_trades)} trades = ${sell_volume:.2f} USDT")
    logger.info(f"  ⚪ UNKNOWN trades: {len(unknown_trades)} trades = ${unknown_volume:.2f} USDT")
    logger.info(f"  💰 Total volume: ${total_volume:.2f} USDT")
    logger.info(f"  🎯 Expected total: ${expected_total:.2f} USDT")

    # Validation checks
    validation_passed = True

    # Check if sell trades are incorrectly included
    if sell_trades:
        logger.error(f"❌ SELL TRADES DETECTED: {len(sell_trades)} sell trades should not be included in buy volume!")
        validation_passed = False

    # Check total calculation
    if abs(total_volume - expected_total) > 0.01:
        logger.error(f"❌ VOLUME CALCULATION MISMATCH: {total_volume:.2f} != {expected_total:.2f}")
        validation_passed = False

    # Check individual trade calculations
    for i, trade in enumerate(buy_trades[:5]):  # Check first 5 trades
        expected_trade_value = trade['price'] * trade['quantity']
        if abs(trade['sum_value'] - expected_trade_value) > 0.01:
            logger.error(f"❌ TRADE {i+1} CALCULATION ERROR: {trade['sum_value']:.2f} != {expected_trade_value:.2f}")
            validation_passed = False

    if validation_passed:
        logger.info(f"✅ Buy volume aggregation validated: ${buy_volume:.2f} USDT from {len(buy_trades)} BUY trades")

    return validation_passed, buy_volume, sell_volume

async def send_alert(price, quantity, sum_value, exchange, timestamp, exchange_url, num_trades=1, trade_details=None,
                     pair_type="JKC/USDT", usdt_price=None, usdt_sum_value=None, btc_rate=None):
    """Send an alert to all active chats with robust error handling and fallback."""
    global PHOTO

    # Determine pair type for validation
    pair_currency = "BTC" if pair_type == "JKC/BTC" else "USDT"

    # Validate the alert calculation before sending
    is_valid, corrected_value = validate_price_calculation(price, quantity, sum_value, f"Alert from {exchange}", pair_currency)
    if not is_valid:
        logger.warning(f"Alert calculation corrected: {sum_value:.2f} -> {corrected_value:.2f} USDT")
        sum_value = corrected_value  # Use corrected value for the alert

    # Enhanced logging for alert processing
    logger.info(f"🚨 ALERT TRIGGERED: {quantity:.4f} JKC at ${price:.6f} = ${sum_value:.2f} USDT from {exchange}")
    logger.info(f"📊 Alert details: {num_trades} trade(s), threshold: ${VALUE_REQUIRE} USDT")

    # Log individual trade details if provided
    if trade_details and len(trade_details) > 1:
        logger.info(f"📋 Individual trade breakdown:")
        for i, trade in enumerate(trade_details[:5]):  # Log first 5 trades
            trade_side = trade.get('trade_side', 'unknown').upper()
            logger.info(f"  Trade {i+1}: {trade['quantity']:.4f} JKC @ ${trade['price']:.6f} = ${trade['sum_value']:.2f} USDT ({trade_side})")
        if len(trade_details) > 5:
            logger.info(f"  ... and {len(trade_details) - 5} more trades")

    # Get a random image for this alert with enhanced error handling
    random_photo = None
    try:
        random_photo = load_random_image()
        if random_photo is None:
            random_photo = PHOTO  # Fallback to global PHOTO if no random image available
            logger.info("Using global PHOTO as fallback image")
        else:
            logger.info("Successfully loaded random image for alert")
    except Exception as image_load_error:
        logger.warning(f"Image loading failed, will use text-only alert: {image_load_error}")
        random_photo = None

    # Get comprehensive market data for additional context
    try:
        # Fetch real-time prices for both trading pairs
        market_data_usdt = await get_nonkyc_ticker()  # JKC/USDT
        volume_data = await calculate_combined_volume_periods()
        volume_periods = volume_data["combined"]

        # Get current prices for both pairs
        current_price_usdt = market_data_usdt.get("lastPriceNumber", price) if market_data_usdt else price
        market_cap = market_data_usdt.get("marketcapNumber", 0) if market_data_usdt else 0

        # JKC only trades against USDT - no BTC conversion needed
        current_price_btc = 0  # BTC functionality removed, set to 0
        current_price_usdt_from_btc = price  # Price is already in USDT

    except Exception as e:
        logger.warning(f"Could not fetch market data for alert: {e}")
        market_cap = 0
        current_price_usdt = price
        current_price_btc = 0
        current_price_usdt_from_btc = price
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
        alert_text = "🔥 <b>MAJOR Buy Alert JunkCoin Traders!</b> 🔥"
    elif magnitude_ratio >= 2:
        alert_text = "💥 <b>SIGNIFICANT Transaction Alert!</b> 💥"
    else:
        alert_text = "🚨 <b>Buy Transaction Detected</b> 🚨"

    # Add special emoji for sweep orders
    if "Sweep" in exchange and "Sweep Buy" in exchange:
        alert_text = alert_text.replace("TRANSACTION", "SWEEP BUY")
        alert_text = alert_text.replace("Transaction", "Sweep Buy")
        alert_text = alert_text.replace("Buy", "Sweep Buy")

    # JKC only trades against USDT
    message = (
        f"{magnitude_indicator}\n\n"
        f"{alert_text}\n\n"
        f"💰 <b>Amount:</b> {quantity:.4f} JKC\n"
        f"💵 <b>Trade Price:</b> ${price:.6f} USDT\n"
        f"💲 <b>Total Value:</b> ${sum_value:.2f} USDT\n"
        f"🏦 <b>Exchange:</b> {exchange}\n"
    )

    # Add number of trades if it's an aggregated alert
    if num_trades > 1:
        message += f"🔄 <b>Trades:</b> {num_trades} BUY orders\n"

    message += f"⏰ <b>Time:</b> {formatted_time}\n"

    # Add individual buy order details for aggregated alerts
    if trade_details and len(trade_details) > 1:
        message += f"\n📋 <b>Aggregated Buy Orders:</b>\n"

        # Display individual orders (up to 5)
        orders_to_show = min(5, len(trade_details))
        for i in range(orders_to_show):
            trade = trade_details[i]
            if pair_type == "JKC/BTC":
                # Format for BTC pairs with USDT equivalent
                usdt_equiv = trade.get('usdt_price', 0)
                if usdt_equiv:
                    message += f"Order {i+1}: {trade['quantity']:.4f} JKC at {trade['price']:.8f} BTC (≈ ${usdt_equiv:.6f} USDT)\n"
                else:
                    message += f"Order {i+1}: {trade['quantity']:.4f} JKC at {trade['price']:.8f} BTC\n"
            else:
                # Format for USDT pairs
                message += f"Order {i+1}: {trade['quantity']:.4f} JKC at ${trade['price']:.6f} USDT\n"

        # If more than 5 orders, aggregate the remaining ones
        if len(trade_details) > 5:
            remaining_trades = trade_details[5:]
            remaining_quantity = sum(t['quantity'] for t in remaining_trades)
            remaining_count = len(remaining_trades)
            message += f"Orders 6-{len(trade_details)}: {remaining_quantity:.4f} JKC total ({remaining_count} additional orders)\n"

        # Add summary calculations
        message += f"\n📊 <b>Summary:</b>\n"
        if pair_type == "JKC/BTC":
            message += f"Average Price: {price:.8f} BTC\n"
            if usdt_price:
                message += f"USDT Equivalent: ≈ ${usdt_price:.6f} USDT\n"
            message += f"Total Volume: {quantity:.4f} JKC\n"
            message += f"Total Value: {sum_value:.8f} BTC\n"
            if usdt_sum_value:
                message += f"USDT Equivalent: ≈ ${usdt_sum_value:.2f} USDT\n"
        else:
            message += f"Average Price: ${price:.6f} USDT\n"
            message += f"Total Volume: {quantity:.4f} JKC\n"
            message += f"Total Value: ${sum_value:.2f} USDT\n"

    # Add real-time price information
    message += f"\n📊 <b>Current Market Prices:</b>\n"
    if current_price_usdt > 0:
        price_change_usdt = ((current_price_usdt - price) / price) * 100 if price > 0 else 0
        price_change_emoji = "📈" if price_change_usdt >= 0 else "📉"
        message += f"💵 JKC/USDT: ${current_price_usdt:.6f} {price_change_emoji} ({price_change_usdt:+.2f}%)\n"

    if current_price_btc > 0:
        message += f"₿ JKC/BTC: {current_price_btc:.8f} BTC\n"

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
    
    # Send to all active chats with comprehensive error handling
    bot = Bot(token=BOT_TOKEN)
    successful_deliveries = 0
    failed_deliveries = 0

    logger.info(f"📤 Attempting to send alert to {len(ACTIVE_CHAT_IDS)} chat(s): {ACTIVE_CHAT_IDS}")

    for chat_id in ACTIVE_CHAT_IDS:
        chat_type = "private" if chat_id > 0 else "group/supergroup"
        logger.info(f"📱 Sending alert to {chat_type} chat {chat_id}")

        try:
            # Pre-validate chat access
            try:
                await bot.get_chat(chat_id)
                logger.info(f"✅ Chat {chat_id} is accessible")
            except Exception as access_error:
                logger.error(f"❌ Chat {chat_id} is not accessible: {access_error}")
                failed_deliveries += 1
                continue

            # Attempt image delivery first
            if random_photo:
                try:
                    # Enhanced image type detection for animations (GIF and MP4)
                    is_animation = False
                    image_filename = ""

                    if hasattr(random_photo, 'name'):
                        image_filename = random_photo.name
                        # Check for both GIF and MP4 (converted GIF) files
                        is_animation = (image_filename.lower().endswith('.gif') or
                                      image_filename.lower().endswith('.mp4'))
                    elif isinstance(random_photo, str):
                        image_filename = random_photo
                        # Check for both GIF and MP4 (converted GIF) files
                        is_animation = (image_filename.lower().endswith('.gif') or
                                      image_filename.lower().endswith('.mp4'))

                        # Also check file type detection for MP4 files
                        try:
                            detected_type = detect_file_type(image_filename)
                            if detected_type == 'mp4':
                                is_animation = True
                        except:
                            pass  # If detection fails, rely on extension check

                    logger.info(f"🖼️ Attempting to send {'animation' if is_animation else 'static image'}: {image_filename}")

                    if is_animation:
                        # Use send_animation for GIF and MP4 files to preserve animation
                        await bot.send_animation(
                            chat_id=chat_id,
                            animation=random_photo,
                            caption=message,
                            reply_markup=keyboard,
                            parse_mode="HTML",
                            read_timeout=30,
                            write_timeout=30
                        )
                        logger.info(f"✅ Alert with animation sent successfully to chat {chat_id}")
                    else:
                        # Use send_photo for static images
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=random_photo,
                            caption=message,
                            reply_markup=keyboard,
                            parse_mode="HTML",
                            read_timeout=30,
                            write_timeout=30
                        )
                        logger.info(f"✅ Alert with static image sent successfully to chat {chat_id}")

                    successful_deliveries += 1

                except Exception as image_error:
                    # Enhanced image error logging
                    logger.warning(f"🖼️ Image sending failed for chat {chat_id}: {type(image_error).__name__}: {image_error}")

                    # Implement robust text-only fallback
                    try:
                        fallback_message = f"🖼️ <b>JKC Alert</b> (Image delivery failed)\n\n{message}"
                        await bot.send_message(
                            chat_id=chat_id,
                            text=fallback_message,
                            reply_markup=keyboard,
                            parse_mode="HTML",
                            read_timeout=30,
                            write_timeout=30
                        )
                        logger.info(f"✅ Fallback text-only alert sent successfully to chat {chat_id}")
                        successful_deliveries += 1
                    except Exception as fallback_error:
                        logger.error(f"❌ Fallback text-only alert also failed for chat {chat_id}: {fallback_error}")
                        failed_deliveries += 1
            else:
                # No image available, send text-only alert
                try:
                    text_only_message = f"📝 <b>JKC Alert</b> (Text-only mode)\n\n{message}"
                    await bot.send_message(
                        chat_id=chat_id,
                        text=text_only_message,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                        read_timeout=30,
                        write_timeout=30
                    )
                    logger.info(f"✅ Text-only alert sent successfully to chat {chat_id}")
                    successful_deliveries += 1
                except Exception as text_error:
                    logger.error(f"❌ Text-only alert failed for chat {chat_id}: {text_error}")
                    failed_deliveries += 1

        except Exception as e:
            logger.error(f"❌ Unexpected error sending alert to chat {chat_id}: {type(e).__name__}: {e}")
            print(f"Error sending message to chat {chat_id}: {e}")
            failed_deliveries += 1

    # Final delivery summary
    total_chats = len(ACTIVE_CHAT_IDS)
    logger.info(f"📊 ALERT DELIVERY SUMMARY: {successful_deliveries}/{total_chats} successful, {failed_deliveries}/{total_chats} failed")

    if successful_deliveries == 0:
        logger.error(f"🚨 CRITICAL: Alert delivery failed to ALL chats for ${sum_value:.2f} USDT trade!")
    elif failed_deliveries > 0:
        logger.warning(f"⚠️ Partial delivery failure: {failed_deliveries} chat(s) did not receive the alert")
    else:
        logger.info(f"🎉 Perfect delivery: Alert successfully sent to all {total_chats} chat(s)")

async def chart_command(update: Update, context: CallbackContext) -> None:
    """Generate and send price chart for JKC/USDT pair."""
    await update.message.reply_text("📊 Generating JKC/USDT chart, please wait...")

    try:
        # Get historical trades for JKC/USDT
        trades_usdt = await get_nonkyc_trades()

        if not trades_usdt:
            await update.message.reply_text("❌ No trade data available to generate charts.")
            return

        # Convert to DataFrame for USDT pair
        df_usdt = pd.DataFrame(trades_usdt)
        df_usdt['timestamp'] = pd.to_datetime(df_usdt['timestamp'])
        df_usdt['price'] = df_usdt['price'].astype(float)
        df_usdt['quantity'] = df_usdt['quantity'].astype(float)
        df_usdt = df_usdt.sort_values('timestamp')

        # Create JKC/USDT chart
        fig_usdt = go.Figure(data=[go.Scatter(
            x=df_usdt['timestamp'],
            y=df_usdt['price'],
            mode='lines',
            name='JKC/USDT',
            line=dict(color='#00D4AA', width=2)  # NonKYC green color
        )])

        fig_usdt.update_layout(
            title='📈 JKC/USDT Price Chart (NonKYC Exchange)',
            xaxis_title='Time',
            yaxis_title='Price (USDT)',
            template='plotly_dark',
            autosize=True,
            width=1000,
            height=600,
            font=dict(size=12),
            title_font=dict(size=16)
        )

        # Save JKC/USDT chart
        chart_usdt_path = 'temp_chart_usdt.png'
        fig_usdt.write_image(chart_usdt_path)

        # Send JKC/USDT chart with trading link
        usdt_caption = (
            "📊 <b>JKC/USDT Price Chart</b>\n"
            "💱 <a href='https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3'>Trade JKC/USDT on NonKYC</a>\n"
            "📈 Real-time trading data from NonKYC Exchange"
        )

        with open(chart_usdt_path, 'rb') as f:
            await update.message.reply_photo(
                photo=f,
                caption=usdt_caption,
                parse_mode="HTML"
            )

        # BTC pair removed - JKC only trades against USDT

        # Clean up USDT chart
        os.remove(chart_usdt_path)

        # Send summary message with trading links
        summary_message = (
            "📊 <b>JKC Trading on NonKYC Exchange</b>\n\n"
            "💱 <a href='https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3'>JKC/USDT Trading</a>\n\n"
            "🌐 <a href='https://nonkyc.io'>Visit NonKYC Exchange</a>"
        )

        await update.message.reply_text(summary_message, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error generating charts: {e}")
        await update.message.reply_text(f"❌ Error generating charts: {str(e)}")

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

    if not await can_use_admin_commands(update, context):
        logger.warning(f"User {user_id} tried to use setmin command without admin permissions")
        chat_id = update.effective_chat.id
        public_supergroups = CONFIG.get("public_supergroups", [])
        if chat_id in public_supergroups:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "The /setmin command is restricted to the bot owner only.\n"
                "This is a public supergroup where settings are managed centrally.\n\n"
                "📊 You can still use:\n"
                "• /help - View available commands\n"
                "• /price - Check current JKC price\n"
                "• /chart - Generate price chart",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "You do not have permission to set the minimum threshold value.\n"
                "This command is restricted to bot administrators only.",
                parse_mode="HTML"
            )
        return ConversationHandler.END

    logger.info(f"User {user_id} has admin permissions, proceeding with setmin command")

    # Get current configuration for context
    dynamic_enabled = CONFIG.get("dynamic_threshold", {}).get("enabled", False)
    aggregation_enabled = CONFIG.get("trade_aggregation", {}).get("enabled", True)

    prompt_message = (
        f"⚙️ <b>Set Minimum Alert Threshold</b>\n\n"
        f"🎯 <b>Current Value:</b> ${VALUE_REQUIRE:.2f} USDT\n"
        f"📊 <b>Dynamic Threshold:</b> {'Enabled' if dynamic_enabled else 'Disabled'}\n"
        f"🔄 <b>Trade Aggregation:</b> {'Enabled' if aggregation_enabled else 'Disabled'}\n\n"
        f"💡 <b>Please enter the new minimum threshold value:</b>\n\n"
        f"<b>Valid Range:</b> $0.01 - $100,000 USDT\n"
        f"<b>Examples:</b>\n"
        f"• <code>100</code> (for $100 USDT)\n"
        f"• <code>250.50</code> (for $250.50 USDT)\n"
        f"• <code>1000</code> (for $1,000 USDT)\n\n"
        f"🔔 <i>The bot will alert on JKC transactions at or above this value.</i>"
    )

    await update.message.reply_text(prompt_message, parse_mode="HTML")
    return INPUT_NUMBER

async def set_minimum_input(update: Update, context: CallbackContext) -> int:
    global VALUE_REQUIRE, CONFIG

    user_id = update.effective_user.id
    input_text = update.message.text.strip()

    logger.info(f"User {user_id} attempting to set minimum value to: {input_text}")

    try:
        # Parse the input value
        new_value = float(input_text)

        # Store old value for comparison
        old_value = VALUE_REQUIRE

        # Validate the input value
        if new_value <= 0:
            await update.message.reply_text(
                "❌ <b>Invalid Value</b>\n\n"
                "Minimum threshold must be positive.\n"
                "Please enter a value greater than 0.",
                parse_mode="HTML"
            )
            logger.warning(f"User {user_id} entered non-positive value: {new_value}")
            return INPUT_NUMBER

        # Check for reasonable range (0.01 to 100,000 USDT)
        if new_value < 0.01:
            await update.message.reply_text(
                "❌ <b>Value Too Small</b>\n\n"
                "Minimum threshold is too small.\n"
                "Please enter a value of at least $0.01 USDT.",
                parse_mode="HTML"
            )
            logger.warning(f"User {user_id} entered value too small: {new_value}")
            return INPUT_NUMBER

        if new_value > 100000:
            await update.message.reply_text(
                "❌ <b>Value Too Large</b>\n\n"
                "Minimum threshold is too large.\n"
                "Please enter a value between $0.01 and $100,000 USDT.",
                parse_mode="HTML"
            )
            logger.warning(f"User {user_id} entered value too large: {new_value}")
            return INPUT_NUMBER

        # Update the global value and configuration
        VALUE_REQUIRE = new_value
        CONFIG["value_require"] = new_value

        # Save configuration to file
        try:
            save_config(CONFIG)
            logger.info(f"Configuration saved successfully. Minimum value updated from {old_value} to {new_value} USDT")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            # Revert the change if save failed
            VALUE_REQUIRE = old_value
            CONFIG["value_require"] = old_value
            await update.message.reply_text(
                "❌ <b>Configuration Save Failed</b>\n\n"
                "Could not save the new threshold value to configuration file.\n"
                "Please try again or contact the administrator.",
                parse_mode="HTML"
            )
            return ConversationHandler.END

        # Determine change direction for emoji
        if new_value > old_value:
            change_emoji = "📈"
            change_text = "increased"
        elif new_value < old_value:
            change_emoji = "📉"
            change_text = "decreased"
        else:
            change_emoji = "➡️"
            change_text = "unchanged"

        # Calculate percentage change
        if old_value > 0:
            percent_change = ((new_value - old_value) / old_value) * 100
            if abs(percent_change) >= 0.01:  # Only show if change is significant
                percent_text = f" ({percent_change:+.1f}%)"
            else:
                percent_text = ""
        else:
            percent_text = ""

        # Send comprehensive success message
        success_message = (
            f"✅ <b>Minimum Threshold Updated Successfully!</b>\n\n"
            f"{change_emoji} <b>Previous Value:</b> ${old_value:.2f} USDT\n"
            f"🎯 <b>New Value:</b> ${new_value:.2f} USDT{percent_text}\n\n"
            f"📊 <b>Status:</b> Threshold {change_text}\n"
            f"💾 <b>Configuration:</b> Saved to file\n"
            f"⚡ <b>Effect:</b> Active immediately\n\n"
            f"🔔 The bot will now alert on JKC transactions of ${new_value:.2f} USDT or higher."
        )

        await update.message.reply_text(success_message, parse_mode="HTML")
        logger.info(f"User {user_id} successfully updated minimum threshold from {old_value} to {new_value} USDT")

    except ValueError:
        await update.message.reply_text(
            "❌ <b>Invalid Input Format</b>\n\n"
            "Please enter a valid number.\n\n"
            "<b>Examples:</b>\n"
            "• <code>100</code> (for $100 USDT)\n"
            "• <code>50.5</code> (for $50.50 USDT)\n"
            "• <code>1000</code> (for $1,000 USDT)\n\n"
            "Try again with a numeric value:",
            parse_mode="HTML"
        )
        logger.warning(f"User {user_id} entered invalid format: {input_text}")
        return INPUT_NUMBER

    except Exception as e:
        logger.error(f"Unexpected error in set_minimum_input: {e}")
        await update.message.reply_text(
            "❌ <b>Unexpected Error</b>\n\n"
            "An unexpected error occurred while updating the threshold.\n"
            "Please try again or contact the administrator.",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    return ConversationHandler.END

async def set_image_command(update: Update, context: CallbackContext) -> int:
    """Command to set the image used in alerts."""
    user_id = update.effective_user.id
    logger.info(f"setimage command called by user {user_id}")

    if not await can_use_admin_commands(update, context):
        logger.warning(f"User {user_id} tried to use setimage command without admin permissions")
        chat_id = update.effective_chat.id
        public_supergroups = CONFIG.get("public_supergroups", [])
        if chat_id in public_supergroups:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "The /setimage command is restricted to the bot owner only.\n"
                "This is a public supergroup where settings are managed centrally.",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "You do not have permission to set the image.\n"
                "This command is restricted to administrators only.",
                parse_mode="HTML"
            )
        return ConversationHandler.END

    logger.info(f"User {user_id} has admin permissions, proceeding with setimage command")
    await update.message.reply_text(
        "Please send the image you want to use for alerts.\n"
        "The image should be clear and appropriate."
    )
    return INPUT_IMAGE_SETIMAGE

async def set_image_input(update: Update, context: CallbackContext) -> int:
    global PHOTO, CONFIG

    try:
        logger.info(f"Processing image upload from user {update.effective_user.id}")

        # Handle different types of media with enhanced detection
        file = None
        file_extension = ".jpg"  # Default
        media_type = "unknown"

        if update.message.photo:
            # Regular photo
            photo = update.message.photo[-1]  # Get highest resolution
            file = await photo.get_file()
            file_extension = ".jpg"
            media_type = "photo"
            logger.info(f"Processing photo: file_id={file.file_id}, file_size={file.file_size}")
        elif update.message.document:
            # Document (could be image file)
            document = update.message.document
            file = await document.get_file()
            media_type = "document"

            # Get extension from filename or mime type
            if document.file_name:
                file_extension = os.path.splitext(document.file_name)[1].lower()
                if not file_extension:
                    file_extension = ".jpg"
                logger.info(f"Processing document: file_id={file.file_id}, file_size={file.file_size}, name={document.file_name}, mime={document.mime_type}")
            else:
                # Try to determine from MIME type
                mime_type = document.mime_type or ""
                if "gif" in mime_type:
                    file_extension = ".gif"
                elif "png" in mime_type:
                    file_extension = ".png"
                elif "jpeg" in mime_type or "jpg" in mime_type:
                    file_extension = ".jpg"
                elif "webp" in mime_type:
                    file_extension = ".webp"
                logger.info(f"Processing document without filename: file_id={file.file_id}, mime={mime_type}, assigned_ext={file_extension}")
        elif update.message.animation:
            # GIF/animation - Telegram converts GIFs to MP4
            animation = update.message.animation
            file = await animation.get_file()
            media_type = "animation"

            # Telegram animations are typically MP4 format, even if originally GIF
            file_extension = ".mp4"  # Telegram converts GIFs to MP4
            logger.info(f"Processing animation (GIF→MP4): file_id={file.file_id}, file_size={file.file_size}, mime={animation.mime_type}")
        else:
            logger.error("No supported media type found in message")
            await update.message.reply_text("❌ Please send a photo, image file, or GIF.")
            return ConversationHandler.END

        # Download the image
        image_data = await file.download_as_bytearray()
        logger.info(f"Downloaded image data: {len(image_data)} bytes")

        # Ensure images directory exists
        ensure_images_directory()

        # Generate unique filename with timestamp
        timestamp = int(time.time())
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

        # Detect the actual file type after saving
        detected_type = detect_file_type(image_path)

        # Get collection count
        collection_count = len(get_image_collection())

        # Create detailed success message
        type_info = {
            'photo': '📷 Photo (JPEG)',
            'document': f'📄 Document ({detected_type.upper()})',
            'animation': '🎬 Animation (GIF→MP4 conversion)'
        }.get(media_type, f'📁 File ({detected_type.upper()})')

        await update.message.reply_text(
            f"✅ Image added to collection successfully!\n"
            f"📁 Collection now has {collection_count} images\n"
            f"🎲 Images will be randomly selected for alerts\n"
            f"📄 Saved as: {filename}\n"
            f"🎯 Type: {type_info}\n"
            f"💾 Size: {len(image_data)} bytes ({len(image_data)/1024:.1f} KB)"
        )
        logger.info(f"Image upload completed successfully. Collection now has {collection_count} images. Type: {media_type}→{detected_type}, File: {filename}")

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

    # Check if user can start/stop bot using enhanced permission system
    if await can_start_stop_bot(update, context):
        if chat_id not in ACTIVE_CHAT_IDS:
            ACTIVE_CHAT_IDS.append(chat_id)
            CONFIG["active_chat_ids"] = ACTIVE_CHAT_IDS
            save_config(CONFIG)

            # Get aggregation status
            aggregation_enabled = CONFIG.get("trade_aggregation", {}).get("enabled", True)
            aggregation_window = CONFIG.get("trade_aggregation", {}).get("window_seconds", 3)

            # Send welcome message with commands
            welcome_text = (
                "🎉 <b>JunkCoin (JKC) Alert Bot Started!</b> 🎉\n\n"
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
        # Enhanced error message based on chat type
        chat_type = "private chat" if chat_id > 0 else "group/supergroup"
        public_supergroups = CONFIG.get("public_supergroups", [])
        if chat_id in public_supergroups:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "The /start command is restricted to the bot owner only.\n"
                "This is a public supergroup where alerts are managed centrally.\n\n"
                "📊 You can still use:\n"
                "• /help - View available commands\n"
                "• /price - Check current JKC price\n"
                "• /chart - Generate price chart\n"
                "• /debug - View your user info",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Permission Denied</b>\n\n"
                f"You don't have permission to start/stop alerts in this {chat_type}.\n"
                f"Only the bot owner can control alert settings.\n\n"
                f"📊 You can still use public commands like /help, /price, and /chart.",
                parse_mode="HTML"
            )

async def stop_bot(update: Update, context: CallbackContext) -> None:
    global ACTIVE_CHAT_IDS, CONFIG

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Debug log
    logger.info(f"Stop command accessed by user ID: {user_id}, BOT_OWNER: {BOT_OWNER}")

    # Check if user can start/stop bot using enhanced permission system
    if await can_start_stop_bot(update, context):
        if chat_id in ACTIVE_CHAT_IDS:
            ACTIVE_CHAT_IDS.remove(chat_id)
            CONFIG["active_chat_ids"] = ACTIVE_CHAT_IDS
            save_config(CONFIG)
            await update.message.reply_text(
                "🛑 <b>JKC Alert Bot Stopped</b>\n\n"
                "You will no longer receive alerts in this chat.\n"
                "Use /start to resume alerts.",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "ℹ️ <b>Bot Not Running</b>\n\n"
                "Alerts are not currently active in this chat.\n"
                "Use /start to begin receiving alerts.",
                parse_mode="HTML"
            )
    else:
        # Enhanced error message based on chat type
        chat_type = "private chat" if chat_id > 0 else "group/supergroup"
        public_supergroups = CONFIG.get("public_supergroups", [])
        if chat_id in public_supergroups:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "The /stop command is restricted to the bot owner only.\n"
                "This is a public supergroup where alerts are managed centrally.\n\n"
                "📊 You can still use:\n"
                "• /help - View available commands\n"
                "• /price - Check current JKC price\n"
                "• /chart - Generate price chart\n"
                "• /debug - View your user info",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Permission Denied</b>\n\n"
                f"You don't have permission to start/stop alerts in this {chat_type}.\n"
                f"Only the bot owner can control alert settings.\n\n"
                f"📊 You can still use public commands like /help, /price, and /chart.",
                parse_mode="HTML"
            )

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

    # Get market data for current price - try NonKYC first, then LiveCoinWatch as fallback
    market_data = await get_nonkyc_ticker()
    data_source = "NonKYC Exchange"

    if not market_data:
        logger.info("NonKYC API failed, using LiveCoinWatch fallback")
        market_data = await get_livecoinwatch_data()
        data_source = "LiveCoinWatch"

    if not market_data:
        await update.message.reply_text("Error fetching market data from all sources. Please try again later.")
        return

    # Get combined volume data from both exchanges
    volume_data = await calculate_combined_volume_periods()
    volume_periods = volume_data.get("combined", {}) if volume_data else {}

    # Ensure all volume periods have default values
    volume_periods = {
        "15m": volume_periods.get("15m", 0) or 0,
        "1h": volume_periods.get("1h", 0) or 0,
        "4h": volume_periods.get("4h", 0) or 0,
        "24h": volume_periods.get("24h", 0) or 0
    }

    # Extract data based on source with safety checks first
    if data_source == "LiveCoinWatch":
        # LiveCoinWatch API format
        current_price = market_data.get("rate", 0) or 0
        volume_24h_usdt = market_data.get("volume", 0) or 0
        market_cap_nonkyc = market_data.get("cap", 0) or 0
        total_supply = market_data.get("totalSupply", 0) or 0

        # Calculate 24h change from delta object
        delta = market_data.get("delta", {}) or {}
        change_percent = delta.get("day", 0) if delta else 0
        change_percent = change_percent or 0

        # LiveCoinWatch doesn't provide all fields, set defaults
        yesterday_price = current_price / (1 + change_percent/100) if change_percent != 0 else current_price
        high_24h = current_price * 1.05  # Estimate
        low_24h = current_price * 0.95   # Estimate
        volume_24h_jkc = volume_24h_usdt / current_price if current_price > 0 else 0
        best_bid = current_price * 0.999  # Estimate
        best_ask = current_price * 1.001  # Estimate
        spread_percent = 0.2  # Estimate
    else:
        # NonKYC API format with safety checks
        current_price = market_data.get("lastPriceNumber", 0) or 0
        yesterday_price = market_data.get("yesterdayPriceNumber", 0) or 0
        high_24h = market_data.get("highPriceNumber", 0) or 0
        low_24h = market_data.get("lowPriceNumber", 0) or 0
        volume_24h_jkc = market_data.get("volumeNumber", 0) or 0
        volume_24h_usdt = market_data.get("volumeUsdNumber", 0) or 0
        change_percent = market_data.get("changePercentNumber", 0) or 0
        market_cap_nonkyc = market_data.get("marketcapNumber", 0) or 0
        best_bid = market_data.get("bestBidNumber", 0) or 0
        best_ask = market_data.get("bestAskNumber", 0) or 0
        spread_percent = market_data.get("spreadPercentNumber", 0) or 0

    # Get momentum data for different timeframes
    momentum_periods = {"15m": 0, "1h": 0, "4h": 0, "24h": 0}
    try:
        trades_data = await get_nonkyc_trades()
        if trades_data and data_source == "NonKYC Exchange":
            momentum_periods = await calculate_momentum_periods(trades_data, current_price)
    except Exception as e:
        logger.warning(f"Could not calculate momentum periods: {e}")

    # Calculate additional metrics
    price_change_usdt = current_price - yesterday_price if yesterday_price > 0 else 0

    # Format change with crypto-appropriate emojis
    if change_percent >= 10:
        change_emoji = "🚀"
    elif change_percent >= 5:
        change_emoji = "📈"
    elif change_percent > 0:
        change_emoji = "⬆️"
    elif change_percent >= -5:
        change_emoji = "➡️"
    elif change_percent >= -10:
        change_emoji = "⬇️"
    elif change_percent >= -20:
        change_emoji = "📉"
    else:
        change_emoji = "💀"

    change_sign = "+" if change_percent >= 0 else ""

    # Create buttons with trading links
    button1 = InlineKeyboardButton(
        text="📊 CoinGecko", url="https://www.coingecko.com/en/coins/junkcoin")
    button2 = InlineKeyboardButton(
        text="📈 CoinMarketCap", url="https://coinmarketcap.com/currencies/junkcoin/")
    button3 = InlineKeyboardButton(
        text="💱 Trade JKC/USDT", url="https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3")
    button4 = InlineKeyboardButton(
        text="🔍 Explorer", url="https://jkc-explorer.dedoo.xyz/")
    button5 = InlineKeyboardButton(
        text="🌐 JunkCoin Website", url="https://junk-coin.com/")
    button6 = InlineKeyboardButton(
        text="💰 Get JKC Wallet", url="https://junk-coin.com/wallets/")
    keyboard = InlineKeyboardMarkup([
        [button1, button2],
        [button3, button4],
        [button5, button6]
    ])

    # Remove market sentiment - keep display professional and data-driven

    # Format momentum values with proper signs and emojis
    def format_momentum(value):
        if value > 0:
            return f"+{value:.2f}%"
        elif value < 0:
            return f"{value:.2f}%"
        else:
            return "0.00%"

    # Format the message with rich data including momentum and volume periods
    message = (
        f"🪙 <b>JunkCoin (JKC) Market Data</b> 🪙\n\n"
        f"💰 <b>Price:</b> ${current_price:.6f} USDT\n"
        f"{change_emoji} <b>24h Change:</b> {change_sign}{change_percent:.2f}% "
        f"({change_sign}${price_change_usdt:.6f})\n\n"

        f"🏦 <b>Market Cap:</b> ${market_cap_nonkyc:,}\n\n"

        f"📊 <b>Momentum (Price Change):</b>\n"
        f"🕐 <b>15m:</b> {format_momentum(momentum_periods['15m'])}\n"
        f"🕐 <b>1h:</b> {format_momentum(momentum_periods['1h'])}\n"
        f"🕐 <b>4h:</b> {format_momentum(momentum_periods['4h'])}\n"
        f"🕐 <b>24h:</b> {format_momentum(momentum_periods['24h'])}\n\n"

        f"📊 <b>24h Statistics:</b>\n"
        f"📈 <b>High:</b> ${high_24h:.6f}\n"
        f"📉 <b>Low:</b> ${low_24h:.6f}\n"
        f"💹 <b>Volume:</b> {volume_24h_jkc:,.4f} JKC (${volume_24h_usdt:,.0f})\n\n"

        f"📈 <b>Combined Volume (NonKYC + CoinEx):</b>\n"
        f"🕐 <b>15m:</b> ${volume_periods['15m']:,.0f}\n"
        f"🕐 <b>1h:</b> ${volume_periods['1h']:,.0f}\n"
        f"🕐 <b>4h:</b> ${volume_periods['4h']:,.0f}\n"
        f"🕐 <b>24h:</b> ${volume_periods['24h']:,.0f}\n\n"

        f"📋 <b>Order Book:</b>\n"
        f"🟢 <b>Best Bid:</b> ${best_bid:.6f}\n"
        f"🔴 <b>Best Ask:</b> ${best_ask:.6f}\n"
        f"📏 <b>Spread:</b> {spread_percent:.2f}%\n\n"

        f"📡 <b>Data Source:</b> {data_source}"
    )

    await update.message.reply_text(
        message,
        parse_mode="HTML",
        reply_markup=keyboard
    )

async def config_command(update: Update, context: CallbackContext) -> int:
    """Command to access the configuration menu."""
    if not await can_use_admin_commands(update, context):
        chat_id = update.effective_chat.id
        public_supergroups = CONFIG.get("public_supergroups", [])
        if chat_id in public_supergroups:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "Configuration commands are restricted to the bot owner only.\n"
                "This is a public supergroup where settings are managed centrally.\n\n"
                "📊 You can still use:\n"
                "• /help - View available commands\n"
                "• /price - Check current JKC price\n"
                "• /chart - Generate price chart",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "You do not have permission to access configuration.\n"
                "This command is restricted to administrators only.",
                parse_mode="HTML"
            )
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
    """Show help information and available commands based on chat type and permissions."""
    chat_id = update.effective_chat.id

    # Load public supergroups from config
    public_supergroups = CONFIG.get("public_supergroups", [])
    is_public_supergroup = (chat_id in public_supergroups)
    is_user_admin = await can_use_admin_commands(update, context)
    is_owner = await is_owner_only(update, context)

    # Base help text for all users
    base_help = (
        "<b>JunkCoin ($JKC) Alert Bot</b>\n\n"
        "🚨 <b>Real-time JunkCoin (JKC) market data and price monitoring</b>\n"
        "🎯 <b>Live price updates, market cap tracking, and volume analysis</b>\n"
        "🎨 <b>Professional alert system with rich market data</b>\n\n"

        "📊 <b>Information Commands (Available to Everyone):</b>\n"
        "/price - Check current JKC price and market cap\n"
        "/chart - Generate and send a price chart\n"
        "/tx &lt;hash&gt; - Look up transaction information\n"
        "/address &lt;address&gt; - Check wallet balance and info\n"
        "/debug - Show user ID, chat info, and permissions\n"
        "/help - Show this help message\n\n"
    )

    if is_public_supergroup:
        # Public supergroup - limited commands
        help_text = base_help + (
            "🏛️ <b>Public Supergroup Mode</b>\n"
            "This is a public community chat where alerts are managed centrally.\n"
            "All users can access information commands above.\n\n"

            "🔒 <b>Restricted Commands:</b>\n"
            "• /start, /stop - Owner only (alerts managed centrally)\n"
            "• /config, /setmin - Owner only (settings managed centrally)\n"
            "• Admin commands - Owner only for security\n\n"

            "🚨 <b>Alert Information:</b>\n"
            "• Alerts are automatically delivered to this group\n"
            "• Current threshold: ${} USDT\n"
            "• Trade aggregation: 8-second window\n"
            "• Alert types: 🚨 Standard | 💥 Significant | 🔥 Major | 🐋 Whale\n\n"
        ).format(VALUE_REQUIRE)
    else:
        # Private chat or other groups - full functionality
        help_text = base_help

        if is_owner or is_user_admin:
            help_text += (
                "🛑 <b>Control Commands:</b>\n"
                "/start - Start receiving alerts in this chat\n"
                "/stop - Stop receiving alerts in this chat\n\n"
            )

        if is_user_admin:
            help_text += (
                "⚙️ <b>Admin Configuration:</b>\n"
                "/config - Interactive configuration menu\n"
                "/setmin [value] - Set minimum transaction value (e.g. /setmin 150)\n"
                "/toggle_aggregation - Enable/disable trade aggregation\n\n"

                "🎨 <b>Image Management (Admin):</b>\n"
                "/setimage - Add image to collection (send image after command)\n"
                "/list_images - View all images in your collection\n"
                "/clear_images - Remove all images from collection\n\n"
            )

        if is_owner:
            help_text += (
                "🔐 <b>Owner Only Commands:</b>\n"
                "/setapikey - Configure exchange API keys\n"
                "/ipwan - Get server's public IP address\n\n"
            )

        help_text += (
            "🚨 <b>Alert Types:</b>\n"
            "🚨 Standard (1x threshold) | 💥 Significant (2x)\n"
            "🔥 Major (3x) | 🔥🔥 Huge (5x) | 🐋🐋🐋 Whale (10x+)\n\n"

            "📈 <b>Data Sources:</b>\n"
            "• NonKYC Exchange (Primary - Real-time trades and orderbook)\n"
            "• LiveCoinWatch API (Fallback - Price and market data)\n\n"

            "💡 <b>Pro Tips:</b>\n"
            "• Use /setimage multiple times to build a varied collection\n"
            "• Enable trade aggregation to catch coordinated buying\n"
            "• Set threshold based on your preferred alert frequency\n"
            "• Use /debug to verify your permissions\n\n"
        )

    # Common footer for all users
    help_text += (
        "☕ <b>JKCBuyBot Developer Coffee Tip:</b>\n"
        "If you find this bot helpful, consider supporting the developer!\n"
        "Developer: @moonether\n"
        "JKC Address: <code>7Vm7sXtC53aXWgMnEKDYdp9rfz2BkX454w</code>"
    )
    
    # Create buttons for quick access to common commands
    # Basic buttons for all users (public commands)
    keyboard = [
        [
            InlineKeyboardButton("📊 Check Price", callback_data="cmd_price"),
            InlineKeyboardButton("📈 View Chart", callback_data="cmd_chart")
        ],
        [
            InlineKeyboardButton("🔍 Debug Info", callback_data="cmd_debug"),
            InlineKeyboardButton("💝 Donate to Dev", callback_data="cmd_donate")
        ]
    ]

    # Add buttons based on permissions and chat type
    if not is_public_supergroup:
        # In private chats or other groups, show control buttons
        if is_owner or is_user_admin:
            keyboard.insert(1, [
                InlineKeyboardButton("🚀 Start Bot", callback_data="cmd_start"),
                InlineKeyboardButton("🛑 Stop Bot", callback_data="cmd_stop")
            ])

        # Add admin configuration buttons
        if is_user_admin:
            keyboard.insert(-1, [
                InlineKeyboardButton("⚙️ Configuration", callback_data="cmd_config"),
                InlineKeyboardButton("🎨 List Images", callback_data="cmd_list_images")
            ])
    else:
        # In public supergroup, show limited info
        keyboard.insert(-1, [
            InlineKeyboardButton("ℹ️ Group Info", callback_data="cmd_group_info")
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

    if query.data == "cmd_price":
        # Handle price command directly with callback query response
        try:
            # Get market data for current price - try NonKYC first, then LiveCoinWatch as fallback
            market_data = await get_nonkyc_ticker()
            data_source = "NonKYC Exchange"

            if not market_data:
                logger.info("NonKYC API failed, using LiveCoinWatch fallback")
                market_data = await get_livecoinwatch_data()
                data_source = "LiveCoinWatch"

            if not market_data:
                await query.edit_message_text("Error fetching market data from all sources. Please try again later.")
                return

            # Get combined volume data from both exchanges
            volume_data = await calculate_combined_volume_periods()
            volume_periods = volume_data.get("combined", {}) if volume_data else {}

            # Ensure all volume periods have default values
            volume_periods = {
                "15m": volume_periods.get("15m", 0) or 0,
                "1h": volume_periods.get("1h", 0) or 0,
                "4h": volume_periods.get("4h", 0) or 0,
                "24h": volume_periods.get("24h", 0) or 0
            }

            # Extract data based on source with safety checks
            if data_source == "LiveCoinWatch":
                current_price = market_data.get("rate", 0) or 0
                volume_24h_usdt = market_data.get("volume", 0) or 0
                market_cap_nonkyc = market_data.get("cap", 0) or 0
                delta = market_data.get("delta", {}) or {}
                change_percent = delta.get("day", 0) if delta else 0
                change_percent = change_percent or 0
                yesterday_price = current_price / (1 + change_percent/100) if change_percent != 0 else current_price
                high_24h = current_price * 1.05
                low_24h = current_price * 0.95
                volume_24h_jkc = volume_24h_usdt / current_price if current_price > 0 else 0
                best_bid = current_price * 0.999
                best_ask = current_price * 1.001
                spread_percent = 0.2
            else:
                current_price = market_data.get("lastPriceNumber", 0) or 0
                yesterday_price = market_data.get("yesterdayPriceNumber", 0) or 0
                high_24h = market_data.get("highPriceNumber", 0) or 0
                low_24h = market_data.get("lowPriceNumber", 0) or 0
                volume_24h_jkc = market_data.get("volumeNumber", 0) or 0
                volume_24h_usdt = market_data.get("volumeUsdNumber", 0) or 0
                change_percent = market_data.get("changePercentNumber", 0) or 0
                market_cap_nonkyc = market_data.get("marketcapNumber", 0) or 0
                best_bid = market_data.get("bestBidNumber", 0) or 0
                best_ask = market_data.get("bestAskNumber", 0) or 0
                spread_percent = market_data.get("spreadPercentNumber", 0) or 0

            # Get momentum data for different timeframes
            momentum_periods = {"15m": 0, "1h": 0, "4h": 0, "24h": 0}
            try:
                trades_data = await get_nonkyc_trades()
                if trades_data and data_source == "NonKYC Exchange":
                    momentum_periods = await calculate_momentum_periods(trades_data, current_price)
            except Exception as e:
                logger.warning(f"Could not calculate momentum periods: {e}")

            # Calculate additional metrics
            price_change_usdt = current_price - yesterday_price if yesterday_price > 0 else 0

            # Format change with crypto-appropriate emojis
            if change_percent >= 10:
                change_emoji = "🚀"
            elif change_percent >= 5:
                change_emoji = "📈"
            elif change_percent > 0:
                change_emoji = "⬆️"
            elif change_percent >= -5:
                change_emoji = "➡️"
            elif change_percent >= -10:
                change_emoji = "⬇️"
            elif change_percent >= -20:
                change_emoji = "📉"
            else:
                change_emoji = "💀"

            change_sign = "+" if change_percent >= 0 else ""

            # Format momentum values with proper signs and emojis
            def format_momentum(value):
                if value > 0:
                    return f"+{value:.2f}%"
                elif value < 0:
                    return f"{value:.2f}%"
                else:
                    return "0.00%"

            # Format the message with rich data including momentum and volume periods
            message = (
                f"🪙 <b>JunkCoin (JKC) Market Data</b> 🪙\n\n"
                f"💰 <b>Price:</b> ${current_price:.6f} USDT\n"
                f"{change_emoji} <b>24h Change:</b> {change_sign}{change_percent:.2f}% "
                f"({change_sign}${price_change_usdt:.6f})\n\n"

                f"🏦 <b>Market Cap:</b> ${market_cap_nonkyc:,}\n\n"

                f"📊 <b>Momentum (Price Change):</b>\n"
                f"🕐 <b>15m:</b> {format_momentum(momentum_periods['15m'])}\n"
                f"🕐 <b>1h:</b> {format_momentum(momentum_periods['1h'])}\n"
                f"🕐 <b>4h:</b> {format_momentum(momentum_periods['4h'])}\n"
                f"🕐 <b>24h:</b> {format_momentum(momentum_periods['24h'])}\n\n"

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

                f"📡 <b>Data Source:</b> {data_source}"
            )

            # Create buttons with trading links
            keyboard = [
                [
                    InlineKeyboardButton("📊 CoinGecko", url="https://www.coingecko.com/en/coins/junkcoin"),
                    InlineKeyboardButton("📈 CoinMarketCap", url="https://coinmarketcap.com/currencies/junkcoin/")
                ],
                [
                    InlineKeyboardButton("💱 Trade JKC/USDT", url="https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3"),
                    InlineKeyboardButton("🔍 Explorer", url="https://jkc-explorer.dedoo.xyz/")
                ],
                [
                    InlineKeyboardButton("🌐 JunkCoin Website", url="https://junk-coin.com/"),
                    InlineKeyboardButton("💰 Get JKC Wallet", url="https://junk-coin.com/wallets/")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                message,
                parse_mode="HTML",
                reply_markup=reply_markup
            )

        except Exception as e:
            await query.edit_message_text(f"❌ Error fetching price data: {str(e)}")

    elif query.data == "cmd_chart":
        # Handle chart command directly with callback query response
        try:
            # Send initial processing message
            await query.edit_message_text("🔄 Generating charts for both trading pairs, please wait...")

            # Get historical trades for JKC/USDT
            trades_usdt = await get_nonkyc_trades()

            if not trades_usdt:
                await query.edit_message_text("❌ No trade data available to generate charts.")
                return

            # Convert to DataFrame for USDT pair
            df_usdt = pd.DataFrame(trades_usdt)

            # Validate required columns exist
            required_columns = ['timestamp', 'price', 'quantity']
            for col in required_columns:
                if col not in df_usdt.columns:
                    await query.edit_message_text(f"❌ Invalid trade data format: missing '{col}' column.")
                    return

            # Convert data types with error handling
            try:
                df_usdt['timestamp'] = pd.to_datetime(df_usdt['timestamp'])
                df_usdt['price'] = pd.to_numeric(df_usdt['price'], errors='coerce')
                df_usdt['quantity'] = pd.to_numeric(df_usdt['quantity'], errors='coerce')

                # Remove rows with invalid data
                df_usdt = df_usdt.dropna(subset=['timestamp', 'price', 'quantity'])

                if len(df_usdt) == 0:
                    await query.edit_message_text("❌ No valid trade data available for chart generation.")
                    return

                df_usdt = df_usdt.sort_values('timestamp')

            except Exception as data_error:
                logger.error(f"Error processing trade data: {data_error}")
                await query.edit_message_text("❌ Error processing trade data for chart generation.")
                return

            # Create JKC/USDT chart
            fig_usdt = go.Figure(data=[go.Scatter(
                x=df_usdt['timestamp'],
                y=df_usdt['price'],
                mode='lines',
                name='JKC/USDT',
                line=dict(color='#00D4AA', width=2)  # NonKYC green color
            )])

            fig_usdt.update_layout(
                title='📈 JKC/USDT Price Chart (NonKYC Exchange)',
                xaxis_title='Time',
                yaxis_title='Price (USDT)',
                template='plotly_dark',
                autosize=True,
                width=1000,
                height=600,
                font=dict(size=12),
                title_font=dict(size=16)
            )

            # Save JKC/USDT chart
            chart_usdt_path = 'temp_chart_usdt_button.png'
            fig_usdt.write_image(chart_usdt_path)

            # Send JKC/USDT chart with trading link
            usdt_caption = (
                "📊 <b>JKC/USDT Price Chart</b>\n"
                "💱 <a href='https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3'>Trade JKC/USDT on NonKYC</a>\n"
                "📈 Real-time trading data from NonKYC Exchange"
            )

            # Send the chart as a new message (since we can't edit message to include photo)
            with open(chart_usdt_path, 'rb') as f:
                await context.bot.send_photo(
                    chat_id=query.message.chat.id,
                    photo=f,
                    caption=usdt_caption,
                    parse_mode="HTML"
                )

            # Try to generate BTC chart
            try:
                # Get current BTC price to convert USDT prices to BTC equivalent
                btc_price_usdt = 45000.0  # Approximate BTC price - you could fetch this from an API

                df_btc = df_usdt.copy()
                # Ensure price column is numeric before division
                df_btc['price'] = pd.to_numeric(df_btc['price'], errors='coerce')
                df_btc['price_btc'] = df_btc['price'] / btc_price_usdt

                fig_btc = go.Figure(data=[go.Scatter(
                    x=df_btc['timestamp'],
                    y=df_btc['price_btc'],
                    mode='lines',
                    name='JKC/BTC',
                    line=dict(color='#F7931A', width=2)  # Bitcoin orange color
                )])

                fig_btc.update_layout(
                    title='₿ JKC/BTC Price Chart (Estimated)',
                    xaxis_title='Time',
                    yaxis_title='Price (BTC)',
                    template='plotly_dark',
                    autosize=True,
                    width=1000,
                    height=600,
                    font=dict(size=12),
                    title_font=dict(size=16)
                )

                # Save JKC/BTC chart
                chart_btc_path = 'temp_chart_btc_button.png'
                fig_btc.write_image(chart_btc_path)

                # Send JKC/BTC chart with trading link
                btc_caption = (
                    "₿ <b>JKC/BTC Price Chart</b>\n"
                    "💱 <a href='https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3'>Trade JKC/BTC on NonKYC</a>\n"
                    "📊 Estimated from USDT pair data"
                )

                with open(chart_btc_path, 'rb') as f:
                    await context.bot.send_photo(
                        chat_id=query.message.chat.id,
                        photo=f,
                        caption=btc_caption,
                        parse_mode="HTML"
                    )

                # Clean up BTC chart
                os.remove(chart_btc_path)

            except Exception as btc_error:
                logger.warning(f"Could not generate BTC chart: {btc_error}")
                # Send message about BTC trading link anyway
                await context.bot.send_message(
                    chat_id=query.message.chat.id,
                    text="₿ <b>JKC/BTC Trading</b>\n"
                         "💱 <a href='https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3'>Trade JKC/BTC on NonKYC</a>",
                    parse_mode="HTML"
                )

            # Clean up USDT chart
            os.remove(chart_usdt_path)

            # Send summary message with both trading links
            summary_message = (
                "📊 <b>JKC Trading on NonKYC Exchange</b>\n\n"
                "💱 <a href='https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3'>JKC/USDT Trading</a>\n\n"
                "🌐 <a href='https://nonkyc.io'>Visit NonKYC Exchange</a>"
            )

            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text=summary_message,
                parse_mode="HTML"
            )

            # Update the original message to show completion
            await query.edit_message_text("✅ Charts generated successfully! Check the messages above.")

        except Exception as e:
            logger.error(f"Error generating charts from button: {e}")
            await query.edit_message_text(f"❌ Error generating charts: {str(e)}")

    elif query.data == "cmd_debug":
        # Handle debug command directly
        user_id = query.from_user.id
        chat_id = query.message.chat.id
        chat_type = query.message.chat.type
        is_user_admin = await is_admin(update, context)

        debug_info = (
            "🔍 <b>Debug Information</b>\n\n"
            f"👤 <b>Your User ID:</b> {user_id}\n"
            f"💬 <b>Chat ID:</b> {chat_id}\n"
            f"💬 <b>Chat Type:</b> {chat_type}\n"
            f"👑 <b>Admin Status:</b> {'Yes' if is_user_admin else 'No'}\n\n"
            f"⚙️ <b>Config Values:</b>\n"
            f"- Bot Owner ID: {BOT_OWNER}\n"
            f"- Bypass ID: {BY_PASS}"
        )

        await query.edit_message_text(debug_info, parse_mode="HTML")

    elif query.data == "cmd_start":
        if await can_start_stop_bot(update, context):
            await query.edit_message_text("🚀 Use /start command to start the bot in this chat.")
        else:
            chat_id = query.message.chat.id
            public_supergroups = CONFIG.get("public_supergroups", [])
            if chat_id in public_supergroups:
                await query.edit_message_text(
                    "❌ <b>Permission Denied</b>\n\n"
                    "The /start command is restricted to the bot owner only.\n"
                    "This is a public supergroup where alerts are managed centrally.",
                    parse_mode="HTML"
                )
            else:
                await query.edit_message_text("❌ You don't have permission to start/stop alerts")

    elif query.data == "cmd_stop":
        if await can_start_stop_bot(update, context):
            await query.edit_message_text("🛑 Use /stop command to stop the bot in this chat.")
        else:
            chat_id = query.message.chat.id
            public_supergroups = CONFIG.get("public_supergroups", [])
            if chat_id in public_supergroups:
                await query.edit_message_text(
                    "❌ <b>Permission Denied</b>\n\n"
                    "The /stop command is restricted to the bot owner only.\n"
                    "This is a public supergroup where alerts are managed centrally.",
                    parse_mode="HTML"
                )
            else:
                await query.edit_message_text("❌ You don't have permission to start/stop alerts")

    elif query.data == "cmd_config":
        if await can_use_admin_commands(update, context):
            await query.edit_message_text("⚙️ Configuration menu access granted. Use /config command for full interface.")
        else:
            chat_id = query.message.chat.id
            public_supergroups = CONFIG.get("public_supergroups", [])
            if chat_id in public_supergroups:
                await query.edit_message_text(
                    "❌ <b>Permission Denied</b>\n\n"
                    "Configuration commands are restricted to the bot owner only.\n"
                    "This is a public supergroup where settings are managed centrally.",
                    parse_mode="HTML"
                )
            else:
                await query.edit_message_text("❌ You don't have permission to access configuration.")

    elif query.data == "cmd_list_images":
        if await can_use_admin_commands(update, context):
            images = get_image_collection()
            if not images:
                await query.edit_message_text(
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
                await query.edit_message_text(message, parse_mode="HTML")
        else:
            chat_id = query.message.chat.id
            public_supergroups = CONFIG.get("public_supergroups", [])
            if chat_id in public_supergroups:
                await query.edit_message_text(
                    "❌ <b>Permission Denied</b>\n\n"
                    "Image management is restricted to the bot owner only.\n"
                    "This is a public supergroup where settings are managed centrally.",
                    parse_mode="HTML"
                )
            else:
                await query.edit_message_text("❌ You don't have permission to list images.")

    elif query.data == "cmd_group_info":
        # Show information about the public supergroup
        group_info = (
            "🏛️ <b>JKC Public Supergroup Information</b>\n\n"
            "📊 <b>Available Commands for Everyone:</b>\n"
            "• /help - View this help information\n"
            "• /price - Check current JKC price and market data\n"
            "• /chart - Generate JKC price charts\n"
            "• /debug - View your user information\n\n"

            "🚨 <b>Alert System:</b>\n"
            f"• Threshold: ${VALUE_REQUIRE} USDT\n"
            "• Trade aggregation: 8-second window\n"
            "• Automatic delivery to this group\n"
            "• Real-time NonKYC Exchange monitoring\n\n"

            "🔒 <b>Restricted Commands:</b>\n"
            "• /start, /stop - Owner only\n"
            "• /config, /setmin - Owner only\n"
            "• Admin commands - Owner only\n\n"

            "💱 <b>Trading Links:</b>\n"
            "• <a href='https://nonkyc.io/market/JKC_USDT?ref=684e356ba01b7b892824a7b3'>JKC/USDT Trading</a>\n"
            "• <a href='https://junk-coin.com/'>JunkCoin Website</a>"
        )

        await query.edit_message_text(group_info, parse_mode="HTML")

    elif query.data == "cmd_help":
        # Redirect back to help command
        await help_command(update, context)

    elif query.data == "cmd_donate":
        # Handle donate command directly
        donate_text = (
            "☕ <b>JKCBuyBot Developer Coffee Tip</b>\n\n"
            "If you find this JKC Alert Bot helpful, consider supporting the developer!\n\n"
            "👨‍💻 <b>Developer:</b> @moonether\n"
            "🪙 <b>JKC Address:</b>\n"
            "<code>7Vm7sXtC53aXWgMnEKDYdp9rfz2BkX454w</code>\n\n"
            "💡 <i>Tap and hold the address above to copy it</i>\n\n"
            "Your support helps maintain and improve this bot. Thank you! 🙏"
        )

        # Create a button to copy the JKC address
        keyboard = [
            [
                InlineKeyboardButton(
                    "📋 Copy JKC Address",
                    callback_data="copy_jkc_address"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔗 Contact Developer",
                    url="https://t.me/moonether"
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            donate_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    elif query.data == "copy_jkc_address":
        # Show the JKC address in a copyable format
        await query.edit_message_text(
            "☕ <b>JKCBuyBot Developer Coffee Tip</b>\n\n"
            "🪙 <b>JKC Address:</b>\n"
            "<code>7Vm7sXtC53aXWgMnEKDYdp9rfz2BkX454w</code>\n\n"
            "💡 <i>Tap and hold the address above to copy it</i>\n\n"
            "Thank you for your support! 🙏",
            parse_mode="HTML"
        )

async def donate_command(update: Update, context: CallbackContext) -> None:
    """Show donation information for the developer."""
    donate_text = (
        "☕ <b>JKCBuyBot Developer Coffee Tip</b>\n\n"
        "If you find this JKC Alert Bot helpful, consider supporting the developer!\n\n"
        "👨‍💻 <b>Developer:</b> @moonether\n"
        "🪙 <b>JKC Address:</b>\n"
        "<code>7Vm7sXtC53aXWgMnEKDYdp9rfz2BkX454w</code>\n\n"
        "💡 <i>Tap and hold the address above to copy it</i>\n\n"
        "Your support helps maintain and improve this bot. Thank you! 🙏"
    )

    # Create a button to copy the JKC address
    keyboard = [
        [
            InlineKeyboardButton(
                "📋 Copy JKC Address",
                callback_data="copy_jkc_address"
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 Contact Developer",
                url="https://t.me/moonether"
            )
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        donate_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def toggle_aggregation(update: Update, context: CallbackContext) -> None:
    """Toggle trade aggregation on/off - admin only command."""
    global CONFIG
    user_id = update.effective_user.id
    logger.info(f"toggle_aggregation command called by user {user_id}")

    if await can_use_admin_commands(update, context):
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
        chat_id = update.effective_chat.id
        public_supergroups = CONFIG.get("public_supergroups", [])
        if chat_id in public_supergroups:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "The /toggle_aggregation command is restricted to the bot owner only.\n"
                "This is a public supergroup where settings are managed centrally.",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "You do not have permission to use this command.\n"
                "This command is restricted to administrators only.",
                parse_mode="HTML"
            )

async def list_images_command(update: Update, context: CallbackContext) -> None:
    """List all images in the collection with visual previews and management options - admin only command."""
    # Get user ID with multiple fallback methods to ensure we get the correct one
    user_id = None
    if update.effective_user:
        user_id = update.effective_user.id
    elif update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id

    logger.info(f"list_images command called by user {user_id}")

    if await can_use_admin_commands(update, context):
        logger.info(f"User {user_id} has admin permissions, listing images with visual previews")
        images = get_image_collection()

        if not images:
            await update.message.reply_text(
                "📁 <b>Image Collection Empty</b>\n\n"
                "No images found in the collection.\n"
                "Use /setimage to add images to the collection.",
                parse_mode="HTML"
            )
        else:
            # Send overview message first
            total_size = sum(os.path.getsize(img) for img in images if os.path.exists(img))
            total_size_mb = total_size / (1024 * 1024)

            overview_message = (
                f"📁 <b>Image Collection Overview</b>\n\n"
                f"📊 Total Images: {len(images)}\n"
                f"💾 Total Size: {total_size_mb:.2f} MB\n"
                f"🎲 Random selection for alerts\n\n"
                f"📸 Sending visual previews with management options..."
            )

            await update.message.reply_text(overview_message, parse_mode="HTML")

            # Send each image with detailed information and management buttons
            for i, img_path in enumerate(images, 1):
                try:
                    await send_image_preview(update, context, img_path, i, len(images))
                except Exception as e:
                    logger.error(f"Error sending image preview {i}: {e}")
                    # Send error message for this image
                    filename = os.path.basename(img_path)
                    error_message = (
                        f"❌ <b>Image {i}/{len(images)}: {filename}</b>\n\n"
                        f"Error loading image: {str(e)}\n"
                        f"File may be corrupted or inaccessible."
                    )

                    # Create management buttons even for error cases
                    keyboard = [
                        [InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_image_{i-1}"),
                         InlineKeyboardButton("ℹ️ Info", callback_data=f"image_info_{i-1}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await update.message.reply_text(
                        error_message,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )

            # Send bulk management options
            if len(images) > 1:
                bulk_keyboard = [
                    [InlineKeyboardButton("🗑️ Clear All Images", callback_data="clear_all_images"),
                     InlineKeyboardButton("🔄 Refresh List", callback_data="refresh_image_list")],
                    [InlineKeyboardButton("📊 Collection Stats", callback_data="image_stats")]
                ]
                bulk_reply_markup = InlineKeyboardMarkup(bulk_keyboard)

                await update.message.reply_text(
                    "🛠️ <b>Bulk Management Options</b>",
                    parse_mode="HTML",
                    reply_markup=bulk_reply_markup
                )
    else:
        logger.warning(f"User {user_id} tried to use list_images command without admin permissions")
        chat_id = update.effective_chat.id
        public_supergroups = CONFIG.get("public_supergroups", [])
        if chat_id in public_supergroups:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "Image management is restricted to the bot owner only.\n"
                "This is a public supergroup where settings are managed centrally.",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "❌ <b>Permission Denied</b>\n\n"
                "You do not have permission to list images.\n"
                "This command is restricted to administrators only.",
                parse_mode="HTML"
            )

async def send_image_preview(update: Update, context: CallbackContext, img_path: str, index: int, total: int):
    """Send a single image preview with detailed information and management buttons."""
    from datetime import datetime

    filename = os.path.basename(img_path)

    try:
        # Get file information
        file_stat = os.stat(img_path)
        file_size = file_stat.st_size
        file_size_mb = file_size / (1024 * 1024)

        # Get file format and type
        file_ext = os.path.splitext(filename)[1].lower()
        detected_type = detect_file_type(img_path)

        # Determine file type for proper sending
        is_gif_mp4 = detected_type == 'mp4' and 'alert_image' in filename  # GIF converted to MP4
        is_animation = file_ext in ['.gif'] or is_gif_mp4
        is_image = file_ext in ['.jpg', '.jpeg', '.png', '.webp']

        # Create detailed caption
        format_display = f"{detected_type.upper()}"
        if is_gif_mp4:
            format_display += " (GIF→MP4)"

        caption = (
            f"📸 <b>Image {index}/{total}: {filename}</b>\n\n"
            f"💾 Size: {file_size_mb:.2f} MB ({file_size:,} bytes)\n"
            f"📁 Format: {format_display}\n"
            f"📅 Modified: {datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🔍 Extension: {file_ext}"
        )

        # Create management buttons
        keyboard = [
            [InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_image_{index-1}"),
             InlineKeyboardButton("ℹ️ Info", callback_data=f"image_info_{index-1}")],
            [InlineKeyboardButton("📤 Test Send", callback_data=f"test_image_{index-1}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send the image with appropriate method
        with open(img_path, 'rb') as image_file:
            if is_animation:
                # Send GIF/MP4 as animation
                await update.message.reply_animation(
                    animation=image_file,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
                logger.info(f"Sent image {index} as animation: {filename}")
            elif is_image:
                # Send as photo
                await update.message.reply_photo(
                    photo=image_file,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
                logger.info(f"Sent image {index} as photo: {filename}")
            else:
                # Send as document for unknown formats
                await update.message.reply_document(
                    document=image_file,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
                logger.info(f"Sent image {index} as document: {filename}")

    except Exception as e:
        logger.error(f"Error sending image preview for {filename}: {e}")
        raise

async def image_management_callback(update: Update, context: CallbackContext) -> None:
    """Handle image management button callbacks."""
    query = update.callback_query
    await query.answer()

    # Check if user has admin permissions
    if not await can_use_admin_commands(update, context):
        await query.edit_message_text(
            "❌ <b>Permission Denied</b>\n\n"
            "Image management is restricted to administrators only.",
            parse_mode="HTML"
        )
        return

    try:
        if query.data.startswith("delete_image_"):
            # Delete specific image
            image_index = int(query.data.split("_")[-1])
            images = get_image_collection()

            if 0 <= image_index < len(images):
                img_path = images[image_index]
                filename = os.path.basename(img_path)

                # Create confirmation dialog
                keyboard = [
                    [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_{image_index}"),
                     InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    f"🗑️ <b>Confirm Deletion</b>\n\n"
                    f"Are you sure you want to delete:\n"
                    f"📄 <code>{filename}</code>\n\n"
                    f"⚠️ This action cannot be undone!",
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text("❌ Image not found or index out of range.")

        elif query.data.startswith("confirm_delete_"):
            # Confirmed deletion
            image_index = int(query.data.split("_")[-1])
            images = get_image_collection()

            if 0 <= image_index < len(images):
                img_path = images[image_index]
                filename = os.path.basename(img_path)

                try:
                    os.remove(img_path)
                    new_count = len(get_image_collection())

                    await query.edit_message_text(
                        f"✅ <b>Image Deleted Successfully</b>\n\n"
                        f"📄 Deleted: <code>{filename}</code>\n"
                        f"📁 Collection now has {new_count} images\n\n"
                        f"Use /list_images to see updated collection.",
                        parse_mode="HTML"
                    )
                    logger.info(f"Image deleted by user {query.from_user.id}: {filename}")

                except Exception as e:
                    await query.edit_message_text(
                        f"❌ <b>Deletion Failed</b>\n\n"
                        f"Error deleting {filename}: {str(e)}",
                        parse_mode="HTML"
                    )
                    logger.error(f"Error deleting image {filename}: {e}")
            else:
                await query.edit_message_text("❌ Image not found or index out of range.")

        elif query.data == "cancel_delete":
            await query.edit_message_text("🚫 Deletion cancelled.")

        elif query.data.startswith("image_info_"):
            # Show detailed image information
            image_index = int(query.data.split("_")[-1])
            images = get_image_collection()

            if 0 <= image_index < len(images):
                img_path = images[image_index]
                filename = os.path.basename(img_path)

                try:
                    from datetime import datetime
                    file_stat = os.stat(img_path)
                    file_size = file_stat.st_size
                    detected_type = detect_file_type(img_path)

                    info_message = (
                        f"ℹ️ <b>Image Information</b>\n\n"
                        f"📄 <b>Filename:</b> <code>{filename}</code>\n"
                        f"📁 <b>Path:</b> <code>{img_path}</code>\n"
                        f"💾 <b>Size:</b> {file_size:,} bytes ({file_size/1024:.1f} KB)\n"
                        f"🔍 <b>Detected Type:</b> {detected_type.upper()}\n"
                        f"📅 <b>Created:</b> {datetime.fromtimestamp(file_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"📝 <b>Modified:</b> {datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"🎲 <b>Status:</b> Active in random selection"
                    )

                    await query.edit_message_text(info_message, parse_mode="HTML")

                except Exception as e:
                    await query.edit_message_text(
                        f"❌ <b>Error Getting Info</b>\n\n"
                        f"Could not retrieve information for {filename}: {str(e)}",
                        parse_mode="HTML"
                    )
            else:
                await query.edit_message_text("❌ Image not found or index out of range.")

        elif query.data.startswith("test_image_"):
            # Test send image
            image_index = int(query.data.split("_")[-1])
            images = get_image_collection()

            if 0 <= image_index < len(images):
                img_path = images[image_index]
                filename = os.path.basename(img_path)

                try:
                    detected_type = detect_file_type(img_path)

                    with open(img_path, 'rb') as image_file:
                        test_caption = f"🧪 <b>Test Image Send</b>\n\n📄 {filename}\n🔍 Type: {detected_type.upper()}"

                        if detected_type == 'mp4' or img_path.endswith('.gif'):
                            await context.bot.send_animation(
                                chat_id=query.message.chat_id,
                                animation=image_file,
                                caption=test_caption,
                                parse_mode="HTML"
                            )
                        else:
                            await context.bot.send_photo(
                                chat_id=query.message.chat_id,
                                photo=image_file,
                                caption=test_caption,
                                parse_mode="HTML"
                            )

                    await query.edit_message_text(
                        f"✅ <b>Test Send Complete</b>\n\n"
                        f"📄 Sent: <code>{filename}</code>\n"
                        f"🔍 Type: {detected_type.upper()}\n"
                        f"📤 Check the message above for the test image.",
                        parse_mode="HTML"
                    )

                except Exception as e:
                    await query.edit_message_text(
                        f"❌ <b>Test Send Failed</b>\n\n"
                        f"Error sending {filename}: {str(e)}",
                        parse_mode="HTML"
                    )
            else:
                await query.edit_message_text("❌ Image not found or index out of range.")

        elif query.data == "clear_all_images":
            # Clear all images with confirmation
            images = get_image_collection()

            if not images:
                await query.edit_message_text("📁 Image collection is already empty.")
            else:
                keyboard = [
                    [InlineKeyboardButton("✅ Yes, Clear All", callback_data="confirm_clear_all"),
                     InlineKeyboardButton("❌ Cancel", callback_data="cancel_clear")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    f"🗑️ <b>Confirm Clear All Images</b>\n\n"
                    f"Are you sure you want to delete all {len(images)} images?\n\n"
                    f"⚠️ This action cannot be undone!",
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

        elif query.data == "confirm_clear_all":
            # Confirmed clear all
            images = get_image_collection()
            deleted_count = 0

            for img_path in images:
                try:
                    os.remove(img_path)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting image {img_path}: {e}")

            await query.edit_message_text(
                f"✅ <b>Collection Cleared</b>\n\n"
                f"🗑️ Deleted {deleted_count} images\n"
                f"📁 Collection is now empty\n\n"
                f"Use /setimage to add new images.",
                parse_mode="HTML"
            )
            logger.info(f"All images cleared by user {query.from_user.id}: {deleted_count} files deleted")

        elif query.data == "cancel_clear":
            await query.edit_message_text("🚫 Clear all cancelled.")

        elif query.data == "refresh_image_list":
            await query.edit_message_text(
                "🔄 <b>Refreshing Image List</b>\n\n"
                "Use /list_images command again to see the updated collection.",
                parse_mode="HTML"
            )

        elif query.data == "image_stats":
            # Show detailed collection statistics
            images = get_image_collection()

            if not images:
                await query.edit_message_text("📁 Image collection is empty.")
            else:
                total_size = 0
                type_counts = {}

                for img_path in images:
                    try:
                        size = os.path.getsize(img_path)
                        total_size += size

                        detected_type = detect_file_type(img_path)
                        type_counts[detected_type] = type_counts.get(detected_type, 0) + 1
                    except Exception as e:
                        logger.warning(f"Error analyzing {img_path}: {e}")

                type_breakdown = "\n".join([f"• {type_name.upper()}: {count}" for type_name, count in type_counts.items()])

                stats_message = (
                    f"📊 <b>Collection Statistics</b>\n\n"
                    f"📁 <b>Total Images:</b> {len(images)}\n"
                    f"💾 <b>Total Size:</b> {total_size/1024/1024:.2f} MB\n"
                    f"📈 <b>Average Size:</b> {total_size/len(images)/1024:.1f} KB\n\n"
                    f"🎯 <b>Format Breakdown:</b>\n{type_breakdown}\n\n"
                    f"🎲 <b>Selection:</b> Random for each alert\n"
                    f"📂 <b>Directory:</b> <code>images/</code>"
                )

                await query.edit_message_text(stats_message, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in image management callback: {e}")
        await query.edit_message_text(
            f"❌ <b>Error</b>\n\n"
            f"An error occurred: {str(e)}",
            parse_mode="HTML"
        )

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

async def tx_command(update: Update, context: CallbackContext) -> None:
    """Look up transaction information by hash."""
    if not context.args:
        await update.message.reply_text(
            "❌ <b>Usage:</b> /tx &lt;transaction_hash&gt;\n\n"
            "<b>Example:</b>\n"
            "<code>/tx f73365020dfbe878676456c558ba0a8045d72445f5a4306ca9b221c23f3b0055</code>",
            parse_mode="HTML"
        )
        return

    tx_hash = context.args[0].strip()

    # Validate transaction hash format (64 character hex string)
    if len(tx_hash) != 64 or not all(c in '0123456789abcdefABCDEF' for c in tx_hash):
        await update.message.reply_text(
            "❌ <b>Invalid transaction hash format</b>\n\n"
            "Transaction hash must be a 64-character hexadecimal string.",
            parse_mode="HTML"
        )
        return

    await update.message.reply_text("🔍 Looking up transaction information...")

    try:
        import requests

        # Query the JKC explorer API
        api_url = f"https://jkc-explorer.dedoo.xyz/ext/gettx/{tx_hash}"
        response = requests.get(api_url, timeout=10)

        if response.status_code == 200:
            data = response.json()

            if "tx" in data and data["tx"]:
                tx = data["tx"]

                # Format transaction information
                tx_info = (
                    f"🔍 <b>Transaction Information</b>\n\n"
                    f"📋 <b>Hash:</b> <code>{tx['txid']}</code>\n"
                    f"🧱 <b>Block:</b> {tx.get('blockindex', 'Unknown')}\n"
                    f"✅ <b>Confirmations:</b> {data.get('confirmations', 'Unknown')}\n"
                    f"💰 <b>Total Value:</b> {tx.get('total', 'Unknown')} JKC\n"
                    f"📅 <b>Timestamp:</b> {tx.get('timestamp', 'Unknown')}\n\n"
                )

                # Add input information
                if tx.get('vin'):
                    tx_info += f"📥 <b>Inputs ({len(tx['vin'])}):</b>\n"
                    for i, vin in enumerate(tx['vin'][:3]):  # Show first 3 inputs
                        if vin.get('is_coinbase'):
                            tx_info += f"  • Coinbase (Block Reward)\n"
                        else:
                            tx_info += f"  • {vin.get('txid', 'Unknown')[:16]}...\n"
                    if len(tx['vin']) > 3:
                        tx_info += f"  • ... and {len(tx['vin']) - 3} more\n"
                    tx_info += "\n"

                # Add output information
                if tx.get('vout'):
                    tx_info += f"📤 <b>Outputs ({len(tx['vout'])}):</b>\n"
                    for i, vout in enumerate(tx['vout'][:3]):  # Show first 3 outputs
                        if vout.get('value', 0) > 0:
                            address = vout.get('scriptpubkey_address', 'Unknown')
                            value = vout.get('value', 0)
                            if isinstance(value, (int, float)):
                                value_jkc = value / 100000000  # Convert satoshis to JKC
                                tx_info += f"  • {address[:20]}... → {value_jkc:.8f} JKC\n"
                            else:
                                tx_info += f"  • {address[:20]}... → {value} JKC\n"
                    if len(tx['vout']) > 3:
                        tx_info += f"  • ... and {len(tx['vout']) - 3} more\n"

                # Add explorer link
                tx_info += f"\n🔗 <a href='https://jkc-explorer.dedoo.xyz/tx/{tx_hash}'>View on Explorer</a>"

                await update.message.reply_text(tx_info, parse_mode="HTML", disable_web_page_preview=True)
            else:
                await update.message.reply_text(
                    f"❌ <b>Transaction not found</b>\n\n"
                    f"The transaction hash <code>{tx_hash}</code> was not found in the blockchain.\n\n"
                    f"🔗 <a href='https://jkc-explorer.dedoo.xyz/'>Search on Explorer</a>",
                    parse_mode="HTML"
                )
        else:
            await update.message.reply_text(
                f"❌ <b>Error querying blockchain</b>\n\n"
                f"HTTP {response.status_code}: Unable to fetch transaction data.\n\n"
                f"🔗 <a href='https://jkc-explorer.dedoo.xyz/tx/{tx_hash}'>Try on Explorer</a>",
                parse_mode="HTML"
            )

    except requests.exceptions.Timeout:
        await update.message.reply_text(
            "⏰ <b>Request timeout</b>\n\n"
            "The blockchain explorer is taking too long to respond. Please try again later.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in tx_command: {e}")
        await update.message.reply_text(
            f"❌ <b>Error occurred</b>\n\n"
            f"Unable to fetch transaction information: {str(e)}\n\n"
            f"🔗 <a href='https://jkc-explorer.dedoo.xyz/tx/{tx_hash}'>Try on Explorer</a>",
            parse_mode="HTML"
        )

async def address_command(update: Update, context: CallbackContext) -> None:
    """Look up address balance and information."""
    if not context.args:
        await update.message.reply_text(
            "❌ <b>Usage:</b> /address &lt;wallet_address&gt;\n\n"
            "<b>Example:</b>\n"
            "<code>/address 3P3UvT6vdDJVrbB2mn6WrP8gywpu2Knx8C</code>",
            parse_mode="HTML"
        )
        return

    address = context.args[0].strip()

    # Basic address validation (JKC addresses typically start with specific characters)
    if len(address) < 26 or len(address) > 35:
        await update.message.reply_text(
            "❌ <b>Invalid address format</b>\n\n"
            "Please provide a valid JKC wallet address.",
            parse_mode="HTML"
        )
        return

    await update.message.reply_text("🔍 Looking up address information...")

    try:
        import requests

        # Query the JKC explorer API for balance
        balance_url = f"https://jkc-explorer.dedoo.xyz/ext/getbalance/{address}"
        balance_response = requests.get(balance_url, timeout=10)

        if balance_response.status_code == 200:
            try:
                balance = float(balance_response.text.strip())

                # Query for detailed address information
                address_url = f"https://jkc-explorer.dedoo.xyz/ext/getaddress/{address}"
                address_response = requests.get(address_url, timeout=10)

                address_info = (
                    f"💰 <b>Address Information</b>\n\n"
                    f"📋 <b>Address:</b> <code>{address}</code>\n"
                    f"💎 <b>Balance:</b> {balance:,.8f} JKC\n"
                )

                if address_response.status_code == 200:
                    try:
                        addr_data = address_response.json()
                        if isinstance(addr_data, dict):
                            if 'sent' in addr_data:
                                address_info += f"📤 <b>Total Sent:</b> {addr_data['sent']:,.8f} JKC\n"
                            if 'received' in addr_data:
                                address_info += f"📥 <b>Total Received:</b> {addr_data['received']:,.8f} JKC\n"
                            if 'txs' in addr_data:
                                address_info += f"📊 <b>Transaction Count:</b> {addr_data['txs']}\n"
                    except:
                        pass  # If detailed info fails, just show balance

                # Add explorer link
                address_info += f"\n🔗 <a href='https://jkc-explorer.dedoo.xyz/address/{address}'>View on Explorer</a>"

                await update.message.reply_text(address_info, parse_mode="HTML", disable_web_page_preview=True)

            except ValueError:
                await update.message.reply_text(
                    f"❌ <b>Invalid response from explorer</b>\n\n"
                    f"Unable to parse balance information.\n\n"
                    f"🔗 <a href='https://jkc-explorer.dedoo.xyz/address/{address}'>Try on Explorer</a>",
                    parse_mode="HTML"
                )
        else:
            await update.message.reply_text(
                f"❌ <b>Address not found</b>\n\n"
                f"The address <code>{address}</code> was not found or has no transactions.\n\n"
                f"🔗 <a href='https://jkc-explorer.dedoo.xyz/'>Search on Explorer</a>",
                parse_mode="HTML"
            )

    except requests.exceptions.Timeout:
        await update.message.reply_text(
            "⏰ <b>Request timeout</b>\n\n"
            "The blockchain explorer is taking too long to respond. Please try again later.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in address_command: {e}")
        await update.message.reply_text(
            f"❌ <b>Error occurred</b>\n\n"
            f"Unable to fetch address information: {str(e)}\n\n"
            f"🔗 <a href='https://jkc-explorer.dedoo.xyz/address/{address}'>Try on Explorer</a>",
            parse_mode="HTML"
        )

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
            exchange_url="https://www.coinex.com/en/exchange/JKC-usdt"
        )

        await update.message.reply_text(
            f"✅ <b>Test Complete!</b>\n\n"
            f"Simulated trade:\n"
            f"💰 Amount: {simulated_quantity:.4f} JKC\n"
            f"💵 Price: ${simulated_price:.6f}\n"
            f"💲 Value: ${simulated_value:.2f} USDT\n"
            f"🎯 Threshold: ${VALUE_REQUIRE} USDT",
            parse_mode="HTML"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ <b>Test Error:</b> {str(e)}", parse_mode="HTML")

async def exchange_availability_monitor():
    """Periodically check exchange availability and log status changes."""
    global running, EXCHANGE_AVAILABILITY

    logger.info("Starting exchange availability monitor...")
    previous_availability = EXCHANGE_AVAILABILITY.copy()

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
        await asyncio.sleep(300)

async def heartbeat():
    """Send periodic heartbeat messages to show the bot is running."""
    global running, EXCHANGE_AVAILABILITY
    counter = 0
    while running:
        counter += 1
        if counter % 60 == 0:  # Log every minute
            available_exchanges = [ex for ex, available in EXCHANGE_AVAILABILITY.items() if available]
            if available_exchanges:
                logger.info(f"Bot running - Monitoring JKC on: {', '.join(available_exchanges)} | Threshold: {VALUE_REQUIRE} USDT")
            else:
                logger.info(f"Bot running - Using LiveCoinWatch API | Threshold: {VALUE_REQUIRE} USDT")
        await asyncio.sleep(1)

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token with error handling
    application = Application.builder().token(BOT_TOKEN).build()

    # Add error handler for Telegram API conflicts
    async def error_handler(update: object, context) -> None:
        """Handle errors in the bot."""
        import traceback
        logger.error(f"Exception while handling an update: {context.error}")

        # Handle specific Telegram API conflicts
        if "Conflict: terminated by other getUpdates request" in str(context.error):
            logger.warning("⚠️ Telegram API conflict detected - another bot instance may be running")
            logger.warning("🔄 Bot will continue attempting to reconnect...")
            # Don't exit, let the bot retry automatically
            return

        # Log full traceback for other errors
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = ''.join(tb_list)
        logger.error(f"Full traceback: {tb_string}")

    application.add_error_handler(error_handler)

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
    application.add_handler(CommandHandler("tx", tx_command))  # Transaction lookup command
    application.add_handler(CommandHandler("address", address_command))  # Address lookup command
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
            INPUT_IMAGE_SETIMAGE: [MessageHandler(filters.PHOTO | filters.Document.IMAGE | filters.ANIMATION, set_image_input)]
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

    # Add callback query handler for copy button
    application.add_handler(CallbackQueryHandler(button_command_callback, pattern="^copy_"))

    # Add callback query handler for image management
    application.add_handler(CallbackQueryHandler(image_management_callback, pattern="^delete_image_|^confirm_delete_|^cancel_delete$|^image_info_|^test_image_|^clear_all_images$|^confirm_clear_all$|^cancel_clear$|^refresh_image_list$|^image_stats$"))

    # Start the websocket listeners in separate tasks
    loop = asyncio.get_event_loop()
    
    # Start all background tasks
    try:
        # Start exchange availability monitor first
        loop.create_task(exchange_availability_monitor())

        # Start WebSocket connections (they will wait for JKC availability)
        loop.create_task(nonkyc_websocket_usdt())
        loop.create_task(coinex_websocket())
        loop.create_task(ascendex_websocket())
        loop.create_task(nonkyc_orderbook_websocket())

        # Start heartbeat
        loop.create_task(heartbeat())

        logger.info("Started all background tasks including WebSocket monitoring")
        logger.info("WebSocket connections will activate when JKC becomes available on exchanges")
        logger.info("Primary data source: LiveCoinWatch API")
        logger.info("Real-time monitoring: Conditional WebSocket connections (NonKYC, CoinEx, AscendEX)")
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
        log_file = os.path.join("logs", f"jkc_telebot_{current_time}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)

        logger.info(f"Logging to file: {log_file}")
        logger.info("Starting JunkCoin (JKC) Alert Bot...")

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






