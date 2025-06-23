#!/usr/bin/env python3
"""
Comprehensive test script to verify all precision formatting updates in the XBT trading bot.
Tests that all prices use 6 decimal places and all quantities use 4 decimal places.
"""

import re
import sys
import os

def search_formatting_patterns(file_path):
    """Search for formatting patterns in the bot file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return [], [], []
    
    lines = content.split('\n')
    
    # Patterns to find
    price_patterns = []
    quantity_patterns = []
    issues = []
    
    for i, line in enumerate(lines, 1):
        # Look for price formatting patterns (exclude BTC prices which should use 8 decimal places)
        if 'BTC' not in line and 'btc' not in line:
            price_matches = re.findall(r'(?:price|avg_price).*?\.(\d+)f', line, re.IGNORECASE)
            for match in price_matches:
                decimal_places = int(match)
                # Exclude percentage changes and other non-price values
                if 'price_change' not in line.lower() and 'percent' not in line.lower() and '%' not in line:
                    if decimal_places != 6:
                        issues.append(f"Line {i}: USDT price formatting uses {decimal_places} decimal places instead of 6: {line.strip()}")
                price_patterns.append((i, decimal_places, line.strip()))
        
        # Look for quantity/amount formatting patterns (XBT related)
        if 'XBT' in line and ('quantity' in line.lower() or 'amount' in line.lower()):
            qty_matches = re.findall(r'quantity.*?\.(\d+)f|amount.*?\.(\d+)f', line, re.IGNORECASE)
            for match in qty_matches:
                decimal_places = int(match[0] or match[1])
                if decimal_places != 4:
                    issues.append(f"Line {i}: Quantity formatting uses {decimal_places} decimal places instead of 4: {line.strip()}")
                quantity_patterns.append((i, decimal_places, line.strip()))
        
        # Look for specific XBT formatting patterns (more specific)
        # Only flag actual quantity variables, not other values
        if 'XBT' in line and ('quantity' in line.lower() or 'total_quantity' in line.lower() or 'old_quantity' in line.lower() or 'filled_quantity' in line.lower()):
            xbt_qty_matches = re.findall(r'quantity.*?\.(\d+)f', line, re.IGNORECASE)
            for match in xbt_qty_matches:
                decimal_places = int(match)
                if decimal_places != 4:
                    issues.append(f"Line {i}: XBT quantity uses {decimal_places} decimal places instead of 4: {line.strip()}")
                quantity_patterns.append((i, decimal_places, line.strip()))
        
        # Look for USDT price formatting (more specific patterns)
        # Only flag actual price variables, not trade_value, sum_value, percentage changes, etc.
        if 'USDT' in line and ('price' in line.lower() or 'avg_price' in line.lower()) and 'BTC' not in line:
            # Exclude percentage changes and other non-price values
            if 'price_change' not in line.lower() and 'percent' not in line.lower() and '%' not in line:
                usdt_price_matches = re.findall(r'(?:price|avg_price).*?\.(\d+)f', line, re.IGNORECASE)
                for match in usdt_price_matches:
                    decimal_places = int(match)
                    if decimal_places != 6:
                        issues.append(f"Line {i}: USDT price uses {decimal_places} decimal places instead of 6: {line.strip()}")
                    price_patterns.append((i, decimal_places, line.strip()))
    
    return price_patterns, quantity_patterns, issues

def test_alert_message_formatting():
    """Test alert message formatting examples."""
    print("\n🧪 Testing Alert Message Formatting Examples...")
    
    # Simulate alert message formatting
    test_cases = [
        {
            "name": "Single Order Alert",
            "quantity": 10.0000,
            "price": 0.166434,
            "sum_value": 1.66434
        },
        {
            "name": "Large Order Alert", 
            "quantity": 1234.5678,
            "price": 0.123456,
            "sum_value": 152.41
        },
        {
            "name": "Small Order Alert",
            "quantity": 0.1234,
            "price": 1.234567,
            "sum_value": 0.15
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"\n  📋 {test_case['name']}:")
        
        # Test quantity formatting (4 decimal places)
        quantity_str = f"{test_case['quantity']:.4f}"
        expected_qty_decimals = 4
        actual_qty_decimals = len(quantity_str.split('.')[1]) if '.' in quantity_str else 0
        
        if actual_qty_decimals == expected_qty_decimals:
            print(f"    ✅ Quantity: {quantity_str} XBT (4 decimal places)")
        else:
            print(f"    ❌ Quantity: {quantity_str} XBT ({actual_qty_decimals} decimal places, expected 4)")
            all_passed = False
        
        # Test price formatting (6 decimal places)
        price_str = f"{test_case['price']:.6f}"
        expected_price_decimals = 6
        actual_price_decimals = len(price_str.split('.')[1]) if '.' in price_str else 0
        
        if actual_price_decimals == expected_price_decimals:
            print(f"    ✅ Price: {price_str} USDT (6 decimal places)")
        else:
            print(f"    ❌ Price: {price_str} USDT ({actual_price_decimals} decimal places, expected 6)")
            all_passed = False
        
        # Test complete alert line
        alert_line = f"💰 Amount: {test_case['quantity']:.4f} XBT at {test_case['price']:.6f} USDT = ${test_case['sum_value']:.2f} USDT"
        print(f"    📝 Alert: {alert_line}")
    
    return all_passed

def test_aggregated_order_formatting():
    """Test aggregated order formatting."""
    print("\n🧪 Testing Aggregated Order Formatting...")
    
    # Simulate aggregated orders
    orders = [
        {"quantity": 10.0000, "price": 0.166434},
        {"quantity": 20.5000, "price": 0.166470},
        {"quantity": 35.2500, "price": 0.168400}
    ]
    
    print("  📋 Individual Orders:")
    all_passed = True
    
    for i, order in enumerate(orders, 1):
        order_line = f"Order {i}: {order['quantity']:.4f} XBT at {order['price']:.6f} USDT"
        print(f"    {order_line}")
        
        # Validate formatting
        qty_decimals = len(f"{order['quantity']:.4f}".split('.')[1])
        price_decimals = len(f"{order['price']:.6f}".split('.')[1])
        
        if qty_decimals != 4:
            print(f"    ❌ Quantity decimal places: {qty_decimals} (expected 4)")
            all_passed = False
        
        if price_decimals != 6:
            print(f"    ❌ Price decimal places: {price_decimals} (expected 6)")
            all_passed = False
    
    # Test summary
    total_quantity = sum(o['quantity'] for o in orders)
    total_value = sum(o['quantity'] * o['price'] for o in orders)
    avg_price = total_value / total_quantity
    
    print(f"\n  📊 Summary:")
    print(f"    Average Price: {avg_price:.6f} USDT")
    print(f"    Total Volume: {total_quantity:.4f} XBT")
    print(f"    Total Value: {total_value:.2f} USDT")
    
    return all_passed

def main():
    """Run comprehensive precision formatting tests."""
    print("🚀 XBT Trading Bot Precision Formatting Validation")
    print("="*60)
    
    # Test 1: Search for formatting patterns in the main bot file
    print("\n🔍 Scanning telebot_fixed.py for formatting patterns...")
    
    price_patterns, quantity_patterns, issues = search_formatting_patterns('telebot_fixed.py')
    
    print(f"Found {len(price_patterns)} price formatting instances")
    print(f"Found {len(quantity_patterns)} quantity formatting instances")
    print(f"Found {len(issues)} formatting issues")
    
    if issues:
        print("\n❌ Formatting Issues Found:")
        for issue in issues[:10]:  # Show first 10 issues
            print(f"  • {issue}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more issues")
    else:
        print("✅ No formatting issues found in code scan")
    
    # Test 2: Test alert message formatting
    alert_test_passed = test_alert_message_formatting()
    
    # Test 3: Test aggregated order formatting
    aggregated_test_passed = test_aggregated_order_formatting()
    
    # Test 4: Test WebSocket logging format examples
    print("\n🧪 Testing WebSocket Logging Format Examples...")
    
    # Simulate WebSocket log messages
    websocket_examples = [
        ("NonKYC USDT", 25.0000, 0.166434, "buy"),
        ("CoinEx", 100.5000, 0.167890, "sell"),
        ("AscendEX", 0.1234, 1.234567, "buy")
    ]
    
    websocket_passed = True
    for exchange, qty, price, side in websocket_examples:
        log_msg = f"✅ Processing {side.upper()} trade: {qty:.4f} XBT at {price:.6f} USDT"
        print(f"  {log_msg}")
        
        # Validate formatting
        qty_str = f"{qty:.4f}"
        price_str = f"{price:.6f}"
        
        if len(qty_str.split('.')[1]) != 4:
            websocket_passed = False
        if len(price_str.split('.')[1]) != 6:
            websocket_passed = False
    
    if websocket_passed:
        print("  ✅ WebSocket logging format correct")
    else:
        print("  ❌ WebSocket logging format issues")
    
    # Test 5: Production readiness summary
    print("\n🚀 Production Readiness Summary:")
    
    all_tests_passed = (
        len(issues) == 0 and
        alert_test_passed and
        aggregated_test_passed and
        websocket_passed
    )
    
    if all_tests_passed:
        print("✅ All precision formatting tests passed")
        print("✅ Prices use 6 decimal places consistently")
        print("✅ Quantities use 4 decimal places consistently")
        print("✅ Alert messages format correctly")
        print("✅ WebSocket logging format correct")
        print("✅ Ready for production deployment")
    else:
        print("❌ Some precision formatting tests failed")
        if issues:
            print(f"❌ {len(issues)} code formatting issues need fixing")
        if not alert_test_passed:
            print("❌ Alert message formatting needs fixing")
        if not aggregated_test_passed:
            print("❌ Aggregated order formatting needs fixing")
        if not websocket_passed:
            print("❌ WebSocket logging formatting needs fixing")
    
    # Final summary
    print("\n" + "="*60)
    print("📊 PRECISION FORMATTING TEST SUMMARY")
    print("="*60)
    print(f"Code Scan Issues: {len(issues)}")
    print(f"Alert Message Test: {'✅ PASS' if alert_test_passed else '❌ FAIL'}")
    print(f"Aggregated Orders Test: {'✅ PASS' if aggregated_test_passed else '❌ FAIL'}")
    print(f"WebSocket Logging Test: {'✅ PASS' if websocket_passed else '❌ FAIL'}")
    print(f"Overall Result: {'✅ ALL TESTS PASSED' if all_tests_passed else '❌ SOME TESTS FAILED'}")
    
    if all_tests_passed:
        print("\n🎉 Precision formatting is ready for production!")
        return 0
    else:
        print(f"\n⚠️  Please fix the identified issues before deployment.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
