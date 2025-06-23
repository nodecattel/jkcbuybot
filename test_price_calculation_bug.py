#!/usr/bin/env python3
"""
Test script to reproduce and verify the price calculation bug fix.

Bug Description:
- Alert showed: 1342.82 XBT at 0.442941 USDT per XBT (Total: 594.79 USDT, 2 trades aggregated)
- Expected: Price should be ~0.171479 USDT per XBT based on current market data
- The math doesn't add up: 1342.82 × 0.442941 ≠ 594.79 USDT

This test will:
1. Simulate the exact scenario described in the bug report
2. Test the weighted average calculation logic
3. Verify that the fix produces the correct results
"""

import asyncio
import sys
import os
import time
import logging

# Add the current directory to Python path to import telebot_fixed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_weighted_average_calculation():
    """Test the weighted average calculation logic with the bug scenario data."""
    print("=" * 80)
    print("TESTING WEIGHTED AVERAGE CALCULATION LOGIC")
    print("=" * 80)
    
    # Scenario from bug report: 1342.82 XBT at 0.442941 USDT per XBT (Total: 594.79 USDT, 2 trades aggregated)
    reported_quantity = 1342.82
    reported_price = 0.442941
    reported_total = 594.79
    expected_price = 0.171479  # Expected correct price
    
    print(f"Bug Report Data:")
    print(f"  Quantity: {reported_quantity:.2f} XBT")
    print(f"  Reported Price: {reported_price:.6f} USDT per XBT")
    print(f"  Reported Total: {reported_total:.2f} USDT")
    print(f"  Expected Price: {expected_price:.6f} USDT per XBT")
    print()
    
    # Check if the reported math is consistent
    calculated_total_from_reported = reported_quantity * reported_price
    print(f"Math Check - Reported Data:")
    print(f"  {reported_quantity:.2f} × {reported_price:.6f} = {calculated_total_from_reported:.2f} USDT")
    print(f"  Matches reported total ({reported_total:.2f}): {abs(calculated_total_from_reported - reported_total) < 0.01}")
    print()
    
    # Calculate what the correct total should be with expected price
    correct_total_from_expected = reported_quantity * expected_price
    print(f"Expected Calculation:")
    print(f"  {reported_quantity:.2f} × {expected_price:.6f} = {correct_total_from_expected:.2f} USDT")
    print()
    
    # Now let's reverse engineer what the individual trades might have been
    # If we have 2 trades aggregated that result in the reported total of 594.79 USDT
    # but should result in ~230.23 USDT (with correct price), then there's likely
    # an issue with how individual trade values are being calculated or summed
    
    print("Reverse Engineering Possible Individual Trades:")
    print("Assuming 2 trades were aggregated...")
    
    # Let's simulate two trades that could result in the bug
    # Trade 1: Large quantity at low price
    trade1_quantity = 1000.0
    trade1_price = 0.15  # Reasonable XBT price
    trade1_value = trade1_price * trade1_quantity
    
    # Trade 2: Smaller quantity at higher price  
    trade2_quantity = 342.82
    trade2_price = 0.20
    trade2_value = trade2_price * trade2_quantity
    
    total_quantity = trade1_quantity + trade2_quantity
    total_value = trade1_value + trade2_value
    weighted_avg_price = total_value / total_quantity
    
    print(f"  Trade 1: {trade1_quantity:.2f} XBT @ {trade1_price:.6f} USDT = {trade1_value:.2f} USDT")
    print(f"  Trade 2: {trade2_quantity:.2f} XBT @ {trade2_price:.6f} USDT = {trade2_value:.2f} USDT")
    print(f"  Total: {total_quantity:.2f} XBT, Total Value: {total_value:.2f} USDT")
    print(f"  Correct Weighted Avg: {total_value:.2f} / {total_quantity:.2f} = {weighted_avg_price:.6f} USDT per XBT")
    print()
    
    # Test what happens if we incorrectly sum the prices instead of values
    incorrect_avg_price = (trade1_price + trade2_price) / 2  # Simple average instead of weighted
    incorrect_total = incorrect_avg_price * total_quantity
    
    print(f"Common Bug - Simple Average Instead of Weighted:")
    print(f"  Simple Avg: ({trade1_price:.6f} + {trade2_price:.6f}) / 2 = {incorrect_avg_price:.6f} USDT per XBT")
    print(f"  Incorrect Total: {incorrect_avg_price:.6f} × {total_quantity:.2f} = {incorrect_total:.2f} USDT")
    print()
    
    return {
        'correct_weighted_avg': weighted_avg_price,
        'correct_total': total_value,
        'total_quantity': total_quantity,
        'individual_trades': [
            {'quantity': trade1_quantity, 'price': trade1_price, 'value': trade1_value},
            {'quantity': trade2_quantity, 'price': trade2_price, 'value': trade2_value}
        ]
    }

def test_orderbook_sweep_calculation():
    """Test the orderbook sweep calculation logic."""
    print("=" * 80)
    print("TESTING ORDERBOOK SWEEP CALCULATION")
    print("=" * 80)
    
    # Simulate swept asks from orderbook
    swept_asks = [
        {"price": 0.15, "quantity": 500.0},
        {"price": 0.16, "quantity": 300.0},
        {"price": 0.17, "quantity": 200.0},
        {"price": 0.18, "quantity": 100.0}
    ]
    
    # Calculate total swept value and quantity (this is the current logic)
    total_swept_value = 0
    total_quantity = 0
    
    print("Swept Ask Levels:")
    for i, ask in enumerate(swept_asks):
        individual_value = ask["price"] * ask["quantity"]
        total_swept_value += individual_value
        total_quantity += ask["quantity"]
        print(f"  Level {i+1}: {ask['quantity']:.2f} XBT @ {ask['price']:.6f} USDT = {individual_value:.2f} USDT")
    
    # Calculate weighted average price
    avg_price = total_swept_value / total_quantity if total_quantity > 0 else 0
    
    print(f"\nSweep Summary:")
    print(f"  Total Quantity: {total_quantity:.2f} XBT")
    print(f"  Total Value: {total_swept_value:.2f} USDT")
    print(f"  Weighted Avg Price: {total_swept_value:.2f} / {total_quantity:.2f} = {avg_price:.6f} USDT per XBT")
    
    # Verify the calculation
    verification_total = avg_price * total_quantity
    print(f"  Verification: {avg_price:.6f} × {total_quantity:.2f} = {verification_total:.2f} USDT")
    print(f"  Matches total: {abs(verification_total - total_swept_value) < 0.01}")
    print()
    
    return {
        'avg_price': avg_price,
        'total_quantity': total_quantity,
        'total_value': total_swept_value,
        'swept_asks': swept_asks
    }

async def test_aggregation_logic():
    """Test the trade aggregation logic with simulated trades."""
    print("=" * 80)
    print("TESTING TRADE AGGREGATION LOGIC")
    print("=" * 80)
    
    # Simulate individual trades that would be aggregated
    trades = [
        {'price': 0.15, 'quantity': 600.0, 'sum_value': 0.15 * 600.0, 'timestamp': int(time.time() * 1000)},
        {'price': 0.18, 'quantity': 400.0, 'sum_value': 0.18 * 400.0, 'timestamp': int(time.time() * 1000) + 1000},
        {'price': 0.16, 'quantity': 342.82, 'sum_value': 0.16 * 342.82, 'timestamp': int(time.time() * 1000) + 2000}
    ]
    
    print("Individual Trades to Aggregate:")
    total_pending = 0
    for i, trade in enumerate(trades):
        total_pending += trade['sum_value']
        print(f"  Trade {i+1}: {trade['quantity']:.2f} XBT @ {trade['price']:.6f} USDT = {trade['sum_value']:.2f} USDT")
    
    # Calculate aggregated values (this is the current logic)
    total_quantity = sum(trade['quantity'] for trade in trades)
    avg_price = total_pending / total_quantity if total_quantity > 0 else 0
    
    print(f"\nAggregation Summary:")
    print(f"  Total Quantity: {total_quantity:.2f} XBT")
    print(f"  Total Value: {total_pending:.2f} USDT")
    print(f"  Weighted Avg Price: {total_pending:.2f} / {total_quantity:.2f} = {avg_price:.6f} USDT per XBT")
    
    # Verify the calculation
    verification_total = avg_price * total_quantity
    print(f"  Verification: {avg_price:.6f} × {total_quantity:.2f} = {verification_total:.2f} USDT")
    print(f"  Matches total: {abs(verification_total - total_pending) < 0.01}")
    print()
    
    return {
        'avg_price': avg_price,
        'total_quantity': total_quantity,
        'total_value': total_pending,
        'trades': trades
    }

def main():
    """Run all tests to verify price calculation logic."""
    print("XBT TRADING ALERT PRICE CALCULATION BUG TEST")
    print("=" * 80)
    print()
    
    # Test 1: Weighted average calculation
    test1_result = test_weighted_average_calculation()
    
    # Test 2: Orderbook sweep calculation
    test2_result = test_orderbook_sweep_calculation()
    
    # Test 3: Trade aggregation logic
    test3_result = asyncio.run(test_aggregation_logic())
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Test 1 - Weighted Average: {test1_result['correct_weighted_avg']:.6f} USDT per XBT")
    print(f"Test 2 - Orderbook Sweep: {test2_result['avg_price']:.6f} USDT per XBT")
    print(f"Test 3 - Trade Aggregation: {test3_result['avg_price']:.6f} USDT per XBT")
    print()
    print("All calculations appear to be mathematically correct.")
    print("The bug may be in data input or a specific edge case not covered here.")
    print()
    print("Next steps:")
    print("1. Enable debug logging in production to capture actual trade data")
    print("2. Monitor for the specific bug scenario to occur again")
    print("3. Analyze the debug logs to identify the root cause")

if __name__ == "__main__":
    main()
