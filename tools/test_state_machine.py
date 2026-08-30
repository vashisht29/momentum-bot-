import urllib.request
import json
import sys
import datetime

sys.path.append("/Users/air/.gemini/antigravity/scratch/momentum_bot_fixed")
import config
from confirmation import confirm_buy_signal

def run_historical_test():
    symbol = "1000BONKUSDT"
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=5m&limit=1000"
    
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
            "time": int(k[0]),
            "symbol": symbol
        } for k in klines]
        
        # Find index matching 11:45 IST on June 26
        match_idx = None
        for idx, c in enumerate(candles):
            utc_time = datetime.datetime.fromtimestamp(c["time"]/1000, datetime.timezone.utc)
            ist_time = utc_time.astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
            if ist_time.strftime('%Y-%m-%d %H:%M') == "2026-06-26 11:45":
                match_idx = idx
                break
                
        if match_idx is None:
            print("Could not find the 11:45 IST candle.")
            return

        # -------------------------------------------------------------
        # TEST 1: Strict Config (PULLBACK_MIN = 15.0, PULLBACK_MAX = 54.0)
        # Should fail because depth is 55.6%
        # -------------------------------------------------------------
        config.PULLBACK_MIN = 15.0
        config.PULLBACK_MAX = 54.0
        
        print("\n" + "="*80)
        print("TEST 1: STRICT PULLBACK CONFIG (15% - 54%) - EXPECTED: FAILED")
        print("="*80)
        
        target_time = "2026-06-26 12:55"
        end_idx = next(idx for idx, c in enumerate(candles) if datetime.datetime.fromtimestamp(c["time"]/1000, datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime('%Y-%m-%d %H:%M') == target_time)
        
        passed, report = confirm_buy_signal(candles[:end_idx + 1])
        print(f"RESULT: {'PASSED' if passed else 'FAILED'}")
        print("REPORT:", report)
        
        # -------------------------------------------------------------
        # TEST 2: Relaxed Pullback (PULLBACK_MIN = 10.0, PULLBACK_MAX = 70.0)
        # Should pass because 55.6% depth is within limits, and verify the transitions
        # -------------------------------------------------------------
        config.PULLBACK_MIN = 10.0
        config.PULLBACK_MAX = 70.0
        
        print("\n" + "="*80)
        print("TEST 2: RELAXED PULLBACK CONFIG (10% - 70%) - EXPECTED: PASSED (TRIGGER BUY)")
        print("="*80)
        
        passed, report = confirm_buy_signal(candles[:end_idx + 1])
        print(f"RESULT: {'PASSED' if passed else 'FAILED'}")
        print("REPORT:", report)
        if passed:
            print(f"  Entry: {report['entry_price']:.6f}")
            print(f"  SL: {report['stop_loss']:.6f} (Expected: 0.004045 based on 0.004049 swing low)")
            print(f"  TP: {report['take_profit']:.6f}")
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    run_historical_test()
