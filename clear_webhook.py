#!/usr/bin/env python3
"""
Clear Telegram webhook and resolve API conflicts for JKC bot.
This script helps resolve "Conflict: terminated by other getUpdates request" errors.
"""

import json
import requests
import sys
import time

def load_bot_token():
    """Load bot token from config.json"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            return config.get('bot_token', '')
    except Exception as e:
        print(f"Error loading config: {e}")
        return None

def clear_webhook(bot_token):
    """Clear any existing webhook for the bot"""
    url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    
    try:
        response = requests.post(url, json={"drop_pending_updates": True}, timeout=10)
        result = response.json()
        
        if result.get('ok'):
            print("✅ Webhook cleared successfully")
            return True
        else:
            print(f"❌ Failed to clear webhook: {result.get('description', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Error clearing webhook: {e}")
        return False

def get_bot_info(bot_token):
    """Get bot information to verify token is working"""
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    
    try:
        response = requests.get(url, timeout=10)
        result = response.json()
        
        if result.get('ok'):
            bot_info = result.get('result', {})
            print(f"✅ Bot info: @{bot_info.get('username', 'unknown')} ({bot_info.get('first_name', 'Unknown')})")
            return True
        else:
            print(f"❌ Failed to get bot info: {result.get('description', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Error getting bot info: {e}")
        return False

def get_webhook_info(bot_token):
    """Get current webhook information"""
    url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
    
    try:
        response = requests.get(url, timeout=10)
        result = response.json()
        
        if result.get('ok'):
            webhook_info = result.get('result', {})
            webhook_url = webhook_info.get('url', '')
            pending_updates = webhook_info.get('pending_update_count', 0)
            
            if webhook_url:
                print(f"📡 Active webhook: {webhook_url}")
                print(f"📊 Pending updates: {pending_updates}")
            else:
                print("📡 No webhook configured (using polling)")
                
            return webhook_info
        else:
            print(f"❌ Failed to get webhook info: {result.get('description', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"❌ Error getting webhook info: {e}")
        return None

def main():
    print("🔧 JKC Bot Telegram API Conflict Resolver")
    print("=" * 50)
    
    # Load bot token
    bot_token = load_bot_token()
    if not bot_token:
        print("❌ Could not load bot token from config.json")
        sys.exit(1)
    
    print(f"🤖 Using bot token: {bot_token[:10]}...{bot_token[-5:]}")
    
    # Check bot info
    print("\n1. Checking bot information...")
    if not get_bot_info(bot_token):
        print("❌ Bot token appears to be invalid")
        sys.exit(1)
    
    # Get webhook info
    print("\n2. Checking webhook status...")
    webhook_info = get_webhook_info(bot_token)
    
    # Clear webhook
    print("\n3. Clearing webhook...")
    if clear_webhook(bot_token):
        print("✅ Webhook cleared successfully")
    else:
        print("❌ Failed to clear webhook")
        sys.exit(1)
    
    # Wait a moment for Telegram servers to process
    print("\n4. Waiting for Telegram servers to process...")
    time.sleep(5)
    
    # Verify webhook is cleared
    print("\n5. Verifying webhook is cleared...")
    final_webhook_info = get_webhook_info(bot_token)
    
    if final_webhook_info and not final_webhook_info.get('url'):
        print("✅ Webhook successfully cleared - bot should now work with polling")
    else:
        print("⚠️ Webhook may still be active - manual intervention may be required")
    
    print("\n" + "=" * 50)
    print("🎉 Conflict resolution completed!")
    print("💡 You can now restart your JKC bot container")
    print("🔄 Command: docker restart jkc-telebot-container")

if __name__ == "__main__":
    main()
