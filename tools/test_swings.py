import urllib.request
import json
import sys

def find_swing_lows_strict(candles, count=3, window=3):
    swings = []
    for i in range(window, len(candles) - window):
        low = candles[i]["low"]
        is_swing = True
        for j in range(1, window + 1):
            if candles[i - j]["low"] <= low or candles[i + j]["low"] <= low:
                is_swing = False
                break
        if is_swing:
            swings.append({"index": i, "price": low})
    return swings[-count:] if len(swings) >= count else swings

def find_swing_lows_relaxed(candles, count=3, window=3):
    swings = []
    for i in range(window, len(candles) - window):
        low = candles[i]["low"]
        is_swing = True
        for j in range(1, window + 1):
            if candles[i - j]["low"] < low or candles[i + j]["low"] < low:
                is_swing = False
                break
        if is_swing:
            swings.append({"index": i, "price": low})
    return swings[-count:] if len(swings) >= count else swings

def test():
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
        
        # Slice candles up to 12:55 candle (Index 276)
        subset = candles[:277]
        
        swings_strict = find_swing_lows_strict(subset, count=3, window=3)
        swings_relaxed = find_swing_lows_relaxed(subset, count=3, window=3)
        
        print("STRICT SWINGS:")
        for s in swings_strict:
            print(f"Index {s['index']} | Price: {s['price']:.6f}")
            
        print("\nRELAXED SWINGS:")
        for s in swings_relaxed:
            print(f"Index {s['index']} | Price: {s['price']:.6f}")
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test()
