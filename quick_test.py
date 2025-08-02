#!/usr/bin/env python3
"""
Quick validation test for the JKC Bot Data Reliability Test Suite
================================================================

This script performs a quick validation to ensure the test framework
is working correctly before running the full test suite.
"""

import asyncio
import sys
import time

# Add the app directory to Python path
sys.path.append('/app')

async def quick_validation():
    """Run quick validation tests"""
    print("🧪 Quick Validation Test for JKC Bot")
    print("="*50)
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Import bot modules
    total_tests += 1
    print("1️⃣ Testing bot module imports...")
    try:
        from telebot_fixed import (
            get_nonkyc_ticker, get_livecoinwatch_data,
            calculate_combined_volume_periods
        )
        print("   ✅ Bot modules imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ Failed to import bot modules: {e}")
    
    # Test 2: NonKYC API connectivity
    total_tests += 1
    print("2️⃣ Testing NonKYC API connectivity...")
    try:
        start_time = time.time()
        data = await get_nonkyc_ticker()
        response_time = time.time() - start_time
        
        if data and data.get("lastPriceNumber", 0) > 0:
            print(f"   ✅ NonKYC API working (${data.get('lastPriceNumber'):.6f}, {response_time:.2f}s)")
            tests_passed += 1
        else:
            print("   ❌ NonKYC API returned invalid data")
    except Exception as e:
        print(f"   ❌ NonKYC API failed: {e}")
    
    # Test 3: LiveCoinWatch API connectivity
    total_tests += 1
    print("3️⃣ Testing LiveCoinWatch API connectivity...")
    try:
        start_time = time.time()
        data = await get_livecoinwatch_data()
        response_time = time.time() - start_time
        
        if data and data.get("rate", 0) > 0:
            print(f"   ✅ LiveCoinWatch API working (${data.get('rate'):.6f}, {response_time:.2f}s)")
            tests_passed += 1
        else:
            print("   ❌ LiveCoinWatch API returned invalid data")
    except Exception as e:
        print(f"   ❌ LiveCoinWatch API failed: {e}")
    
    # Test 4: Volume calculation
    total_tests += 1
    print("4️⃣ Testing volume calculation...")
    try:
        start_time = time.time()
        data = await calculate_combined_volume_periods()
        response_time = time.time() - start_time
        
        if data and "combined" in data:
            combined = data["combined"]
            print(f"   ✅ Volume calculation working (24h: ${combined.get('24h', 0):,.0f}, {response_time:.2f}s)")
            tests_passed += 1
        else:
            print("   ❌ Volume calculation returned invalid data")
    except Exception as e:
        print(f"   ❌ Volume calculation failed: {e}")
    
    # Test 5: Configuration loading
    total_tests += 1
    print("5️⃣ Testing configuration loading...")
    try:
        import json
        with open('/app/config.json', 'r') as f:
            config = json.load(f)
        
        if config.get("bot_token") and config.get("value_require"):
            print(f"   ✅ Configuration loaded (threshold: ${config.get('value_require')} USDT)")
            tests_passed += 1
        else:
            print("   ❌ Configuration missing required fields")
    except Exception as e:
        print(f"   ❌ Configuration loading failed: {e}")
    
    # Summary
    print("\n" + "="*50)
    success_rate = (tests_passed / total_tests) * 100
    print(f"📊 Quick Validation Results: {tests_passed}/{total_tests} ({success_rate:.1f}%)")
    
    if success_rate >= 80:
        print("✅ System ready for comprehensive testing!")
        return True
    else:
        print("❌ System not ready - fix issues before running full tests")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(quick_validation())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"❌ Quick validation failed: {e}")
        sys.exit(1)
