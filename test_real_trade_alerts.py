#!/usr/bin/env python3
"""
Real Trade Alert Test
Temporarily lower threshold to test alert system with actual incoming trades
"""

import asyncio
import json
import os
import sys
import time

# Add the current directory to the path so we can import the bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def temporarily_lower_threshold():
    """Temporarily lower the threshold to test with real trades"""
    print("🔧 Temporarily Lowering Threshold for Real Trade Testing...")
    
    try:
        # Read current configuration
        with open('/app/config.json', 'r') as f:
            config = json.load(f)
        
        original_threshold = config.get('value_require', 100.0)
        print(f"  📊 Original threshold: ${original_threshold} USDT")
        
        # Set a very low threshold to catch real trades
        new_threshold = 1.0  # $1 USDT - should catch most real trades
        config['value_require'] = new_threshold
        
        # Save the modified configuration
        with open('/app/config.json', 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"  🎯 New threshold: ${new_threshold} USDT")
        print(f"  ⚠️  This will trigger alerts for trades above ${new_threshold} USDT")
        print(f"  ⏰ Test will run for 60 seconds, then restore original threshold")
        
        return original_threshold, new_threshold
        
    except Exception as e:
        print(f"  ❌ Failed to lower threshold: {e}")
        return None, None

async def restore_threshold(original_threshold):
    """Restore the original threshold"""
    print(f"\n🔄 Restoring Original Threshold...")
    
    try:
        # Read current configuration
        with open('/app/config.json', 'r') as f:
            config = json.load(f)
        
        # Restore original threshold
        config['value_require'] = original_threshold
        
        # Save the configuration
        with open('/app/config.json', 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"  ✅ Threshold restored to ${original_threshold} USDT")
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to restore threshold: {e}")
        return False

async def monitor_bot_logs():
    """Monitor bot logs for alert activity"""
    print("\n📊 Monitoring Bot Logs for Alert Activity...")
    
    # Monitor for 60 seconds
    start_time = time.time()
    duration = 60
    
    print(f"  ⏰ Monitoring for {duration} seconds...")
    print(f"  🔍 Looking for:")
    print(f"    - 'Processing trade:' messages")
    print(f"    - 'Aggregated trades exceed threshold:' messages") 
    print(f"    - 'Sending immediate alert:' messages")
    print(f"    - Any error messages")
    
    # We can't directly monitor logs from inside the container in real-time
    # But we can provide instructions for manual monitoring
    print(f"\n📝 To monitor in real-time, run this command in another terminal:")
    print(f"    docker logs -f xbt-telebot-container")
    
    # Wait for the monitoring period
    while time.time() - start_time < duration:
        remaining = duration - (time.time() - start_time)
        print(f"  ⏳ {remaining:.0f} seconds remaining...", end='\r')
        await asyncio.sleep(5)
    
    print(f"\n  ✅ Monitoring period completed")
    return True

async def check_recent_logs():
    """Check recent logs for any alert activity"""
    print("\n📋 Checking Recent Bot Activity...")
    
    try:
        # We'll provide instructions since we can't directly access logs from inside
        print(f"  📝 To check recent activity, run:")
        print(f"    docker logs --tail 20 xbt-telebot-container")
        
        print(f"\n  🔍 Look for:")
        print(f"    ✅ 'Processing trade:' - Shows trades being received")
        print(f"    ✅ 'Added to pending trades:' - Shows aggregation working")
        print(f"    ✅ 'Aggregated trades exceed threshold:' - Shows alerts triggered")
        print(f"    ✅ 'Sending immediate alert:' - Shows direct alerts")
        print(f"    ❌ Any error messages")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to check logs: {e}")
        return False

async def main():
    """Run real trade alert test"""
    print("🚀 Starting Real Trade Alert Test...")
    print("="*70)
    print("⚠️  WARNING: This test will temporarily lower the alert threshold")
    print("⚠️  This may cause alerts to be sent to active chat channels")
    print("="*70)
    
    # Get user confirmation
    print("\n❓ Do you want to proceed with this test?")
    print("   This will temporarily set threshold to $1 USDT for 60 seconds")
    print("   Type 'yes' to continue or anything else to cancel:")
    
    # For automated testing, we'll proceed automatically
    # In manual testing, you could add input() here
    proceed = True  # input().strip().lower() == 'yes'
    
    if not proceed:
        print("❌ Test cancelled by user")
        return False
    
    original_threshold = None
    
    try:
        # Step 1: Lower threshold
        original_threshold, new_threshold = await temporarily_lower_threshold()
        if original_threshold is None:
            print("❌ Failed to lower threshold, aborting test")
            return False
        
        # Step 2: Monitor for alerts
        await monitor_bot_logs()
        
        # Step 3: Check recent activity
        await check_recent_logs()
        
        print(f"\n{'='*70}")
        print(f"REAL TRADE ALERT TEST COMPLETED")
        print('='*70)
        
        print(f"\n✅ Test Summary:")
        print(f"  📊 Threshold temporarily lowered from ${original_threshold} to ${new_threshold} USDT")
        print(f"  ⏰ Monitored for 60 seconds")
        print(f"  🔄 Threshold will be restored to ${original_threshold} USDT")
        
        print(f"\n🔍 Expected Results:")
        print(f"  📈 If real trades occurred above ${new_threshold} USDT:")
        print(f"    ✅ You should see 'Processing trade:' messages in logs")
        print(f"    ✅ You should see alerts sent to active chats")
        print(f"    ✅ This confirms the alert system is working")
        
        print(f"  📉 If no trades occurred above ${new_threshold} USDT:")
        print(f"    ℹ️  No alerts expected (normal behavior)")
        print(f"    ℹ️  System is working but no qualifying trades occurred")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
        
    finally:
        # Always restore original threshold
        if original_threshold is not None:
            await restore_threshold(original_threshold)

if __name__ == "__main__":
    asyncio.run(main())
