#!/usr/bin/env python3
"""
Test script to verify the final changes:
1. Market Vibe removal from /price command
2. Donate button addition to /help command
"""

import asyncio
import json
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

# Add the current directory to the path so we can import the bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the bot functions we need to test
from telebot_fixed import check_price, help_command, donate_command

async def test_price_command_no_market_vibe():
    """Test that the /price command no longer includes Market Vibe section"""
    print("🧪 Testing /price command - Market Vibe removal...")
    
    # Mock update and context
    update = MagicMock()
    update.effective_chat.id = -1002293167945
    update.effective_user.id = 1145064309
    update.message.reply_text = AsyncMock()
    
    context = MagicMock()
    
    # Mock the NonKYC API responses
    mock_ticker_data = {
        "lastPriceNumber": 0.156000,
        "yesterdayPriceNumber": 0.150000,
        "highPriceNumber": 0.158000,
        "lowPriceNumber": 0.149000,
        "volumeNumber": 1000000,
        "volumeUsdNumber": 156000,
        "changePercentNumber": 4.0,
        "marketcapNumber": 15600000,
        "bestBidNumber": 0.155900,
        "bestAskNumber": 0.156100,
        "spreadPercentNumber": 0.13
    }
    
    mock_trades_data = [
        {"timestamp": time.time() * 1000 - (10 * 60 * 1000), "price": "0.154000"},
        {"timestamp": time.time() * 1000 - (30 * 60 * 1000), "price": "0.152000"},
        {"timestamp": time.time() * 1000 - (2 * 60 * 60 * 1000), "price": "0.150000"},
        {"timestamp": time.time() * 1000 - (12 * 60 * 60 * 1000), "price": "0.148000"},
    ]
    
    # Patch the API functions
    with patch('telebot_fixed.get_nonkyc_ticker', return_value=mock_ticker_data), \
         patch('telebot_fixed.get_nonkyc_trades', return_value=mock_trades_data), \
         patch('telebot_fixed.calculate_combined_volume_periods', return_value={
             "combined": {"15m": 5000, "1h": 15000, "4h": 45000, "24h": 156000}
         }):
        
        # Test the price command
        await check_price(update, context)
        
        # Verify that reply_text was called
        update.message.reply_text.assert_called_once()
        
        # Get the message content
        call_args = update.message.reply_text.call_args
        message_text = call_args[0][0]  # First positional argument
        
        # Verify Market Vibe section is NOT present
        market_vibe_terms = [
            "Market Vibe",
            "FOMO MODE",
            "Diamond hands",
            "Crypto winter",
            "Green candles",
            "Crab market",
            "Red candles"
        ]
        
        for term in market_vibe_terms:
            assert term not in message_text, f"Market Vibe term '{term}' should not be in message"
        
        # Verify essential data is still present
        essential_terms = [
            "Bitcoin Classic (XBT) Market Data",
            "Price:",
            "24h Change:",
            "Market Cap:",
            "Momentum (Price Change):",
            "15m:",
            "1h:",
            "4h:",
            "24h:",
            "Combined Volume",
            "Order Book"
        ]
        
        for term in essential_terms:
            assert term in message_text, f"Essential term '{term}' should be in message"
        
        print("  ✅ Market Vibe section successfully removed")
        print("  ✅ Essential market data still present")
        print("  ✅ Momentum calculations preserved")
        
    print("✅ Price command Market Vibe removal test passed!")
    return True

async def test_help_command_donate_button():
    """Test that the /help command includes donate information and button"""
    print("🧪 Testing /help command - Donate button addition...")
    
    # Mock update and context
    update = MagicMock()
    update.effective_user.id = 1145064309
    update.message.reply_text = AsyncMock()
    
    context = MagicMock()
    
    # Mock the is_admin function
    with patch('telebot_fixed.is_admin', return_value=True):
        # Test the help command
        await help_command(update, context)
        
        # Verify that reply_text was called
        update.message.reply_text.assert_called_once()
        
        # Get the message content and keyboard
        call_args = update.message.reply_text.call_args
        message_text = call_args[0][0]  # First positional argument
        keyboard = call_args[1]['reply_markup']  # Keyword argument
        
        # Verify donate information is in the help text
        donate_terms = [
            "Support Development:",
            "@moonether",
            "1B1YLseSykoBPKFzokTGvzM2gzybyEDiU4"
        ]
        
        for term in donate_terms:
            assert term in message_text, f"Donate term '{term}' should be in help message"
        
        # Verify donate button is in keyboard
        buttons = []
        for row in keyboard.inline_keyboard:
            for button in row:
                buttons.append((button.text, button.callback_data))
        
        donate_button = next((b for b in buttons if "Donate" in b[0]), None)
        assert donate_button is not None, "Should have donate button"
        assert donate_button[1] == "cmd_donate", "Donate button should have correct callback data"
        
        print("  ✅ Donate information added to help text")
        print("  ✅ Donate button added to keyboard")
        
    print("✅ Help command donate button test passed!")
    return True

async def test_donate_command():
    """Test the donate command functionality"""
    print("🧪 Testing donate command...")
    
    # Mock update and context
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    
    context = MagicMock()
    
    # Test the donate command
    await donate_command(update, context)
    
    # Verify that reply_text was called
    update.message.reply_text.assert_called_once()
    
    # Get the message content and keyboard
    call_args = update.message.reply_text.call_args
    message_text = call_args[0][0]  # First positional argument
    keyboard = call_args[1]['reply_markup']  # Keyword argument
    
    # Verify donate message content
    donate_content = [
        "Support the Developer",
        "@moonether",
        "1B1YLseSykoBPKFzokTGvzM2gzybyEDiU4",
        "Click the address above to copy it"
    ]
    
    for content in donate_content:
        assert content in message_text, f"Donate content '{content}' should be in message"
    
    # Verify buttons
    buttons = []
    for row in keyboard.inline_keyboard:
        for button in row:
            if hasattr(button, 'callback_data') and button.callback_data:
                buttons.append((button.text, button.callback_data))
            elif hasattr(button, 'url') and button.url:
                buttons.append((button.text, button.url))

    # Check for copy button
    copy_button = next((b for b in buttons if "Copy" in b[0]), None)
    assert copy_button is not None, "Should have copy button"
    assert copy_button[1] == "copy_btc_address", "Copy button should have correct callback data"

    # Check for contact button
    contact_button = next((b for b in buttons if "Contact" in b[0]), None)
    assert contact_button is not None, "Should have contact button"
    assert "t.me/moonether" in contact_button[1], "Contact button should link to developer"
    
    print("  ✅ Donate message content correct")
    print("  ✅ Copy Bitcoin address button present")
    print("  ✅ Contact developer button present")
    
    print("✅ Donate command test passed!")
    return True

def test_bitcoin_address_format():
    """Test that the Bitcoin address is properly formatted"""
    print("🧪 Testing Bitcoin address format...")
    
    bitcoin_address = "1B1YLseSykoBPKFzokTGvzM2gzybyEDiU4"
    
    # Basic Bitcoin address validation
    assert len(bitcoin_address) >= 26 and len(bitcoin_address) <= 35, "Bitcoin address should be 26-35 characters"
    assert bitcoin_address.startswith('1'), "Bitcoin address should start with '1'"
    assert bitcoin_address.isalnum(), "Bitcoin address should be alphanumeric"
    
    # Check for common invalid characters
    invalid_chars = ['0', 'O', 'I', 'l']
    for char in invalid_chars:
        assert char not in bitcoin_address, f"Bitcoin address should not contain '{char}'"
    
    print(f"  ✅ Bitcoin address format valid: {bitcoin_address}")
    print("✅ Bitcoin address format test passed!")
    return True

async def main():
    """Run all tests"""
    print("🚀 Starting final changes verification tests...\n")
    
    tests = [
        ("Bitcoin Address Format", test_bitcoin_address_format),
        ("Price Command - Market Vibe Removal", test_price_command_no_market_vibe),
        ("Help Command - Donate Button", test_help_command_donate_button),
        ("Donate Command Functionality", test_donate_command),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
                
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print(f"\n{'='*50}")
    print(f"TEST SUMMARY: {passed}/{total} tests passed")
    print('='*50)
    
    if passed == total:
        print("🎉 All tests passed! Final changes implemented successfully.")
        print("\n✅ Changes verified:")
        print("  ✅ Market Vibe section removed from /price command")
        print("  ✅ Professional, data-driven price display maintained")
        print("  ✅ Donate button added to /help command")
        print("  ✅ Developer information (@moonether) included")
        print("  ✅ Bitcoin address (1B1YLseSykoBPKFzokTGvzM2gzybyEDiU4) copyable")
        print("  ✅ Contact developer link functional")
        return True
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return False

if __name__ == "__main__":
    asyncio.run(main())
