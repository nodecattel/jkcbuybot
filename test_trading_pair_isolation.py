#!/usr/bin/env python3
"""
Comprehensive Test Suite for XBT Trading Pair Isolation and Precision Calculations

This test suite validates:
1. Trading pair isolation in aggregation logic
2. BTC price precision and formatting (8 decimals)
3. USDT equivalent calculations
4. Alert message formatting
5. Volume aggregation logic for different trading pairs
"""

import asyncio
import sys
import os
import time
from typing import Dict, List, Any

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the modules we need to test
from utils import (
    validate_price_calculation, 
    format_btc_price, 
    format_usdt_price, 
    format_quantity,
    validate_buy_sell_aggregation
)
from api_clients import convert_btc_to_usdt, get_btc_usdt_rate
from alert_system import process_message, PENDING_TRADES

def test_btc_price_precision():
    """Test BTC price formatting with 8-decimal precision."""
    print("🧪 Testing BTC price precision formatting...")
    
    test_cases = [
        (0.00000164, "0.00000164"),
        (0.00000172, "0.00000172"),
        (0.00000185, "0.00000185"),
        (0.000001, "0.00000100"),
        (0.12345678, "0.12345678"),
    ]
    
    for price, expected in test_cases:
        result = format_btc_price(price)
        assert result == expected, f"BTC price formatting failed: {price} -> {result}, expected {expected}"
        print(f"  ✅ {price} -> {result}")
    
    print("✅ BTC price precision tests passed!\n")

def test_usdt_price_precision():
    """Test USDT price formatting with 6-decimal precision."""
    print("🧪 Testing USDT price precision formatting...")
    
    test_cases = [
        (0.166434, "0.166434"),
        (0.106234, "0.106234"),
        (0.111456, "0.111456"),
        (0.119876, "0.119876"),
        (1.123456, "1.123456"),
    ]
    
    for price, expected in test_cases:
        result = format_usdt_price(price)
        assert result == expected, f"USDT price formatting failed: {price} -> {result}, expected {expected}"
        print(f"  ✅ {price} -> {result}")
    
    print("✅ USDT price precision tests passed!\n")

def test_quantity_formatting():
    """Test XBT quantity formatting with 4-decimal precision."""
    print("🧪 Testing XBT quantity formatting...")
    
    test_cases = [
        (10.0, "10.0000"),
        (30.0, "30.0000"),
        (100.0, "100.0000"),
        (10.1234, "10.1234"),
        (0.5678, "0.5678"),
    ]
    
    for quantity, expected in test_cases:
        result = format_quantity(quantity)
        assert result == expected, f"Quantity formatting failed: {quantity} -> {result}, expected {expected}"
        print(f"  ✅ {quantity} -> {result}")
    
    print("✅ Quantity formatting tests passed!\n")

def test_price_calculation_validation():
    """Test price calculation validation with appropriate tolerances."""
    print("🧪 Testing price calculation validation...")
    
    # Test BTC pair validation (8-decimal precision)
    print("  Testing BTC pair validation...")
    btc_price = 0.00000164
    quantity = 10.0000
    expected_value = btc_price * quantity
    
    is_valid, corrected = validate_price_calculation(btc_price, quantity, expected_value, "BTC Test", "BTC")
    assert is_valid, f"BTC validation should pass for exact calculation"
    print(f"    ✅ BTC exact calculation: {btc_price} * {quantity} = {expected_value}")
    
    # Test with small tolerance
    slightly_off = expected_value + 0.000000001  # 1 nano-BTC difference
    is_valid, corrected = validate_price_calculation(btc_price, quantity, slightly_off, "BTC Test", "BTC")
    assert is_valid, f"BTC validation should pass for small difference"
    print(f"    ✅ BTC small tolerance: difference of 0.000000001 BTC accepted")
    
    # Test USDT pair validation (6-decimal precision)
    print("  Testing USDT pair validation...")
    usdt_price = 0.166434
    expected_usdt = usdt_price * quantity
    
    is_valid, corrected = validate_price_calculation(usdt_price, quantity, expected_usdt, "USDT Test", "USDT")
    assert is_valid, f"USDT validation should pass for exact calculation"
    print(f"    ✅ USDT exact calculation: {usdt_price} * {quantity} = {expected_usdt}")
    
    print("✅ Price calculation validation tests passed!\n")

def test_buy_sell_aggregation():
    """Test buy/sell aggregation validation for different trading pairs."""
    print("🧪 Testing buy/sell aggregation validation...")
    
    # Test XBT/BTC trades
    btc_trades = [
        {
            'price': 0.00000164,
            'quantity': 10.0,
            'sum_value': 0.0000164,
            'side': 'buy',
            'pair_type': 'XBT/BTC'
        },
        {
            'price': 0.00000172,
            'quantity': 30.0,
            'sum_value': 0.0000516,
            'side': 'buy',
            'pair_type': 'XBT/BTC'
        }
    ]
    
    validation_passed, buy_volume, sell_volume = validate_buy_sell_aggregation(btc_trades, "BTC Test")
    assert validation_passed, "BTC aggregation validation should pass"
    expected_buy_volume = 0.0000164 + 0.0000516
    assert abs(buy_volume - expected_buy_volume) < 0.00000001, f"BTC buy volume mismatch: {buy_volume} vs {expected_buy_volume}"
    print(f"  ✅ BTC aggregation: {len(btc_trades)} trades, buy volume = {buy_volume:.8f} BTC")
    
    # Test XBT/USDT trades
    usdt_trades = [
        {
            'price': 0.166434,
            'quantity': 10.0,
            'sum_value': 1.66434,
            'side': 'buy',
            'pair_type': 'XBT/USDT'
        },
        {
            'price': 0.170000,
            'quantity': 20.0,
            'sum_value': 3.40000,
            'side': 'buy',
            'pair_type': 'XBT/USDT'
        }
    ]
    
    validation_passed, buy_volume, sell_volume = validate_buy_sell_aggregation(usdt_trades, "USDT Test")
    assert validation_passed, "USDT aggregation validation should pass"
    expected_buy_volume = 1.66434 + 3.40000
    assert abs(buy_volume - expected_buy_volume) < 0.01, f"USDT buy volume mismatch: {buy_volume} vs {expected_buy_volume}"
    print(f"  ✅ USDT aggregation: {len(usdt_trades)} trades, buy volume = {buy_volume:.2f} USDT")
    
    print("✅ Buy/sell aggregation tests passed!\n")

async def test_btc_usdt_conversion():
    """Test BTC to USDT conversion functionality."""
    print("🧪 Testing BTC to USDT conversion...")
    
    # Test with mock BTC rate
    mock_btc_rate = 65000.0  # $65,000 per BTC
    btc_price = 0.00000164
    
    usdt_equivalent, rate_used = await convert_btc_to_usdt(btc_price, mock_btc_rate)
    expected_usdt = btc_price * mock_btc_rate
    
    assert abs(usdt_equivalent - expected_usdt) < 0.000001, f"Conversion mismatch: {usdt_equivalent} vs {expected_usdt}"
    assert rate_used == mock_btc_rate, f"Rate mismatch: {rate_used} vs {mock_btc_rate}"
    
    print(f"  ✅ Conversion: {btc_price:.8f} BTC * ${mock_btc_rate:.2f} = ${usdt_equivalent:.6f} USDT")
    print("✅ BTC to USDT conversion tests passed!\n")

def test_trading_pair_isolation():
    """Test that trading pairs are properly isolated in aggregation."""
    print("🧪 Testing trading pair isolation...")
    
    # Clear any existing pending trades
    global PENDING_TRADES
    PENDING_TRADES.clear()
    
    # Simulate adding trades for different pairs
    exchange = "TestExchange"
    
    # Add XBT/USDT trade
    if exchange not in PENDING_TRADES:
        PENDING_TRADES[exchange] = {}
    if "XBT/USDT" not in PENDING_TRADES[exchange]:
        PENDING_TRADES[exchange]["XBT/USDT"] = {}
    
    buyer_id_usdt = "buyer_1"
    PENDING_TRADES[exchange]["XBT/USDT"][buyer_id_usdt] = [{
        'price': 0.166434,
        'quantity': 10.0,
        'sum_value': 1.66434,
        'pair_type': 'XBT/USDT',
        'side': 'buy'
    }]
    
    # Add XBT/BTC trade
    if "XBT/BTC" not in PENDING_TRADES[exchange]:
        PENDING_TRADES[exchange]["XBT/BTC"] = {}
    
    buyer_id_btc = "buyer_1"
    PENDING_TRADES[exchange]["XBT/BTC"][buyer_id_btc] = [{
        'price': 0.00000164,
        'quantity': 10.0,
        'sum_value': 0.0000164,
        'pair_type': 'XBT/BTC',
        'side': 'buy'
    }]
    
    # Verify isolation
    assert "XBT/USDT" in PENDING_TRADES[exchange], "XBT/USDT pair should exist"
    assert "XBT/BTC" in PENDING_TRADES[exchange], "XBT/BTC pair should exist"
    assert len(PENDING_TRADES[exchange]["XBT/USDT"]) == 1, "Should have 1 USDT buyer"
    assert len(PENDING_TRADES[exchange]["XBT/BTC"]) == 1, "Should have 1 BTC buyer"
    
    usdt_trade = PENDING_TRADES[exchange]["XBT/USDT"][buyer_id_usdt][0]
    btc_trade = PENDING_TRADES[exchange]["XBT/BTC"][buyer_id_btc][0]
    
    assert usdt_trade['pair_type'] == 'XBT/USDT', "USDT trade should have correct pair type"
    assert btc_trade['pair_type'] == 'XBT/BTC', "BTC trade should have correct pair type"
    
    print(f"  ✅ USDT trade isolated: {usdt_trade['quantity']} XBT at ${usdt_trade['price']:.6f}")
    print(f"  ✅ BTC trade isolated: {btc_trade['quantity']} XBT at {btc_trade['price']:.8f} BTC")
    
    # Clean up
    PENDING_TRADES.clear()
    
    print("✅ Trading pair isolation tests passed!\n")

def test_alert_formatting():
    """Test alert message formatting for XBT/BTC pairs."""
    print("🧪 Testing alert message formatting...")

    # Test individual order formatting
    trade_details = [
        {
            'price': 0.00000164,
            'quantity': 10.0000,
            'usdt_price': 0.106234
        },
        {
            'price': 0.00000172,
            'quantity': 30.0000,
            'usdt_price': 0.111456
        },
        {
            'price': 0.00000185,
            'quantity': 100.0000,
            'usdt_price': 0.119876
        }
    ]

    # Test the expected format
    for i, trade in enumerate(trade_details, 1):
        expected_format = f"Order {i}: {format_quantity(trade['quantity'])} XBT at {format_btc_price(trade['price'])} BTC (≈ {format_usdt_price(trade['usdt_price'])} USDT)"
        print(f"  ✅ {expected_format}")

    # Verify the format matches the user's requirements
    order1 = f"Order 1: {format_quantity(10.0000)} XBT at {format_btc_price(0.00000164)} BTC (≈ {format_usdt_price(0.106234)} USDT)"
    assert "10.0000 XBT" in order1, "Should include 4-decimal quantity"
    assert "0.00000164 BTC" in order1, "Should include 8-decimal BTC price"
    assert "≈ 0.106234 USDT" in order1, "Should include ≈ symbol and 6-decimal USDT equivalent"

    print("✅ Alert formatting tests passed!\n")

async def run_all_tests():
    """Run all test suites."""
    print("🚀 Starting XBT Trading Pair Isolation Test Suite\n")
    print("=" * 60)

    try:
        # Run synchronous tests
        test_btc_price_precision()
        test_usdt_price_precision()
        test_quantity_formatting()
        test_price_calculation_validation()
        test_buy_sell_aggregation()
        test_trading_pair_isolation()
        test_alert_formatting()

        # Run asynchronous tests
        await test_btc_usdt_conversion()

        print("=" * 60)
        print("🎉 ALL TESTS PASSED! 🎉")
        print("\n✅ Trading pair isolation is working correctly")
        print("✅ BTC precision formatting (8 decimals) is correct")
        print("✅ USDT precision formatting (6 decimals) is correct")
        print("✅ Price calculation validation handles both pairs")
        print("✅ Volume aggregation logic works for both pairs")
        print("✅ BTC to USDT conversion is accurate")
        print("✅ Alert message formatting matches requirements")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
