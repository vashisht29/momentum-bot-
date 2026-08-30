import urllib.request
import json
import datetime

def find_all_lows():
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
        
        matches = []
        for idx, c in enumerate(candles):
            if abs(c["low"] - 0.004049) < 0.000008 or (c["low"] <= 0.004052 and c["low"] >= 0.004040):
                utc_time = datetime.datetime.fromtimestamp(c["time"]/1000, datetime.timezone.utc)
                ist_time = utc_time.astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
                matches.append((idx, utc_time, ist_time, c))
                
        print(f"Found {len(matches)} potential low candles:")
        for idx, utc, ist, c in matches:
            print(f"Index {idx} | UTC: {utc.strftime('%Y-%m-%d %H:%M')} | IST: {ist.strftime('%Y-%m-%d %H:%M')} | Low: {c['low']:.6f} | Close: {c['close']:.6f}")
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    find_all_lows()
