"""
Telegram Handlers Module for JKC Trading Bot

This module contains all Telegram command handlers, callback handlers, and conversation flows.
It provides the user interface for the bot through various commands and interactive elements.
"""

import logging
import time
import os
from datetime import datetime
from typing import Optional, List

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
    from telegram.ext import CallbackContext, ConversationHandler
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    # Handle missing telegram dependency gracefully
    Update = None
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    InputFile = None
    CallbackContext = None
    ConversationHandler = None
    TelegramError = Exception
    TELEGRAM_AVAILABLE = False

from config import get_config, update_config, get_bot_owner, get_active_chat_ids
from permissions import is_admin, is_owner_only, can_use_admin_commands, can_use_public_commands
from utils import (INPUT_NUMBER, INPUT_IMAGE, CONFIG_MENU, DYNAMIC_CONFIG, INPUT_API_KEYS,
                   INPUT_IMAGE_SETIMAGE, format_momentum, get_change_emoji, get_public_ip,
                   format_price, format_usdt_price, format_btc_price, format_quantity)
from image_manager import (get_image_collection, get_image_stats, save_image_to_collection, 
                          delete_image_from_collection, clear_image_collection, get_image_info,
                          generate_unique_filename, detect_file_type, is_animation, load_random_image)
from api_clients import get_livecoinwatch_data, get_nonkyc_ticker, calculate_combined_volume_periods
from alert_system import send_alert

# Set up module logger
logger = logging.getLogger(__name__)

# Global variables for state management
PHOTO = None

def set_global_photo(photo):
    """Set the global photo variable."""
    global PHOTO
    PHOTO = photo

async def start_bot(update: Update, context: CallbackContext) -> None:
    """Start the bot - admin only command."""
    user_id = update.effective_user.id
    logger.info(f"Start command called by user {user_id}")

    if await can_use_admin_commands(update, context):
        logger.info(f"User {user_id} has admin permissions, starting bot")
        await update.message.reply_text("Bot started and monitoring JKC trades!")
    else:
        logger.warning(f"User {user_id} tried to start bot without admin permissions")
        await update.message.reply_text("You do not have permission to use this command.")

async def stop_bot(update: Update, context: CallbackContext) -> None:
    """Stop the bot - admin only command."""
    user_id = update.effective_user.id
    logger.info(f"Stop command called by user {user_id}")

    if await can_use_admin_commands(update, context):
        logger.info(f"User {user_id} has admin permissions, stopping bot")
        await update.message.reply_text("Bot stopped. No longer monitoring trades.")
    else:
        logger.warning(f"User {user_id} tried to stop bot without admin permissions")
        await update.message.reply_text("You do not have permission to use this command.")

async def help_command(update: Update, context: CallbackContext) -> None:
    """Show help message with available commands."""
    user_id = update.effective_user.id
    logger.info(f"Help command called by user {user_id}")

    # Check if user has admin permissions for admin commands
    has_admin = await can_use_admin_commands(update, context)
    
    help_text = """
🤖 <b>JKC Trading Alert Bot - Help</b>

<b>📊 Public Commands:</b>
/help - Show this help message
/price - Get current JKC price and market data
/chart - Generate JKC price chart

<b>🔧 Admin Commands:</b>"""

    if has_admin:
        help_text += """
/start - Start the bot monitoring
/stop - Stop the bot monitoring
/setmin - Set minimum alert threshold
/config - Open configuration menu
/setimage - Set alert image
/list_images - Manage image collection
/clear_images - Clear all images
/toggle_aggregation - Toggle trade aggregation
/debug - Show debug information
/test - Test alert system
/ipwan - Get server IP address"""
    else:
        help_text += """
<i>Admin commands are restricted to authorized users.</i>"""

    help_text += """

<b>💰 JKCBuyBot Developer Coffee Tip</b>
Support the developer: <code>1B1YLseSykoBPKFzokTGvzM2gzybyEDiU4</code>

<b>🔗 Links:</b>
• <a href="https://www.classicjkc.com">JunkCoin Website</a>
• <a href="https://nonkyc.io/market/JKC_USDT">Trade JKC/USDT</a>
• <a href="https://nonkyc.io/market/JKC_BTC">Trade JKC/BTC</a>

<i>Tap Bitcoin address to copy on mobile</i>"""

    await update.message.reply_text(help_text, parse_mode="HTML", disable_web_page_preview=True)

async def check_price(update: Update, context: CallbackContext) -> None:
    """Get current JKC price and market data."""
    user_id = update.effective_user.id
    logger.info(f"Price command called by user {user_id}")

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

    try:
        # Extract price data based on source
        if data_source == "NonKYC Exchange":
            current_price = float(market_data.get("lastPriceNumber", 0))
            volume_24h = float(market_data.get("volumeNumber", 0))
            change_percent = float(market_data.get("changeNumber", 0))
            market_cap_nonkyc = float(market_data.get("marketcapNumber", 0))
        else:  # LiveCoinWatch
            current_price = float(market_data.get("rate", 0))
            volume_24h = float(market_data.get("volume", 0))
            change_percent = float(market_data.get("delta", {}).get("day", 0))
            market_cap_nonkyc = float(market_data.get("cap", 0))

        # Calculate additional metrics
        yesterday_price = current_price / (1 + change_percent / 100) if change_percent != 0 else current_price
        price_change_usdt = current_price - yesterday_price if yesterday_price > 0 else 0

        # Format change with crypto-appropriate emojis
        change_emoji = get_change_emoji(change_percent)
        change_sign = "+" if change_percent >= 0 else ""

        # Get volume data for momentum calculation
        try:
            volume_data = await calculate_combined_volume_periods()
            volume_periods = volume_data["combined"]
            
            # Calculate momentum (price change) for different periods
            momentum_periods = {
                "15m": change_percent * 0.1,  # Approximate momentum
                "1h": change_percent * 0.3,
                "4h": change_percent * 0.7,
                "24h": change_percent
            }
        except Exception as e:
            logger.error(f"Error calculating momentum: {e}")
            volume_periods = {"15m": 0, "1h": 0, "4h": 0, "24h": volume_24h}
            momentum_periods = {"15m": 0, "1h": 0, "4h": 0, "24h": change_percent}

        # Format the message with rich data including momentum and volume periods
        message = (
            f"🪙 <b>JunkCoin (JKC) Market Data</b> 🪙\n\n"
            f"💰 <b>Price:</b> ${format_usdt_price(current_price)} USDT\n"
            f"{change_emoji} <b>24h Change:</b> {change_sign}{change_percent:.2f}% "
            f"({change_sign}${format_usdt_price(price_change_usdt)})\n\n"

            f"🏦 <b>Market Cap:</b> ${market_cap_nonkyc:,}\n\n"

            f"📊 <b>Momentum (Price Change):</b>\n"
            f"🕐 <b>15m:</b> {format_momentum(momentum_periods['15m'])}\n"
            f"🕐 <b>1h:</b> {format_momentum(momentum_periods['1h'])}\n"
            f"🕐 <b>4h:</b> {format_momentum(momentum_periods['4h'])}\n"
            f"🕐 <b>24h:</b> {format_momentum(momentum_periods['24h'])}\n\n"

            f"📈 <b>Volume (24h periods):</b>\n"
            f"🕐 <b>15m:</b> {volume_periods['15m']:.2f} JKC\n"
            f"🕐 <b>1h:</b> {volume_periods['1h']:.2f} JKC\n"
            f"🕐 <b>4h:</b> {volume_periods['4h']:.2f} JKC\n"
            f"🕐 <b>24h:</b> {volume_periods['24h']:.2f} JKC\n\n"

            f"📡 <b>Data Source:</b> {data_source}\n\n"

            f"🔗 <b>Trade JKC:</b>\n"
            f"• <a href='https://nonkyc.io/market/JKC_USDT'>JKC/USDT on NonKYC</a>\n"
            f"• <a href='https://nonkyc.io/market/JKC_BTC'>JKC/BTC on NonKYC</a>"
        )

        await update.message.reply_text(message, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error processing price data: {e}")
        await update.message.reply_text("Error processing market data. Please try again later.")

async def chart_command(update: Update, context: CallbackContext) -> None:
    """Generate and send JKC price chart."""
    user_id = update.effective_user.id
    logger.info(f"Chart command called by user {user_id}")

    # Create inline keyboard with chart options
    keyboard = [
        [
            InlineKeyboardButton("📊 JKC/USDT Chart", url="https://nonkyc.io/market/JKC_USDT"),
            InlineKeyboardButton("📊 JKC/BTC Chart", url="https://nonkyc.io/market/JKC_BTC")
        ],
        [
            InlineKeyboardButton("🔄 Refresh Price", callback_data="cmd_price")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    chart_message = (
        "📊 <b>JKC Price Charts</b>\n\n"
        "Click the buttons below to view live JKC price charts:\n\n"
        "📈 <b>JKC/USDT:</b> Trade against USDT\n"
        "📈 <b>JKC/BTC:</b> Trade against Bitcoin\n\n"
        "Charts show real-time price data, volume, and trading history."
    )

    await update.message.reply_text(
        chart_message,
        parse_mode="HTML",
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

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

async def toggle_aggregation(update: Update, context: CallbackContext) -> None:
    """Toggle trade aggregation on/off - admin only command."""
    user_id = update.effective_user.id
    logger.info(f"Toggle aggregation command called by user {user_id}")

    if not await is_admin(update, context):
        await update.message.reply_text("You do not have permission to use this command.")
        return

    config = get_config()
    current_state = config.get("trade_aggregation", {}).get("enabled", True)
    new_state = not current_state

    # Update configuration
    trade_aggregation = config.get("trade_aggregation", {})
    trade_aggregation["enabled"] = new_state
    
    if update_config({"trade_aggregation": trade_aggregation}):
        status = "enabled" if new_state else "disabled"
        await update.message.reply_text(f"Trade aggregation has been {status}.")
        logger.info(f"Trade aggregation {status} by user {user_id}")
    else:
        await update.message.reply_text("Failed to update configuration.")

async def debug_command(update: Update, context: CallbackContext) -> None:
    """Show debug information - admin only command."""
    user_id = update.effective_user.id
    logger.info(f"Debug command called by user {user_id}")

    if not await is_admin(update, context):
        await update.message.reply_text("You do not have permission to use this command.")
        return

    config = get_config()
    
    debug_info = (
        f"🔧 <b>Debug Information</b>\n\n"
        f"👤 <b>Bot Owner:</b> {config.get('bot_owner', 'Not set')}\n"
        f"💰 <b>Value Threshold:</b> {config.get('value_require', 0)} USDT\n"
        f"📱 <b>Active Chats:</b> {len(config.get('active_chat_ids', []))}\n"
        f"🔄 <b>Trade Aggregation:</b> {'Enabled' if config.get('trade_aggregation', {}).get('enabled', True) else 'Disabled'}\n"
        f"⏱️ <b>Aggregation Window:</b> {config.get('trade_aggregation', {}).get('window_seconds', 8)}s\n"
        f"📈 <b>Dynamic Threshold:</b> {'Enabled' if config.get('dynamic_threshold', {}).get('enabled', False) else 'Disabled'}\n"
        f"🖼️ <b>Image Collection:</b> {len(get_image_collection())} images\n"
        f"⏰ <b>Current Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    await update.message.reply_text(debug_info, parse_mode="HTML")

async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel current conversation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

# Configuration Management Handlers

async def set_minimum_command(update: Update, context: CallbackContext) -> int:
    """Set minimum alert threshold - admin only command."""
    user_id = update.effective_user.id
    logger.info(f"Set minimum command called by user {user_id}")

    if not await can_use_admin_commands(update, context):
        await update.message.reply_text("You do not have permission to use this command.")
        return ConversationHandler.END

    logger.info(f"User {user_id} has admin permissions, proceeding with setmin command")
    await update.message.reply_text(
        "Please enter the new minimum value threshold in USDT.\n"
        "Current threshold: {} USDT".format(get_config().get('value_require', 300))
    )
    return INPUT_NUMBER

async def set_minimum_input(update: Update, context: CallbackContext) -> int:
    """Process minimum threshold input."""
    try:
        new_threshold = float(update.message.text)
        if new_threshold <= 0:
            await update.message.reply_text("Please enter a positive number.")
            return INPUT_NUMBER

        if update_config({"value_require": new_threshold}):
            await update.message.reply_text(f"Minimum threshold updated to {new_threshold} USDT.")
            logger.info(f"Threshold updated to {new_threshold} by user {update.effective_user.id}")
        else:
            await update.message.reply_text("Failed to update configuration.")

    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return INPUT_NUMBER

    return ConversationHandler.END

async def config_command(update: Update, context: CallbackContext) -> int:
    """Open configuration menu - admin only command."""
    user_id = update.effective_user.id
    logger.info(f"Config command called by user {user_id}")

    if not await can_use_admin_commands(update, context):
        await update.message.reply_text("You do not have permission to use this command.")
        return ConversationHandler.END

    config = get_config()

    # Create configuration menu
    keyboard = [
        [InlineKeyboardButton("💰 Set Threshold", callback_data="set_threshold")],
        [InlineKeyboardButton("🖼️ Manage Images", callback_data="manage_images")],
        [InlineKeyboardButton("📊 Dynamic Threshold", callback_data="dynamic_threshold")],
        [InlineKeyboardButton("🔄 Trade Aggregation", callback_data="trade_aggregation")],
        [InlineKeyboardButton("🔑 API Keys", callback_data="api_keys")],
        [InlineKeyboardButton("❌ Close", callback_data="close_config")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    config_text = (
        f"⚙️ <b>Bot Configuration</b>\n\n"
        f"💰 <b>Alert Threshold:</b> {config.get('value_require', 300)} USDT\n"
        f"🔄 <b>Trade Aggregation:</b> {'Enabled' if config.get('trade_aggregation', {}).get('enabled', True) else 'Disabled'}\n"
        f"📈 <b>Dynamic Threshold:</b> {'Enabled' if config.get('dynamic_threshold', {}).get('enabled', False) else 'Disabled'}\n"
        f"🖼️ <b>Images:</b> {len(get_image_collection())} in collection\n\n"
        f"Select an option to configure:"
    )

    await update.message.reply_text(config_text, parse_mode="HTML", reply_markup=reply_markup)
    return CONFIG_MENU

# Image Management Handlers

async def set_image_command(update: Update, context: CallbackContext) -> int:
    """Set alert image - admin only command."""
    user_id = update.effective_user.id
    logger.info(f"Set image command called by user {user_id}")

    if not await can_use_admin_commands(update, context):
        await update.message.reply_text("You do not have permission to use this command.")
        return ConversationHandler.END

    logger.info(f"User {user_id} has admin permissions, proceeding with setimage command")
    await update.message.reply_text(
        "Please send the image you want to use for alerts.\n"
        "The image should be clear and appropriate."
    )
    return INPUT_IMAGE_SETIMAGE

async def set_image_input(update: Update, context: CallbackContext) -> int:
    """Process image upload."""
    global PHOTO

    try:
        logger.info(f"Processing image upload from user {update.effective_user.id}")

        # Handle different types of media with enhanced detection
        file = None
        file_extension = ".jpg"  # Default
        media_type = "unknown"

        if update.message.photo:
            # Photo message
            file = await update.message.photo[-1].get_file()
            file_extension = ".jpg"
            media_type = "photo"
            logger.info("Detected photo upload")

        elif update.message.document:
            # Document message (could be image, GIF, etc.)
            document = update.message.document
            file = await document.get_file()

            # Get file extension from document
            if document.file_name:
                file_extension = os.path.splitext(document.file_name)[1].lower()
                if not file_extension:
                    file_extension = ".jpg"

            media_type = "document"
            logger.info(f"Detected document upload: {document.file_name}")

        elif update.message.animation:
            # Animation (GIF converted to MP4 by Telegram)
            animation = update.message.animation
            file = await animation.get_file()
            file_extension = ".mp4"  # Telegram converts GIFs to MP4
            media_type = "animation"
            logger.info("Detected animation upload (GIF→MP4)")

        if not file:
            await update.message.reply_text("❌ No valid image file detected. Please send a photo, GIF, or image document.")
            return INPUT_IMAGE_SETIMAGE

        # Download the image
        image_data = await file.download_as_bytearray()
        logger.info(f"Downloaded image data: {len(image_data)} bytes")

        # Generate unique filename with timestamp
        filename = generate_unique_filename("alert_image", file_extension)

        # Save to collection
        try:
            image_path = save_image_to_collection(image_data, filename)
            logger.info(f"Successfully saved image to: {image_path}")
        except Exception as e:
            logger.error(f"Error saving image to collection: {e}")
            await update.message.reply_text(f"❌ Error saving image to collection: {e}")
            return ConversationHandler.END

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

        success_message = (
            f"✅ <b>Image Successfully Added to Collection!</b>\n\n"
            f"📁 <b>File Type:</b> {type_info}\n"
            f"💾 <b>Size:</b> {len(image_data):,} bytes ({len(image_data)/1024/1024:.2f} MB)\n"
            f"📂 <b>Saved As:</b> {filename}\n"
            f"🖼️ <b>Collection Total:</b> {collection_count} images\n\n"
            f"The bot will now randomly select from all images in the collection for alerts."
        )

        await update.message.reply_text(success_message, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error processing image upload: {e}")
        await update.message.reply_text(f"❌ Error processing image: {e}")

    return ConversationHandler.END

async def list_images_command(update: Update, context: CallbackContext) -> None:
    """List all images in the collection with management options."""
    user_id = update.effective_user.id
    logger.info(f"List images command called by user {user_id}")

    if not await is_admin(update, context):
        await update.message.reply_text("You do not have permission to use this command.")
        return

    images = get_image_collection()

    if not images:
        await update.message.reply_text(
            "📁 <b>Image Collection is Empty</b>\n\n"
            "Use /setimage to add images to the collection.",
            parse_mode="HTML"
        )
        return

    # Get collection statistics
    stats = get_image_stats()

    # Create management buttons
    keyboard = [
        [InlineKeyboardButton("📊 Collection Stats", callback_data="image_stats")],
        [InlineKeyboardButton("🔄 Refresh List", callback_data="refresh_image_list")],
        [InlineKeyboardButton("🗑️ Clear All", callback_data="clear_all_images")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    collection_message = (
        f"🖼️ <b>Image Collection ({stats['count']} images)</b>\n\n"
        f"💾 <b>Total Size:</b> {stats['total_size_mb']:.2f} MB\n"
        f"🎬 <b>Animations:</b> {stats['animations']}\n\n"
        f"📋 <b>File Types:</b>\n"
    )

    for file_type, count in stats['type_counts'].items():
        collection_message += f"• {file_type.upper()}: {count}\n"

    collection_message += "\nUse the buttons below to manage your collection:"

    await update.message.reply_text(
        collection_message,
        parse_mode="HTML",
        reply_markup=reply_markup
    )

async def clear_images_command(update: Update, context: CallbackContext) -> None:
    """Clear all images from collection - admin only command."""
    user_id = update.effective_user.id
    logger.info(f"Clear images command called by user {user_id}")

    if not await is_admin(update, context):
        await update.message.reply_text("You do not have permission to use this command.")
        return

    # Create confirmation keyboard
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Clear All", callback_data="confirm_clear_images")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_clear_images")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    images_count = len(get_image_collection())

    await update.message.reply_text(
        f"⚠️ <b>Clear Image Collection</b>\n\n"
        f"This will permanently delete all {images_count} images from the collection.\n\n"
        f"Are you sure you want to continue?",
        parse_mode="HTML",
        reply_markup=reply_markup
    )

async def test_command(update: Update, context: CallbackContext) -> None:
    """Test command to show current data format and simulate alert."""
    if not await is_admin(update, context):
        await update.message.reply_text("You do not have permission to use this command.")
        return

    await update.message.reply_text("🧪 <b>Testing Data Sources...</b>", parse_mode="HTML")

    # Test NonKYC API
    try:
        nonkyc_data = await get_nonkyc_ticker()
        if nonkyc_data:
            await update.message.reply_text(
                f"✅ <b>NonKYC API:</b> Working\n"
                f"Price: ${float(nonkyc_data.get('lastPriceNumber', 0)):.6f} USDT",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("❌ <b>NonKYC API:</b> Failed", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ <b>NonKYC API Error:</b> {e}", parse_mode="HTML")

    # Test LiveCoinWatch API
    try:
        lcw_data = await get_livecoinwatch_data()
        if lcw_data:
            await update.message.reply_text(
                f"✅ <b>LiveCoinWatch API:</b> Working\n"
                f"Price: ${float(lcw_data.get('rate', 0)):.6f} USD",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("❌ <b>LiveCoinWatch API:</b> Failed", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ <b>LiveCoinWatch API Error:</b> {e}", parse_mode="HTML")

    # Test alert system
    try:
        await send_alert(
            price=0.166434,
            quantity=1000.0000,
            sum_value=166.43,
            exchange="Test Exchange",
            timestamp=int(time.time() * 1000),
            exchange_url="https://example.com",
            num_trades=1
        )
        await update.message.reply_text("✅ <b>Alert System:</b> Test alert sent", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ <b>Alert System Error:</b> {e}", parse_mode="HTML")

# Callback Query Handlers

async def button_callback(update: Update, context: CallbackContext) -> Optional[int]:
    """Handle button callbacks from inline keyboards."""
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

            # Extract price data based on source
            if data_source == "NonKYC Exchange":
                current_price = float(market_data.get("lastPriceNumber", 0))
                change_percent = float(market_data.get("changeNumber", 0))
                market_cap_nonkyc = float(market_data.get("marketcapNumber", 0))
            else:  # LiveCoinWatch
                current_price = float(market_data.get("rate", 0))
                change_percent = float(market_data.get("delta", {}).get("day", 0))
                market_cap_nonkyc = float(market_data.get("cap", 0))

            # Calculate additional metrics
            yesterday_price = current_price / (1 + change_percent / 100) if change_percent != 0 else current_price
            price_change_usdt = current_price - yesterday_price if yesterday_price > 0 else 0

            # Format change with crypto-appropriate emojis
            change_emoji = get_change_emoji(change_percent)
            change_sign = "+" if change_percent >= 0 else ""

            # Get volume data for momentum calculation
            try:
                volume_data = await calculate_combined_volume_periods()
                volume_periods = volume_data["combined"]

                # Calculate momentum (price change) for different periods
                momentum_periods = {
                    "15m": change_percent * 0.1,  # Approximate momentum
                    "1h": change_percent * 0.3,
                    "4h": change_percent * 0.7,
                    "24h": change_percent
                }
            except Exception as e:
                logger.error(f"Error calculating momentum: {e}")
                volume_periods = {"15m": 0, "1h": 0, "4h": 0, "24h": 0}
                momentum_periods = {"15m": 0, "1h": 0, "4h": 0, "24h": change_percent}

            # Format the message with rich data including momentum and volume periods
            message = (
                f"🪙 <b>JunkCoin (JKC) Market Data</b> 🪙\n\n"
                f"💰 <b>Price:</b> ${format_usdt_price(current_price)} USDT\n"
                f"{change_emoji} <b>24h Change:</b> {change_sign}{change_percent:.2f}% "
                f"({change_sign}${format_usdt_price(price_change_usdt)})\n\n"

                f"🏦 <b>Market Cap:</b> ${market_cap_nonkyc:,}\n\n"

                f"📊 <b>Momentum (Price Change):</b>\n"
                f"🕐 <b>15m:</b> {format_momentum(momentum_periods['15m'])}\n"
                f"🕐 <b>1h:</b> {format_momentum(momentum_periods['1h'])}\n"
                f"🕐 <b>4h:</b> {format_momentum(momentum_periods['4h'])}\n"
                f"🕐 <b>24h:</b> {format_momentum(momentum_periods['24h'])}\n\n"

                f"📈 <b>Volume (24h periods):</b>\n"
                f"🕐 <b>15m:</b> {volume_periods['15m']:.2f} JKC\n"
                f"🕐 <b>1h:</b> {volume_periods['1h']:.2f} JKC\n"
                f"🕐 <b>4h:</b> {volume_periods['4h']:.2f} JKC\n"
                f"🕐 <b>24h:</b> {volume_periods['24h']:.2f} JKC\n\n"

                f"📡 <b>Data Source:</b> {data_source}\n\n"

                f"🔗 <b>Trade JKC:</b>\n"
                f"• <a href='https://nonkyc.io/market/JKC_USDT'>JKC/USDT on NonKYC</a>\n"
                f"• <a href='https://nonkyc.io/market/JKC_BTC'>JKC/BTC on NonKYC</a>"
            )

            await query.edit_message_text(message, parse_mode="HTML", disable_web_page_preview=True)

        except Exception as e:
            logger.error(f"Error in price callback: {e}")
            await query.edit_message_text("Error processing market data. Please try again later.")

    elif query.data == "close_config":
        await query.edit_message_text("⚙️ Configuration menu closed.")
        return ConversationHandler.END

    elif query.data == "confirm_clear_images":
        try:
            deleted_count = clear_image_collection()
            await query.edit_message_text(
                f"✅ <b>Collection Cleared</b>\n\n"
                f"Successfully deleted {deleted_count} images from the collection.",
                parse_mode="HTML"
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Error clearing collection: {e}")

    elif query.data == "cancel_clear_images":
        await query.edit_message_text("❌ Clear operation cancelled.")

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
            stats = get_image_stats()

            stats_message = (
                f"📊 <b>Collection Statistics</b>\n\n"
                f"📁 <b>Total Images:</b> {stats['count']}\n"
                f"💾 <b>Total Size:</b> {stats['total_size_mb']:.2f} MB ({stats['total_size']:,} bytes)\n"
                f"🎬 <b>Animations:</b> {stats['animations']}\n\n"
                f"📋 <b>File Type Breakdown:</b>\n"
            )

            for file_type, count in stats['type_counts'].items():
                percentage = (count / stats['count']) * 100
                stats_message += f"• {file_type.upper()}: {count} ({percentage:.1f}%)\n"

            await query.edit_message_text(stats_message, parse_mode="HTML")

    return None
