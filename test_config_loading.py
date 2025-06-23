#!/usr/bin/env python3
"""
Test configuration loading with new GIF path
"""

import json
import os
import sys

def test_config_loading():
    """Test that configuration loads correctly with GIF path."""
    print("🧪 Testing configuration loading...")
    
    try:
        # Load config.json
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        print("✅ Configuration loaded successfully")
        
        # Check image path
        image_path = config.get("image_path", "")
        print(f"📁 Image path: {image_path}")
        
        if image_path == "xbt_buy_alert.gif":
            print("✅ Image path is correct")
        else:
            print(f"❌ Image path incorrect: expected 'xbt_buy_alert.gif', got '{image_path}'")
            return False
        
        # Check if the image file exists
        if os.path.exists(image_path):
            print(f"✅ Image file exists: {image_path}")
            file_size = os.path.getsize(image_path)
            print(f"📊 File size: {file_size:,} bytes")
        else:
            print(f"❌ Image file not found: {image_path}")
            return False
        
        # Test other essential config values
        essential_keys = ["bot_token", "value_require", "bot_owner"]
        for key in essential_keys:
            if key in config:
                if key == "bot_token":
                    print(f"✅ {key}: [REDACTED]")
                else:
                    print(f"✅ {key}: {config[key]}")
            else:
                print(f"❌ Missing essential config key: {key}")
                return False
        
        print("✅ All essential configuration keys present")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        return False
    except FileNotFoundError:
        print("❌ config.json not found")
        return False
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return False

def test_image_loading_simulation():
    """Simulate the bot's image loading process."""
    print("\n🧪 Testing image loading simulation...")
    
    try:
        # Load config
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        image_path = config.get("image_path", "")
        
        # Simulate bot's image loading
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            print(f"✅ Successfully loaded {len(image_data):,} bytes from {image_path}")
            
            # Check if it's a valid GIF
            if image_data.startswith(b'GIF'):
                print("✅ Valid GIF format detected")
                
                # Check for animation
                if b'\x21\xF9' in image_data:
                    print("✅ Animated GIF detected")
                else:
                    print("ℹ️  Static GIF (no animation frames)")
                
                return True
            else:
                print("❌ Invalid GIF format")
                return False
        else:
            print(f"❌ Image file not found: {image_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error in image loading simulation: {e}")
        return False

def main():
    """Run configuration tests."""
    print("🚀 XBT Bot Configuration Tests")
    print("=" * 40)
    
    tests = [
        test_config_loading,
        test_image_loading_simulation
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test exception: {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 40)
    print("📊 CONFIGURATION TEST SUMMARY")
    print("=" * 40)
    print(f"Tests passed: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All configuration tests passed!")
        print("✅ Bot is ready to use the new GIF for alerts")
    else:
        print("❌ Some tests failed - check configuration")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
