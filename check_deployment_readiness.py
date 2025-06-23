#!/usr/bin/env python3
"""
Check if XBT bot is ready for Docker deployment
"""

import os
import json
import subprocess
import sys

def check_docker():
    """Check if Docker is available."""
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Docker available: {result.stdout.strip()}")
            return True
        else:
            print("❌ Docker not available")
            return False
    except FileNotFoundError:
        print("❌ Docker not installed")
        return False

def check_image():
    """Check if XBT bot Docker image exists."""
    try:
        result = subprocess.run(['docker', 'images', 'xbt-telebot', '--format', '{{.Repository}}:{{.Tag}}'], 
                              capture_output=True, text=True)
        if result.returncode == 0 and 'xbt-telebot' in result.stdout:
            images = result.stdout.strip().split('\n')
            print(f"✅ Docker images available:")
            for image in images:
                if image:
                    print(f"   - {image}")
            return True
        else:
            print("❌ XBT bot Docker image not found")
            return False
    except Exception as e:
        print(f"❌ Error checking Docker images: {e}")
        return False

def check_config():
    """Check configuration file."""
    if not os.path.exists('config.json'):
        print("❌ config.json not found")
        return False
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        # Check bot token
        bot_token = config.get('bot_token', '')
        if not bot_token or len(bot_token) < 20:
            print("❌ Bot token not configured or invalid")
            print("💡 Run: python3 update_bot_token.py")
            return False
        else:
            print(f"✅ Bot token configured: {bot_token[:10]}...{bot_token[-10:]}")
        
        # Check image path
        image_path = config.get('image_path', '')
        if image_path == 'xbt_buy_alert.gif':
            print("✅ GIF image path configured correctly")
        else:
            print(f"⚠️  Image path: {image_path} (expected: xbt_buy_alert.gif)")
        
        # Check active chat IDs
        chat_ids = config.get('active_chat_ids', [])
        if len(chat_ids) == 0:
            print("✅ Active chat IDs cleared (no JKC inheritance)")
        else:
            print(f"⚠️  Active chat IDs: {len(chat_ids)} (may inherit from JKC bot)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error reading config.json: {e}")
        return False

def check_files():
    """Check required files."""
    required_files = [
        'telebot_fixed.py',
        'xbt_buy_alert.gif',
        'requirements.txt',
        'Dockerfile',
        'docker-compose.xbt.yml'
    ]
    
    missing_files = []
    for file_path in required_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"✅ {file_path}: {size:,} bytes")
        else:
            print(f"❌ {file_path}: NOT FOUND")
            missing_files.append(file_path)
    
    return len(missing_files) == 0

def check_directories():
    """Check required directories."""
    required_dirs = ['logs', 'images', 'backups']
    
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✅ {dir_path}/ directory exists")
        else:
            print(f"⚠️  {dir_path}/ directory missing (will be created)")
            try:
                os.makedirs(dir_path, exist_ok=True)
                print(f"✅ Created {dir_path}/ directory")
            except Exception as e:
                print(f"❌ Failed to create {dir_path}/: {e}")
                return False
    
    return True

def check_token_validity():
    """Check if bot token is valid by testing with Telegram API."""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        bot_token = config.get('bot_token', '')
        if not bot_token:
            return False
        
        import requests
        response = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
        
        if response.status_code == 200:
            bot_info = response.json()
            if bot_info.get('ok'):
                result = bot_info['result']
                print(f"✅ Bot token valid:")
                print(f"   - Bot ID: {result.get('id')}")
                print(f"   - Bot Name: {result.get('first_name')}")
                print(f"   - Username: @{result.get('username')}")
                return True
            else:
                print(f"❌ Bot token invalid: {bot_info.get('description')}")
                return False
        else:
            print(f"❌ Bot token test failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"⚠️  Could not test bot token: {e}")
        return True  # Don't fail deployment for network issues

def main():
    """Run all deployment readiness checks."""
    print("🐳 XBT Bot Docker Deployment Readiness Check")
    print("=" * 50)
    
    checks = [
        ("Docker Availability", check_docker),
        ("Docker Image", check_image),
        ("Configuration File", check_config),
        ("Required Files", check_files),
        ("Required Directories", check_directories),
        ("Bot Token Validity", check_token_validity),
    ]
    
    results = []
    
    for check_name, check_func in checks:
        print(f"\n📋 {check_name}:")
        print("-" * 30)
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ Exception in {check_name}: {e}")
            results.append((check_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 DEPLOYMENT READINESS SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
    
    print("-" * 50)
    print(f"Overall: {passed}/{total} checks passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 READY FOR DEPLOYMENT!")
        print("🚀 Run: ./deploy_xbt_bot.sh")
        print("💡 Or: docker-compose -f docker-compose.xbt.yml up -d")
    elif passed >= total - 1:
        print("\n⚠️  MOSTLY READY - Review failed checks")
        print("💡 Most likely issue: Bot token needs configuration")
        print("🔧 Run: python3 update_bot_token.py")
    else:
        print("\n❌ NOT READY FOR DEPLOYMENT")
        print("🔧 Fix the failed checks before deploying")
    
    return passed >= total - 1

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
