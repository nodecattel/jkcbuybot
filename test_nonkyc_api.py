#!/usr/bin/env python3
"""
Test script to check NonKYC API data availability
"""
import asyncio
import json
import websockets

async def test_nonkyc_ticker():
    """Test NonKYC ticker data to see what's available."""
    uri = "wss://ws.nonkyc.io"
    
    try:
        async with websockets.connect(uri, ping_interval=30) as websocket:
            # Request ticker data
            ticker_msg = {
                "method": "getMarket",
                "params": {
                    "symbol": "XBT/USDT"
                },
                "id": 999
            }
            await websocket.send(json.dumps(ticker_msg))
            
            # Wait for response
            response = json.loads(await websocket.recv())
            
            print("=== NonKYC Ticker Response ===")
            print(json.dumps(response, indent=2))
            
            if "result" in response:
                result = response["result"]
                print("\n=== Available Fields ===")
                for key, value in result.items():
                    print(f"{key}: {value} (type: {type(value).__name__})")
                
                # Check for volume and other market data
                volume_fields = [k for k in result.keys() if 'volume' in k.lower()]
                price_fields = [k for k in result.keys() if 'price' in k.lower()]
                change_fields = [k for k in result.keys() if 'change' in k.lower() or 'percent' in k.lower()]
                
                print(f"\nVolume fields: {volume_fields}")
                print(f"Price fields: {price_fields}")
                print(f"Change fields: {change_fields}")
                
                return result
            else:
                print("No result in response")
                return None
                
    except Exception as e:
        print(f"Error getting NonKYC ticker: {e}")
        return None

async def test_nonkyc_trades():
    """Test NonKYC trades data to calculate momentum."""
    uri = "wss://ws.nonkyc.io"
    
    try:
        async with websockets.connect(uri, ping_interval=30) as websocket:
            # Request trades data
            trades_msg = {
                "method": "getTrades",
                "params": {
                    "symbol": "XBT/USDT",
                    "limit": 100,
                    "sort": "DESC"
                },
                "id": 888
            }
            await websocket.send(json.dumps(trades_msg))
            
            # Wait for response
            response = json.loads(await websocket.recv())
            
            print("\n=== NonKYC Trades Response ===")
            if "result" in response and "data" in response["result"]:
                trades = response["result"]["data"]
                print(f"Number of trades: {len(trades)}")
                
                if trades:
                    print("\nFirst trade structure:")
                    print(json.dumps(trades[0], indent=2))
                    
                    # Calculate some basic momentum indicators
                    prices = [float(trade["price"]) for trade in trades]
                    volumes = [float(trade["quantity"]) for trade in trades]
                    
                    if len(prices) >= 2:
                        latest_price = prices[0]
                        older_price = prices[-1]
                        price_change = ((latest_price - older_price) / older_price) * 100
                        
                        total_volume = sum(volumes)
                        avg_price = sum(prices) / len(prices)
                        
                        print(f"\nCalculated metrics:")
                        print(f"Latest price: {latest_price}")
                        print(f"Oldest price (in sample): {older_price}")
                        print(f"Price change: {price_change:.2f}%")
                        print(f"Total volume (sample): {total_volume}")
                        print(f"Average price: {avg_price}")
                
                return trades
            else:
                print("No trades data in response")
                return None
                
    except Exception as e:
        print(f"Error getting NonKYC trades: {e}")
        return None

async def main():
    """Run all tests."""
    print("Testing NonKYC API data availability...\n")
    
    # Test ticker data
    ticker_data = await test_nonkyc_ticker()
    
    # Test trades data
    trades_data = await test_nonkyc_trades()
    
    print("\n=== Summary ===")
    if ticker_data:
        print("✅ Ticker data available")
        # Check for specific fields we need
        has_volume = any('volume' in k.lower() for k in ticker_data.keys())
        has_change = any('change' in k.lower() or 'percent' in k.lower() for k in ticker_data.keys())
        print(f"📊 Volume data: {'✅' if has_volume else '❌'}")
        print(f"📈 Change data: {'✅' if has_change else '❌'}")
    else:
        print("❌ Ticker data not available")
    
    if trades_data:
        print("✅ Trades data available for momentum calculation")
    else:
        print("❌ Trades data not available")

if __name__ == "__main__":
    asyncio.run(main())
