#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import logging
import asyncio
import io
import signal
import traceback
import requests
import websockets
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from types import SimpleNamespace

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, CallbackContext

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    return config

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
INPUT_IMAGE = 1
CONFIG_MENU = 2
DYNAMIC_CONFIG = 3
INPUT_API_KEYS = 4

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

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Command handlers
async def start_bot(update: Update, context: CallbackContext) -> None:
    """Start the bot in this chat."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    is_user_admin = user_id == BOT_OWNER or user_id == BY_PASS
    
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
            
            await update.message.reply_text(welcome_text, parse_mode="HTML")
        else:
            await update.message.reply_text("Bot is already active in this chat.")
    else:
        await update.message.reply_text("You don't have permission to start the bot.")

async def stop_bot(update: Update, context: CallbackContext) -> None:
    """Stop the bot in this chat."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if user_id == BOT_OWNER or user_id == BY_PASS:
        if chat_id in ACTIVE_CHAT_IDS:
            ACTIVE_CHAT_IDS.remove(chat_id)
            CONFIG["active_chat_ids"] = ACTIVE_CHAT_IDS
            save_config(CONFIG)
            await update.message.reply_text("Bot stopped in this chat. Use /start to reactivate.")
        else:
            await update.message.reply_text("Bot is not active in this chat.")
    else:
        await update.message.reply_text("Only the bot owner can stop the bot.")

async def check_price(update: Update, context: CallbackContext) -> None:
    global USER_CHECK_PRICE

    exist = False
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    for item in USER_CHECK_PRICE:
        if item.get('user_id') == user_id:
            exist = True
            if int(item["time"]) > int(time.time() * 1000):
                # Check if this is a button callback or direct command
                if hasattr(update, 'callback_query'):
                    await update.callback_query.edit_message_text("Request limit within 30sec")
                else:
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
        # Check if this is a button callback or direct command
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text("Error fetching market data. Please try again later.")
        else:
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

    price_text = (
        f"⛵️ <b>JunkCoin (JKC) Price</b> ⛵️\n\n"
        f"💵 <b>Price:</b> {current_price} USDT\n"
        f"📈 <b>Market Cap:</b> <b>${marketcap:,}</b>"
    )

    # Check if this is a button callback or direct command
    if hasattr(update, 'callback_query'):
        await update.callback_query.edit_message_text(
            price_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            price_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

async def chart_command(update: Update, context: CallbackContext) -> None:
    """Generate and send a price chart."""
    # Check if this is a button callback or direct command
    if hasattr(update, 'callback_query'):
        await update.callback_query.edit_message_text("Generating chart, please wait...")
    else:
        await update.message.reply_text("Generating chart, please wait...")
    
    try:
        # Get historical data
        response = requests.get("https://api.nonkyc.io/market/history?symbol=JKC/USDT&resolution=60&from=1749927600&to=1750100400")
        data = response.json()
        
        if not data or "s" not in data or data["s"] != "ok":
            error_msg = "Failed to fetch chart data. Please try again later."
            if hasattr(update, 'callback_query'):
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
            return
        
        # Create the chart
        plt.figure(figsize=(10, 6))
        plt.plot(data["t"], data["c"])
        plt.title("JKC/USDT Price Chart (Last 24 Hours)")
        plt.xlabel("Time")
        plt.ylabel("Price (USDT)")
        plt.grid(True)
        
        # Format x-axis as time
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        
        # Send the chart
        if hasattr(update, 'callback_query'):
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
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
        "/setapikeys - Set exchange API keys\n"
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
        ],
        [
            InlineKeyboardButton("💰 Set Min Value", callback_data="cmd_setmin"),
            InlineKeyboardButton("🔄 Toggle Aggregation", callback_data="cmd_toggle_agg")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def get_ipwan_command(update: Update, context: CallbackContext) -> None:
    """Get the server's public IP address."""
    user_id = update.effective_user.id
    
    if user_id == BOT_OWNER:
        try:
            response = requests.get("https://api.ipify.org")
            ip_address = response.text
            await update.message.reply_text(f"Server public IP: {ip_address}")
        except Exception as e:
            await update.message.reply_text(f"Error getting IP: {str(e)}")
    else:
        await update.message.reply_text("This command is only available to the bot owner.")

async def config_command(update: Update, context: CallbackContext) -> int:
    """Show configuration menu."""
    user_id = update.effective_user.id
    
    if user_id == BOT_OWNER or user_id == BY_PASS:
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
    else:
        await update.message.reply_text("You don't have permission to access configuration.")
        return ConversationHandler.END

async def button_callback(update: Update, context: CallbackContext) -> int:
    """Handle button callbacks for configuration menu."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "set_min":
        await query.edit_message_text(f"Current minimum value is {VALUE_REQUIRE} USDT. Enter a new value:")
        return INPUT_NUMBER
    
    elif query.data == "set_img":
        await query.edit_message_text("Send a new image for alerts:")
        return INPUT_IMAGE
    
    elif query.data == "dynamic_config":
        # Show dynamic threshold configuration
        dynamic_config = CONFIG.get("dynamic_threshold", {})
        enabled = dynamic_config.get("enabled", False)
        
        keyboard = [
            [InlineKeyboardButton(
                f"{'Disable' if enabled else 'Enable'} Dynamic Threshold", 
                callback_data=f"toggle_dynamic"
            )],
            [InlineKeyboardButton("Set Base Value", callback_data="set_base_value")],
            [InlineKeyboardButton("Set Volume Multiplier", callback_data="set_volume_mult")],
            [InlineKeyboardButton("Set Min Threshold", callback_data="set_min_threshold")],
            [InlineKeyboardButton("Set Max Threshold", callback_data="set_max_threshold")],
            [InlineKeyboardButton("Back to Main Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "Dynamic Threshold Configuration:\n\n"
            f"Enabled: {'Yes' if enabled else 'No'}\n"
            f"Base Value: {dynamic_config.get('base_value', 300)} USDT\n"
            f"Volume Multiplier: {dynamic_config.get('volume_multiplier', 0.05)}\n"
            f"Min Threshold: {dynamic_config.get('min_threshold', 100)} USDT\n"
            f"Max Threshold: {dynamic_config.get('max_threshold', 1000)} USDT\n"
        )
        
        await query.edit_message_text(message, reply_markup=reply_markup)
        return DYNAMIC_CONFIG
    
    elif query.data == "aggregation_config":
        # Show trade aggregation configuration
        agg_config = CONFIG.get("trade_aggregation", {})
        enabled = agg_config.get("enabled", True)
        
        keyboard = [
            [InlineKeyboardButton(
                f"{'Disable' if enabled else 'Enable'} Trade Aggregation", 
                callback_data=f"toggle_aggregation"
            )],
            [InlineKeyboardButton("Set Window Seconds", callback_data="set_window_seconds")],
            [InlineKeyboardButton("Back to Main Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "Trade Aggregation Configuration:\n\n"
            f"Enabled: {'Yes' if enabled else 'No'}\n"
            f"Window Seconds: {agg_config.get('window_seconds', 3)}\n"
        )
        
        await query.edit_message_text(message, reply_markup=reply_markup)
        return DYNAMIC_CONFIG  # Reuse the same state
    
    elif query.data == "show_config":
        # Show current configuration
        dynamic_config = CONFIG.get("dynamic_threshold", {})
        agg_config = CONFIG.get("trade_aggregation", {})
        sweep_config = CONFIG.get("sweep_orders", {})
        
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
            f"- Window Seconds: {agg_config.get('window_seconds', 3)}\n\n"
            "Sweep Orders:\n"
            f"- Enabled: {'Yes' if sweep_config.get('enabled', False) else 'No'}\n"
            f"- Min Value: {sweep_config.get('min_value', 50)} USDT\n"
            f"- Check Interval: {sweep_config.get('check_interval', 2)} seconds\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("Back to Main Menu", callback_data="back_to_main")]
        ]
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
    
    return CONFIG_MENU

async def dynamic_config_callback(update: Update, context: CallbackContext) -> int:
    """Handle button callbacks for dynamic threshold configuration."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "toggle_dynamic":
        # Toggle dynamic threshold
        if "dynamic_threshold" not in CONFIG:
            CONFIG["dynamic_threshold"] = {
                "enabled": True,
                "base_value": 300,
                "volume_multiplier": 0.05,
                "price_check_interval": 3600,
                "min_threshold": 100,
                "max_threshold": 1000
            }
        
        CONFIG["dynamic_threshold"]["enabled"] = not CONFIG["dynamic_threshold"]["enabled"]
        save_config(CONFIG)
        
        # Update the message
        enabled = CONFIG["dynamic_threshold"]["enabled"]
        
        keyboard = [
            [InlineKeyboardButton(
                f"{'Disable' if enabled else 'Enable'} Dynamic Threshold", 
                callback_data=f"toggle_dynamic"
            )],
            [InlineKeyboardButton("Set Base Value", callback_data="set_base_value")],
            [InlineKeyboardButton("Set Volume Multiplier", callback_data="set_volume_mult")],
            [InlineKeyboardButton("Set Min Threshold", callback_data="set_min_threshold")],
            [InlineKeyboardButton("Set Max Threshold", callback_data="set_max_threshold")],
            [InlineKeyboardButton("Back to Main Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "Dynamic Threshold Configuration:\n\n"
            f"Enabled: {'Yes' if enabled else 'No'}\n"
            f"Base Value: {CONFIG['dynamic_threshold'].get('base_value', 300)} USDT\n"
            f"Volume Multiplier: {CONFIG['dynamic_threshold'].get('volume_multiplier', 0.05)}\n"
            f"Min Threshold: {CONFIG['dynamic_threshold'].get('min_threshold', 100)} USDT\n"
            f"Max Threshold: {CONFIG['dynamic_threshold'].get('max_threshold', 1000)} USDT\n"
        )
        
        await query.edit_message_text(message, reply_markup=reply_markup)
        return DYNAMIC_CONFIG
    
    elif query.data == "toggle_aggregation":
        # Toggle trade aggregation
        if "trade_aggregation" not in CONFIG:
            CONFIG["trade_aggregation"] = {"enabled": True, "window_seconds": 3}
        
        CONFIG["trade_aggregation"]["enabled"] = not CONFIG["trade_aggregation"]["enabled"]
        save_config(CONFIG)
        
        # Update the message
        enabled = CONFIG["trade_aggregation"]["enabled"]
        
        keyboard = [
            [InlineKeyboardButton(
                f"{'Disable' if enabled else 'Enable'} Trade Aggregation", 
                callback_data=f"toggle_aggregation"
            )],
            [InlineKeyboardButton("Set Window Seconds", callback_data="set_window_seconds")],
            [InlineKeyboardButton("Back to Main Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "Trade Aggregation Configuration:\n\n"
            f"Enabled: {'Yes' if enabled else 'No'}\n"
            f"Window Seconds: {CONFIG['trade_aggregation'].get('window_seconds', 3)}\n"
        )
        
        await query.edit_message_text(message, reply_markup=reply_markup)
        return DYNAMIC_CONFIG
    
    elif query.data in ["set_base_value", "set_volume_mult", "set_min_threshold", "set_max_threshold", "set_window_seconds"]:
        # Store the setting to update in user_data
        context.user_data["setting"] = query.data
        
        # Prompt for the new value
        setting_name = {
            "set_base_value": "base value (USDT)",
            "set_volume_mult": "volume multiplier (e.g., 0.05)",
            "set_min_threshold": "minimum threshold (USDT)",
            "set_max_threshold": "maximum threshold (USDT)",
            "set_window_seconds": "aggregation window (seconds)"
        }
        
        await query.edit_message_text(f"Enter new {setting_name[query.data]}:")
        return DYNAMIC_CONFIG
    
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
    
    return DYNAMIC_CONFIG

async def dynamic_config_input(update: Update, context: CallbackContext) -> int:
    """Handle text input for dynamic threshold configuration."""
    setting = context.user_data.get("setting")
    if not setting:
        await update.message.reply_text("Error: No setting selected. Please try again.")
        return ConversationHandler.END
    
    try:
        value = update.message.text.strip()
        
        # Convert to appropriate type
        if setting in ["set_volume_mult"]:
            value = float(value)
        else:
            value = int(value)
        
        # Update the appropriate setting
        if setting == "set_base_value":
            CONFIG["dynamic_threshold"]["base_value"] = value
        elif setting == "set_volume_mult":
            CONFIG["dynamic_threshold"]["volume_multiplier"] = value
        elif setting == "set_min_threshold":
            CONFIG["dynamic_threshold"]["min_threshold"] = value
        elif setting == "set_max_threshold":
            CONFIG["dynamic_threshold"]["max_threshold"] = value
        elif setting == "set_window_seconds":
            if "trade_aggregation" not in CONFIG:
                CONFIG["trade_aggregation"] = {"enabled": True}
            CONFIG["trade_aggregation"]["window_seconds"] = value
        
        # Save the config
        save_config(CONFIG)
        
        # Confirm the change
        await update.message.reply_text(f"Setting updated successfully!")
        
        # Show the updated config menu
        if setting == "set_window_seconds":
            # Show trade aggregation config
            agg_config = CONFIG.get("trade_aggregation", {})
            enabled = agg_config.get("enabled", True)
            
            keyboard = [
                [InlineKeyboardButton(
                    f"{'Disable' if enabled else 'Enable'} Trade Aggregation", 
                    callback_data=f"toggle_aggregation"
                )],
                [InlineKeyboardButton("Set Window Seconds", callback_data="set_window_seconds")],
                [InlineKeyboardButton("Back to Main Menu", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = (
                "Trade Aggregation Configuration:\n\n"
                f"Enabled: {'Yes' if enabled else 'No'}\n"
                f"Window Seconds: {agg_config.get('window_seconds', 3)}\n"
            )
            
            await update.message.reply_text(message, reply_markup=reply_markup)
        else:
            # Show dynamic threshold config
            dynamic_config = CONFIG.get("dynamic_threshold", {})
            enabled = dynamic_config.get("enabled", False)
            
            keyboard = [
                [InlineKeyboardButton(
                    f"{'Disable' if enabled else 'Enable'} Dynamic Threshold", 
                    callback_data=f"toggle_dynamic"
                )],
                [InlineKeyboardButton("Set Base Value", callback_data="set_base_value")],
                [InlineKeyboardButton("Set Volume Multiplier", callback_data="set_volume_mult")],
                [InlineKeyboardButton("Set Min Threshold", callback_data="set_min_threshold")],
                [InlineKeyboardButton("Set Max Threshold", callback_data="set_max_threshold")],
                [InlineKeyboardButton("Back to Main Menu", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = (
                "Dynamic Threshold Configuration:\n\n"
                f"Enabled: {'Yes' if enabled else 'No'}\n"
                f"Base Value: {dynamic_config.get('base_value', 300)} USDT\n"
                f"Volume Multiplier: {dynamic_config.get('volume_multiplier', 0.05)}\n"
                f"Min Threshold: {dynamic_config.get('min_threshold', 100)} USDT\n"
                f"Max Threshold: {dynamic_config.get('max_threshold', 1000)} USDT\n"
            )
            
            await update.message.reply_text(message, reply_markup=reply_markup)
        
        return DYNAMIC_CONFIG
        
    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number.")
        return DYNAMIC_CONFIG
    except Exception as e:
        await update.message.reply_text(f"Error updating setting: {str(e)}")
        return DYNAMIC_CONFIG

async def set_minimum_command(update: Update, context: CallbackContext) -> int:
    """Command to set the minimum transaction value."""
    user_id = update.effective_user.id
    
    if user_id == BOT_OWNER or user_id == BY_PASS:
        await update.message.reply_text(f"Current minimum value is {VALUE_REQUIRE} USDT. Enter a new value:")
        return INPUT_NUMBER
    else:
        await update.message.reply_text("You don't have permission to change this setting.")
        return ConversationHandler.END

async def set_minimum_input(update: Update, context: CallbackContext) -> int:
    """Process input for minimum transaction value."""
    global VALUE_REQUIRE
    
    try:
        new_value = float(update.message.text.strip())
        if new_value <= 0:
            await update.message.reply_text("Value must be greater than 0.")
            return INPUT_NUMBER
        
        VALUE_REQUIRE = new_value
        CONFIG["value_require"] = new_value
        save_config(CONFIG)
        
        await update.message.reply_text(f"Minimum transaction value set to {new_value} USDT.")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number.")
        return INPUT_NUMBER

async def set_image_command(update: Update, context: CallbackContext) -> int:
    """Command to set the image for alerts."""
    user_id = update.effective_user.id
    
    if user_id == BOT_OWNER or user_id == BY_PASS:
        await update.message.reply_text("Send a new image for alerts:")
        return INPUT_IMAGE
    else:
        await update.message.reply_text("You don't have permission to change this setting.")
        return ConversationHandler.END

async def set_image_input(update: Update, context: CallbackContext) -> int:
    """Process input for alert image."""
    global PHOTO, IMAGE_PATH
    
    try:
        # Get the photo with the highest resolution
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # Download the file
        photo_data = await file.download_as_bytearray()
        
        # Save the file
        with open(IMAGE_PATH, 'wb') as f:
            f.write(photo_data)
        
        # Update the PHOTO variable
        with open(IMAGE_PATH, 'rb') as photo_file:
            img = photo_file.read()
            PHOTO = InputFile(io.BytesIO(img), filename=IMAGE_PATH)
        
        await update.message.reply_text("Image updated successfully.")
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Error updating image: {str(e)}")
        return ConversationHandler.END

async def toggle_aggregation(update: Update, context: CallbackContext) -> None:
    """Toggle trade aggregation on/off."""
    user_id = update.effective_user.id
    
    if user_id == BOT_OWNER or user_id == BY_PASS:
        # Ensure trade_aggregation exists in config
        if "trade_aggregation" not in CONFIG:
            CONFIG["trade_aggregation"] = {"enabled": True, "window_seconds": 3}
        
        # Toggle the enabled state
        CONFIG["trade_aggregation"]["enabled"] = not CONFIG["trade_aggregation"]["enabled"]
        
        # Save the config
        save_config(CONFIG)
        
        # Inform the user
        state = "enabled" if CONFIG["trade_aggregation"]["enabled"] else "disabled"
        await update.message.reply_text(f"Trade aggregation is now {state}.")
    else:
        await update.message.reply_text("You don't have permission to change this setting.")

async def set_api_keys_command(update: Update, context: CallbackContext) -> int:
    """Command to set API keys for exchanges."""
    user_id = update.effective_user.id
    
    if user_id == BOT_OWNER:
        keyboard = [
            [InlineKeyboardButton("Set CoinEx API Keys", callback_data="set_coinex_keys")],
            [InlineKeyboardButton("Set AscendEX API Keys", callback_data="set_ascendex_keys")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Select which API keys to set:", reply_markup=reply_markup)
        return CONFIG_MENU
    else:
        await update.message.reply_text("Only the bot owner can set API keys.")
        return ConversationHandler.END

async def api_keys_callback(update: Update, context: CallbackContext) -> int:
    """Handle button callbacks for API key configuration."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "set_coinex_keys":
        context.user_data["exchange"] = "coinex"
        await query.edit_message_text(
            "Enter CoinEx API keys in the format:\n"
            "access_id:secret_key\n\n"
            "Example:\n"
            "ABC123:XYZ456"
        )
        return INPUT_API_KEYS
    
    elif query.data == "set_ascendex_keys":
        context.user_data["exchange"] = "ascendex"
        await query.edit_message_text(
            "Enter AscendEX API keys in the format:\n"
            "access_id:secret_key\n\n"
            "Example:\n"
            "ABC123:XYZ456"
        )
        return INPUT_API_KEYS
    
    return CONFIG_MENU

async def set_api_keys_input(update: Update, context: CallbackContext) -> int:
    """Process input for API keys."""
    exchange = context.user_data.get("exchange")
    if not exchange:
        await update.message.reply_text("Error: No exchange selected. Please try again.")
        return ConversationHandler.END
    
    try:
        # Delete the message containing the API keys for security
        await update.message.delete()
        
        # Parse the input
        keys = update.message.text.strip().split(":")
        if len(keys) != 2:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid format. Please use access_id:secret_key"
            )
            return INPUT_API_KEYS
        
        access_id, secret_key = keys
        
        # Update the config
        if exchange == "coinex":
            CONFIG["coinex_access_id"] = access_id
            CONFIG["coinex_secret_key"] = secret_key
        elif exchange == "ascendex":
            CONFIG["ascendex_access_id"] = access_id
            CONFIG["ascendex_secret_key"] = secret_key
        
        # Save the config
        save_config(CONFIG)
        
        # Confirm the change
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{exchange.capitalize()} API keys updated successfully."
        )
        
        return ConversationHandler.END
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Error updating API keys: {str(e)}"
        )
        return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the current conversation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def button_command_callback(update: Update, context: CallbackContext) -> None:
    """Handle button commands from the help menu."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cmd_price":
        # Create a new update object for the check_price function
        new_update = Update(
            update_id=update.update_id,
            message=query.message,
            callback_query=query
        )
        await check_price(new_update, context)
    elif query.data == "cmd_chart":
        # Create a new update object for the chart_command function
        new_update = Update(
            update_id=update.update_id,
            message=query.message,
            callback_query=query
        )
        await chart_command(new_update, context)
    elif query.data == "cmd_config":
        if update.effective_user.id in (BY_PASS, BOT_OWNER):
            keyboard = [
                [InlineKeyboardButton("Set Minimum Value", callback_data="set_min")],
                [InlineKeyboardButton("Set Image", callback_data="set_img")],
                [InlineKeyboardButton("Dynamic Threshold Settings", callback_data="dynamic_config")],
                [InlineKeyboardButton("Trade Aggregation Settings", callback_data="aggregation_config")],
                [InlineKeyboardButton("Show Current Settings", callback_data="show_config")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Bot Configuration Menu:", reply_markup=reply_markup)
        else:
            await query.edit_message_text("You don't have permission to access configuration.")
    elif query.data == "cmd_stop":
        # Create a new update object for the stop_bot function
        new_update = Update(
            update_id=update.update_id,
            message=query.message,
            callback_query=query
        )
        await stop_bot(new_update, context)
    elif query.data == "cmd_setmin":
        if update.effective_user.id in (BY_PASS, BOT_OWNER):
            await query.edit_message_text(f"Current minimum value is {VALUE_REQUIRE} USDT. Enter a new value:")
            context.user_data["from_button"] = True
            return INPUT_NUMBER
        else:
            await query.edit_message_text("You don't have permission to change this setting.")
    elif query.data == "cmd_toggle_agg":
        if update.effective_user.id in (BY_PASS, BOT_OWNER):
            # Toggle trade aggregation
            if "trade_aggregation" not in CONFIG:
                CONFIG["trade_aggregation"] = {"enabled": True, "window_seconds": 3}
            
            CONFIG["trade_aggregation"]["enabled"] = not CONFIG["trade_aggregation"]["enabled"]
            save_config(CONFIG)
            
            state = "enabled" if CONFIG["trade_aggregation"]["enabled"] else "disabled"
            await query.edit_message_text(f"Trade aggregation is now {state}.")
        else:
            await query.edit_message_text("You don't have permission to change this setting.")
    else:
        await query.edit_message_text("Unknown command. Please try again.")

# API functions
async def get_nonkyc_ticker():
    """Get ticker data from NonKYC exchange."""
    try:
        response = requests.get("https://api.nonkyc.io/market/ticker?symbol=JKC/USDT")
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {})
        return None
    except Exception as e:
        logger.error(f"Error fetching NonKYC ticker: {e}")
        return None

async def get_coinex_ticker():
    """Get ticker data from CoinEx exchange."""
    try:
        response = requests.get("https://api.coinex.com/v1/market/ticker?market=JKCUSDT")
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("ticker", {})
        return None
    except Exception as e:
        logger.error(f"Error fetching CoinEx ticker: {e}")
        return None

async def get_ascendex_ticker():
    """Get ticker data from AscendEX exchange."""
    try:
        response = requests.get("https://ascendex.com/api/pro/v1/ticker?symbol=JKC/USDT")
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                return data.get("data", {})
        return None
    except Exception as e:
        logger.error(f"Error fetching AscendEX ticker: {e}")
        return None

# WebSocket functions
async def nonkyc_websocket():
    """Connect to NonKYC WebSocket and process trade messages."""
    global LAST_TRANS_KYC, running
    
    uri = "wss://api.nonkyc.io/ws"
    
    while running:
        try:
            async with websockets.connect(uri) as websocket:
                logger.info("Connected to NonKYC WebSocket")
                
                # Subscribe to trade channel
                subscribe_msg = {
                    "method": "SUBSCRIBE",
                    "params": ["trade@JKC/USDT"],
                    "id": 1
                }
                await websocket.send(json.dumps(subscribe_msg))
                
                while running:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        # Process trade data
                        if "data" in data and "e" in data["data"] and data["data"]["e"] == "trade":
                            trade_data = data["data"]
                            
                            # Extract trade details
                            price = float(trade_data.get("p", 0))
                            quantity = float(trade_data.get("q", 0))
                            value = price * quantity
                            buyer = trade_data.get("b", "Unknown")
                            seller = trade_data.get("a", "Unknown")
                            is_buyer_maker = trade_data.get("m", False)
                            timestamp = int(trade_data.get("T", 0))
                            
                            # Skip old trades
                            if timestamp <= LAST_TRANS_KYC:
                                continue
                            
                            LAST_TRANS_KYC = timestamp
                            
                            # Check if we should aggregate this trade
                            if CONFIG.get("trade_aggregation", {}).get("enabled", True):
                                # Add to pending trades
                                if "nonkyc" not in PENDING_TRADES:
                                    PENDING_TRADES["nonkyc"] = {}
                                
                                buyer_id = buyer
                                if buyer_id not in PENDING_TRADES["nonkyc"]:
                                    PENDING_TRADES["nonkyc"][buyer_id] = []
                                
                                PENDING_TRADES["nonkyc"][buyer_id].append({
                                    "price": price,
                                    "quantity": quantity,
                                    "value": value,
                                    "buyer": buyer,
                                    "seller": seller,
                                    "is_buyer_maker": is_buyer_maker,
                                    "timestamp": timestamp,
                                    "exchange": "NonKYC"
                                })
                            else:
                                # Process immediately if aggregation is disabled
                                await process_trade({
                                    "price": price,
                                    "quantity": quantity,
                                    "value": value,
                                    "buyer": buyer,
                                    "seller": seller,
                                    "is_buyer_maker": is_buyer_maker,
                                    "timestamp": timestamp,
                                    "exchange": "NonKYC"
                                })
                    except json.JSONDecodeError:
                        logger.warning("Received invalid JSON from NonKYC WebSocket")
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("NonKYC WebSocket connection closed")
                        break
                    except Exception as e:
                        logger.error(f"Error processing NonKYC WebSocket message: {e}")
                        traceback.print_exc()
        except Exception as e:
            if running:
                logger.error(f"NonKYC WebSocket error: {e}")
                logger.info("Reconnecting to NonKYC WebSocket in 5 seconds...")
                await asyncio.sleep(5)
            else:
                break

async def coinex_websocket():
    """Connect to CoinEx WebSocket and process trade messages."""
    global LAST_TRANS_COINEX, running
    
    uri = "wss://socket.coinex.com/"
    
    while running:
        try:
            async with websockets.connect(uri) as websocket:
                logger.info("Connected to CoinEx WebSocket")
                
                # Subscribe to trade channel
                subscribe_msg = {
                    "method": "deals.subscribe",
                    "params": ["JKCUSDT"],
                    "id": 1
                }
                await websocket.send(json.dumps(subscribe_msg))
                
                while running:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        # Process trade data
                        if "method" in data and data["method"] == "deals.update" and "params" in data:
                            trades = data["params"][1]
                            for trade in trades:
                                # Extract trade details
                                price = float(trade.get("price", 0))
                                quantity = float(trade.get("amount", 0))
                                value = price * quantity
                                is_buy = trade.get("type") == "buy"
                                timestamp = int(trade.get("time", 0) * 1000)  # Convert to milliseconds
                                
                                # Skip old trades
                                if timestamp <= LAST_TRANS_COINEX:
                                    continue
                                
                                LAST_TRANS_COINEX = timestamp
                                
                                # Check if we should aggregate this trade
                                if CONFIG.get("trade_aggregation", {}).get("enabled", True):
                                    # Add to pending trades
                                    if "coinex" not in PENDING_TRADES:
                                        PENDING_TRADES["coinex"] = {}
                                    
                                    # Use trade ID as buyer ID
                                    buyer_id = trade.get("id", "unknown")
                                    if buyer_id not in PENDING_TRADES["coinex"]:
                                        PENDING_TRADES["coinex"][buyer_id] = []
                                    
                                    PENDING_TRADES["coinex"][buyer_id].append({
                                        "price": price,
                                        "quantity": quantity,
                                        "value": value,
                                        "buyer": "Unknown",
                                        "seller": "Unknown",
                                        "is_buyer_maker": not is_buy,
                                        "timestamp": timestamp,
                                        "exchange": "CoinEx"
                                    })
                                else:
                                    # Process immediately if aggregation is disabled
                                    await process_trade({
                                        "price": price,
                                        "quantity": quantity,
                                        "value": value,
                                        "buyer": "Unknown",
                                        "seller": "Unknown",
                                        "is_buyer_maker": not is_buy,
                                        "timestamp": timestamp,
                                        "exchange": "CoinEx"
                                    })
                    except json.JSONDecodeError:
                        logger.warning("Received invalid JSON from CoinEx WebSocket")
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("CoinEx WebSocket connection closed")
                        break
                    except Exception as e:
                        logger.error(f"Error processing CoinEx WebSocket message: {e}")
                        traceback.print_exc()
        except Exception as e:
            if running:
                logger.error(f"CoinEx WebSocket error: {e}")
                logger.info("Reconnecting to CoinEx WebSocket in 5 seconds...")
                await asyncio.sleep(5)
            else:
                break

async def process_trade(trade):
    """Process a trade and send alerts if it meets the criteria."""
    global VALUE_REQUIRE, LAST_THRESHOLD_UPDATE
    
    # Check if dynamic threshold is enabled
    if CONFIG.get("dynamic_threshold", {}).get("enabled", False):
        # Update threshold periodically
        current_time = time.time()
        check_interval = CONFIG["dynamic_threshold"].get("price_check_interval", 3600)
        
        if current_time - LAST_THRESHOLD_UPDATE > check_interval:
            await update_dynamic_threshold()
            LAST_THRESHOLD_UPDATE = current_time
    
    # Check if the trade value meets the threshold
    if trade["value"] >= VALUE_REQUIRE:
        # Only process buy orders (not sell orders)
        if trade["is_buyer_maker"]:
            # This is a sell order, so we skip it
            return
        
        # Determine exchange URL
        exchange_name = trade["exchange"].split(" ")[0].lower()
        if exchange_name == "nonkyc":
            exchange_url = "https://nonkyc.io/market/JKC_USDT"
        elif exchange_name == "coinex":
            exchange_url = "https://www.coinex.com/exchange/JKC-USDT"
        elif exchange_name == "ascendex":
            exchange_url = "https://ascendex.com/en/cashtrade-spottrading/usdt/jkc"
        else:
            exchange_url = "https://nonkyc.io/market/JKC_USDT"  # Default
        
        # Send the alert
        await send_alert(
            trade["price"],
            trade["quantity"],
            trade["value"],
            trade["exchange"],
            trade["timestamp"],
            exchange_url,
            num_trades=1 if "Aggregated" not in trade["exchange"] else int(trade["exchange"].split("Aggregated ")[1].split(" ")[0])
        )

async def update_dynamic_threshold():
    """Update the dynamic threshold based on trading volume."""
    global VALUE_REQUIRE
    
    try:
        # Get 24h trading volume
        ticker = await get_nonkyc_ticker()
        if not ticker:
            logger.warning("Failed to get ticker data for dynamic threshold update")
            return
        
        volume = float(ticker.get("volume", 0))
        
        # Calculate new threshold
        base_value = CONFIG["dynamic_threshold"].get("base_value", 300)
        multiplier = CONFIG["dynamic_threshold"].get("volume_multiplier", 0.05)
        min_threshold = CONFIG["dynamic_threshold"].get("min_threshold", 100)
        max_threshold = CONFIG["dynamic_threshold"].get("max_threshold", 1000)
        
        new_threshold = base_value + (volume * multiplier)
        
        # Apply min/max constraints
        new_threshold = max(min_threshold, min(new_threshold, max_threshold))
        
        # Update the threshold
        VALUE_REQUIRE = new_threshold
        CONFIG["value_require"] = new_threshold
        save_config(CONFIG)
        
        logger.info(f"Dynamic threshold updated to {new_threshold:.2f} USDT (volume: {volume:.2f})")
    except Exception as e:
        logger.error(f"Error updating dynamic threshold: {e}")

async def check_aggregated_trades():
    """Check and process aggregated trades."""
    global PENDING_TRADES, LAST_AGGREGATION_CHECK
    
    while running:
        try:
            current_time = time.time()
            window = CONFIG.get("trade_aggregation", {}).get("window_seconds", TRADE_AGGREGATION_WINDOW)
            
            # Only process if enough time has passed
            if current_time - LAST_AGGREGATION_CHECK >= window:
                LAST_AGGREGATION_CHECK = current_time
                
                # Process each exchange
                for exchange, buyers in list(PENDING_TRADES.items()):
                    for buyer_id, trades in list(buyers.items()):
                        if trades:
                            # Aggregate trades
                            total_quantity = sum(trade["quantity"] for trade in trades)
                            total_value = sum(trade["value"] for trade in trades)
                            avg_price = total_value / total_quantity if total_quantity > 0 else 0
                            
                            # Use the most recent timestamp
                            timestamp = max(trade["timestamp"] for trade in trades)
                            
                            # Use the first trade's buyer/seller info
                            first_trade = trades[0]
                            
                            # Process the aggregated trade
                            await process_trade({
                                "price": avg_price,
                                "quantity": total_quantity,
                                "value": total_value,
                                "buyer": first_trade["buyer"],
                                "seller": first_trade["seller"],
                                "is_buyer_maker": first_trade["is_buyer_maker"],
                                "timestamp": timestamp,
                                "exchange": f"{exchange.capitalize()} (Aggregated {len(trades)} trades)"
                            })
                            
                            # Clear processed trades
                            PENDING_TRADES[exchange][buyer_id] = []
            
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in check_aggregated_trades: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)

async def check_sweep_orders():
    """Check for sweep orders (multiple orders filled in a short time)."""
    while running:
        try:
            # Only run if sweep orders are enabled
            if not CONFIG.get("sweep_orders", {}).get("enabled", False):
                await asyncio.sleep(5)
                continue
            
            # Get recent trades from NonKYC
            response = requests.get("https://api.nonkyc.io/market/trades?symbol=JKC/USDT&limit=50")
            if response.status_code != 200:
                await asyncio.sleep(5)
                continue
            
            data = response.json()
            if "data" not in data:
                await asyncio.sleep(5)
                continue
            
            trades = data["data"]
            
            # Group trades by timestamp (rounded to nearest second)
            grouped_trades = {}
            for trade in trades:
                timestamp = int(trade["time"] / 1000)  # Convert to seconds
                if timestamp not in grouped_trades:
                    grouped_trades[timestamp] = []
                grouped_trades[timestamp].append(trade)
            
            # Check for timestamps with multiple trades
            for timestamp, trades_at_time in grouped_trades.items():
                if len(trades_at_time) >= CONFIG["sweep_orders"].get("min_orders_filled", 2):
                    # Calculate total value
                    total_value = sum(float(trade["price"]) * float(trade["amount"]) for trade in trades_at_time)
                    
                    # Check if total value meets threshold
                    if total_value >= CONFIG["sweep_orders"].get("min_value", 50):
                        # Determine if it's a buy or sell sweep
                        is_buy = trades_at_time[0]["side"] == "buy"
                        emoji = "🟢" if is_buy else "🔴"
                        action = "Buy" if is_buy else "Sell"
                        
                        # Calculate total quantity
                        total_quantity = sum(float(trade["amount"]) for trade in trades_at_time)
                        
                        # Calculate average price
                        avg_price = total_value / total_quantity if total_quantity > 0 else 0
                        
                        message = (
                            f"⚡ <b>{action} Sweep Detected!</b> ⚡\n\n"
                            f"{emoji} <b>{len(trades_at_time)} orders filled</b> in 1 second\n"
                            f"💰 <b>Total Value:</b> {total_value:.2f} USDT\n"
                            f"🪙 <b>Total Quantity:</b> {total_quantity:.2f} JKC\n"
                            f"💵 <b>Average Price:</b> {avg_price:.6f} USDT\n"
                            f"🏦 <b>Exchange:</b> NonKYC\n"
                        )
                        
                        # Send the alert to all active chats
                        for chat_id in ACTIVE_CHAT_IDS:
                            try:
                                if PHOTO:
                                    await bot.send_photo(
                                        chat_id=chat_id,
                                        photo=PHOTO,
                                        caption=message,
                                        parse_mode="HTML"
                                    )
                                else:
                                    await bot.send_message(
                                        chat_id=chat_id,
                                        text=message,
                                        parse_mode="HTML"
                                    )
                            except Exception as e:
                                logger.error(f"Error sending sweep alert to chat {chat_id}: {e}")
            
            # Sleep for the configured interval
            await asyncio.sleep(CONFIG["sweep_orders"].get("check_interval", 2))
        except Exception as e:
            logger.error(f"Error in check_sweep_orders: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)

# Main function
async def main():
    """Start the bot and run it until interrupted."""
    global bot
    
    # Set up logging to file
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = f"{log_dir}/telebot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    logger.info("Logging to file: %s", log_file)
    logger.info("Starting JunkCoin Alert Bot...")
    logger.info("Configuration loaded: %s", json.dumps(CONFIG))
    logger.info("Bot owner ID: %s", BOT_OWNER)
    logger.info("Minimum value threshold: %s USDT", VALUE_REQUIRE)
    logger.info("Active in %s chats", len(ACTIVE_CHAT_IDS))
    logger.info("Trade aggregation window: %s seconds", TRADE_AGGREGATION_WINDOW)
    logger.info("Dynamic threshold enabled: %s", CONFIG["dynamic_threshold"]["enabled"])
    logger.info("Trade aggregation enabled: %s", CONFIG.get("trade_aggregation", {}).get("enabled", True))
    logger.info("Sweep orders enabled: %s", CONFIG.get("sweep_orders", {}).get("enabled", False))
    
    # Create the bot instance
    bot = Bot(token=BOT_TOKEN)
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_bot))
    application.add_handler(CommandHandler("stop", stop_bot))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("price", check_price))
    application.add_handler(CommandHandler("chart", chart_command))
    application.add_handler(CommandHandler("toggle_aggregation", toggle_aggregation))
    application.add_handler(CommandHandler("ipwan", get_ip))
    
    # Add conversation handlers
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("setmin", set_minimum_command),
            CommandHandler("setimage", set_image_command),
            CommandHandler("config", config_command),
            CommandHandler("setapikeys", set_api_keys_command),
            CallbackQueryHandler(button_command_callback, pattern=r"^cmd_")
        ],
        states={
            INPUT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_minimum_input)],
            INPUT_IMAGE: [MessageHandler(filters.PHOTO, set_image_input)],
            CONFIG_MENU: [
                CallbackQueryHandler(config_callback),
                CallbackQueryHandler(api_keys_callback, pattern=r"^set_.*_keys$")
            ],
            DYNAMIC_CONFIG: [
                CallbackQueryHandler(dynamic_config_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, dynamic_config_input)
            ],
            INPUT_API_KEYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_api_keys_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    application.add_handler(conv_handler)
    
    # Add callback query handler for button commands
    application.add_handler(CallbackQueryHandler(button_command_callback, pattern=r"^cmd_"))
    
    # Start the websocket listeners in separate tasks
    asyncio.create_task(nonkyc_websocket())
    asyncio.create_task(coinex_websocket())
    asyncio.create_task(check_aggregated_trades())
    asyncio.create_task(check_sweep_orders())
    
    # Start the Bot
    await application.start()
    await application.updater.start_polling()
    
    logger.info("Bot started and ready to receive commands!")
    
    # Keep the bot running until interrupted
    try:
        await asyncio.Future()  # Run forever
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopping...")
    finally:
        # Clean shutdown
        global running
        running = False
        await application.stop()
        await application.updater.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        error_msg = f"Bot crashed with error: {str(e)}\n\n{traceback.format_exc()}"
        logger.critical(error_msg)
        
        # Try to notify the owner
        try:
            asyncio.run(notify_owner_of_error(error_msg))
        except Exception as notify_error:
            logger.error(f"Failed to notify owner about crash: {notify_error}")
