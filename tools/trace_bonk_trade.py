import urllib.request
import json
import sys
import datetime

sys.path.append("/Users/air/.gemini/antigravity/scratch/momentum_bot_fixed")
import config
from confirmation import (
    confirm_buy_signal, 
    detect_breakout, 
    check_volume_spike, 
    check_recovery_candle,
    find_swing_lows,
    calculate_atr
)

def trace_trade():
    symbol = "1000BONKUSDT"
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=5m&limit=300"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as r:
            klines = json.loads(r.read().decode())
            
        candles = [{
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "time": int(k[0])
        } for k in klines]
        
        # We know the breakout happens after 11:45 (Index 262)
        # Let's run confirm_buy_signal for subsets starting around index 265 to 285
        print("Tracing confirmation outputs around the trade period:")
        for i in range(263, min(len(candles), 295)):
            subset = candles[:i+1]
            passed, report = confirm_buy_signal(subset)
            ist_time = datetime.datetime.fromtimestamp(subset[-1]["time"]/1000, datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime('%Y-%m-%d %H:%M')
            if passed:
                print(f"Index {i} | IST {ist_time} | PASSED!")
                print(f"  Entry: {report['entry_price']:.6f} | SL: {report['stop_loss']:.6f} | TP: {report['take_profit']:.6f}")
            else:
                print(f"Index {i} | IST {ist_time} | FAILED | Reason: {report.get('failed_at')}")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    trace_trade()
