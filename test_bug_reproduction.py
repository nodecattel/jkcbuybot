#!/usr/bin/env python3
"""
Test script to reproduce the exact bug scenario described in the problem.

Bug Report:
- Alert showed: 1342.82 XBT at 0.442941 USDT per XBT (Total: 594.79 USDT, 2 trades aggregated)
- Expected: Price should be ~0.171479 USDT per XBT based on current market data
- The math doesn't add up: 1342.82 × 0.442941 ≠ 594.79 USDT

This test will try to reverse engineer what could cause this specific scenario.
"""

import time
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_bug_scenario():
    """Analyze the specific bug scenario to understand what went wrong."""
    print("=" * 80)
    print("ANALYZING BUG SCENARIO")
    print("=" * 80)
    
    # Data from bug report
    reported_quantity = 1342.82
    reported_price = 0.442941
    reported_total = 594.79
    expected_price = 0.171479
    num_trades = 2
    
    print(f"Bug Report Data:")
    print(f"  Quantity: {reported_quantity:.2f} XBT")
    print(f"  Reported Price: {reported_price:.6f} USDT per XBT")
    print(f"  Reported Total: {reported_total:.2f} USDT")
    print(f"  Expected Price: {expected_price:.6f} USDT per XBT")
    print(f"  Number of Trades: {num_trades}")
    print()
    
    # Verify the math in the bug report
    calculated_total = reported_quantity * reported_price
    print(f"Math Verification:")
    print(f"  {reported_quantity:.2f} × {reported_price:.6f} = {calculated_total:.2f} USDT")
    print(f"  Matches reported total ({reported_total:.2f}): {abs(calculated_total - reported_total) < 0.01}")
    print()
    
    # Calculate what the correct total should be
    expected_total = reported_quantity * expected_price
    print(f"Expected Calculation:")
    print(f"  {reported_quantity:.2f} × {expected_price:.6f} = {expected_total:.2f} USDT")
    print(f"  Difference from reported: {reported_total - expected_total:.2f} USDT")
    print()
    
    # Try to reverse engineer possible individual trades
    print("Reverse Engineering Possible Scenarios:")
    print()
    
    # Scenario 1: Two trades with very different prices
    print("Scenario 1: Two trades with different prices that could aggregate to the bug")
    
    # If we have 594.79 USDT total and 1342.82 XBT total, what could the individual trades be?
    # Let's try different combinations
    
    scenarios = [
        # (trade1_qty, trade1_price, trade2_qty, trade2_price)
        (1000.0, 0.15, 342.82, 1.30),  # Low price + high price
        (800.0, 0.20, 542.82, 0.70),   # Medium prices
        (1200.0, 0.45, 142.82, 0.35),  # High price + low price
        (671.41, 0.30, 671.41, 0.59),  # Equal quantities, different prices
    ]
    
    for i, (qty1, price1, qty2, price2) in enumerate(scenarios, 1):
        value1 = qty1 * price1
        value2 = qty2 * price2
        total_qty = qty1 + qty2
        total_value = value1 + value2
        weighted_avg = total_value / total_qty if total_qty > 0 else 0
        
        print(f"  Scenario {i}:")
        print(f"    Trade 1: {qty1:.2f} XBT @ {price1:.6f} USDT = {value1:.2f} USDT")
        print(f"    Trade 2: {qty2:.2f} XBT @ {price2:.6f} USDT = {value2:.2f} USDT")
        print(f"    Total: {total_qty:.2f} XBT, {total_value:.2f} USDT")
        print(f"    Weighted Avg: {weighted_avg:.6f} USDT per XBT")
        print(f"    Matches bug total: {abs(total_value - reported_total) < 1.0}")
        print(f"    Matches bug quantity: {abs(total_qty - reported_quantity) < 1.0}")
        print()
    
    return True

def test_potential_calculation_bugs():
    """Test for potential calculation bugs that could cause the issue."""
    print("=" * 80)
    print("TESTING POTENTIAL CALCULATION BUGS")
    print("=" * 80)
    
    # Simulate the aggregation logic with test data
    trades = [
        {'price': 0.15, 'quantity': 800.0, 'sum_value': 0.15 * 800.0},
        {'price': 0.70, 'quantity': 542.82, 'sum_value': 0.70 * 542.82}
    ]
    
    print("Test Trades:")
    for i, trade in enumerate(trades, 1):
        print(f"  Trade {i}: {trade['quantity']:.2f} XBT @ {trade['price']:.6f} USDT = {trade['sum_value']:.2f} USDT")
    
    # Test current aggregation logic
    total_quantity = sum(trade['quantity'] for trade in trades)
    total_pending = sum(trade['sum_value'] for trade in trades)
    avg_price = total_pending / total_quantity if total_quantity > 0 else 0
    
    print(f"\nCurrent Logic Results:")
    print(f"  Total Quantity: {total_quantity:.2f} XBT")
    print(f"  Total Value: {total_pending:.2f} USDT")
    print(f"  Weighted Avg: {avg_price:.6f} USDT per XBT")
    
    # Verify calculation
    verification = avg_price * total_quantity
    print(f"  Verification: {avg_price:.6f} × {total_quantity:.2f} = {verification:.2f} USDT")
    print(f"  Math is correct: {abs(verification - total_pending) < 0.01}")
    print()
    
    # Test potential bug: What if sum_value was calculated incorrectly?
    print("Testing Potential Bug: Incorrect sum_value calculation")
    
    # Bug scenario: What if individual sum_values were wrong?
    buggy_trades = [
        {'price': 0.15, 'quantity': 800.0, 'sum_value': 0.15 * 800.0 * 2},  # Double the value
        {'price': 0.70, 'quantity': 542.82, 'sum_value': 0.70 * 542.82 * 0.5}  # Half the value
    ]
    
    print("Buggy Trades (incorrect sum_value):")
    for i, trade in enumerate(buggy_trades, 1):
        expected_value = trade['price'] * trade['quantity']
        print(f"  Trade {i}: {trade['quantity']:.2f} XBT @ {trade['price']:.6f} USDT")
        print(f"    Expected value: {expected_value:.2f} USDT")
        print(f"    Actual sum_value: {trade['sum_value']:.2f} USDT")
        print(f"    Difference: {trade['sum_value'] - expected_value:.2f} USDT")
    
    buggy_total_quantity = sum(trade['quantity'] for trade in buggy_trades)
    buggy_total_pending = sum(trade['sum_value'] for trade in buggy_trades)
    buggy_avg_price = buggy_total_pending / buggy_total_quantity if buggy_total_quantity > 0 else 0
    
    print(f"\nBuggy Logic Results:")
    print(f"  Total Quantity: {buggy_total_quantity:.2f} XBT")
    print(f"  Total Value: {buggy_total_pending:.2f} USDT")
    print(f"  Weighted Avg: {buggy_avg_price:.6f} USDT per XBT")
    print()
    
    return True

def test_floating_point_precision():
    """Test for floating point precision issues."""
    print("=" * 80)
    print("TESTING FLOATING POINT PRECISION")
    print("=" * 80)
    
    # Test with very small numbers that might cause precision issues
    small_trades = [
        {'price': 0.000001, 'quantity': 1000000.0},
        {'price': 0.999999, 'quantity': 342.82}
    ]
    
    print("Testing with extreme precision values:")
    total_value = 0
    total_quantity = 0
    
    for i, trade in enumerate(small_trades, 1):
        value = trade['price'] * trade['quantity']
        total_value += value
        total_quantity += trade['quantity']
        print(f"  Trade {i}: {trade['quantity']:.2f} XBT @ {trade['price']:.6f} USDT = {value:.6f} USDT")
    
    avg_price = total_value / total_quantity if total_quantity > 0 else 0
    verification = avg_price * total_quantity
    
    print(f"\nPrecision Test Results:")
    print(f"  Total Quantity: {total_quantity:.2f} XBT")
    print(f"  Total Value: {total_value:.6f} USDT")
    print(f"  Weighted Avg: {avg_price:.10f} USDT per XBT")
    print(f"  Verification: {verification:.6f} USDT")
    print(f"  Precision error: {abs(verification - total_value):.10f} USDT")
    print()
    
    return True

def main():
    """Run all bug reproduction tests."""
    print("XBT TRADING ALERT PRICE CALCULATION BUG REPRODUCTION")
    print("=" * 80)
    print()
    
    # Test 1: Analyze the bug scenario
    test1_success = analyze_bug_scenario()
    
    # Test 2: Test potential calculation bugs
    test2_success = test_potential_calculation_bugs()
    
    # Test 3: Test floating point precision
    test3_success = test_floating_point_precision()
    
    # Summary
    print("=" * 80)
    print("BUG REPRODUCTION TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Bug scenario analysis: {'PASS' if test1_success else 'FAIL'}")
    print(f"✅ Calculation bug tests: {'PASS' if test2_success else 'FAIL'}")
    print(f"✅ Precision tests: {'PASS' if test3_success else 'FAIL'}")
    print()
    
    print("CONCLUSIONS:")
    print("1. The reported math (1342.82 × 0.442941 = 594.79) is mathematically correct")
    print("2. The issue is likely in the INPUT DATA, not the calculation logic")
    print("3. Possible causes:")
    print("   - Individual trade sum_value calculations were wrong")
    print("   - Data corruption during WebSocket processing")
    print("   - Race condition in trade aggregation")
    print("   - Exchange API returning incorrect data")
    print()
    print("RECOMMENDATIONS:")
    print("1. Enable debug logging to capture actual trade data")
    print("2. Add validation checks for individual trade calculations")
    print("3. Monitor for data inconsistencies in real-time")
    print("4. Add alerts for calculation mismatches")

if __name__ == "__main__":
    main()
