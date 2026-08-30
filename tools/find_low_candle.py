import urllib.request
import json
import datetime

def find_low_candle():
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
        
        # Find index where low is close to 0.004049
        match_idx = None
        for idx, c in enumerate(candles):
            if abs(c["low"] - 0.004049) < 0.000005:
                match_idx = idx
                print(f"Found match at index {idx}, time UTC: {datetime.datetime.fromtimestamp(c['time']/1000).strftime('%H:%M')}")
                break
                
        if match_idx is not None:
            print("CANDLES AROUND THE LOW:")
            print(f"{'Time (UTC)':<12} | {'Time (Local)':<12} | {'Open':<10} | {'High':<10} | {'Low':<10} | {'Close':<10}")
            print("-" * 75)
            # Print 15 candles before and 25 candles after
            start = max(0, match_idx - 15)
            end = min(len(candles), match_idx + 25)
            for i in range(start, end):
                c = candles[i]
                utc_time = datetime.datetime.fromtimestamp(c["time"]/1000, datetime.timezone.utc)
                # Convert to UTC+5:30 (India Standard Time)
                ist_time = utc_time.astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
                
                utc_str = utc_time.strftime('%H:%M')
                ist_str = ist_time.strftime('%H:%M')
                
                marker = " <- LOW" if i == match_idx else ""
                print(f"{utc_str:<12} | {ist_str:<12} | {c['open']:<10.6f} | {c['high']:<10.6f} | {c['low']:<10.6f} | {c['close']:<10.6f}{marker}")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    find_low_candle()
