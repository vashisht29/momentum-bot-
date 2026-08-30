import urllib.request
import json
import sys

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

def run_trace():
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
        
        import datetime
        for end_idx in range(50, len(candles) + 1):
            subset = candles[:end_idx]
            passed, report = confirm_buy_signal(subset)
            if passed and datetime.datetime.fromtimestamp(subset[-1]["time"]/1000).strftime('%Y-%m-%d %H:%M') == "2026-06-26 12:55":
                # Let's reproduce the steps
                bo_idx = None
                max_lookback = config.BREAKOUT_LOOKBACK + config.PULLBACK_MAX_CANDLES_AFTER_BREAKOUT
                start_idx = max(0, len(subset) - max_lookback)
                
                print("--- STEP-BY-STEP TRACE FOR 12:55 SIGNAL ---")
                for i in range(len(subset) - 2, start_idx - 1, -1):
                    direction, reason = detect_breakout(subset[:i + 1])
                    if direction == "LONG":
                        vol_ok, vol_reason = check_volume_spike(subset[:i + 1])
                        if vol_ok:
                            bo_idx = i
                            bo_time = datetime.datetime.fromtimestamp(subset[i]["time"]/1000).strftime('%H:%M')
                            print(f"1. Breakout Candle Found at {bo_time} (Close: {subset[i]['close']:.6f})")
                            print(f"   - Breakout Volume Spike: PASS ({vol_reason})")
                            break

                bo_candle = subset[bo_idx]
                bo_range = bo_candle["high"] - bo_candle["low"]
                
                pullback_low = float('inf')
                trigger_high = None
                triggered_at_idx = None
                
                print("2. Pullback & Recovery Candles Tracking:")
                for idx in range(bo_idx + 1, len(subset)):
                    curr_candle = subset[idx]
                    curr_time = datetime.datetime.fromtimestamp(curr_candle["time"]/1000).strftime('%H:%M')
                    
                    if trigger_high is not None and curr_candle["high"] > trigger_high * 1.001:
                        triggered_at_idx = idx
                        print(f"   - {curr_time}: Trigger high of {trigger_high:.6f} BROKEN at {curr_candle['high']:.6f} -> Entry Triggered!")
                        break
                        
                    if curr_candle["low"] < pullback_low:
                        pullback_low = curr_candle["low"]
                        print(f"   - {curr_time}: New Pullback Low = {pullback_low:.6f}")
                        trigger_high = None
                        
                    rec_ok, rec_reason = check_recovery_candle(curr_candle, "LONG")
                    if rec_ok:
                        depth = (bo_candle["high"] - curr_candle["low"]) / bo_range * 100
                        print(f"   - {curr_time}: Recovery Candle Found. Pullback Depth = {depth:.1f}% (Range: 10%-70%)")
                        if config.PULLBACK_DEPTH_MIN <= depth <= config.PULLBACK_DEPTH_MAX:
                            trigger_high = curr_candle["high"]
                            print(f"     -> Active Trigger High set to {trigger_high:.6f}")

                print("3. Execution Details:")
                swings = find_swing_lows(subset, count=1, window=3)
                if swings:
                    print(f"   - Swing Low detected by helper: {swings[-1]['price']:.6f}")
                else:
                    print("   - No swing low detected by helper.")
                print(f"   - Entry Price: {report['entry_price']:.6f}")
                print(f"   - Stop Loss (SL): {report['stop_loss']:.6f}")
                print(f"   - Take Profit (TP): {report['take_profit']:.6f}")
                print("------------------------------------------")
                break
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_trace()
