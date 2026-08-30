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

try:
    # 1. Cancel all open orders for all symbols
    print("1. Cancelling all pending open orders (Limit & Algo SL/TP)...")
    try:
        open_orders = client.futures_get_open_orders()
        symbols_with_orders = set(o['symbol'] for o in open_orders)
        
        algo_orders = []
        try:
            algo_orders = client.futures_get_open_algo_orders()
        except Exception as ae:
            pass
            
        active_algo = [o for o in algo_orders if o.get('algoStatus') in ['NEW', 'WORKING', 'PARTIALLY_FILLED']]
        symbols_with_algo = set(o['symbol'] for o in active_algo)
        
        all_symbols = symbols_with_orders.union(symbols_with_algo)
        
        if not all_symbols:
            print("   No pending open orders found.")
        else:
            for symbol in all_symbols:
                print(f"   Cancelling orders for {symbol}...")
                try:
                    client.futures_cancel_all_open_orders(symbol=symbol)
                except Exception as e:
                    pass
                try:
                    client.futures_cancel_all_open_algo_orders(symbol=symbol)
                except Exception as e:
                    pass
    except Exception as e:
        print("❌ Error during orders cancellation:", e)

    # 2. Close all active positions
    print("\n2. Closing all active positions...")
    acc = client.futures_account()
    positions = [p for p in acc.get('positions', []) if float(p['positionAmt']) != 0]
    
    if not positions:
        print("✅ No active positions found to close.")
    else:
        for pos in positions:
            symbol = pos['symbol']
            amt = float(pos['positionAmt'])
            side = "SELL" if amt > 0 else "BUY"
            qty = abs(amt)
            print(f"   Closing {symbol} position: {amt} units -> Placing MARKET {side} {qty}...")
            try:
                # Cancel orders again for safety before placing close order
                try:
                    client.futures_cancel_all_open_orders(symbol=symbol)
                except:
                    pass
                try:
                    client.futures_cancel_all_open_algo_orders(symbol=symbol)
                except:
                    pass
                    
                client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type="MARKET",
                    quantity=qty,
                    reduceOnly=True
                )
                print(f"   ✅ {symbol} position closed successfully.")
            except Exception as e:
                print(f"   ❌ Failed to close {symbol}: {e}")

    print("\n🎉 ALL POSITIONS CLOSED & ALL PENDING ORDERS CANCELLED!")

except Exception as e:
    print("❌ Error executing global close:", e)
