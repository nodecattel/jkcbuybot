import asyncio
from datetime import datetime, timezone, timedelta
import time
import io
import json
import os
import signal
import sys
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import Application, CommandHandler, CallbackContext, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
import requests
import threading
import websockets
import plotly.graph_objects as go
import pandas as pd

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
            }
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
BOT_OWNER = CONFIG["bot_owner"]
BY_PASS = CONFIG["by_pass"]
IMAGE_PATH = CONFIG["image_path"]

# Constants for conversation handlers
INPUT_NUMBER = 1
INPUT_IMAGE = 1
CONFIG_MENU = 2
DYNAMIC_CONFIG = 3

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

async def nonkyc_websocket():
    """Connect to NonKYC WebSocket API and process trade data."""
    global LAST_TRANS_KYC, running
    uri = "wss://ws.nonkyc.io"
    
    while running:
        try:
            async with websockets.connect(uri, ping_interval=30) as websocket:
                logger.info(f"Connected to NonKYC WebSocket at {uri}")
                
                # Subscribe to JKC/USDT trades
                subscribe_msg = {
                    "method": "subscribeTrades",
                    "params": {
                        "symbol": "JKC/USDT"
                    },
                    "id": 1
                }
                await websocket.send(json.dumps(subscribe_msg))
                logger.info("Subscribed to JKC/USDT trades on NonKYC")
                
                # Process messages
                while running:
                    try:
                        response = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))
                        
                        # Handle trade updates
                        if response.get("method") == "updateTrades":
                            trades = response.get("params", {}).get("data", [])
                            if trades:
                                logger.debug(f"Received {len(trades)} trades from NonKYC")
                            
                            for trade in trades:
                                # Convert timestamp to milliseconds if needed
                                timestamp = int(datetime.fromisoformat(trade["timestamp"].replace("Z", "+00:00")).timestamp() * 1000)
                                
                                if LAST_TRANS_KYC < timestamp:
                                    LAST_TRANS_KYC = timestamp
                                    price = float(trade["price"])
                                    quantity = float(trade["quantity"])
                                    sum_value = price * quantity
                                    
                                    if round(sum_value, 2) > VALUE_REQUIRE:
                                        logger.info(f"Large trade detected on NonKYC: {quantity} JKC at {price} USDT (Total: {sum_value} USDT)")
                                        await process_message(price, quantity, sum_value, "NonKYC", timestamp, "https://nonkyc.io/market/JKC_USDT")
                    except asyncio.TimeoutError:
                        # Just a timeout, continue
                        continue
                    except Exception as e:
                        if not running:
                            break
                        logger.error(f"Error processing NonKYC message: {e}")
                        await asyncio.sleep(5)
                        
        except Exception as e:
            if not running:
                break
            logger.error(f"NonKYC WebSocket error: {e}")
            await asyncio.sleep(10)

async def coinex_websocket():
    """Listen for trades on CoinEx WebSocket API."""
    global LAST_TRANS_COINEX, running
    uri = "wss://socket.coinex.com/"
    
    while running:
        try:
            async with websockets.connect(uri) as websocket:
                print(f"Connected to {uri}")
                # Subscribe to deals
                subscribe_msg = {
                    "method": "deals.subscribe",
                    "params": ["JKCUSDT"],
                    "id": 456
                }
                await websocket.send(json.dumps(subscribe_msg))
                
                # Process messages
                while running:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=5)
                        data = json.loads(message)
                        
                        if "method" in data and data["method"] == "deals.update":
                            for trade in data["params"][1]:
                                # Process each trade
                                price = float(trade["price"])
                                quantity = float(trade["amount"])
                                sum_value = price * quantity
                                timestamp = int(trade["time"] * 1000)  # Convert to milliseconds
                                
                                # Only process new trades
                                if timestamp > LAST_TRANS_COINEX and sum_value >= VALUE_REQUIRE:
                                    LAST_TRANS_COINEX = timestamp
                                    await process_message(price, quantity, sum_value, "CoinEx", timestamp, "https://www.coinex.com/en/exchange/jkc-usdt")
                    except asyncio.TimeoutError:
                        # Just a timeout, continue
                        continue
                    except Exception as e:
                        if not running:
                            break
                        print(f"Error processing CoinEx message: {e}")
                        await asyncio.sleep(5)
                        
        except Exception as e:
            if not running:
                break
            print(f"CoinEx WebSocket error: {e}")
            await asyncio.sleep(10)

async def ascendex_websocket():
    """Listen for trades on Ascendex WebSocket API."""
    global LAST_TRANS_ASENDEX, running
    uri = "wss://ascendex.com/1/api/pro/v1/stream"
    
    while running:
        try:
            async with websockets.connect(uri) as websocket:
                print(f"Connected to {uri}")
                # Subscribe to trades
                subscribe_msg = {
                    "op": "sub",
                    "ch": "trades:JKC/USDT"
                }
                await websocket.send(json.dumps(subscribe_msg))
                
                # Process messages
                while running:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=5)
                        data = json.loads(message)
                        
                        if "m" in data and data["m"] == "trades" and "data" in data:
                            for trade in data["data"]:
                                # Process each trade
                                price = float(trade["p"])
                                quantity = float(trade["q"])
                                sum_value = price * quantity
                                timestamp = int(trade["ts"])
                                
                                # Only process new trades
                                if timestamp > LAST_TRANS_ASENDEX and sum_value >= VALUE_REQUIRE:
                                    LAST_TRANS_ASENDEX = timestamp
                                    await process_message(price, quantity, sum_value, "Ascendex", timestamp, "https://ascendex.com/en/cashtrade-spottrading/usdt/jkc")
                    except asyncio.TimeoutError:
                        # Just a timeout, continue
                        continue
                    except Exception as e:
                        if not running:
                            break
                        print(f"Error processing Ascendex message: {e}")
                        await asyncio.sleep(5)
                        
        except Exception as e:
            if not running:
                break
            print(f"Ascendex WebSocket error: {e}")
            await asyncio.sleep(10)

async def process_message(price, quantity, sum_value, exchange, timestamp, exchange_url):
    """Process a trade message and send notification if it meets criteria."""
    global PHOTO
    
    # Update threshold based on volume
    await update_threshold()
    
    # Format the message
    dt_object = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
    vietnam_tz = timezone(timedelta(hours=7))
    dt_vietnam = dt_object.astimezone(vietnam_tz)
    formatted_time = dt_vietnam.strftime("%H:%M:%S %d/%m/%Y")
    
    message = (
        f"🚨 <b>Large Transaction Alert</b> 🚨\n\n"
        f"💰 <b>Amount:</b> {quantity:.2f} JKC\n"
        f"💵 <b>Price:</b> {price:.6f} USDT\n"
        f"💲 <b>Total Value:</b> {sum_value:.2f} USDT\n"
        f"🏦 <b>Exchange:</b> {exchange}\n"
        f"⏰ <b>Time:</b> {formatted_time}\n"
    )
    
    # Create inline button to exchange
    button = InlineKeyboardButton(text=f"Trade on {exchange}", url=exchange_url)
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
    user_id = update.effective_user.id
    if user_id == BOT_OWNER:
        await update.message.reply_text(get_public_ip())
    else:
        await update.message.reply_text("You do not have permission to use this command.")

async def set_minimum_command(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    if user_id in (BY_PASS, BOT_OWNER):
        await update.message.reply_text("Please enter the new minimum value:")
        return INPUT_NUMBER
    else:
        await update.message.reply_text("You do not have permission to set the minimum value.")
        return ConversationHandler.END

async def set_minimum_input(update: Update, context: CallbackContext) -> int:
    global VALUE_REQUIRE, CONFIG
    try:
        value = int(update.message.text)
        VALUE_REQUIRE = value
        CONFIG["value_require"] = value
        save_config(CONFIG)
        await update.message.reply_text(f"Minimum value set to {value}")
    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number.")
    return ConversationHandler.END

async def set_image_command(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    if user_id in (BY_PASS, BOT_OWNER):
        await update.message.reply_text("Please send the image you want to set:")
        return INPUT_IMAGE
    else:
        await update.message.reply_text("You do not have permission to set the image.")
        return ConversationHandler.END

async def set_image_input(update: Update, context: CallbackContext) -> int:
    global PHOTO, CONFIG
    photo = update.message.photo[-1]
    file = await photo.get_file()
    PHOTO = InputFile(io.BytesIO(await file.download_as_bytearray()), filename=IMAGE_PATH)
    await file.download_to_drive(IMAGE_PATH)
    await update.message.reply_text("Image updated successfully!")
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def start_bot(update: Update, context: CallbackContext) -> None:
    global ACTIVE_CHAT_IDS, CONFIG

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    chat_member = await context.bot.get_chat_member(chat_id, user_id)

    if chat_member.status in ["administrator", "creator"] or BOT_OWNER == user_id:
        if chat_id not in ACTIVE_CHAT_IDS:
            ACTIVE_CHAT_IDS.append(chat_id)
            CONFIG["active_chat_ids"] = ACTIVE_CHAT_IDS
            save_config(CONFIG)
            await update.message.reply_text("Bot started")
        else:
            await update.message.reply_text("Bot already running!")
    else:
        await update.message.reply_text("You need to be an admin to start the bot.")

async def stop_bot(update: Update, context: CallbackContext) -> None:
    global ACTIVE_CHAT_IDS, CONFIG
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    chat_member = await context.bot.get_chat_member(chat_id, user_id)
    if chat_member.status in ["administrator", "creator"] or BOT_OWNER == user_id:
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
        f"💵Price: {current_price} USDT\n📈Market Cap: <b>${marketcap:,}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

async def config_command(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    if user_id in (BY_PASS, BOT_OWNER):
        keyboard = [
            [InlineKeyboardButton("Set Minimum Value", callback_data="set_min")],
            [InlineKeyboardButton("Set Image", callback_data="set_img")],
            [InlineKeyboardButton("Dynamic Threshold Settings", callback_data="dynamic_config")],
            [InlineKeyboardButton("Show Current Settings", callback_data="show_config")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Bot Configuration Menu:", reply_markup=reply_markup)
        return CONFIG_MENU
    else:
        await update.message.reply_text("You do not have permission to access configuration.")
        return ConversationHandler.END

async def button_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "set_min":
        await query.edit_message_text("Please enter the new minimum value:")
        return INPUT_NUMBER
    elif query.data == "set_img":
        await query.edit_message_text("Please send the new image as a reply to this message.")
        return INPUT_IMAGE
    elif query.data == "dynamic_config":
        keyboard = [
            [InlineKeyboardButton("Enable Dynamic Threshold", callback_data="dynamic_enable")],
            [InlineKeyboardButton("Disable Dynamic Threshold", callback_data="dynamic_disable")],
            [InlineKeyboardButton("Set Base Value", callback_data="dynamic_base")],
            [InlineKeyboardButton("Set Volume Multiplier", callback_data="dynamic_mult")],
            [InlineKeyboardButton("Back", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Dynamic Threshold Settings:\n"
            f"Enabled: {CONFIG['dynamic_threshold']['enabled']}\n"
            f"Base Value: {CONFIG['dynamic_threshold']['base_value']}\n"
            f"Volume Multiplier: {CONFIG['dynamic_threshold']['volume_multiplier']}\n"
            f"Current Value: {VALUE_REQUIRE}",
            reply_markup=reply_markup
        )
        return DYNAMIC_CONFIG
    elif query.data == "show_config":
        config_text = (
            f"Current Configuration:\n"
            f"Minimum Value: {VALUE_REQUIRE}\n"
            f"Dynamic Threshold: {'Enabled' if CONFIG['dynamic_threshold']['enabled'] else 'Disabled'}\n"
            f"Active Chats: {len(ACTIVE_CHAT_IDS)}\n"
            f"Image: {IMAGE_PATH}"
        )
        keyboard = [[InlineKeyboardButton("Back", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(config_text, reply_markup=reply_markup)
        return CONFIG_MENU
    elif query.data == "back_to_main":
        return await config_command(update, context)
    elif query.data.startswith("dynamic_"):
        return await handle_dynamic_config(update, context, query.data)
    
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

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_bot))
    application.add_handler(CommandHandler("stop", stop_bot))
    application.add_handler(CommandHandler("price", check_price))
    application.add_handler(CommandHandler("chart", chart_command))
    application.add_handler(CommandHandler("ipwan", get_ipwan_command))
    
    # Add conversation handlers
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
                MessageHandler(filters.TEXT & ~filters.COMMAND, cancel),
                CallbackQueryHandler(button_callback)
            ],
            INPUT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_minimum_input)],
            INPUT_IMAGE: [MessageHandler(filters.PHOTO, set_image_input)],
            DYNAMIC_CONFIG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, dynamic_config_input),
                CallbackQueryHandler(button_callback)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    
    # Start the websocket listeners in separate tasks
    loop = asyncio.get_event_loop()
    loop.create_task(nonkyc_websocket())
    loop.create_task(coinex_websocket())
    loop.create_task(ascendex_websocket())
    loop.create_task(heartbeat())
    
    logger.info("Bot started and ready to receive commands!")
    logger.info(f"Monitoring trades with threshold: {VALUE_REQUIRE} USDT")
    logger.info(f"Active in {len(ACTIVE_CHAT_IDS)} chats")
    logger.info("Press Ctrl+C to stop the bot")
    
    # Start the Bot
    application.run_polling()

# Add a heartbeat function to show the bot is still running
async def heartbeat():
    """Send periodic heartbeat messages to show the bot is running."""
    global running
    counter = 0
    while running:
        counter += 1
        if counter % 60 == 0:  # Log every minute
            logger.info(f"Bot running - Monitoring trades with threshold: {VALUE_REQUIRE} USDT")
        await asyncio.sleep(1)

if __name__ == "__main__":
    main()
