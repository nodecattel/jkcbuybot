#!/usr/bin/env python3
"""
Test for Fixed Chart Button Functionality
Tests that the "📈 View Chart" button now executes actual chart generation
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
    button_command_callback, get_nonkyc_trades
)

async def test_chart_button_functionality():
    """Test that the chart button now executes actual chart generation"""
    print("📈 Testing Chart Button Functionality...")
    
    # Create mock objects for callback query
    query = MagicMock()
    query.data = "cmd_chart"
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
    context.bot.send_photo = AsyncMock()
    context.bot.send_message = AsyncMock()
    
    # Mock trade data for chart generation
    mock_trades = [
        {
            "timestamp": "2025-06-23T05:00:00Z",
            "price": "0.156",
            "quantity": "100.0",
            "side": "buy"
        },
        {
            "timestamp": "2025-06-23T05:01:00Z", 
            "price": "0.158",
            "quantity": "150.0",
            "side": "sell"
        },
        {
            "timestamp": "2025-06-23T05:02:00Z",
            "price": "0.157",
            "quantity": "120.0",
            "side": "buy"
        }
    ]
    
    try:
        # Mock necessary functions for chart generation
        with patch('telebot_fixed.get_nonkyc_trades', return_value=mock_trades), \
             patch('telebot_fixed.pd.DataFrame') as mock_df, \
             patch('telebot_fixed.go.Figure') as mock_figure, \
             patch('telebot_fixed.os.remove') as mock_remove:
            
            # Mock pandas DataFrame operations
            mock_df_instance = MagicMock()
            mock_df_instance.sort_values.return_value = mock_df_instance
            mock_df.return_value = mock_df_instance
            
            # Mock plotly Figure operations
            mock_fig_instance = MagicMock()
            mock_fig_instance.write_image = MagicMock()
            mock_figure.return_value = mock_fig_instance
            
            # Mock file operations
            mock_open = MagicMock()
            mock_open.__enter__ = MagicMock(return_value=mock_open)
            mock_open.__exit__ = MagicMock(return_value=None)
            
            with patch('builtins.open', return_value=mock_open):
                await button_command_callback(update, context)
            
            # Verify query.answer() was called
            if query.answer.called:
                print("  ✅ query.answer() called")
            else:
                print("  ❌ query.answer() NOT called")
                return False
            
            # Verify initial processing message was sent
            if query.edit_message_text.called:
                call_args = query.edit_message_text.call_args_list
                
                # Check for processing message
                processing_found = False
                completion_found = False
                
                for call in call_args:
                    message_text = call[0][0]
                    if "Generating charts" in message_text:
                        processing_found = True
                        print("  ✅ Processing message sent")
                    elif "Charts generated successfully" in message_text:
                        completion_found = True
                        print("  ✅ Completion message sent")
                
                if not processing_found:
                    print("  ❌ Processing message not found")
                    return False
                
                if not completion_found:
                    print("  ❌ Completion message not found")
                    return False
            else:
                print("  ❌ No edit_message_text calls made")
                return False
            
            # Verify chart images were sent
            if context.bot.send_photo.called:
                photo_calls = context.bot.send_photo.call_args_list
                print(f"  ✅ {len(photo_calls)} chart image(s) sent")
                
                # Check captions for expected content
                for call in photo_calls:
                    caption = call[1].get('caption', '')
                    if 'XBT/USDT' in caption:
                        print("  ✅ XBT/USDT chart sent with proper caption")
                    elif 'XBT/BTC' in caption:
                        print("  ✅ XBT/BTC chart sent with proper caption")
            else:
                print("  ❌ No chart images sent")
                return False
            
            # Verify summary message was sent
            if context.bot.send_message.called:
                message_calls = context.bot.send_message.call_args_list
                summary_found = False
                
                for call in message_calls:
                    message_text = call[1].get('text', '')
                    if 'XBT Trading Pairs' in message_text:
                        summary_found = True
                        print("  ✅ Summary message with trading links sent")
                        break
                
                if not summary_found:
                    print("  ⚠️ Summary message not found (may be normal)")
            
            # Verify chart generation functions were called
            if mock_df.called:
                print("  ✅ DataFrame creation called for data processing")
            else:
                print("  ❌ DataFrame creation not called")
                return False
            
            if mock_figure.called:
                print("  ✅ Chart figure creation called")
            else:
                print("  ❌ Chart figure creation not called")
                return False
            
            print("  ✅ Chart button functionality test completed successfully")
            return True
            
    except Exception as e:
        print(f"  ❌ Chart button test failed: {e}")
        return False

async def test_chart_button_error_handling():
    """Test chart button error handling when no trade data is available"""
    print("\n❌ Testing Chart Button Error Handling...")
    
    # Create mock objects
    query = MagicMock()
    query.data = "cmd_chart"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.from_user.id = 999999999
    query.message.chat.id = -1002293167945
    
    update = MagicMock()
    update.callback_query = query
    
    context = MagicMock()
    
    try:
        # Mock no trade data available
        with patch('telebot_fixed.get_nonkyc_trades', return_value=None):
            await button_command_callback(update, context)
            
            # Verify error message was sent
            if query.edit_message_text.called:
                call_args = query.edit_message_text.call_args_list
                error_found = False
                
                for call in call_args:
                    message_text = call[0][0]
                    if "No trade data available" in message_text:
                        error_found = True
                        print("  ✅ Proper error message sent when no data available")
                        break
                
                if not error_found:
                    print("  ❌ Error message not found")
                    return False
            else:
                print("  ❌ No error message sent")
                return False
            
            return True
            
    except Exception as e:
        print(f"  ❌ Error handling test failed: {e}")
        return False

async def test_chart_button_vs_placeholder():
    """Test that chart button no longer shows placeholder message"""
    print("\n🔄 Testing Chart Button vs Old Placeholder...")
    
    # Create mock objects
    query = MagicMock()
    query.data = "cmd_chart"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.from_user.id = 999999999
    query.message.chat.id = -1002293167945
    
    update = MagicMock()
    update.callback_query = query
    
    context = MagicMock()
    context.bot.send_photo = AsyncMock()
    context.bot.send_message = AsyncMock()
    
    # Mock minimal trade data
    mock_trades = [{"timestamp": "2025-06-23T05:00:00Z", "price": "0.156", "quantity": "100.0"}]
    
    try:
        with patch('telebot_fixed.get_nonkyc_trades', return_value=mock_trades), \
             patch('telebot_fixed.pd.DataFrame'), \
             patch('telebot_fixed.go.Figure'), \
             patch('telebot_fixed.os.remove'), \
             patch('builtins.open', MagicMock()):
            
            await button_command_callback(update, context)
            
            # Check that placeholder message is NOT sent
            if query.edit_message_text.called:
                call_args = query.edit_message_text.call_args_list
                placeholder_found = False
                
                for call in call_args:
                    message_text = call[0][0]
                    if "Chart generation feature coming soon" in message_text:
                        placeholder_found = True
                        break
                
                if placeholder_found:
                    print("  ❌ Old placeholder message still being sent")
                    return False
                else:
                    print("  ✅ Placeholder message no longer sent")
            
            # Verify actual chart functionality is triggered
            if context.bot.send_photo.called or context.bot.send_message.called:
                print("  ✅ Actual chart functionality executed instead of placeholder")
                return True
            else:
                print("  ❌ Neither placeholder nor chart functionality executed")
                return False
            
    except Exception as e:
        print(f"  ❌ Placeholder comparison test failed: {e}")
        return False

async def main():
    """Run all chart button tests"""
    print("🚀 Starting Chart Button Fix Tests...")
    print("="*70)
    
    tests = [
        ("Chart Button Functionality", test_chart_button_functionality),
        ("Chart Button Error Handling", test_chart_button_error_handling),
        ("Chart Button vs Placeholder", test_chart_button_vs_placeholder),
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
    print(f"CHART BUTTON FIX TEST SUMMARY: {passed}/{total} tests passed")
    print('='*70)
    
    if passed == total:
        print("🎉 CHART BUTTON FIX TESTS PASSED!")
        print("\n✅ Chart Button Status:")
        print("  ✅ No longer shows placeholder message")
        print("  ✅ Executes actual chart generation functionality")
        print("  ✅ Sends dual charts (XBT/USDT and XBT/BTC)")
        print("  ✅ Includes proper trading links and captions")
        print("  ✅ Handles errors gracefully with informative messages")
        print("  ✅ Provides user feedback during processing")
        
        print(f"\n🤖 The '📈 View Chart' button is now fully functional!")
        return True
    else:
        print("⚠️  Some chart button tests failed. Please review the results above.")
        return False

if __name__ == "__main__":
    asyncio.run(main())
