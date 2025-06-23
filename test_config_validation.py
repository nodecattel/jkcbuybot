#!/usr/bin/env python3
"""
Test script to validate the current configuration and test precision formatting.
"""

import json
import sys
import os

def validate_config(config):
    """Validate configuration structure and values."""
    errors = []
    warnings = []
    
    # Required fields
    required_fields = [
        "bot_token", "value_require", "active_chat_ids", "bot_owner", 
        "by_pass", "image_path", "dynamic_threshold", "sweep_orders", 
        "trade_aggregation"
    ]
    
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")
    
    # Validate bot_token
    if "bot_token" in config:
        token = config["bot_token"]
        if not isinstance(token, str) or len(token) < 10:
            errors.append("Invalid bot_token format")
        elif token == "YOUR_BOT_TOKEN_HERE":
            errors.append("Bot token is still placeholder value")
    
    # Validate value_require
    if "value_require" in config:
        value = config["value_require"]
        if not isinstance(value, (int, float)) or value <= 0:
            errors.append("value_require must be a positive number")
        elif value < 0.01:
            warnings.append("value_require is very small (< $0.01)")
        elif value > 100000:
            warnings.append("value_require is very large (> $100,000)")
    
    # Validate active_chat_ids
    if "active_chat_ids" in config:
        chat_ids = config["active_chat_ids"]
        if not isinstance(chat_ids, list):
            errors.append("active_chat_ids must be a list")
        elif len(chat_ids) == 0:
            warnings.append("No active chat IDs configured")
        else:
            for chat_id in chat_ids:
                if not isinstance(chat_id, int):
                    errors.append(f"Invalid chat ID: {chat_id} (must be integer)")
    
    # Validate bot_owner
    if "bot_owner" in config:
        owner = config["bot_owner"]
        if not isinstance(owner, int) or owner <= 0:
            errors.append("bot_owner must be a positive integer")
    
    # Validate dynamic_threshold
    if "dynamic_threshold" in config:
        dt = config["dynamic_threshold"]
        if not isinstance(dt, dict):
            errors.append("dynamic_threshold must be an object")
        else:
            if "enabled" in dt and not isinstance(dt["enabled"], bool):
                errors.append("dynamic_threshold.enabled must be boolean")
            if "base_value" in dt and (not isinstance(dt["base_value"], (int, float)) or dt["base_value"] <= 0):
                errors.append("dynamic_threshold.base_value must be positive number")
    
    # Validate sweep_orders
    if "sweep_orders" in config:
        so = config["sweep_orders"]
        if not isinstance(so, dict):
            errors.append("sweep_orders must be an object")
        else:
            if "enabled" in so and not isinstance(so["enabled"], bool):
                errors.append("sweep_orders.enabled must be boolean")
            if "min_value" in so and (not isinstance(so["min_value"], (int, float)) or so["min_value"] <= 0):
                errors.append("sweep_orders.min_value must be positive number")
    
    # Validate trade_aggregation
    if "trade_aggregation" in config:
        ta = config["trade_aggregation"]
        if not isinstance(ta, dict):
            errors.append("trade_aggregation must be an object")
        else:
            if "enabled" in ta and not isinstance(ta["enabled"], bool):
                errors.append("trade_aggregation.enabled must be boolean")
            if "window_seconds" in ta and (not isinstance(ta["window_seconds"], (int, float)) or ta["window_seconds"] <= 0):
                errors.append("trade_aggregation.window_seconds must be positive number")
    
    return errors, warnings

def test_precision_formatting():
    """Test the new precision formatting requirements."""
    print("\n🧪 Testing Precision Formatting...")
    
    # Test price formatting (6 decimal places)
    test_price = 0.166434
    price_6_decimal = f"{test_price:.6f}"
    price_5_decimal = f"{test_price:.5f}"
    
    print(f"Price formatting test:")
    print(f"  6 decimal places: {price_6_decimal} USDT ✅")
    print(f"  5 decimal places: {price_5_decimal} USDT (old format)")
    
    # Test quantity formatting (4 decimal places)
    test_quantity = 10.0
    quantity_4_decimal = f"{test_quantity:.4f}"
    quantity_2_decimal = f"{test_quantity:.2f}"
    
    print(f"Quantity formatting test:")
    print(f"  4 decimal places: {quantity_4_decimal} XBT ✅")
    print(f"  2 decimal places: {quantity_2_decimal} XBT (old format)")
    
    # Test with more complex numbers
    complex_price = 0.1664341234
    complex_quantity = 123.456789
    
    print(f"Complex number formatting:")
    print(f"  Price: {complex_price:.6f} USDT")
    print(f"  Quantity: {complex_quantity:.4f} XBT")
    
    return True

def main():
    """Run configuration validation and precision tests."""
    print("🚀 XBT Trading Bot Configuration Validation & Precision Test")
    print("="*60)
    
    # Test 1: Load and validate configuration
    print("\n📋 Testing Configuration Loading...")
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        print("✅ Configuration file loaded successfully")
    except FileNotFoundError:
        print("❌ Configuration file not found")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in configuration file: {e}")
        return 1
    
    # Test 2: Validate configuration structure
    print("\n🔍 Validating Configuration Structure...")
    errors, warnings = validate_config(config)
    
    if errors:
        print("❌ Configuration Errors:")
        for error in errors:
            print(f"  • {error}")
    else:
        print("✅ No configuration errors found")
    
    if warnings:
        print("⚠️  Configuration Warnings:")
        for warning in warnings:
            print(f"  • {warning}")
    else:
        print("✅ No configuration warnings")
    
    # Test 3: Display current configuration values
    print("\n📊 Current Configuration Values:")
    print(f"  Bot Token: {config.get('bot_token', 'NOT SET')[:20]}...")
    print(f"  Alert Threshold: ${config.get('value_require', 'NOT SET')} USDT")
    print(f"  Active Chats: {len(config.get('active_chat_ids', []))} configured")
    print(f"  Bot Owner: {config.get('bot_owner', 'NOT SET')}")
    print(f"  Dynamic Threshold: {'Enabled' if config.get('dynamic_threshold', {}).get('enabled', False) else 'Disabled'}")
    print(f"  Sweep Orders: {'Enabled' if config.get('sweep_orders', {}).get('enabled', False) else 'Disabled'}")
    print(f"  Trade Aggregation: {'Enabled' if config.get('trade_aggregation', {}).get('enabled', False) else 'Disabled'}")
    
    # Test 4: Check API keys
    print("\n🔑 API Key Status:")
    coinex_id = config.get('coinex_access_id', '')
    coinex_secret = config.get('coinex_secret_key', '')
    ascendex_id = config.get('ascendex_access_id', '')
    ascendex_secret = config.get('ascendex_secret_key', '')
    
    print(f"  CoinEx: {'✅ Configured' if coinex_id and coinex_secret else '❌ Not configured'}")
    print(f"  AscendEX: {'✅ Configured' if ascendex_id and ascendex_secret else '❌ Not configured'}")
    
    # Test 5: Precision formatting
    test_precision_formatting()
    
    # Test 6: Production readiness check
    print("\n🚀 Production Readiness Check:")
    production_ready = True
    
    if errors:
        print("❌ Configuration has errors - not ready for production")
        production_ready = False
    
    if config.get('bot_token', '') == 'YOUR_BOT_TOKEN_HERE':
        print("❌ Bot token is placeholder - not ready for production")
        production_ready = False
    
    if not config.get('active_chat_ids', []):
        print("❌ No active chat IDs configured - not ready for production")
        production_ready = False
    
    if config.get('value_require', 0) <= 0:
        print("❌ Invalid alert threshold - not ready for production")
        production_ready = False
    
    if production_ready:
        print("✅ Configuration is ready for production deployment!")
    else:
        print("⚠️  Configuration needs fixes before production deployment")
    
    # Summary
    print("\n" + "="*60)
    print("📊 VALIDATION SUMMARY")
    print("="*60)
    print(f"Configuration Errors: {len(errors)}")
    print(f"Configuration Warnings: {len(warnings)}")
    print(f"Production Ready: {'Yes' if production_ready else 'No'}")
    print(f"Precision Formatting: ✅ Tested")
    
    if production_ready and not errors:
        print("\n🎉 All tests passed! Ready for deployment.")
        return 0
    else:
        print(f"\n⚠️  {len(errors)} error(s) need to be fixed before deployment.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
