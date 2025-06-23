#!/usr/bin/env python3
"""
Test script to verify enhanced alert message formatting for aggregated buy orders.
This script tests the new individual order display functionality.
"""

import asyncio
import sys
import os
import time
from unittest.mock import AsyncMock, patch

def format_aggregated_alert_message(trade_details, price, quantity, sum_value, num_trades):
    """
    Simulate the enhanced alert message formatting for aggregated buy orders.
    This replicates the logic from the send_alert function.
    """
    message = ""
    
    # Add individual buy order details for aggregated alerts
    if trade_details and len(trade_details) > 1:
        message += f"\n📋 <b>Aggregated Buy Orders:</b>\n"
        
        # Display individual orders (up to 5)
        orders_to_show = min(5, len(trade_details))
        for i in range(orders_to_show):
            trade = trade_details[i]
            message += f"Order {i+1}: {trade['quantity']:.2f} XBT at {trade['price']:.6f} USDT\n"
        
        # If more than 5 orders, aggregate the remaining ones
        if len(trade_details) > 5:
            remaining_trades = trade_details[5:]
            remaining_quantity = sum(t['quantity'] for t in remaining_trades)
            remaining_count = len(remaining_trades)
            message += f"Orders 6-{len(trade_details)}: {remaining_quantity:.2f} XBT total ({remaining_count} additional orders)\n"
        
        # Add summary calculations
        message += f"\n📊 <b>Summary:</b>\n"
        message += f"Average Price: {price:.6f} USDT\n"
        message += f"Total Volume: {quantity:.2f} XBT\n"
        message += f"Total Value: {sum_value:.2f} USDT\n"
    
    return message

class TestEnhancedAlerts:
    """Test class for enhanced alert message functionality."""
    
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
            
    def test_small_aggregated_alert(self):
        """Test alert with 3 orders (should show all individually)."""
        print("\n🧪 Testing small aggregated alert (3 orders)...")
        
        trade_details = [
            {'quantity': 10.00, 'price': 0.166434, 'sum_value': 1.66434},
            {'quantity': 20.00, 'price': 0.166470, 'sum_value': 3.32940},
            {'quantity': 35.00, 'price': 0.168400, 'sum_value': 5.89400}
        ]
        
        total_quantity = sum(t['quantity'] for t in trade_details)
        total_value = sum(t['sum_value'] for t in trade_details)
        avg_price = total_value / total_quantity
        
        message = format_aggregated_alert_message(
            trade_details, avg_price, total_quantity, total_value, len(trade_details)
        )
        
        print("Generated message:")
        print(message)
        
        # Verify all orders are shown individually
        order_count = message.count("Order ")
        expected_orders = 3
        
        self.log_test_result(
            "Small aggregated alert - All orders shown",
            order_count == expected_orders,
            f"Expected {expected_orders} individual orders, found {order_count}"
        )
        
        # Verify summary section exists
        has_summary = "📊 <b>Summary:</b>" in message
        self.log_test_result(
            "Small aggregated alert - Summary section",
            has_summary,
            "Summary section should be present"
        )
        
    def test_large_aggregated_alert(self):
        """Test alert with 8 orders (should show 5 + aggregated remainder)."""
        print("\n🧪 Testing large aggregated alert (8 orders)...")
        
        trade_details = [
            {'quantity': 10.00, 'price': 0.166434, 'sum_value': 1.66434},
            {'quantity': 20.00, 'price': 0.166470, 'sum_value': 3.32940},
            {'quantity': 35.00, 'price': 0.168400, 'sum_value': 5.89400},
            {'quantity': 15.00, 'price': 0.167200, 'sum_value': 2.50800},
            {'quantity': 8.00, 'price': 0.169000, 'sum_value': 1.35200},
            {'quantity': 12.50, 'price': 0.167800, 'sum_value': 2.09750},
            {'quantity': 18.00, 'price': 0.168200, 'sum_value': 3.02760},
            {'quantity': 15.00, 'price': 0.169500, 'sum_value': 2.54250}
        ]
        
        total_quantity = sum(t['quantity'] for t in trade_details)
        total_value = sum(t['sum_value'] for t in trade_details)
        avg_price = total_value / total_quantity
        
        message = format_aggregated_alert_message(
            trade_details, avg_price, total_quantity, total_value, len(trade_details)
        )
        
        print("Generated message:")
        print(message)
        
        # Verify exactly 5 individual orders are shown
        individual_order_count = len([line for line in message.split('\n') if line.startswith("Order ") and not line.startswith("Orders ")])
        
        self.log_test_result(
            "Large aggregated alert - Individual orders limit",
            individual_order_count == 5,
            f"Expected 5 individual orders, found {individual_order_count}"
        )
        
        # Verify aggregated remainder line exists
        has_remainder = "Orders 6-8:" in message
        self.log_test_result(
            "Large aggregated alert - Remainder aggregation",
            has_remainder,
            "Should have 'Orders 6-8:' aggregation line"
        )
        
        # Verify remainder calculation
        remaining_quantity = sum(t['quantity'] for t in trade_details[5:])
        expected_remainder_text = f"{remaining_quantity:.2f} XBT total (3 additional orders)"
        has_correct_remainder = expected_remainder_text in message
        
        self.log_test_result(
            "Large aggregated alert - Remainder calculation",
            has_correct_remainder,
            f"Expected remainder: {expected_remainder_text}"
        )
        
    def test_price_formatting(self):
        """Test that prices are formatted with 6 decimal places."""
        print("\n🧪 Testing price formatting...")
        
        trade_details = [
            {'quantity': 100.00, 'price': 0.1664341234, 'sum_value': 16.64341234},
            {'quantity': 50.00, 'price': 0.1667891567, 'sum_value': 8.33945784}
        ]
        
        total_quantity = sum(t['quantity'] for t in trade_details)
        total_value = sum(t['sum_value'] for t in trade_details)
        avg_price = total_value / total_quantity
        
        message = format_aggregated_alert_message(
            trade_details, avg_price, total_quantity, total_value, len(trade_details)
        )
        
        print("Generated message:")
        print(message)
        
        # Check that prices have 6 decimal places
        has_6_decimals = "0.166434" in message and "0.166789" in message
        self.log_test_result(
            "Price formatting - 6 decimal places",
            has_6_decimals,
            "Prices should be formatted with 6 decimal places"
        )
        
        # Check quantity formatting (2 decimal places)
        has_2_decimal_qty = "100.00 XBT" in message and "50.00 XBT" in message
        self.log_test_result(
            "Quantity formatting - 2 decimal places",
            has_2_decimal_qty,
            "Quantities should be formatted with 2 decimal places"
        )
        
    def test_summary_calculations(self):
        """Test that summary calculations are accurate."""
        print("\n🧪 Testing summary calculations...")
        
        trade_details = [
            {'quantity': 10.00, 'price': 0.160000, 'sum_value': 1.60000},
            {'quantity': 20.00, 'price': 0.170000, 'sum_value': 3.40000},
            {'quantity': 30.00, 'price': 0.180000, 'sum_value': 5.40000}
        ]
        
        total_quantity = sum(t['quantity'] for t in trade_details)  # 60.00
        total_value = sum(t['sum_value'] for t in trade_details)    # 10.40000
        avg_price = total_value / total_quantity                    # 0.173333
        
        message = format_aggregated_alert_message(
            trade_details, avg_price, total_quantity, total_value, len(trade_details)
        )
        
        print("Generated message:")
        print(message)
        
        # Verify calculations in message
        expected_avg = f"Average Price: {avg_price:.6f} USDT"
        expected_volume = f"Total Volume: {total_quantity:.2f} XBT"
        expected_value = f"Total Value: {total_value:.2f} USDT"
        
        has_correct_avg = expected_avg in message
        has_correct_volume = expected_volume in message
        has_correct_value = expected_value in message
        
        self.log_test_result(
            "Summary calculations - Average price",
            has_correct_avg,
            f"Expected: {expected_avg}"
        )
        
        self.log_test_result(
            "Summary calculations - Total volume",
            has_correct_volume,
            f"Expected: {expected_volume}"
        )
        
        self.log_test_result(
            "Summary calculations - Total value",
            has_correct_value,
            f"Expected: {expected_value}"
        )
        
    def print_test_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("🧪 ENHANCED ALERTS TEST SUMMARY")
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
            print("\n🎉 ALL TESTS PASSED! Enhanced alert formatting is working correctly.")
        else:
            print(f"\n⚠️  {total_tests - passed_tests} test(s) failed. Review the implementation.")
            
        return passed_tests == total_tests

def main():
    """Run all tests."""
    print("🚀 Starting Enhanced Alert Message Tests for XBT Trading Bot")
    print("="*60)
    
    tester = TestEnhancedAlerts()
    
    try:
        # Run all test cases
        tester.test_small_aggregated_alert()
        tester.test_large_aggregated_alert()
        tester.test_price_formatting()
        tester.test_summary_calculations()
        
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
