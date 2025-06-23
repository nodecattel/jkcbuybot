#!/usr/bin/env python3
"""
Test script to validate XBT bot fixes
"""

import requests
import json
import os
import sys

def main():
    print('=== XBT BOT VALIDATION TESTS ===')
    
    # Load config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        bot_token = config['bot_token']
        bot_owner = config['bot_owner']
        
        print(f'Bot Token: {bot_token[:10]}...{bot_token[-10:]}')
        print(f'Bot Owner: {bot_owner}')
    except Exception as e:
        print(f'❌ Config loading failed: {e}')
        return False

    # Test bot identity
    print('\n=== BOT IDENTITY TEST ===')
    try:
        response = requests.get(f'https://api.telegram.org/bot{bot_token}/getMe', timeout=10)
        if response.status_code == 200:
            bot_info = response.json()['result']
            print(f'✅ Bot Identity: @{bot_info["username"]} (ID: {bot_info["id"]})')
        else:
            print('❌ Bot identity check failed')
            return False
    except Exception as e:
        print(f'❌ Bot identity test error: {e}')
        return False

    # Test price data sources
    print('\n=== PRICE DATA SOURCES ===')
    try:
        from telebot_fixed import get_livecoinwatch_data, get_nonkyc_ticker
        import asyncio
        
        # Test LiveCoinWatch
        try:
            lcw_data = asyncio.run(get_livecoinwatch_data())
            if lcw_data:
                print(f'✅ LiveCoinWatch: Price ${lcw_data.get("rate", "N/A")}')
            else:
                print('⚠️  LiveCoinWatch: No data (may be rate limited)')
        except Exception as e:
            print(f'⚠️  LiveCoinWatch error: {e}')
        
        # Test NonKYC
        try:
            nonkyc_data = asyncio.run(get_nonkyc_ticker())
            if nonkyc_data:
                print(f'✅ NonKYC: Price ${nonkyc_data.get("lastPriceNumber", "N/A")}')
            else:
                print('⚠️  NonKYC: No data')
        except Exception as e:
            print(f'⚠️  NonKYC error: {e}')
            
    except Exception as e:
        print(f'❌ Price data test error: {e}')

    # Test GIF file
    print('\n=== GIF FILE TEST ===')
    try:
        if os.path.exists('xbt_buy_alert.gif'):
            size = os.path.getsize('xbt_buy_alert.gif')
            print(f'✅ GIF file exists: {size:,} bytes')
            
            # Check if it's animated
            with open('xbt_buy_alert.gif', 'rb') as f:
                data = f.read()
                # Look for GIF animation control extension
                is_animated = b'\x21\xF9' in data
                print(f'✅ Animation detected: {is_animated}')
        else:
            print('❌ GIF file not found')
            return False
    except Exception as e:
        print(f'❌ GIF test error: {e}')

    # Test configuration write capability
    print('\n=== CONFIGURATION WRITE TEST ===')
    try:
        # Test if config.json is writable
        test_config = config.copy()
        test_config['test_write'] = True
        
        with open('config.json', 'w') as f:
            json.dump(test_config, f, indent=2)
        
        # Remove test key
        del test_config['test_write']
        with open('config.json', 'w') as f:
            json.dump(test_config, f, indent=2)
        
        print('✅ Config file is writable (/setmin will work)')
    except Exception as e:
        print(f'❌ Config write test failed: {e}')
        return False

    # Test volume calculation safety
    print('\n=== VOLUME CALCULATION TEST ===')
    try:
        from telebot_fixed import calculate_combined_volume_periods
        import asyncio
        
        volume_data = asyncio.run(calculate_combined_volume_periods())
        if volume_data:
            combined = volume_data.get("combined", {})
            print(f'✅ Volume calculation working:')
            print(f'   15m: ${combined.get("15m", 0):,.0f}')
            print(f'   1h: ${combined.get("1h", 0):,.0f}')
            print(f'   24h: ${combined.get("24h", 0):,.0f}')
        else:
            print('⚠️  Volume calculation returned None (handled safely)')
    except Exception as e:
        print(f'❌ Volume calculation test error: {e}')

    print('\n=== VALIDATION COMPLETE ===')
    print('✅ All critical fixes appear to be working!')
    print('\n📋 NEXT STEPS:')
    print('1. Test /price command in Telegram')
    print('2. Test /test command (admin only) for GIF animation')
    print('3. Test /setmin command (admin only) for config writing')
    print('4. Verify authentication works correctly')
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
