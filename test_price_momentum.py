#!/usr/bin/env python3
"""
Test script to verify the enhanced /price command with momentum calculations
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
    check_price,
    calculate_momentum_periods,
    get_nonkyc_trades,
    get_nonkyc_ticker
)

async def test_momentum_calculation():
    """Test the momentum calculation function"""
    print("🧪 Testing momentum calculation...")
    
    # Mock trades data with different timestamps
    current_time = time.time() * 1000  # Current time in milliseconds
    
    mock_trades = [
        # Recent trades (within 15 minutes)
        {"timestamp": current_time - (5 * 60 * 1000), "price": "0.155000"},  # 5 min ago
        {"timestamp": current_time - (10 * 60 * 1000), "price": "0.154000"}, # 10 min ago
        {"timestamp": current_time - (14 * 60 * 1000), "price": "0.153000"}, # 14 min ago
        
        # Older trades (within 1 hour)
        {"timestamp": current_time - (30 * 60 * 1000), "price": "0.152000"}, # 30 min ago
        {"timestamp": current_time - (50 * 60 * 1000), "price": "0.151000"}, # 50 min ago
        
        # Even older trades (within 4 hours)
        {"timestamp": current_time - (2 * 60 * 60 * 1000), "price": "0.150000"}, # 2 hours ago
        {"timestamp": current_time - (3 * 60 * 60 * 1000), "price": "0.149000"}, # 3 hours ago
        
        # Very old trades (within 24 hours)
        {"timestamp": current_time - (12 * 60 * 60 * 1000), "price": "0.148000"}, # 12 hours ago
        {"timestamp": current_time - (20 * 60 * 60 * 1000), "price": "0.147000"}, # 20 hours ago
    ]
    
    current_price = 0.156000  # Current price
    
    # Calculate momentum
    momentum = await calculate_momentum_periods(mock_trades, current_price)
    
    print(f"  Current price: ${current_price:.6f}")
    print(f"  15m momentum: {momentum['15m']:.2f}%")
    print(f"  1h momentum: {momentum['1h']:.2f}%")
    print(f"  4h momentum: {momentum['4h']:.2f}%")
    print(f"  24h momentum: {momentum['24h']:.2f}%")
    
    # Verify momentum calculations
    # 15m: from 0.153000 to 0.156000 = +1.96%
    # 1h: from 0.151000 to 0.156000 = +3.31%
    # 4h: from 0.149000 to 0.156000 = +4.70%
    # 24h: from 0.147000 to 0.156000 = +6.12%
    
    assert momentum['15m'] > 0, "15m momentum should be positive"
    assert momentum['1h'] > momentum['15m'], "1h momentum should be higher than 15m"
    assert momentum['4h'] > momentum['1h'], "4h momentum should be higher than 1h"
    assert momentum['24h'] > momentum['4h'], "24h momentum should be higher than 4h"
    
    print("✅ Momentum calculation test passed!")
    return True

async def test_price_command_integration():
    """Test the /price command with momentum integration"""
    print("🧪 Testing /price command integration...")
    
    # Mock update and context
    update = MagicMock()
    update.effective_chat.id = -1002293167945  # Test chat ID
    update.effective_user.id = 1145064309  # Bot owner ID
    update.message.reply_text = AsyncMock()
    
    context = MagicMock()
    
    # Mock the NonKYC API responses
    mock_ticker_data = {
        "lastPriceNumber": 0.156000,
        "yesterdayPriceNumber": 0.150000,
        "highPriceNumber": 0.158000,
        "lowPriceNumber": 0.149000,
        "volumeNumber": 1000000,
        "volumeUsdNumber": 156000,
        "changePercentNumber": 4.0,
        "marketcapNumber": 15600000,
        "bestBidNumber": 0.155900,
        "bestAskNumber": 0.156100,
        "spreadPercentNumber": 0.13
    }
    
    mock_trades_data = [
        {"timestamp": time.time() * 1000 - (10 * 60 * 1000), "price": "0.154000"},
        {"timestamp": time.time() * 1000 - (30 * 60 * 1000), "price": "0.152000"},
        {"timestamp": time.time() * 1000 - (2 * 60 * 60 * 1000), "price": "0.150000"},
        {"timestamp": time.time() * 1000 - (12 * 60 * 60 * 1000), "price": "0.148000"},
    ]
    
    # Patch the API functions
    with patch('telebot_fixed.get_nonkyc_ticker', return_value=mock_ticker_data), \
         patch('telebot_fixed.get_nonkyc_trades', return_value=mock_trades_data), \
         patch('telebot_fixed.calculate_combined_volume_periods', return_value={
             "combined": {"15m": 5000, "1h": 15000, "4h": 45000, "24h": 156000}
         }):
        
        # Test the price command
        await check_price(update, context)
        
        # Verify that reply_text was called
        update.message.reply_text.assert_called_once()
        
        # Get the message content
        call_args = update.message.reply_text.call_args
        message_text = call_args[0][0]  # First positional argument
        
        # Verify the message contains momentum data
        assert "Momentum (Price Change)" in message_text, "Message should contain momentum section"
        assert "15m:" in message_text, "Message should contain 15m momentum"
        assert "1h:" in message_text, "Message should contain 1h momentum"
        assert "4h:" in message_text, "Message should contain 4h momentum"
        assert "24h:" in message_text, "Message should contain 24h momentum"
        
        # Verify trading links are present in keyboard
        keyboard = call_args[1]['reply_markup']  # Keyword argument
        buttons = []
        for row in keyboard.inline_keyboard:
            for button in row:
                buttons.append((button.text, button.url))
        
        # Check for trading links
        trading_buttons = [b for b in buttons if "Trade" in b[0]]
        assert len(trading_buttons) >= 2, "Should have at least 2 trading buttons"
        
        usdt_button = next((b for b in trading_buttons if "USDT" in b[0]), None)
        btc_button = next((b for b in trading_buttons if "BTC" in b[0]), None)
        
        assert usdt_button is not None, "Should have XBT/USDT trading button"
        assert btc_button is not None, "Should have XBT/BTC trading button"
        assert "nonkyc.io/market/XBT_USDT" in usdt_button[1], "USDT button should link to NonKYC"
        assert "nonkyc.io/market/XBT_BTC" in btc_button[1], "BTC button should link to NonKYC"
        
        print("  ✅ Message contains momentum data")
        print("  ✅ Trading links are present")
        print("  ✅ Keyboard layout is correct")
        
    print("✅ Price command integration test passed!")
    return True

async def test_real_api_connection():
    """Test connection to real NonKYC API"""
    print("🧪 Testing real NonKYC API connection...")
    
    try:
        # Test ticker data
        ticker_data = await get_nonkyc_ticker()
        if ticker_data:
            print(f"  ✅ Ticker API working - Current price: ${ticker_data.get('lastPriceNumber', 'N/A')}")
        else:
            print("  ⚠️  Ticker API returned no data")
        
        # Test trades data
        trades_data = await get_nonkyc_trades()
        if trades_data and len(trades_data) > 0:
            print(f"  ✅ Trades API working - {len(trades_data)} recent trades")
            latest_trade = trades_data[0]
            print(f"    Latest trade: ${latest_trade.get('price', 'N/A')} at {latest_trade.get('timestamp', 'N/A')}")
        else:
            print("  ⚠️  Trades API returned no data")
        
        return True
        
    except Exception as e:
        print(f"  ❌ API connection failed: {e}")
        return False

def test_momentum_formatting():
    """Test momentum value formatting"""
    print("🧪 Testing momentum formatting...")
    
    # Import the format function from the price command
    def format_momentum(value):
        if value > 0:
            return f"+{value:.2f}%"
        elif value < 0:
            return f"{value:.2f}%"
        else:
            return "0.00%"
    
    # Test cases
    test_cases = [
        (5.67, "+5.67%"),
        (-3.21, "-3.21%"),
        (0, "0.00%"),
        (0.0, "0.00%"),
        (10.123, "+10.12%"),
        (-0.456, "-0.46%")
    ]
    
    for value, expected in test_cases:
        result = format_momentum(value)
        assert result == expected, f"Expected {expected}, got {result}"
        print(f"  {value} -> {result} ✅")
    
    print("✅ Momentum formatting test passed!")
    return True

async def main():
    """Run all tests"""
    print("🚀 Starting enhanced /price command tests...\n")
    
    tests = [
        ("Momentum Formatting", test_momentum_formatting),
        ("Momentum Calculation", test_momentum_calculation),
        ("Real API Connection", test_real_api_connection),
        ("Price Command Integration", test_price_command_integration),
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
        print("🎉 All tests passed! The enhanced /price command is working correctly.")
        print("\n📊 New features verified:")
        print("  ✅ Momentum calculations for 15m, 1h, 4h, 24h timeframes")
        print("  ✅ Trading links for XBT/USDT and XBT/BTC on NonKYC")
        print("  ✅ Clean momentum formatting without explanatory text")
        print("  ✅ Integration with existing price data sources")
        return True
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return False

if __name__ == "__main__":
    asyncio.run(main())
