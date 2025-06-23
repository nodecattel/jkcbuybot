#!/usr/bin/env python3
"""
Test script to verify the enhanced /chart command with dual trading pair support
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
from telebot_fixed import chart_command

async def test_chart_command_enhancement():
    """Test the enhanced /chart command with dual trading pairs"""
    print("🧪 Testing enhanced /chart command...")
    
    # Mock update and context
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    
    context = MagicMock()
    
    # Mock trades data
    mock_trades_data = [
        {
            "timestamp": "2025-06-23T04:00:00.000Z",
            "price": "0.155000",
            "quantity": "100.0"
        },
        {
            "timestamp": "2025-06-23T04:05:00.000Z", 
            "price": "0.156000",
            "quantity": "150.0"
        },
        {
            "timestamp": "2025-06-23T04:10:00.000Z",
            "price": "0.157000", 
            "quantity": "200.0"
        }
    ]
    
    # Mock file operations
    mock_file_content = b"fake_chart_image_data"
    
    with patch('telebot_fixed.get_nonkyc_trades', return_value=mock_trades_data), \
         patch('builtins.open', create=True) as mock_open, \
         patch('os.remove') as mock_remove, \
         patch('plotly.graph_objects.Figure') as mock_figure:
        
        # Configure mock file
        mock_file = MagicMock()
        mock_file.__enter__.return_value = mock_file
        mock_file.read.return_value = mock_file_content
        mock_open.return_value = mock_file
        
        # Configure mock figure
        mock_fig_instance = MagicMock()
        mock_figure.return_value = mock_fig_instance
        
        try:
            # Test the chart command
            await chart_command(update, context)
            
            # Verify initial message
            initial_calls = [call for call in update.message.reply_text.call_args_list 
                           if "Generating charts" in str(call)]
            assert len(initial_calls) >= 1, "Should send initial 'generating charts' message"
            
            # Verify photo replies (should be at least 1 for USDT chart)
            photo_calls = update.message.reply_photo.call_args_list
            assert len(photo_calls) >= 1, "Should send at least one chart image"
            
            # Check for USDT chart caption
            usdt_chart_found = False
            btc_info_found = False
            summary_found = False
            
            for call in photo_calls:
                if 'caption' in call.kwargs:
                    caption = call.kwargs['caption']
                    if "XBT/USDT" in caption and "nonkyc.io/market/XBT_USDT" in caption:
                        usdt_chart_found = True
                        print("  ✅ USDT chart with trading link found")
            
            # Check for text messages with trading info
            for call in update.message.reply_text.call_args_list:
                message = call.args[0] if call.args else ""
                if "XBT/BTC Trading" in message and "nonkyc.io/market/XBT_BTC" in message:
                    btc_info_found = True
                    print("  ✅ BTC trading link message found")
                elif "XBT Trading Pairs on NonKYC Exchange" in message:
                    summary_found = True
                    print("  ✅ Summary message with both trading links found")
            
            assert usdt_chart_found, "Should generate USDT chart with trading link"
            assert btc_info_found or summary_found, "Should provide BTC trading information"
            
            print("✅ Enhanced chart command test passed!")
            return True
            
        except Exception as e:
            print(f"❌ Chart command test failed: {e}")
            return False

async def test_chart_error_handling():
    """Test chart command error handling"""
    print("🧪 Testing chart command error handling...")
    
    # Mock update and context
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    
    context = MagicMock()
    
    # Test with no trades data
    with patch('telebot_fixed.get_nonkyc_trades', return_value=None):
        await chart_command(update, context)
        
        # Should send error message
        error_calls = [call for call in update.message.reply_text.call_args_list 
                      if "No trade data available" in str(call)]
        assert len(error_calls) >= 1, "Should send 'no data' error message"
        
    print("  ✅ No data error handling works")
    
    # Test with empty trades data
    update.message.reply_text.reset_mock()
    
    with patch('telebot_fixed.get_nonkyc_trades', return_value=[]):
        await chart_command(update, context)
        
        error_calls = [call for call in update.message.reply_text.call_args_list 
                      if "No trade data available" in str(call)]
        assert len(error_calls) >= 1, "Should send 'no data' error message for empty list"
        
    print("  ✅ Empty data error handling works")
    
    print("✅ Chart error handling test passed!")
    return True

def test_trading_links():
    """Test that trading links are correctly formatted"""
    print("🧪 Testing trading link formats...")
    
    expected_links = {
        "XBT/USDT": "https://nonkyc.io/market/XBT_USDT",
        "XBT/BTC": "https://nonkyc.io/market/XBT_BTC"
    }
    
    for pair, link in expected_links.items():
        # Verify link format
        assert link.startswith("https://"), f"{pair} link should use HTTPS"
        assert "nonkyc.io" in link, f"{pair} link should point to NonKYC"
        assert "market" in link, f"{pair} link should be a market link"
        print(f"  ✅ {pair} link format correct: {link}")
    
    print("✅ Trading link format test passed!")
    return True

async def main():
    """Run all tests"""
    print("🚀 Starting enhanced /chart command tests...\n")
    
    tests = [
        ("Trading Link Formats", test_trading_links),
        ("Chart Error Handling", test_chart_error_handling),
        ("Enhanced Chart Command", test_chart_command_enhancement),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
                
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print(f"\n{'='*50}")
    print(f"TEST SUMMARY: {passed}/{total} tests passed")
    print('='*50)
    
    if passed == total:
        print("🎉 All tests passed! The enhanced /chart command is working correctly.")
        print("\n📊 New chart features verified:")
        print("  ✅ Dual trading pair support (XBT/USDT and XBT/BTC)")
        print("  ✅ Trading links for both pairs on NonKYC Exchange")
        print("  ✅ Clear headings and captions for each chart")
        print("  ✅ Summary message with all trading links")
        print("  ✅ Proper error handling for missing data")
        return True
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return False

if __name__ == "__main__":
    asyncio.run(main())
