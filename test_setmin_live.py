#!/usr/bin/env python3
"""
Live Test for /setmin Command Configuration Save
Tests the actual configuration save functionality in the running container
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
    set_minimum_command, set_minimum_input, save_config,
    BOT_OWNER, VALUE_REQUIRE, CONFIG, INPUT_NUMBER, ConversationHandler
)

async def test_config_save_functionality():
    """Test that configuration save works with read-write mount"""
    print("💾 Testing Configuration Save Functionality...")
    
    # Test 1: Verify current config can be read
    try:
        with open('/app/config.json', 'r') as f:
            current_config = json.load(f)
        print(f"  ✅ Current config read successfully")
        print(f"  📊 Current value_require: {current_config.get('value_require', 'NOT_FOUND')}")
    except Exception as e:
        print(f"  ❌ Failed to read current config: {e}")
        return False
    
    # Test 2: Test save_config function directly
    try:
        # Make a small test change
        test_config = current_config.copy()
        test_config['test_timestamp'] = time.time()
        
        save_config(test_config)
        print(f"  ✅ save_config() function executed successfully")
        
        # Verify the change was written
        with open('/app/config.json', 'r') as f:
            saved_config = json.load(f)
        
        if 'test_timestamp' in saved_config:
            print(f"  ✅ Configuration changes written to file")
        else:
            print(f"  ❌ Configuration changes not found in file")
            return False
        
        # Clean up test change
        del saved_config['test_timestamp']
        save_config(saved_config)
        print(f"  ✅ Test cleanup completed")
        
    except Exception as e:
        print(f"  ❌ save_config() function failed: {e}")
        return False
    
    # Test 3: Test file permissions
    try:
        # Check if we can write to the config file
        with open('/app/config.json', 'a') as f:
            pass  # Just test opening for append
        print(f"  ✅ Config file has write permissions")
    except Exception as e:
        print(f"  ❌ Config file write permission denied: {e}")
        return False
    
    return True

async def test_setmin_input_with_real_save():
    """Test setmin input function with actual file save"""
    print("\n🔧 Testing /setmin Input with Real Configuration Save...")
    
    # Store original value for restoration
    original_value = VALUE_REQUIRE
    
    # Test with a new value
    test_value = 150.0
    
    # Create mock update object
    update = MagicMock()
    update.effective_user.id = BOT_OWNER
    update.message.text = str(test_value)
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    
    try:
        # Execute the setmin input function
        result = await set_minimum_input(update, context)
        
        # Check if function completed successfully
        if result == ConversationHandler.END:
            print(f"  ✅ set_minimum_input() completed successfully")
        else:
            print(f"  ❌ set_minimum_input() returned unexpected result: {result}")
            return False
        
        # Check if success message was sent
        if update.message.reply_text.called:
            call_args = update.message.reply_text.call_args
            message_text = call_args[0][0]
            
            if "Successfully!" in message_text:
                print(f"  ✅ Success message sent to user")
                print(f"  📝 Message preview: {message_text[:100]}...")
            else:
                print(f"  ❌ Success message not found in response")
                print(f"  📝 Actual message: {message_text}")
                return False
        else:
            print(f"  ❌ No message sent to user")
            return False
        
        # Verify the configuration was actually saved
        try:
            with open('/app/config.json', 'r') as f:
                saved_config = json.load(f)
            
            saved_value = saved_config.get('value_require')
            if saved_value == test_value:
                print(f"  ✅ Configuration saved correctly: {saved_value}")
            else:
                print(f"  ❌ Configuration not saved correctly. Expected: {test_value}, Got: {saved_value}")
                return False
        except Exception as e:
            print(f"  ❌ Failed to verify saved configuration: {e}")
            return False
        
        # Restore original value
        restore_update = MagicMock()
        restore_update.effective_user.id = BOT_OWNER
        restore_update.message.text = str(original_value)
        restore_update.message.reply_text = AsyncMock()
        
        await set_minimum_input(restore_update, context)
        print(f"  ✅ Original value restored: {original_value}")
        
    except Exception as e:
        print(f"  ❌ setmin input test failed: {e}")
        return False
    
    return True

async def test_setmin_command_flow():
    """Test the complete /setmin command flow"""
    print("\n🎯 Testing Complete /setmin Command Flow...")
    
    # Test 1: Admin access
    update = MagicMock()
    update.effective_user.id = BOT_OWNER
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    
    try:
        with patch('telebot_fixed.is_admin', return_value=True):
            result = await set_minimum_command(update, context)
            
            if result == INPUT_NUMBER:
                print(f"  ✅ Admin user granted access to setmin command")
            else:
                print(f"  ❌ Admin access failed. Result: {result}")
                return False
            
            # Check setup message
            if update.message.reply_text.called:
                call_args = update.message.reply_text.call_args
                message_text = call_args[0][0]
                
                if "Set Minimum Alert Threshold" in message_text:
                    print(f"  ✅ Setup prompt sent correctly")
                else:
                    print(f"  ❌ Setup prompt not found")
                    return False
            else:
                print(f"  ❌ No setup message sent")
                return False
    
    except Exception as e:
        print(f"  ❌ setmin command test failed: {e}")
        return False
    
    # Test 2: Regular user denied
    update.effective_user.id = 999999999  # Regular user
    update.message.reply_text.reset_mock()
    
    try:
        with patch('telebot_fixed.is_admin', return_value=False):
            result = await set_minimum_command(update, context)
            
            if result == ConversationHandler.END:
                print(f"  ✅ Regular user properly denied access")
            else:
                print(f"  ❌ Regular user access control failed. Result: {result}")
                return False
            
            # Check denial message
            if update.message.reply_text.called:
                call_args = update.message.reply_text.call_args
                message_text = call_args[0][0]
                
                if "Permission Denied" in message_text:
                    print(f"  ✅ Permission denied message sent correctly")
                else:
                    print(f"  ❌ Permission denied message not found")
                    return False
            else:
                print(f"  ❌ No denial message sent")
                return False
    
    except Exception as e:
        print(f"  ❌ Regular user denial test failed: {e}")
        return False
    
    return True

async def main():
    """Run all live /setmin tests"""
    print("🚀 Starting Live /setmin Command Tests...")
    print("="*70)
    
    tests = [
        ("Configuration Save Functionality", test_config_save_functionality),
        ("Setmin Input with Real Save", test_setmin_input_with_real_save),
        ("Complete Setmin Command Flow", test_setmin_command_flow),
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
    print(f"LIVE SETMIN TEST SUMMARY: {passed}/{total} tests passed")
    print('='*70)
    
    if passed == total:
        print("🎉 ALL LIVE SETMIN TESTS PASSED!")
        print("\n✅ /setmin Command Status:")
        print("  ✅ Configuration file has read-write access")
        print("  ✅ save_config() function working correctly")
        print("  ✅ File permissions allow configuration updates")
        print("  ✅ Complete command flow functional")
        print("  ✅ Admin access control working")
        print("  ✅ User feedback comprehensive and accurate")
        
        print(f"\n🤖 The /setmin command configuration save issue is RESOLVED!")
        return True
    else:
        print("⚠️  Some live setmin tests failed. Please review the results above.")
        return False

if __name__ == "__main__":
    asyncio.run(main())
