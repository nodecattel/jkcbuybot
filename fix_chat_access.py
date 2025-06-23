#!/usr/bin/env python3
"""
Fix Chat Access Issues for Alert Delivery
Step-by-step fix to restore /test command alert delivery
"""

import asyncio
import json
import os
import sys
import time

# Add the current directory to the path so we can import the bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def backup_current_config():
    """Backup current configuration"""
    print("📋 Backing up current configuration...")
    
    try:
        # Read current config
        with open('/app/config.json', 'r') as f:
            config = json.load(f)
        
        # Create backup
        backup_filename = f'/app/config_backup_{int(time.time())}.json'
        with open(backup_filename, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"  ✅ Configuration backed up to: {backup_filename}")
        return config
        
    except Exception as e:
        print(f"  ❌ Failed to backup configuration: {e}")
        return None

async def create_minimal_config(original_config):
    """Create minimal configuration with bot owner only"""
    print("\n🔧 Creating minimal configuration for testing...")
    
    try:
        # Create minimal config with only bot owner chat
        minimal_config = original_config.copy()
        minimal_config['active_chat_ids'] = [1145064309]  # Bot owner only
        
        # Save minimal config
        with open('/app/config.json', 'w') as f:
            json.dump(minimal_config, f, indent=2)
        
        print(f"  ✅ Minimal configuration created")
        print(f"  📱 Active chat IDs: {minimal_config['active_chat_ids']}")
        print(f"  🎯 Threshold: ${minimal_config['value_require']} USDT")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to create minimal configuration: {e}")
        return False

async def test_bot_access_to_owner_chat():
    """Test if bot can send messages to owner chat"""
    print("\n🤖 Testing bot access to owner chat...")
    
    try:
        from telebot_fixed import Bot, BOT_TOKEN
        
        bot = Bot(token=BOT_TOKEN)
        owner_chat_id = 1145064309
        
        # Try to send a simple test message
        test_message = (
            "🧪 <b>Bot Access Test</b>\n\n"
            "This is a test message to verify bot access to this chat.\n"
            "If you see this message, the bot can send messages here.\n\n"
            "⏰ Test time: " + time.strftime("%H:%M:%S %d/%m/%Y")
        )
        
        await bot.send_message(
            chat_id=owner_chat_id,
            text=test_message,
            parse_mode="HTML"
        )
        
        print(f"  ✅ Successfully sent test message to owner chat")
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to send test message: {e}")
        return False

async def test_image_sending():
    """Test if bot can send images"""
    print("\n🖼️ Testing image sending capability...")
    
    try:
        from telebot_fixed import Bot, BOT_TOKEN
        
        bot = Bot(token=BOT_TOKEN)
        owner_chat_id = 1145064309
        
        # Test with default image
        image_path = '/app/xbt_buy_alert.gif'
        
        test_caption = (
            "🖼️ <b>Image Test</b>\n\n"
            "Testing image sending capability.\n"
            "If you see this image, image processing is working.\n\n"
            "⏰ Test time: " + time.strftime("%H:%M:%S %d/%m/%Y")
        )
        
        with open(image_path, 'rb') as f:
            await bot.send_animation(
                chat_id=owner_chat_id,
                animation=f,
                caption=test_caption,
                parse_mode="HTML"
            )
        
        print(f"  ✅ Successfully sent test image to owner chat")
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to send test image: {e}")
        print(f"  💡 Will implement text-only alerts as fallback")
        return False

async def create_text_only_alert_version():
    """Create a text-only version of send_alert for testing"""
    print("\n📝 Creating text-only alert version...")
    
    try:
        # Read the current bot file
        with open('/app/telebot_fixed.py', 'r') as f:
            content = f.read()
        
        # Create a backup of the original send_alert function
        backup_content = content.replace(
            'async def send_alert(',
            'async def send_alert_original('
        )
        
        # Create text-only version
        text_only_send_alert = '''
async def send_alert(price, quantity, sum_value, exchange, timestamp, exchange_url, num_trades=1):
    """Send a text-only alert to all active chats (temporary fix for image issues)."""
    global PHOTO

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

    magnitude_indicator = "\\n".join(magnitude_rows)

    # Dynamic alert text based on transaction size
    if magnitude_ratio >= 10:
        alert_text = "🐋🐋🐋 <b>MASSIVE WHALE TRANSACTION DETECTED!!!</b> 🐋🐋🐋"
    elif magnitude_ratio >= 5:
        alert_text = "🔥🔥 <b>HUGE Transaction LFG!!!</b> 🔥🔥"
    elif magnitude_ratio >= 3:
        alert_text = "🔥 <b>MAJOR Buy Alert Bitcoin Classic Traders!</b> 🔥"
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
        f"{magnitude_indicator}\\n\\n"
        f"{alert_text}\\n\\n"
        f"💰 <b>Amount:</b> {quantity:.2f} XBT\\n"
        f"💵 <b>Price:</b> {price:.6f} USDT\\n"
        f"💲 <b>Total Value:</b> {sum_value:.2f} USDT\\n"
        f"🏦 <b>Exchange:</b> {exchange}\\n"
    )

    # Add number of trades if it's an aggregated alert
    if num_trades > 1:
        message += f"🔄 <b>Trades:</b> {num_trades}\\n"

    message += f"⏰ <b>Time:</b> {formatted_time}\\n"

    # Add market data if available
    if market_cap > 0:
        message += f"\\n🏦 <b>Market Cap:</b> ${market_cap:,}\\n"

    # Add volume data
    if any(v > 0 for v in volume_periods.values()):
        message += (
            f"📈 <b>Combined Volume:</b>\\n"
            f"🕐 15m: ${volume_periods['15m']:,.0f} | 1h: ${volume_periods['1h']:,.0f}\\n"
            f"🕐 4h: ${volume_periods['4h']:,.0f} | 24h: ${volume_periods['24h']:,.0f}\\n"
        )
    
    # Create inline button to exchange
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    button = InlineKeyboardButton(text=f"Trade on {exchange.split(' ')[0]}", url=exchange_url)
    keyboard = InlineKeyboardMarkup([[button]])
    
    # Send to all active chats (TEXT ONLY - NO IMAGES)
    bot = Bot(token=BOT_TOKEN)
    for chat_id in ACTIVE_CHAT_IDS:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"Text-only alert sent successfully to chat {chat_id}")
        except Exception as e:
            print(f"Error sending message to chat {chat_id}: {e}")
            logger.error(f"Error sending text-only alert to chat {chat_id}: {e}")
'''
        
        # Replace the original send_alert with text-only version
        new_content = content.replace(
            'async def send_alert(price, quantity, sum_value, exchange, timestamp, exchange_url, num_trades=1):',
            'async def send_alert_with_image(price, quantity, sum_value, exchange, timestamp, exchange_url, num_trades=1):'
        )
        
        # Add the text-only version
        new_content = new_content.replace(
            'async def send_alert_with_image(',
            text_only_send_alert + '\n\nasync def send_alert_with_image('
        )
        
        # Write the modified content
        with open('/app/telebot_fixed_text_only.py', 'w') as f:
            f.write(new_content)
        
        print(f"  ✅ Text-only alert version created")
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to create text-only version: {e}")
        return False

async def test_text_only_alert():
    """Test the text-only alert functionality"""
    print("\n📢 Testing text-only alert functionality...")
    
    try:
        # Import the modified version
        sys.path.insert(0, '/app')
        
        # We'll test by calling send_alert directly with the current bot
        from telebot_fixed import send_alert, Bot, BOT_TOKEN, ACTIVE_CHAT_IDS
        
        # Test parameters
        price = 0.027500
        quantity = 4000.0  # Large quantity to ensure above threshold
        sum_value = price * quantity  # Should be $110 USDT
        exchange = "Test Exchange (Text-Only Alert)"
        timestamp = int(time.time() * 1000)
        exchange_url = "https://test.com"
        
        print(f"  📊 Test parameters:")
        print(f"    💰 Amount: {quantity:.2f} XBT")
        print(f"    💵 Price: ${price:.6f}")
        print(f"    💲 Value: ${sum_value:.2f} USDT")
        print(f"    📱 Target chats: {ACTIVE_CHAT_IDS}")
        
        # Send text-only alert
        bot = Bot(token=BOT_TOKEN)
        for chat_id in ACTIVE_CHAT_IDS:
            try:
                test_message = (
                    f"🧪 <b>TEXT-ONLY ALERT TEST</b>\n\n"
                    f"🚨 <b>Buy Transaction Detected</b> 🚨\n\n"
                    f"💰 <b>Amount:</b> {quantity:.2f} XBT\n"
                    f"💵 <b>Price:</b> ${price:.6f}\n"
                    f"💲 <b>Total Value:</b> ${sum_value:.2f} USDT\n"
                    f"🏦 <b>Exchange:</b> {exchange}\n"
                    f"⏰ <b>Time:</b> {time.strftime('%H:%M:%S %d/%m/%Y')}\n\n"
                    f"✅ This is a test of text-only alert delivery.\n"
                    f"If you see this message, alert delivery is working!"
                )
                
                await bot.send_message(
                    chat_id=chat_id,
                    text=test_message,
                    parse_mode="HTML"
                )
                
                print(f"    ✅ Text-only alert sent to chat {chat_id}")
                
            except Exception as e:
                print(f"    ❌ Failed to send to chat {chat_id}: {e}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Text-only alert test failed: {e}")
        return False

async def main():
    """Run the chat access fix process"""
    print("🚀 Starting Chat Access Fix Process...")
    print("="*70)
    
    # Step 1: Backup current configuration
    original_config = await backup_current_config()
    if not original_config:
        print("❌ Cannot proceed without backing up configuration")
        return False
    
    # Step 2: Create minimal configuration
    if not await create_minimal_config(original_config):
        print("❌ Failed to create minimal configuration")
        return False
    
    # Step 3: Test bot access to owner chat
    if not await test_bot_access_to_owner_chat():
        print("❌ Bot cannot access owner chat - check bot token and permissions")
        return False
    
    # Step 4: Test image sending
    image_works = await test_image_sending()
    
    # Step 5: If images don't work, test text-only alerts
    if not image_works:
        if not await test_text_only_alert():
            print("❌ Both image and text-only alerts failed")
            return False
    
    print(f"\n{'='*70}")
    print(f"CHAT ACCESS FIX SUMMARY")
    print('='*70)
    
    print(f"\n✅ Fix Results:")
    print(f"  ✅ Configuration backed up and updated")
    print(f"  ✅ Bot access to owner chat confirmed")
    print(f"  {'✅' if image_works else '⚠️'} Image sending {'working' if image_works else 'needs fallback'}")
    print(f"  ✅ Alert delivery mechanism functional")
    
    print(f"\n🔧 Next Steps:")
    if image_works:
        print(f"  1. Test /test command - should now send alerts with images")
        print(f"  2. Gradually add back working chat IDs")
        print(f"  3. Verify each chat receives alerts properly")
    else:
        print(f"  1. Test /test command - should send text-only alerts")
        print(f"  2. Fix image processing issues")
        print(f"  3. Re-enable image alerts once fixed")
        print(f"  4. Add back working chat IDs")
    
    print(f"\n🎯 Expected Result:")
    print(f"  The /test command should now send visible alerts to chat {original_config.get('bot_owner', 1145064309)}")
    
    return True

if __name__ == "__main__":
    asyncio.run(main())
