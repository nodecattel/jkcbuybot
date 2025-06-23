#!/usr/bin/env python3
"""
Button Callback Diagnostic Tool for XBT Telegram Bot
Diagnoses and tests the button callback system in the help command
"""

import asyncio
import json
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

# Add the current directory to the path so we can import the bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the bot functions we need to test
from telebot_fixed import (
    help_command, button_command_callback, check_price, chart_command,
    debug_command, donate_command, config_command, list_images_command,
    stop_bot, is_admin, BOT_OWNER, BY_PASS
)

async def test_help_command_button_generation():
    """Test that help command generates correct buttons"""
    print("🔘 Testing Help Command Button Generation...")
    
    # Test for regular user
    update = MagicMock()
    update.effective_user.id = 999999999  # Regular user
    update.effective_chat.id = -1002293167945
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    
    with patch('telebot_fixed.is_admin', return_value=False):
        await help_command(update, context)
        
        # Get the keyboard from the call
        call_args = update.message.reply_text.call_args
        keyboard = call_args[1]['reply_markup']
        
        # Extract all buttons and their callback data
        buttons = []
        for row in keyboard.inline_keyboard:
            for button in row:
                buttons.append((button.text, button.callback_data))
        
        print("  📋 Regular User Buttons:")
        for text, callback_data in buttons:
            print(f"    - '{text}' → '{callback_data}'")
        
        # Verify expected buttons
        expected_buttons = [
            ("📊 Check Price", "cmd_price"),
            ("📈 View Chart", "cmd_chart"),
            ("🔍 Debug Info", "cmd_debug"),
            ("🛑 Stop Bot", "cmd_stop"),
            ("💝 Donate to Dev", "cmd_donate")
        ]
        
        for expected_text, expected_callback in expected_buttons:
            found = any(text == expected_text and callback == expected_callback 
                       for text, callback in buttons)
            if found:
                print(f"    ✅ Found: {expected_text} → {expected_callback}")
            else:
                print(f"    ❌ Missing: {expected_text} → {expected_callback}")
    
    # Test for admin user
    print("\n  📋 Admin User Buttons:")
    update.effective_user.id = BOT_OWNER
    with patch('telebot_fixed.is_admin', return_value=True):
        await help_command(update, context)
        
        # Get the keyboard from the call
        call_args = update.message.reply_text.call_args
        keyboard = call_args[1]['reply_markup']
        
        # Extract all buttons and their callback data
        admin_buttons = []
        for row in keyboard.inline_keyboard:
            for button in row:
                admin_buttons.append((button.text, button.callback_data))
        
        for text, callback_data in admin_buttons:
            print(f"    - '{text}' → '{callback_data}'")
        
        # Verify admin buttons are present
        admin_expected = [
            ("⚙️ Configuration", "cmd_config"),
            ("🎨 List Images", "cmd_list_images")
        ]
        
        for expected_text, expected_callback in admin_expected:
            found = any(text == expected_text and callback == expected_callback 
                       for text, callback in admin_buttons)
            if found:
                print(f"    ✅ Found: {expected_text} → {expected_callback}")
            else:
                print(f"    ❌ Missing: {expected_text} → {expected_callback}")

async def test_individual_button_callbacks():
    """Test each button callback individually"""
    print("\n🔘 Testing Individual Button Callbacks...")
    
    callback_tests = [
        ("cmd_price", "Price Command"),
        ("cmd_chart", "Chart Command"),
        ("cmd_debug", "Debug Command"),
        ("cmd_donate", "Donate Command"),
        ("cmd_stop", "Stop Command"),
        ("cmd_config", "Config Command"),
        ("cmd_list_images", "List Images Command"),
        ("copy_btc_address", "Copy Bitcoin Address")
    ]
    
    for callback_data, test_name in callback_tests:
        print(f"\n  🧪 Testing: {test_name} ({callback_data})")
        
        # Create mock objects
        query = MagicMock()
        query.data = callback_data
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.from_user.id = 999999999
        query.message.message_id = 123
        query.message.date = time.time()
        query.message.chat.id = -1002293167945
        query.message.chat.type = "supergroup"
        
        update = MagicMock()
        update.callback_query = query
        update.effective_user.id = 999999999
        update.effective_chat.id = -1002293167945
        update.update_id = 123
        
        context = MagicMock()
        
        try:
            # Mock necessary functions for different callback types
            if callback_data == "cmd_price":
                with patch('telebot_fixed.get_nonkyc_ticker', return_value={
                    "lastPriceNumber": 0.156, "changePercentNumber": 4.0,
                    "marketcapNumber": 15600000, "volumeNumber": 1000000,
                    "volumeUsdNumber": 156000, "highPriceNumber": 0.158,
                    "lowPriceNumber": 0.149, "bestBidNumber": 0.155,
                    "bestAskNumber": 0.156, "spreadPercentNumber": 0.13
                }), patch('telebot_fixed.calculate_combined_volume_periods', return_value={
                    "combined": {"15m": 5000, "1h": 15000, "4h": 45000, "24h": 156000}
                }), patch('telebot_fixed.get_nonkyc_trades', return_value=[]):
                    await button_command_callback(update, context)
            
            elif callback_data == "cmd_chart":
                with patch('telebot_fixed.get_nonkyc_trades', return_value=[
                    {"timestamp": "2025-06-23T05:00:00Z", "price": "0.156", "quantity": "100"}
                ]), patch('telebot_fixed.pd.DataFrame') as mock_df, \
                patch('telebot_fixed.plt') as mock_plt:
                    # Mock pandas DataFrame
                    mock_df.return_value.to_datetime = MagicMock()
                    mock_df.return_value.astype = MagicMock()
                    await button_command_callback(update, context)
            
            elif callback_data == "cmd_debug":
                with patch('telebot_fixed.is_admin', return_value=False):
                    await button_command_callback(update, context)
            
            elif callback_data == "cmd_donate":
                await button_command_callback(update, context)
            
            elif callback_data == "cmd_stop":
                with patch('telebot_fixed.is_admin', return_value=False):
                    await button_command_callback(update, context)
            
            elif callback_data == "cmd_config":
                with patch('telebot_fixed.is_admin', return_value=False):
                    await button_command_callback(update, context)
            
            elif callback_data == "cmd_list_images":
                with patch('telebot_fixed.is_admin', return_value=False):
                    await button_command_callback(update, context)
            
            elif callback_data == "copy_btc_address":
                await button_command_callback(update, context)
            
            # Verify query.answer() was called
            if query.answer.called:
                print(f"    ✅ query.answer() called")
            else:
                print(f"    ❌ query.answer() NOT called")
            
            # Check for any response
            if (query.edit_message_text.called or 
                hasattr(update, 'message') and hasattr(update.message, 'reply_text') and 
                update.message.reply_text.called):
                print(f"    ✅ Response sent")
            else:
                print(f"    ⚠️ No response detected")
            
            print(f"    ✅ {test_name} callback executed successfully")
            
        except Exception as e:
            print(f"    ❌ {test_name} callback failed: {e}")

async def test_callback_handler_patterns():
    """Test that callback handler patterns are working"""
    print("\n🔘 Testing Callback Handler Patterns...")
    
    # Test pattern matching
    patterns = [
        ("cmd_price", "^cmd_", True),
        ("cmd_chart", "^cmd_", True),
        ("cmd_debug", "^cmd_", True),
        ("cmd_donate", "^cmd_", True),
        ("copy_btc_address", "^copy_", True),
        ("invalid_pattern", "^cmd_", False),
        ("another_invalid", "^copy_", False)
    ]
    
    import re
    
    for callback_data, pattern, should_match in patterns:
        matches = bool(re.match(pattern, callback_data))
        if matches == should_match:
            print(f"    ✅ '{callback_data}' vs '{pattern}' → {matches} (expected {should_match})")
        else:
            print(f"    ❌ '{callback_data}' vs '{pattern}' → {matches} (expected {should_match})")

async def test_message_object_creation():
    """Test the message object creation in button_command_callback"""
    print("\n🔘 Testing Message Object Creation...")
    
    try:
        from telegram import Message, User, Chat
        
        # Test creating a message object like in button_command_callback
        user = User(id=999999999, is_bot=False, first_name="Test")
        chat = Chat(id=-1002293167945, type="supergroup")
        
        message = Message(
            message_id=123,
            date=time.time(),
            chat=chat,
            from_user=user,
            text="/button_command"
        )
        
        print(f"    ✅ Message object created successfully")
        print(f"    - Message ID: {message.message_id}")
        print(f"    - From User: {message.from_user.id}")
        print(f"    - Chat ID: {message.chat.id}")
        
    except Exception as e:
        print(f"    ❌ Message object creation failed: {e}")

async def main():
    """Run all diagnostic tests"""
    print("🚀 Starting Button Callback Diagnostic Tests...")
    print("="*70)
    
    tests = [
        ("Help Command Button Generation", test_help_command_button_generation),
        ("Individual Button Callbacks", test_individual_button_callbacks),
        ("Callback Handler Patterns", test_callback_handler_patterns),
        ("Message Object Creation", test_message_object_creation),
    ]
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"🧪 TESTING: {test_name}")
        print('='*50)
        
        try:
            await test_func()
            print(f"✅ {test_name} completed")
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
    
    print(f"\n{'='*70}")
    print("🎯 DIAGNOSTIC COMPLETE")
    print('='*70)
    
    print("\n📋 RECOMMENDATIONS:")
    print("1. Verify callback handlers are registered in main()")
    print("2. Check that button_command_callback function is accessible")
    print("3. Ensure all required command functions exist")
    print("4. Test with actual Telegram bot to verify real-world behavior")

if __name__ == "__main__":
    asyncio.run(main())
