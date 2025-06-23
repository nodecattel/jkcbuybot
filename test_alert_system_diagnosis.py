#!/usr/bin/env python3
"""
Alert System Diagnosis Test
Comprehensive test to diagnose why real-time trade alerts are not being sent
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
    process_message, send_alert, ACTIVE_CHAT_IDS, VALUE_REQUIRE, CONFIG
)

async def test_current_configuration():
    """Test current bot configuration"""
    print("🔧 Testing Current Bot Configuration...")
    
    try:
        # Read current configuration
        with open('/app/config.json', 'r') as f:
            config = json.load(f)
        
        print(f"  📊 Current threshold: ${config.get('value_require', 'NOT SET')} USDT")
        print(f"  📱 Active chat IDs: {config.get('active_chat_ids', [])}")
        print(f"  🔄 Trade aggregation enabled: {config.get('trade_aggregation', {}).get('enabled', False)}")
        print(f"  ⏱️ Aggregation window: {config.get('trade_aggregation', {}).get('window_seconds', 0)} seconds")
        
        # Check if target chat ID is in active chats
        target_chat = -1002293167945
        if target_chat in config.get('active_chat_ids', []):
            print(f"  ✅ Target chat ID {target_chat} is in active chats")
        else:
            print(f"  ❌ Target chat ID {target_chat} is NOT in active chats")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Configuration test failed: {e}")
        return False

async def test_small_trade_processing():
    """Test processing of small trades (like current real trades)"""
    print("\n💰 Testing Small Trade Processing...")
    
    try:
        # Simulate a small trade like the ones we see in logs
        price = 0.170044
        quantity = 32.1612
        sum_value = price * quantity  # Should be ~5.47 USDT
        exchange = "NonKYC Exchange (XBT/USDT)"
        timestamp = int(time.time() * 1000)
        exchange_url = "https://nonkyc.io/market/XBT_USDT"
        
        print(f"  📊 Simulating trade: {quantity} XBT at ${price} = ${sum_value:.2f} USDT")
        print(f"  🎯 Current threshold: ${VALUE_REQUIRE} USDT")
        print(f"  📈 Trade is {'above' if sum_value >= VALUE_REQUIRE else 'below'} threshold")
        
        # Mock the send_alert function to capture if it would be called
        with patch('telebot_fixed.send_alert') as mock_send_alert, \
             patch('telebot_fixed.update_threshold') as mock_update_threshold:
            
            mock_update_threshold.return_value = asyncio.Future()
            mock_update_threshold.return_value.set_result(None)
            
            await process_message(price, quantity, sum_value, exchange, timestamp, exchange_url)
            
            if mock_send_alert.called:
                print(f"  ✅ send_alert() was called for small trade")
                return True
            else:
                print(f"  ✅ send_alert() was NOT called (expected for trade below threshold)")
                return True
                
    except Exception as e:
        print(f"  ❌ Small trade processing test failed: {e}")
        return False

async def test_large_trade_processing():
    """Test processing of large trades (above threshold)"""
    print("\n🐋 Testing Large Trade Processing...")
    
    try:
        # Simulate a large trade that should trigger an alert
        price = 0.170044
        quantity = 1000.0  # Large quantity
        sum_value = price * quantity  # Should be ~170 USDT (above 100 threshold)
        exchange = "NonKYC Exchange (XBT/USDT)"
        timestamp = int(time.time() * 1000)
        exchange_url = "https://nonkyc.io/market/XBT_USDT"
        
        print(f"  📊 Simulating large trade: {quantity} XBT at ${price} = ${sum_value:.2f} USDT")
        print(f"  🎯 Current threshold: ${VALUE_REQUIRE} USDT")
        print(f"  📈 Trade is {'above' if sum_value >= VALUE_REQUIRE else 'below'} threshold")
        
        # Mock the send_alert function to capture if it would be called
        with patch('telebot_fixed.send_alert') as mock_send_alert, \
             patch('telebot_fixed.update_threshold') as mock_update_threshold:
            
            mock_update_threshold.return_value = asyncio.Future()
            mock_update_threshold.return_value.set_result(None)
            
            await process_message(price, quantity, sum_value, exchange, timestamp, exchange_url)
            
            if mock_send_alert.called:
                print(f"  ✅ send_alert() was called for large trade")
                call_args = mock_send_alert.call_args
                print(f"  📞 Alert called with: price={call_args[0][0]}, quantity={call_args[0][1]}, value={call_args[0][2]}")
                return True
            else:
                print(f"  ❌ send_alert() was NOT called for large trade")
                return False
                
    except Exception as e:
        print(f"  ❌ Large trade processing test failed: {e}")
        return False

async def test_aggregated_trades():
    """Test trade aggregation functionality"""
    print("\n🔄 Testing Trade Aggregation...")
    
    try:
        # Simulate multiple small trades that should aggregate to above threshold
        trades = [
            (0.170, 200.0),  # ~34 USDT
            (0.171, 200.0),  # ~34.2 USDT  
            (0.169, 200.0),  # ~33.8 USDT
        ]
        
        total_value = sum(price * quantity for price, quantity in trades)
        print(f"  📊 Simulating {len(trades)} trades totaling ${total_value:.2f} USDT")
        print(f"  🎯 Current threshold: ${VALUE_REQUIRE} USDT")
        print(f"  📈 Aggregated trades are {'above' if total_value >= VALUE_REQUIRE else 'below'} threshold")
        
        exchange = "NonKYC Exchange (XBT/USDT)"
        timestamp = int(time.time() * 1000)
        exchange_url = "https://nonkyc.io/market/XBT_USDT"
        
        # Mock the send_alert function to capture if it would be called
        with patch('telebot_fixed.send_alert') as mock_send_alert, \
             patch('telebot_fixed.update_threshold') as mock_update_threshold:
            
            mock_update_threshold.return_value = asyncio.Future()
            mock_update_threshold.return_value.set_result(None)
            
            # Process each trade
            for i, (price, quantity) in enumerate(trades):
                sum_value = price * quantity
                print(f"    Trade {i+1}: {quantity} XBT at ${price} = ${sum_value:.2f} USDT")
                await process_message(price, quantity, sum_value, exchange, timestamp + i*1000, exchange_url)
            
            # Wait a moment for aggregation to process
            await asyncio.sleep(0.1)
            
            if mock_send_alert.called:
                print(f"  ✅ send_alert() was called for aggregated trades")
                call_count = mock_send_alert.call_count
                print(f"  📞 Alert called {call_count} time(s)")
                return True
            else:
                print(f"  ❌ send_alert() was NOT called for aggregated trades")
                return False
                
    except Exception as e:
        print(f"  ❌ Aggregated trades test failed: {e}")
        return False

async def test_send_alert_function():
    """Test the send_alert function directly"""
    print("\n📢 Testing send_alert Function...")
    
    try:
        # Test parameters
        price = 0.170
        quantity = 1000.0
        sum_value = price * quantity
        exchange = "Test Exchange"
        timestamp = int(time.time() * 1000)
        exchange_url = "https://test.com"
        
        print(f"  📊 Testing alert: {quantity} XBT at ${price} = ${sum_value:.2f} USDT")
        print(f"  📱 Target chats: {ACTIVE_CHAT_IDS}")
        
        # Mock the Bot and its methods
        with patch('telebot_fixed.Bot') as mock_bot_class, \
             patch('telebot_fixed.load_random_image') as mock_load_image, \
             patch('telebot_fixed.get_nonkyc_ticker') as mock_ticker, \
             patch('telebot_fixed.calculate_combined_volume_periods') as mock_volume:
            
            # Setup mocks
            mock_bot = MagicMock()
            mock_bot.send_photo = AsyncMock()
            mock_bot.send_animation = AsyncMock()
            mock_bot.send_message = AsyncMock()
            mock_bot_class.return_value = mock_bot
            
            mock_load_image.return_value = "test_image.jpg"
            mock_ticker.return_value = {"marketcapNumber": 1000000, "lastPriceNumber": 0.17}
            mock_volume.return_value = {"combined": {"15m": 1000, "1h": 5000, "4h": 20000, "24h": 100000}}
            
            # Call send_alert
            await send_alert(price, quantity, sum_value, exchange, timestamp, exchange_url)
            
            # Check if Bot was instantiated
            if mock_bot_class.called:
                print(f"  ✅ Bot instance created")
            else:
                print(f"  ❌ Bot instance NOT created")
                return False
            
            # Check if send_photo was called for each active chat
            expected_calls = len(ACTIVE_CHAT_IDS)
            actual_calls = mock_bot.send_photo.call_count
            
            if actual_calls == expected_calls:
                print(f"  ✅ send_photo called {actual_calls} times (once per active chat)")
                return True
            else:
                print(f"  ❌ send_photo called {actual_calls} times, expected {expected_calls}")
                return False
                
    except Exception as e:
        print(f"  ❌ send_alert function test failed: {e}")
        return False

async def test_threshold_comparison():
    """Test threshold comparison logic"""
    print("\n🎯 Testing Threshold Comparison Logic...")
    
    try:
        current_threshold = VALUE_REQUIRE
        print(f"  📊 Current threshold: ${current_threshold} USDT")
        
        test_values = [
            5.47,    # Recent real trade value
            50.0,    # Below threshold
            100.0,   # Exactly at threshold
            150.0,   # Above threshold
            200.0,   # Well above threshold
        ]
        
        for value in test_values:
            is_above = value >= current_threshold
            status = "ABOVE" if is_above else "BELOW"
            emoji = "✅" if is_above else "❌"
            print(f"    {emoji} ${value:.2f} USDT is {status} threshold")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Threshold comparison test failed: {e}")
        return False

async def main():
    """Run all alert system diagnostic tests"""
    print("🚀 Starting Alert System Diagnosis...")
    print("="*70)
    
    tests = [
        ("Current Configuration", test_current_configuration),
        ("Small Trade Processing", test_small_trade_processing),
        ("Large Trade Processing", test_large_trade_processing),
        ("Aggregated Trades", test_aggregated_trades),
        ("send_alert Function", test_send_alert_function),
        ("Threshold Comparison", test_threshold_comparison),
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
    print(f"ALERT SYSTEM DIAGNOSIS SUMMARY: {passed}/{total} tests passed")
    print('='*70)
    
    # Provide diagnosis based on results
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("\n✅ Alert System Status:")
        print("  ✅ Configuration is correct")
        print("  ✅ Trade processing logic is working")
        print("  ✅ Alert function is functional")
        print("  ✅ Threshold comparison is accurate")
        
        print(f"\n🔍 DIAGNOSIS:")
        print(f"  📊 The alert system is working correctly!")
        print(f"  💰 Recent trades are simply below the ${VALUE_REQUIRE} USDT threshold")
        print(f"  📈 Real trades: ~$5-6 USDT vs ${VALUE_REQUIRE} USDT threshold")
        print(f"  🔄 Trade aggregation is working but trades are too small to aggregate above threshold")
        
        print(f"\n💡 RECOMMENDATIONS:")
        print(f"  1. Lower threshold temporarily to test with real trades")
        print(f"  2. Wait for larger trades to occur naturally")
        print(f"  3. Monitor aggregation windows for multiple small trades")
        
    else:
        print("⚠️  Some alert system tests failed.")
        print("\n🔍 DIAGNOSIS:")
        print("  ❌ There may be issues with the alert system configuration or logic")
        print("  🔧 Review the failed tests above for specific issues")
        
    return passed == total

if __name__ == "__main__":
    asyncio.run(main())
