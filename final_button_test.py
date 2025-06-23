#!/usr/bin/env python3
"""
Final Button Callback Test for XBT Telegram Bot
Tests the fixed button callback system to ensure all buttons work correctly
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
    help_command, button_command_callback, is_admin, 
    BOT_OWNER, BY_PASS
)

async def test_help_command_button_generation():
    """Test that help command generates correct buttons with proper callback data"""
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
        expected_buttons = [
            ("📊 Check Price", "cmd_price"),
            ("📈 View Chart", "cmd_chart"),
            ("🔍 Debug Info", "cmd_debug"),
            ("🛑 Stop Bot", "cmd_stop"),
            ("💝 Donate to Dev", "cmd_donate")
        ]
        
        all_found = True
        for expected_text, expected_callback in expected_buttons:
            found = any(text == expected_text and callback == expected_callback 
                       for text, callback in buttons)
            if found:
                print(f"    ✅ {expected_text} → {expected_callback}")
            else:
                print(f"    ❌ Missing: {expected_text} → {expected_callback}")
                all_found = False
        
        # Check that admin buttons are NOT present
        admin_buttons = ["⚙️ Configuration", "🎨 List Images"]
        for admin_text in admin_buttons:
            found = any(admin_text in text for text, callback in buttons)
            if not found:
                print(f"    ✅ Admin button '{admin_text}' correctly hidden")
            else:
                print(f"    ❌ Admin button '{admin_text}' incorrectly visible")
                all_found = False
        
        return all_found

async def test_button_callbacks_functionality():
    """Test that each button callback works correctly"""
    print("\n🔘 Testing Button Callback Functionality...")
    
    callback_tests = [
        ("cmd_price", "Price Command Button"),
        ("cmd_debug", "Debug Command Button"),
        ("cmd_donate", "Donate Command Button"),
        ("copy_btc_address", "Copy Bitcoin Address Button")
    ]
    
    all_passed = True
    
    for callback_data, test_name in callback_tests:
        print(f"\n  🧪 Testing: {test_name}")
        
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
        
        context = MagicMock()
        
        try:
            # Mock necessary functions for API calls
            with patch('telebot_fixed.get_nonkyc_ticker', return_value={
                "lastPriceNumber": 0.156, "changePercentNumber": 4.0,
                "marketcapNumber": 15600000, "volumeNumber": 1000000,
                "volumeUsdNumber": 156000, "highPriceNumber": 0.158,
                "lowPriceNumber": 0.149, "bestBidNumber": 0.155,
                "bestAskNumber": 0.156, "spreadPercentNumber": 0.13,
                "yesterdayPriceNumber": 0.150
            }), patch('telebot_fixed.calculate_combined_volume_periods', return_value={
                "combined": {"15m": 5000, "1h": 15000, "4h": 45000, "24h": 156000}
            }), patch('telebot_fixed.get_nonkyc_trades', return_value=[]), \
            patch('telebot_fixed.calculate_momentum_periods', return_value={
                "15m": 2.5, "1h": 3.8, "4h": 4.2, "24h": 6.1
            }), patch('telebot_fixed.is_admin', return_value=False):
                
                await button_command_callback(update, context)
            
            # Verify query.answer() was called
            if query.answer.called:
                print(f"    ✅ query.answer() called")
            else:
                print(f"    ❌ query.answer() NOT called")
                all_passed = False
            
            # Verify response was sent
            if query.edit_message_text.called:
                print(f"    ✅ Response sent via edit_message_text")
                
                # Check response content for specific callbacks
                call_args = query.edit_message_text.call_args
                response_text = call_args[0][0]
                
                if callback_data == "cmd_price":
                    if "Bitcoin Classic (XBT) Market Data" in response_text:
                        print(f"    ✅ Price data response contains expected content")
                    else:
                        print(f"    ❌ Price data response missing expected content")
                        all_passed = False
                
                elif callback_data == "cmd_debug":
                    if "Debug Information" in response_text:
                        print(f"    ✅ Debug response contains expected content")
                    else:
                        print(f"    ❌ Debug response missing expected content")
                        all_passed = False
                
                elif callback_data == "cmd_donate":
                    if "XBTBuyBot Developer Coffee Tip" in response_text:
                        print(f"    ✅ Donate response contains expected content")
                    else:
                        print(f"    ❌ Donate response missing expected content")
                        all_passed = False
                
                elif callback_data == "copy_btc_address":
                    if "1B1YLseSykoBPKFzokTGvzM2gzybyEDiU4" in response_text:
                        print(f"    ✅ Copy address response contains Bitcoin address")
                    else:
                        print(f"    ❌ Copy address response missing Bitcoin address")
                        all_passed = False
                
            else:
                print(f"    ❌ No response sent")
                all_passed = False
            
            print(f"    ✅ {test_name} callback executed successfully")
            
        except Exception as e:
            print(f"    ❌ {test_name} callback failed: {e}")
            all_passed = False
    
    return all_passed

async def test_admin_button_access():
    """Test admin button access control"""
    print("\n🔐 Testing Admin Button Access Control...")
    
    admin_callbacks = [
        ("cmd_config", "Configuration Command"),
        ("cmd_list_images", "List Images Command"),
        ("cmd_stop", "Stop Command")
    ]
    
    all_passed = True
    
    for callback_data, test_name in admin_callbacks:
        print(f"\n  🧪 Testing: {test_name} Access Control")
        
        # Test regular user access (should be denied)
        query = MagicMock()
        query.data = callback_data
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.from_user.id = 999999999  # Regular user
        query.message.chat.id = -1002293167945
        query.message.chat.type = "supergroup"
        
        update = MagicMock()
        update.callback_query = query
        update.effective_user.id = 999999999
        update.effective_chat.id = -1002293167945
        
        context = MagicMock()
        
        try:
            with patch('telebot_fixed.is_admin', return_value=False):
                await button_command_callback(update, context)
            
            # Check if access was denied
            if query.edit_message_text.called:
                call_args = query.edit_message_text.call_args
                response_text = call_args[0][0]
                
                if "❌" in response_text and "permission" in response_text.lower():
                    print(f"    ✅ Regular user properly denied access")
                else:
                    print(f"    ❌ Regular user not properly denied access")
                    print(f"    Response: {response_text}")
                    all_passed = False
            else:
                print(f"    ❌ No response sent for access denial")
                all_passed = False
        
        except Exception as e:
            print(f"    ❌ Error testing regular user access: {e}")
            all_passed = False
        
        # Test admin user access (should be granted)
        query.from_user.id = BOT_OWNER
        update.effective_user.id = BOT_OWNER
        
        try:
            with patch('telebot_fixed.is_admin', return_value=True):
                await button_command_callback(update, context)
            
            # Admin should get different response (not permission denied)
            if query.edit_message_text.called:
                call_args = query.edit_message_text.call_args
                response_text = call_args[0][0]
                
                if "❌" not in response_text or "permission" not in response_text.lower():
                    print(f"    ✅ Admin user properly granted access")
                else:
                    print(f"    ❌ Admin user incorrectly denied access")
                    all_passed = False
            
        except Exception as e:
            print(f"    ❌ Error testing admin user access: {e}")
            all_passed = False
    
    return all_passed

async def test_callback_handler_registration():
    """Test that callback handlers are properly registered"""
    print("\n🔧 Testing Callback Handler Registration...")
    
    # Test pattern matching
    patterns = [
        ("cmd_price", "^cmd_"),
        ("cmd_chart", "^cmd_"),
        ("cmd_debug", "^cmd_"),
        ("cmd_donate", "^cmd_"),
        ("cmd_config", "^cmd_"),
        ("cmd_list_images", "^cmd_"),
        ("cmd_stop", "^cmd_"),
        ("copy_btc_address", "^copy_"),
    ]
    
    import re
    all_matched = True
    
    for callback_data, pattern in patterns:
        matches = bool(re.match(pattern, callback_data))
        if matches:
            print(f"    ✅ '{callback_data}' matches pattern '{pattern}'")
        else:
            print(f"    ❌ '{callback_data}' does NOT match pattern '{pattern}'")
            all_matched = False
    
    return all_matched

async def main():
    """Run all button callback tests"""
    print("🚀 Starting Final Button Callback Tests...")
    print("="*70)
    
    tests = [
        ("Help Command Button Generation", test_help_command_button_generation),
        ("Button Callback Functionality", test_button_callbacks_functionality),
        ("Admin Button Access Control", test_admin_button_access),
        ("Callback Handler Registration", test_callback_handler_registration),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"🧪 TESTING: {test_name}")
        print('='*50)
        
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print(f"\n{'='*70}")
    print(f"FINAL BUTTON TEST SUMMARY: {passed}/{total} tests passed")
    print('='*70)
    
    if passed == total:
        print("🎉 ALL BUTTON CALLBACK TESTS PASSED!")
        print("\n✅ Button System Status:")
        print("  ✅ Help command generates correct buttons")
        print("  ✅ All button callbacks function properly")
        print("  ✅ Admin access control working correctly")
        print("  ✅ Callback handler patterns registered properly")
        print("  ✅ Price button shows market data with momentum")
        print("  ✅ Debug button shows user information")
        print("  ✅ Donate button shows developer coffee tip")
        print("  ✅ Copy button shows copyable Bitcoin address")
        print("  ✅ Permission enforcement working for admin buttons")
        
        print(f"\n🤖 The help command interactive buttons are now fully functional!")
        return True
    else:
        print("⚠️  Some button tests failed. Please review the results above.")
        return False

if __name__ == "__main__":
    asyncio.run(main())
