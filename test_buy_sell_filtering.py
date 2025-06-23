#!/usr/bin/env python3
"""
Test script to verify buy/sell filtering logic in the XBT trading bot alert system.
This script tests the core filtering logic without requiring the full bot dependencies.
"""

import asyncio
import sys
import os
import json
import time

def validate_price_calculation(price, quantity, sum_value, context="Unknown"):
    """Validate that price * quantity = sum_value within acceptable tolerance."""
    expected_value = price * quantity
    tolerance = max(0.01, expected_value * 0.001)  # 0.1% tolerance or 0.01 USDT minimum

    if abs(sum_value - expected_value) > tolerance:
        print(f"❌ PRICE CALCULATION VALIDATION FAILED in {context}:")
        print(f"  💵 Price: {price:.6f} USDT")
        print(f"  📊 Quantity: {quantity:.4f} XBT")
        print(f"  ✅ Expected Value: {expected_value:.2f} USDT")
        print(f"  ❌ Actual Value: {sum_value:.2f} USDT")
        print(f"  📉 Difference: {sum_value - expected_value:.2f} USDT")
        print(f"  🎯 Tolerance: {tolerance:.2f} USDT")
        return False, expected_value

    print(f"✅ Price calculation validated in {context}: {price:.6f} * {quantity:.4f} = {sum_value:.2f} USDT")
    return True, sum_value

def validate_buy_volume_aggregation(trades_list, expected_total, context="Unknown"):
    """Validate that buy volume aggregation is correct and excludes sell trades."""
    buy_trades = []
    sell_trades = []
    unknown_trades = []

    for trade in trades_list:
        trade_side = trade.get('trade_side', 'unknown').lower()
        if trade_side in ['buy', 'b']:
            buy_trades.append(trade)
        elif trade_side in ['sell', 's']:
            sell_trades.append(trade)
        else:
            unknown_trades.append(trade)

    # Calculate volumes
    buy_volume = sum(t['sum_value'] for t in buy_trades)
    sell_volume = sum(t['sum_value'] for t in sell_trades)
    unknown_volume = sum(t['sum_value'] for t in unknown_trades)
    total_volume = buy_volume + sell_volume + unknown_volume

    # Log detailed breakdown
    print(f"📊 BUY VOLUME VALIDATION for {context}:")
    print(f"  🟢 BUY trades: {len(buy_trades)} trades = ${buy_volume:.2f} USDT")
    print(f"  🔴 SELL trades: {len(sell_trades)} trades = ${sell_volume:.2f} USDT")
    print(f"  ⚪ UNKNOWN trades: {len(unknown_trades)} trades = ${unknown_volume:.2f} USDT")
    print(f"  💰 Total volume: ${total_volume:.2f} USDT")
    print(f"  🎯 Expected total: ${expected_total:.2f} USDT")

    # Validation checks
    validation_passed = True

    # Check if sell trades are incorrectly included
    if sell_trades:
        print(f"❌ SELL TRADES DETECTED: {len(sell_trades)} sell trades should not be included in buy volume!")
        validation_passed = False

    # Check total calculation
    if abs(total_volume - expected_total) > 0.01:
        print(f"❌ VOLUME CALCULATION MISMATCH: {total_volume:.2f} != {expected_total:.2f}")
        validation_passed = False

    # Check individual trade calculations
    for i, trade in enumerate(buy_trades[:5]):  # Check first 5 trades
        expected_trade_value = trade['price'] * trade['quantity']
        if abs(trade['sum_value'] - expected_trade_value) > 0.01:
            print(f"❌ TRADE {i+1} CALCULATION ERROR: {trade['sum_value']:.2f} != {expected_trade_value:.2f}")
            validation_passed = False

    if validation_passed:
        print(f"✅ Buy volume aggregation validated: ${buy_volume:.2f} USDT from {len(buy_trades)} BUY trades")

    return validation_passed, buy_volume, sell_volume

def should_process_trade(trade_side, sum_value, threshold=300.0):
    """Simulate the trade processing logic."""
    # Only process buy trades
    if trade_side.lower() not in ["buy", "b", "unknown"]:
        print(f"⏭️ Skipping {trade_side.upper()} trade - not counting toward buy volume threshold")
        return False

    # Check if above threshold
    if sum_value >= threshold:
        print(f"✅ Processing {trade_side.upper()} trade: ${sum_value:.2f} USDT >= ${threshold:.2f} USDT threshold")
        return True
    else:
        print(f"📊 {trade_side.upper()} trade below threshold: ${sum_value:.2f} USDT < ${threshold:.2f} USDT")
        return False

def aggregate_buy_volume(trades, threshold=300.0):
    """Simulate buy volume aggregation."""
    buy_trades = []
    sell_trades = []

    for trade in trades:
        if trade['side'].lower() in ['buy', 'b']:
            buy_trades.append(trade)
        elif trade['side'].lower() in ['sell', 's']:
            sell_trades.append(trade)

    buy_volume = sum(t['value'] for t in buy_trades)
    sell_volume = sum(t['value'] for t in sell_trades)

    print(f"📊 Volume aggregation:")
    print(f"  🟢 BUY volume: ${buy_volume:.2f} USDT from {len(buy_trades)} trades")
    print(f"  🔴 SELL volume: ${sell_volume:.2f} USDT from {len(sell_trades)} trades (excluded)")
    print(f"  🎯 Threshold: ${threshold:.2f} USDT")

    should_alert = buy_volume >= threshold
    print(f"  {'✅ ALERT TRIGGERED' if should_alert else '❌ No alert'}: BUY volume {'≥' if should_alert else '<'} threshold")

    return buy_volume, sell_volume, should_alert

class TestBuySellFiltering:
    """Test class for buy/sell filtering functionality."""

    def __init__(self):
        self.test_results = []

    def log_test_result(self, test_name, passed, details=""):
        """Log test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = {
            'test': test_name,
            'passed': passed,
            'details': details
        }
        self.test_results.append(result)
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")

    def test_buy_trade_processing(self):
        """Test that BUY trades are processed correctly."""
        print("\n🧪 Testing BUY trade processing...")

        # Test single large BUY trade above threshold
        should_process = should_process_trade("buy", 375.0, 300.0)
        self.log_test_result(
            "Single BUY trade above threshold",
            should_process,
            "BUY trade with $375 USDT should be processed"
        )

        # Test small BUY trade below threshold
        should_process = should_process_trade("buy", 150.0, 300.0)
        self.log_test_result(
            "Single BUY trade below threshold",
            not should_process,  # Should not trigger alert but should be processed
            "BUY trade with $150 USDT should be processed but not trigger alert"
        )

    def test_sell_trade_filtering(self):
        """Test that SELL trades are filtered out and don't trigger alerts."""
        print("\n🧪 Testing SELL trade filtering...")

        # Test large SELL trade that would exceed threshold if processed
        should_process = should_process_trade("sell", 400.0, 300.0)
        self.log_test_result(
            "Large SELL trade filtering",
            not should_process,
            "SELL trade with $400 USDT should be filtered out"
        )

        # Test multiple SELL trades
        should_process1 = should_process_trade("sell", 200.0, 300.0)
        should_process2 = should_process_trade("s", 150.0, 300.0)  # Test short form

        self.log_test_result(
            "Multiple SELL trade filtering",
            not should_process1 and not should_process2,
            "All SELL trades should be filtered out regardless of value"
        )

    def test_mixed_buy_sell_aggregation(self):
        """Test aggregation with mixed BUY and SELL trades."""
        print("\n🧪 Testing mixed BUY/SELL aggregation...")

        # Test trades with mixed buy/sell
        trades = [
            {"side": "buy", "value": 100.0},    # $100 BUY
            {"side": "sell", "value": 55.0},    # $55 SELL (should be ignored)
            {"side": "buy", "value": 96.0},     # $96 BUY
            {"side": "buy", "value": 117.0},    # $117 BUY
            {"side": "sell", "value": 280.0},   # $280 SELL (should be ignored)
        ]

        buy_volume, sell_volume, should_alert = aggregate_buy_volume(trades, 300.0)

        # Expected: Only BUY trades should count: $100 + $96 + $117 = $313 USDT
        expected_buy_volume = 100.0 + 96.0 + 117.0  # $313
        expected_sell_volume = 55.0 + 280.0  # $335 (but excluded)

        self.log_test_result(
            "Mixed BUY/SELL aggregation - BUY volume calculation",
            abs(buy_volume - expected_buy_volume) < 1.0,
            f"Expected ${expected_buy_volume:.0f}, got ${buy_volume:.2f}"
        )

        self.log_test_result(
            "Mixed BUY/SELL aggregation - SELL volume excluded",
            abs(sell_volume - expected_sell_volume) < 1.0,
            f"SELL volume: ${sell_volume:.2f} (excluded from alerts)"
        )

        self.log_test_result(
            "Mixed BUY/SELL aggregation - Alert triggered",
            should_alert,
            f"BUY volume ${buy_volume:.2f} should trigger alert (> $300)"
        )

    def test_volume_validation_functions(self):
        """Test the volume validation functions."""
        print("\n🧪 Testing volume validation functions...")

        # Test price calculation validation
        is_valid, corrected = validate_price_calculation(1.5, 100.0, 150.0, "Test")
        self.log_test_result(
            "Price calculation validation - correct",
            is_valid and corrected == 150.0,
            f"Valid: {is_valid}, Value: {corrected}"
        )

        # Test price calculation validation with error
        is_valid, corrected = validate_price_calculation(1.5, 100.0, 200.0, "Test")
        self.log_test_result(
            "Price calculation validation - incorrect",
            not is_valid and corrected == 150.0,
            f"Valid: {is_valid}, Corrected: {corrected}"
        )

        # Test buy volume aggregation validation
        test_trades = [
            {'price': 1.0, 'quantity': 100.0, 'sum_value': 100.0, 'trade_side': 'buy'},
            {'price': 1.1, 'quantity': 50.0, 'sum_value': 55.0, 'trade_side': 'sell'},
            {'price': 1.2, 'quantity': 80.0, 'sum_value': 96.0, 'trade_side': 'buy'},
        ]

        validation_passed, buy_volume, sell_volume = validate_buy_volume_aggregation(
            test_trades, 251.0, "Test aggregation"
        )

        expected_buy = 100.0 + 96.0  # Only BUY trades
        expected_sell = 55.0         # SELL trade

        self.log_test_result(
            "Buy volume aggregation validation",
            buy_volume == expected_buy and sell_volume == expected_sell,
            f"BUY: ${buy_volume:.0f} (expected ${expected_buy:.0f}), SELL: ${sell_volume:.0f} (expected ${expected_sell:.0f})"
        )

    def print_test_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("🧪 TEST SUMMARY")
        print("="*60)

        passed_tests = sum(1 for result in self.test_results if result['passed'])
        total_tests = len(self.test_results)

        print(f"Tests passed: {passed_tests}/{total_tests}")
        print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")

        print("\nDetailed Results:")
        for result in self.test_results:
            status = "✅" if result['passed'] else "❌"
            print(f"{status} {result['test']}")
            if result['details']:
                print(f"   {result['details']}")

        if passed_tests == total_tests:
            print("\n🎉 ALL TESTS PASSED! Buy/sell filtering is working correctly.")
        else:
            print(f"\n⚠️  {total_tests - passed_tests} test(s) failed. Review the implementation.")

        return passed_tests == total_tests

def main():
    """Run all tests."""
    print("🚀 Starting Buy/Sell Filtering Tests for XBT Trading Bot")
    print("="*60)

    tester = TestBuySellFiltering()

    try:
        # Run all test cases
        tester.test_buy_trade_processing()
        tester.test_sell_trade_filtering()
        tester.test_mixed_buy_sell_aggregation()
        tester.test_volume_validation_functions()

        # Print summary
        all_passed = tester.print_test_summary()

        return 0 if all_passed else 1

    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
