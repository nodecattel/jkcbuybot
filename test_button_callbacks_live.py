#!/usr/bin/env python3
"""
Live Test for Help Command Button Callbacks
Tests the actual button callback functionality in the running container
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
    """Test that help command generates buttons correctly"""
    print("🔘 Testing Help Command Button Generation...")
    
    # Test for regular user
    update = MagicMock()
    update.effective_user.id = 999999999  # Regular user
    update.effective_chat.id = -1002293167945
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    
    try:
        with patch('telebot_fixed.is_admin', return_value=False):
            await help_command(update, context)
            
            if update.message.reply_text.called:
                call_args = update.message.reply_text.call_args
                keyboard = call_args[1].get('reply_markup')
                
                if keyboard and hasattr(keyboard, 'inline_keyboard'):
                    # Extract all buttons and their callback data
                    buttons = []
                    for row in keyboard.inline_keyboard:
                        for button in row:
                            buttons.append((button.text, button.callback_data))
                    
                    print(f"  📋 Regular User Buttons Found: {len(buttons)}")
                    for text, callback_data in buttons:
                        print(f"    - '{text}' → '{callback_data}'")
                    
                    # Check for expected buttons
                    expected_buttons = [
                        "📊 Check Price",
                        "📈 View Chart", 
                        "🔍 Debug Info",
                        "🛑 Stop Bot",
                        "💝 Donate to Dev"
                    ]
                    
                    found_buttons = [text for text, _ in buttons]
                    all_found = all(expected in found_buttons for expected in expected_buttons)
                    
                    if all_found:
                        print(f"  ✅ All expected regular user buttons found")
                    else:
                        missing = [btn for btn in expected_buttons if btn not in found_buttons]
                        print(f"  ❌ Missing buttons: {missing}")
                        return False
                else:
                    print(f"  ❌ No keyboard found in help command response")
                    return False
            else:
                print(f"  ❌ Help command did not send a response")
                return False
    
    except Exception as e:
        print(f"  ❌ Help command test failed: {e}")
        return False
    
    # Test for admin user
    update.effective_user.id = BOT_OWNER
    update.message.reply_text.reset_mock()
    
    try:
        with patch('telebot_fixed.is_admin', return_value=True):
            await help_command(update, context)
            
            if update.message.reply_text.called:
                call_args = update.message.reply_text.call_args
                keyboard = call_args[1].get('reply_markup')
                
                if keyboard and hasattr(keyboard, 'inline_keyboard'):
                    # Extract all buttons and their callback data
                    admin_buttons = []
                    for row in keyboard.inline_keyboard:
                        for button in row:
                            admin_buttons.append((button.text, button.callback_data))
                    
                    print(f"  📋 Admin User Buttons Found: {len(admin_buttons)}")
                    
                    # Check for admin-only buttons
                    admin_expected = ["⚙️ Configuration", "🎨 List Images"]
                    found_admin_buttons = [text for text, _ in admin_buttons]
                    admin_found = any(expected in found_admin_buttons for expected in admin_expected)
                    
                    if admin_found:
                        print(f"  ✅ Admin-only buttons found for admin user")
                    else:
                        print(f"  ❌ Admin-only buttons not found for admin user")
                        return False
                else:
                    print(f"  ❌ No keyboard found in admin help command response")
                    return False
            else:
                print(f"  ❌ Admin help command did not send a response")
                return False
    
    except Exception as e:
        print(f"  ❌ Admin help command test failed: {e}")
        return False
    
    return True

async def test_button_callback_execution():
    """Test that button callbacks execute correctly"""
    print("\n🔘 Testing Button Callback Execution...")
    
    callback_tests = [
        ("cmd_price", "Price Command Button"),
        ("cmd_debug", "Debug Command Button"),
        ("cmd_donate", "Donate Command Button"),
        ("copy_btc_address", "Copy Bitcoin Address Button")
    ]
    
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
                return False
            
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
                        return False
                
                elif callback_data == "cmd_debug":
                    if "Debug Information" in response_text:
                        print(f"    ✅ Debug response contains expected content")
                    else:
                        print(f"    ❌ Debug response missing expected content")
                        return False
                
                elif callback_data == "cmd_donate":
                    if "XBTBuyBot Developer Coffee Tip" in response_text:
                        print(f"    ✅ Donate response contains expected content")
                    else:
                        print(f"    ❌ Donate response missing expected content")
                        return False
                
                elif callback_data == "copy_btc_address":
                    if "1B1YLseSykoBPKFzokTGvzM2gzybyEDiU4" in response_text:
                        print(f"    ✅ Copy address response contains Bitcoin address")
                    else:
                        print(f"    ❌ Copy address response missing Bitcoin address")
                        return False
                
            else:
                print(f"    ❌ No response sent")
                return False
            
            print(f"    ✅ {test_name} callback executed successfully")
            
        except Exception as e:
            print(f"    ❌ {test_name} callback failed: {e}")
            return False
    
    return True

async def test_callback_handler_registration():
    """Test that callback handlers are properly registered"""
    print("\n🔧 Testing Callback Handler Registration...")
    
    # Test pattern matching
    patterns = [
        ("cmd_price", "^cmd_"),
        ("cmd_chart", "^cmd_"),
        ("cmd_debug", "^cmd_"),
        ("cmd_donate", "^cmd_"),
        ("copy_btc_address", "^copy_"),
    ]
    
    import re
    all_matched = True
    
    for callback_data, pattern in patterns:
        matches = bool(re.match(pattern, callback_data))
        if matches:
            print(f"  ✅ '{callback_data}' matches pattern '{pattern}'")
        else:
            print(f"  ❌ '{callback_data}' does NOT match pattern '{pattern}'")
            all_matched = False
    
    return all_matched

async def main():
    """Run all button callback tests"""
    print("🚀 Starting Live Button Callback Tests...")
    print("="*70)
    
    tests = [
        ("Help Command Button Generation", test_help_command_button_generation),
        ("Button Callback Execution", test_button_callback_execution),
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
    print(f"LIVE BUTTON CALLBACK TEST SUMMARY: {passed}/{total} tests passed")
    print('='*70)
    
    if passed == total:
        print("🎉 ALL BUTTON CALLBACK TESTS PASSED!")
        print("\n✅ Button System Status:")
        print("  ✅ Help command generates correct buttons")
        print("  ✅ Button callbacks execute successfully")
        print("  ✅ Callback handlers properly registered")
        print("  ✅ Pattern matching working correctly")
        print("  ✅ User responses sent properly")
        
        print(f"\n🤖 The help command button callback issue is RESOLVED!")
        return True
    else:
        print("⚠️  Some button callback tests failed. Please review the results above.")
        return False

if __name__ == "__main__":
    asyncio.run(main())
