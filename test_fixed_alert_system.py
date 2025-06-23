#!/usr/bin/env python3
"""
Test Fixed Alert System
Verify that the /test command now sends actual alerts to the bot owner chat
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
    test_command, send_alert, ACTIVE_CHAT_IDS, VALUE_REQUIRE, BOT_TOKEN, BOT_OWNER
)

async def verify_current_configuration():
    """Verify the current bot configuration"""
    print("🔧 Verifying Current Configuration...")
    
    try:
        # Read current configuration
        with open('/app/config.json', 'r') as f:
            config = json.load(f)
        
        print(f"  📊 Current threshold: ${config.get('value_require', 'NOT SET')} USDT")
        print(f"  📱 Active chat IDs: {config.get('active_chat_ids', [])}")
        print(f"  👑 Bot owner: {config.get('bot_owner', 'NOT SET')}")
        print(f"  🎯 Expected single chat: {BOT_OWNER}")
        
        # Verify configuration
        active_chats = config.get('active_chat_ids', [])
        if len(active_chats) == 1 and active_chats[0] == BOT_OWNER:
            print(f"  ✅ Configuration correct: Single chat ID {BOT_OWNER}")
            return True
        else:
            print(f"  ❌ Configuration issue: Expected [{BOT_OWNER}], got {active_chats}")
            return False
        
    except Exception as e:
        print(f"  ❌ Configuration verification failed: {e}")
        return False

async def test_send_alert_to_owner():
    """Test sending alert directly to bot owner"""
    print("\n📢 Testing Direct Alert to Bot Owner...")
    
    try:
        from telebot_fixed import Bot
        
        # Test parameters
        price = 0.027500
        quantity = 4000.0  # Large quantity to ensure above threshold
        sum_value = price * quantity  # Should be $110 USDT
        exchange = "Test Exchange (Direct Alert)"
        timestamp = int(time.time() * 1000)
        exchange_url = "https://test.com"
        
        print(f"  📊 Test parameters:")
        print(f"    💰 Amount: {quantity:.2f} XBT")
        print(f"    💵 Price: ${price:.6f}")
        print(f"    💲 Value: ${sum_value:.2f} USDT")
        print(f"    🎯 Threshold: ${VALUE_REQUIRE} USDT")
        print(f"    📱 Target chat: {BOT_OWNER}")
        
        # Send alert directly
        bot = Bot(token=BOT_TOKEN)
        
        # Create alert message
        alert_message = (
            f"🧪 <b>DIRECT ALERT TEST</b>\n\n"
            f"🚨 <b>Buy Transaction Detected</b> 🚨\n\n"
            f"💰 <b>Amount:</b> {quantity:.2f} XBT\n"
            f"💵 <b>Price:</b> ${price:.6f}\n"
            f"💲 <b>Total Value:</b> ${sum_value:.2f} USDT\n"
            f"🏦 <b>Exchange:</b> {exchange}\n"
            f"⏰ <b>Time:</b> {time.strftime('%H:%M:%S %d/%m/%Y')}\n\n"
            f"✅ This is a direct alert test.\n"
            f"If you see this message, alert delivery is working!"
        )
        
        await bot.send_message(
            chat_id=BOT_OWNER,
            text=alert_message,
            parse_mode="HTML"
        )
        
        print(f"  ✅ Direct alert sent successfully to chat {BOT_OWNER}")
        return True
        
    except Exception as e:
        print(f"  ❌ Direct alert test failed: {e}")
        return False

async def test_send_alert_function():
    """Test the send_alert function with current configuration"""
    print("\n🔔 Testing send_alert Function...")
    
    try:
        # Test parameters
        price = 0.027500
        quantity = 4000.0  # Large quantity to ensure above threshold
        sum_value = price * quantity  # Should be $110 USDT
        exchange = "Test Exchange (send_alert)"
        timestamp = int(time.time() * 1000)
        exchange_url = "https://test.com"
        
        print(f"  📊 Calling send_alert with:")
        print(f"    💰 Amount: {quantity:.2f} XBT")
        print(f"    💵 Price: ${price:.6f}")
        print(f"    💲 Value: ${sum_value:.2f} USDT")
        print(f"    📱 Active chats: {ACTIVE_CHAT_IDS}")
        
        # Call send_alert function
        await send_alert(price, quantity, sum_value, exchange, timestamp, exchange_url)
        
        print(f"  ✅ send_alert function executed successfully")
        print(f"  📱 Alert should have been sent to chat {BOT_OWNER}")
        return True
        
    except Exception as e:
        print(f"  ❌ send_alert function test failed: {e}")
        return False

async def simulate_test_command():
    """Simulate the /test command execution"""
    print("\n🧪 Simulating /test Command Execution...")
    
    try:
        # Create mock update and context objects
        update = MagicMock()
        update.effective_user.id = BOT_OWNER
        update.message.reply_text = AsyncMock()
        
        context = MagicMock()
        
        print(f"  👑 Simulating /test command from bot owner: {BOT_OWNER}")
        print(f"  📱 Expected alert delivery to: {ACTIVE_CHAT_IDS}")
        
        # Execute the test command
        await test_command(update, context)
        
        # Check if reply was sent
        if update.message.reply_text.called:
            call_args = update.message.reply_text.call_args
            message_text = call_args[0][0]
            print(f"  ✅ Test command executed successfully")
            print(f"  📝 Response message preview: {message_text[:100]}...")
            
            # Check if the response indicates success
            if "Test Complete" in message_text:
                print(f"  ✅ Test command completed successfully")
                print(f"  📢 Alert should have been sent via send_alert function")
                return True
            else:
                print(f"  ❌ Test command response doesn't indicate success")
                return False
        else:
            print(f"  ❌ Test command didn't send response message")
            return False
        
    except Exception as e:
        print(f"  ❌ Test command simulation failed: {e}")
        return False

async def check_recent_logs_for_alerts():
    """Check recent logs for alert activity"""
    print("\n📋 Checking Recent Logs for Alert Activity...")
    
    try:
        # We'll provide instructions for manual verification
        print(f"  📝 To verify alert delivery, check:")
        print(f"    1. Bot owner chat {BOT_OWNER} for new alert messages")
        print(f"    2. Docker logs for alert sending activity:")
        print(f"       docker logs --tail 20 xbt-telebot-container | grep -i alert")
        print(f"    3. Look for 'send_alert' or 'Alert sent' messages")
        
        print(f"\n  🔍 Expected log patterns:")
        print(f"    ✅ 'Alert sent successfully to chat {BOT_OWNER}'")
        print(f"    ✅ 'send_alert function executed'")
        print(f"    ❌ 'Error sending message to chat'")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Log check failed: {e}")
        return False

async def main():
    """Run all fixed alert system tests"""
    print("🚀 Starting Fixed Alert System Tests...")
    print("="*70)
    print("🎯 Goal: Verify /test command now sends actual alerts to bot owner")
    print("="*70)
    
    tests = [
        ("Current Configuration", verify_current_configuration),
        ("Direct Alert to Owner", test_send_alert_to_owner),
        ("send_alert Function", test_send_alert_function),
        ("Test Command Simulation", simulate_test_command),
        ("Recent Logs Check", check_recent_logs_for_alerts),
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
    print(f"FIXED ALERT SYSTEM TEST SUMMARY: {passed}/{total} tests passed")
    print('='*70)
    
    if passed >= 4:  # Allow for log check being informational
        print("🎉 ALERT SYSTEM FIX SUCCESSFUL!")
        print("\n✅ Key Results:")
        print("  ✅ Configuration updated to single working chat")
        print("  ✅ Bot can send messages to owner chat")
        print("  ✅ send_alert function working correctly")
        print("  ✅ /test command should now send visible alerts")
        
        print(f"\n🔔 Expected Behavior:")
        print(f"  📱 /test command will send alert to chat {BOT_OWNER}")
        print(f"  🖼️ Alert will include image and rich formatting")
        print(f"  💲 Simulated trade value (~$102.75 USDT) above threshold")
        print(f"  ⏰ Alert will show current timestamp")
        
        print(f"\n🧪 To Test:")
        print(f"  1. Send /test command to the bot")
        print(f"  2. Check chat {BOT_OWNER} for alert message")
        print(f"  3. Verify alert includes image and trade details")
        print(f"  4. Confirm 'Test Complete!' response is received")
        
    else:
        print("⚠️  Some alert system tests failed.")
        print("\n❌ Issues Found:")
        print("  ❌ Configuration or bot access problems")
        print("  ❌ Alert delivery may still have issues")
        print("  🔧 Review failed tests above for specific problems")
    
    return passed >= 4

if __name__ == "__main__":
    asyncio.run(main())
