import os
import sys
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from binance.client import Client

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

if not API_KEY or not API_SECRET:
    print("[ERROR] BINANCE_API_KEY or BINANCE_API_SECRET is missing in .env file.")
    sys.exit(1)

try:
    client = Client(API_KEY, API_SECRET)
except Exception as e:
    print(f"[ERROR] Failed to initialize Binance Client: {e}")
    sys.exit(1)

def get_symbol_precision(client, symbol):
    try:
        info = client.futures_exchange_info()
        for s in info['symbols']:
            if s['symbol'] == symbol:
                return s.get('pricePrecision', 4), s.get('quantityPrecision', 3)
    except Exception as e:
        print(f"[WARN] Precision fetch failed: {e}")
    return 4, 3

print("=" * 60)
print("             FORCE ATTACH SL/TP TO OPEN TRADES")
print("=" * 60)

try:
    account = client.futures_account()
    positions = [p for p in account.get('positions', []) if float(p['positionAmt']) != 0]

    if not positions:
        print("❌ No active open positions found to fix.")
    else:
        for pos in positions:
            symbol = pos['symbol']
            amt = float(pos['positionAmt'])
            direction = "LONG" if amt > 0 else "SHORT"
            opposite_side = "SELL" if direction == "LONG" else "BUY"
            entry_price = float(pos.get('entryPrice', 0))
            
            print(f"\nChecking {symbol} ({direction}) | Entry: {entry_price}")

            # Get active orders
            open_orders = client.futures_get_open_orders(symbol=symbol)
            has_sl = False
            has_tp = False

            for order in open_orders:
                order_type = order.get('type', '')
                if order_type in ['STOP_MARKET', 'STOP'] or order.get('closePosition') or 'STOP' in order_type:
                    has_sl = True
                elif order_type in ['TAKE_PROFIT_MARKET', 'TAKE_PROFIT'] or order.get('closePosition') or 'PROFIT' in order_type:
                    has_tp = True

            price_prec, _ = get_symbol_precision(client, symbol)

            # Define SL/TP targets: 2% SL, 4% TP
            sl = round(entry_price * 0.98 if direction == "LONG" else entry_price * 1.02, price_prec)
            tp = round(entry_price * 1.04 if direction == "LONG" else entry_price * 0.96, price_prec)

            if not has_sl:
                print(f"  👉 Missing SL. Attempting to place Stop Loss at {sl}...")
                try:
                    sl_resp = client.futures_create_order(
                        symbol=symbol,
                        side=opposite_side,
                        type="STOP_MARKET",
                        stopPrice=sl,
                        closePosition=True
                    )
                    print(f"  ✅ SL attached successfully! OrderID: {sl_resp.get('orderId')}")
                except Exception as e:
                    print(f"  ❌ Failed to attach SL: {e}")
            else:
                print("  ✅ SL already active.")

            if not has_tp:
                print(f"  👉 Missing TP. Attempting to place Take Profit at {tp}...")
                try:
                    tp_resp = client.futures_create_order(
                        symbol=symbol,
                        side=opposite_side,
                        type="TAKE_PROFIT_MARKET",
                        stopPrice=tp,
                        closePosition=True
                    )
                    print(f"  ✅ TP attached successfully! OrderID: {tp_resp.get('orderId')}")
                except Exception as e:
                    print(f"  ❌ Failed to attach TP: {e}")
            else:
                print("  ✅ TP already active.")
                
            print("-" * 60)

except Exception as e:
    print(f"[ERROR] Process failed: {e}")
