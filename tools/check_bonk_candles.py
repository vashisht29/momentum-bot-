import urllib.request
import json
import datetime

def print_bonk_candles():
    symbol = "1000BONKUSDT"
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=5m&limit=150"
    
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
        
        print("BONK CANDLES REPORT:")
        print(f"{'Time':<8} | {'Open':<10} | {'High':<10} | {'Low':<10} | {'Close':<10} | {'Volume':<12}")
        print("-" * 75)
        for c in candles:
            time_str = datetime.datetime.fromtimestamp(c["time"]/1000).strftime('%H:%M')
            # Only print around our window
            if "12:15" <= time_str <= "13:10":
                print(f"{time_str:<8} | {c['open']:<10.6f} | {c['high']:<10.6f} | {c['low']:<10.6f} | {c['close']:<10.6f} | {c['volume']:<12.1f}")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    print_bonk_candles()
