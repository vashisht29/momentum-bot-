import os
import sys
from binance.client import Client
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

if not API_KEY or not API_SECRET:
    print("[ERROR] BINANCE_API_KEY or BINANCE_API_SECRET is missing.")
    sys.exit(1)

client = Client(API_KEY, API_SECRET)
symbol = 'UNIUSDT'

try:
    print(f"Fetching position details for {symbol}...")
    acc = client.futures_account()
    positions = [p for p in acc.get('positions', []) if p['symbol'] == symbol]
    
    if not positions:
        print(f"❌ No position found for {symbol} on this account.")
    else:
        pos = positions[0]
        amt = float(pos['positionAmt'])
        if amt == 0:
            print(f"❌ Position size is 0 for {symbol} (no active position).")
        else:
            print(f"Found active position for {symbol}: {amt} units")
            side = "SELL" if amt > 0 else "BUY"
            qty = abs(amt)
            
            print(f"1. Cancelling all open orders for {symbol} to prevent conflicts...")
            try:
                client.futures_cancel_all_open_orders(symbol=symbol)
                # If they are Portfolio Margin algo orders, cancel them too
                try:
                    client.futures_cancel_all_open_algo_orders(symbol=symbol)
                except:
                    pass
            except Exception as ce:
                print(f"Warning: Cancel orders failed: {ce}")
                
            print(f"2. Placing MARKET order to close position. Side: {side}, Qty: {qty}...")
            res = client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=qty,
                reduceOnly=True
            )
            print("✅ Position closed successfully! API Response:")
            print(res)
except Exception as e:
    print("❌ Error executing close position:", e)
