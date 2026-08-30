#!/bin/bash
set -e
cd /root/momentum_bot
pkill -f "python.*main.py" 2>/dev/null || true
sleep 1
mkdir -p backup/active_backup
for f in config.py confirmation.py trade_manager.py strategy.py main.py check_sl_tp.py check_rejections.py; do
  [ -f "$f" ] && cp "$f" "backup/active_backup/${f}.bak" || true
done

cat > config.py << 'ENDOF_CONFIG_PY'
# config.py
# SCEPTER MOMENTUM BOT v5.0 — CLEAN CONFIG

# ═══════════════════════════════════════════
# GENERAL
# ═══════════════════════════════════════════
SLEEP_SECONDS = 15
TIMEFRAME = "5m"


# ═══════════════════════════════════════════
# RISK MANAGEMENT
# ═══════════════════════════════════════════
MAX_OPEN_TRADES = 2
MAX_RISK_PERCENT = 1.5
RISK_PER_TRADE_PERCENT = 1.0
MAX_SL_PERCENT = 1.5
MAX_MARGIN_PER_TRADE_PERCENT = 50.0
LEVERAGE = 5
CAPITAL_USE_PERCENT = 100
RR_RATIO = 2.0
RISK_REWARD_RATIO = 2
EMERGENCY_DRAWDOWN_PERCENT = 100.0

# ═══════════════════════════════════════════
# INDICATORS
# ═══════════════════════════════════════════
ATR_PERIOD = 14
ATR_EXPANSION_RATIO = 0.80

# ═══════════════════════════════════════════
# VOLUME
# ═══════════════════════════════════════════
VOLUME_LOOKBACK = 10
VOLUME_SPIKE_RATIO = 0.80
VOLUME_BREAKOUT_GT_PULLBACK = True

# ═══════════════════════════════════════════
# BREAKOUT & PULLBACK
# ═══════════════════════════════════════════
BREAKOUT_LOOKBACK = 6
BREAKOUT_RANGE_MIN = 0.50
BREAKOUT_BODY_MIN = 0.40
BREAKOUT_BODY_MAX = 0.50
PULLBACK_MIN = 14.0
PULLBACK_MAX = 54.0
PULLBACK_DEPTH_MIN = 14.0
PULLBACK_DEPTH_MAX = 54.0
PULLBACK_REJECT_ZONE_MAX = 95.0
PULLBACK_MAX_CANDLES_AFTER_BREAKOUT = 9
PULLBACK_TIMING_MAX = 9
CONSOLIDATION_MIN_RANGE_PCT = 0.25
REQUIRE_PURE_BULLISH_SWINGS = True
ADX_PERIOD = 14
ADX_MIN_SLOPE = -1.5

# ═══════════════════════════════════════════
# CANDLE FILTERS
# ═══════════════════════════════════════════
MIN_RANGE_RATIO = 1.0
MIN_BODY_RATIO = 0.40
MAX_UPPER_WICK_RATIO = 0.25
UPPER_WICK_MAX = 0.25

# ═══════════════════════════════════════════
# OVEREXTENSION
# ═══════════════════════════════════════════
OVEREXTENSION_LOOKBACK = 8
OVEREXTENSION_BULLISH_THRESHOLD = 8
CONSECUTIVE_BULLISH_MAX = 8

# ═══════════════════════════════════════════
# ENGULFING
# ═══════════════════════════════════════════
BEARISH_ENGULFING_RATIO = 1.0
BEARISH_ENGULFING_BODY = 0.60
BULLISH_ENGULFING_BODY = 0.60
ENGULFING_MIN_BODY_RATIO = 0.60

# ═══════════════════════════════════════════
# ENTRY & EXIT
# ═══════════════════════════════════════════
ENTRY_BUFFER_PERCENT = 0.10
MAX_SLIPPAGE_PERCENT = 5.0
SLIPPAGE_MAX = 5.0
MAX_SPREAD_PERCENT = 0.27
SPREAD_MAX = 0.27
LONG_EXIT_MIN_R = 1.0

# ═══════════════════════════════════════════
# SELL — FAILED BREAKOUT
# ═══════════════════════════════════════════
FAILED_BREAKOUT_MIN = 65.0
FAILED_BREAKOUT_MAX = 95.0

# ═══════════════════════════════════════════
# SELL — SWING REQUIREMENTS
# ═══════════════════════════════════════════
SWING_LOWS_REQUIRED = 3
SWING_HIGHS_REQUIRED = 3
MIN_SWING_LOWS_SHORT = 3
MIN_SWING_HIGHS_LONG = 2
RECOVERY_CANDLE_MIN_BODY = 0.30
RECOVERY_CANDLE_MAX_WICK = 0.25

# ═══════════════════════════════════════════
# CONFIRMATION SYSTEM
# ═══════════════════════════════════════════
USE_CONFIRMATION = True
REQUIRE_CONFIRMATION = True

# ═══════════════════════════════════════════
# ORDER
# ═══════════════════════════════════════════
ORDER_TYPE = "maker_limit"

# ═══════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════
TRADES_LOG_FOLDER = "logs/trades"
REJECTION_LOG_FOLDER = "logs/rejections"
BACKUP_LOG_FOLDER = "logs/backup"
ENDOF_CONFIG_PY
echo "[OK] config.py"

cat > confirmation.py << 'ENDOF_CONFIRMATION_PY'
"""
CONFIRMATION — Clean Strategy Logic (Breakout & Retest Rules)
Strict: No trade without active setup validation
"""

import math
import config


# ═══════════════════════════════════════════
# HELPER: VOLUME CHECK
# ═══════════════════════════════════════════

def check_volume_spike(candles, lookback=None, spike_ratio=None):
    if lookback is None:
        lookback = config.VOLUME_LOOKBACK
    if spike_ratio is None:
        spike_ratio = config.VOLUME_SPIKE_RATIO
        
    if len(candles) < lookback + 1:
        return False, f"not enough candles for volume check ({len(candles)} < {lookback + 1})"

    curr_vol = candles[-1]["volume"]
    prev_vols = [c["volume"] for c in candles[-lookback - 1 : -1]]
    avg_vol = sum(prev_vols) / len(prev_vols)

    if avg_vol == 0:
        return False, "average volume is 0"

    ratio = curr_vol / avg_vol
    if ratio >= spike_ratio:
        return True, f"volume spike confirmed ({ratio:.2f}x >= {spike_ratio}x)"
    return False, f"volume ratio {ratio:.2f} < {spike_ratio}"


# ═══════════════════════════════════════════
# HELPER: ATR (VOLATILITY)
# ═══════════════════════════════════════════

def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return 0.0

    tr_list = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)

    return sum(tr_list[-period:]) / period


def check_atr_expansion(candles):
    period = config.ATR_PERIOD  # default 14
    if len(candles) < period + 50:
        return False, f"not enough candles for ATR check ({len(candles)} < {period + 50})"

    curr_atr = calculate_atr(candles, period)
    if curr_atr == 0:
        return False, "current ATR is 0"

    atr_history = []
    for i in range(len(candles) - 50, len(candles)):
        atr_val = calculate_atr(candles[:i], period)
        if atr_val > 0:
            atr_history.append(atr_val)

    if not atr_history:
        return False, "no historical ATR data"

    avg_atr = sum(atr_history) / len(atr_history)
    ratio = curr_atr / avg_atr

    if ratio >= config.ATR_EXPANSION_RATIO:
        return True, f"ATR expansion confirmed ({ratio:.2f} >= {config.ATR_EXPANSION_RATIO})"
    return False, f"ATR ratio {ratio:.2f} < {config.ATR_EXPANSION_RATIO}"


def check_overextension(candles, direction="LONG"):
    lookback = config.OVEREXTENSION_LOOKBACK
    if len(candles) < lookback:
        return False, "not enough candles"

    recent = candles[-lookback:]

    if direction == "LONG":
        bullish_count = sum(1 for c in recent if c["close"] > c["open"])
        if bullish_count >= config.OVEREXTENSION_BULLISH_THRESHOLD:
            return True, f"overextended: {bullish_count}/{lookback} bullish"
        consecutive = 0
        max_consecutive = 0
        for c in recent:
            if c["close"] > c["open"]:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
        if max_consecutive >= config.CONSECUTIVE_BULLISH_MAX:
            return True, f"overextended: {max_consecutive} consecutive bullish"
        return False, f"not overextended: {bullish_count}/{lookback} bullish"

    elif direction == "SHORT":
        bearish_count = sum(1 for c in recent if c["close"] < c["open"])
        if bearish_count >= config.OVEREXTENSION_BULLISH_THRESHOLD:
            return True, f"overextended: {bearish_count}/{lookback} bearish"
        consecutive = 0
        max_consecutive = 0
        for c in recent:
            if c["close"] < c["open"]:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
        if max_consecutive >= config.CONSECUTIVE_BULLISH_MAX:
            return True, f"overextended: {max_consecutive} consecutive bearish"
        return False, f"not overextended: {bearish_count}/{lookback} bearish"

    return False, "unknown direction"


# ═══════════════════════════════════════════════════════════════
# MAIN CONFIRMATION: BUY (LONG)
# ═══════════════════════════════════════════════════════════════

def confirm_buy(candles):
    report = {
        "direction": "LONG",
        "overall": False,
        "entry_price": None,
        "stop_loss": None,
        "take_profit": None,
        "failed_at": None
    }

    if len(candles) < 70:
        report["failed_at"] = "not_enough_candles"
        return False, report

    # 1. LIQUIDITY & VOLATILITY CONFIRMATIONS
    atr_ok, atr_msg = check_atr_expansion(candles[:-1])
    if not atr_ok:
        report["failed_at"] = f"atr_expansion_failed: {atr_msg}"
        return False, report

    vol_ok, vol_msg = check_volume_spike(candles[:-1])
    if not vol_ok:
        report["failed_at"] = f"volume_shock_failed: {vol_msg}"
        return False, report

    overextended, oe_msg = check_overextension(candles[:-1], "LONG")
    if overextended:
        report["failed_at"] = f"overextended: {oe_msg}"
        return False, report

    # 2. DETECT HH BREAKOUT CANDLE
    lookback = config.BREAKOUT_LOOKBACK  # default 6
    bo_idx = None
    bo_high = None
    bo_low = None
    bo_open = None
    prev_sl_val = None

    # Scan backwards to find the latest valid breakout candle among completed candles
    for i in range(len(candles) - 2, lookback + 1, -1):
        curr_close = candles[i]["close"]
        window_candles = candles[i - lookback : i]
        highest_high = max(c["high"] for c in window_candles)

        if curr_close > highest_high:
            bo_candle = candles[i]
            # Breakout candle must be bullish
            if bo_candle["close"] <= bo_candle["open"]:
                continue

            bo_range = bo_candle["high"] - bo_candle["low"]
            if bo_range == 0:
                continue

            body = abs(bo_candle["close"] - bo_candle["open"])
            body_ratio = body / bo_range
            upper_wick = bo_candle["high"] - max(bo_candle["open"], bo_candle["close"])
            wick_ratio = upper_wick / bo_range

            # Body strictly 40% - 50% and upper wick <= 25%
            if body_ratio < 0.40 or body_ratio > 0.50:
                continue
            if wick_ratio > config.UPPER_WICK_MAX:
                continue

            # Breakout range > 2.0x ATR
            atr = calculate_atr(candles[:i + 1])
            if atr > 0 and bo_range <= 2.0 * atr:
                continue

            # Scan if there is not 8 consecutive bullish candles before the breakout candle
            consec_bullish = 0
            max_consec = 0
            pre_window = candles[max(0, i - 8) : i]
            for c in pre_window:
                if c["close"] > c["open"]:
                    consec_bullish += 1
                    max_consec = max(max_consec, consec_bullish)
                else:
                    consec_bullish = 0
            if max_consec >= 8:
                continue

            bo_idx = i
            bo_high = bo_candle["high"]
            bo_low = bo_candle["low"]
            bo_open = bo_candle["open"]
            prev_sl_val = min(c["low"] for c in window_candles)
            break

    if bo_idx is None:
        report["failed_at"] = "no_valid_hh_breakout"
        return False, report

    # 3. PULLBACK & TRIGGER PHASE
    pullback_low = float('inf')
    pullback_low_idx = None
    pullback_started = False
    pullback_start_idx = None
    recovery_started = False
    recovery_start_idx = None
    recovery_high = -float('inf')
    buyer_confirmed = False
    confirmed_idx = None

    # Scan pullback & trigger up to the last completed candle (completed candles only)
    for idx in range(bo_idx + 1, len(candles) - 1):
        curr_candle = candles[idx]
        curr_low = curr_candle["low"]
        curr_high = curr_candle["high"]
        curr_close = curr_candle["close"]
        curr_open = curr_candle["open"]
        curr_range = curr_high - curr_low

        # Invalidation Check: close below Previous swing low floor or breakout open
        if curr_close < prev_sl_val or curr_close < bo_open:
            break

        # Check pullback start (must start within 5 candles)
        if not pullback_started:
            if idx - bo_idx > 5:
                break  # Pullback did not start within 5 candles
            if curr_close < bo_high:
                pullback_started = True
                pullback_start_idx = idx

        # A. Pullback phase tracking
        if pullback_started and not recovery_started:
            if curr_candle["close"] < bo_high:
                if curr_low < pullback_low:
                    pullback_low = curr_low
                    pullback_low_idx = idx

            # Recovery candle appears:
            if pullback_low_idx is not None and idx > pullback_low_idx:
                # No new longer low allowed after pullback low is established
                if curr_low < pullback_low:
                    break

                prev_candle = candles[idx - 1]
                if curr_close > curr_open and curr_range > 0:
                    body_ratio = (curr_close - curr_open) / curr_range
                    close_pos = (curr_close - curr_low) / curr_range
                    curr_atr = calculate_atr(candles[:idx + 1])

                    # Valid recovery candle check
                    if (body_ratio >= 0.45 and
                        curr_close > prev_candle["high"] and
                        close_pos >= 0.50 and
                        curr_atr > 0 and curr_range >= 0.50 * curr_atr):
                        
                        recovery_started = True
                        recovery_start_idx = idx
                        recovery_high = curr_high

                        # Retracement check
                        bo_range_val = bo_high - bo_low
                        retracement = (bo_high - pullback_low) / bo_range_val * 100
                        if not (config.PULLBACK_DEPTH_MIN <= retracement <= config.PULLBACK_DEPTH_MAX):
                            report["failed_at"] = f"pullback_retracement_out_of_bounds: {retracement:.2f}%"
                            return False, report

                        # Breakout volume must be higher than average pullback volume
                        pullback_vols = [c["volume"] for c in candles[bo_idx + 1 : pullback_low_idx + 1]]
                        avg_pullback_vol = sum(pullback_vols) / len(pullback_vols) if pullback_vols else 0
                        if candles[bo_idx]["volume"] <= avg_pullback_vol:
                            report["failed_at"] = f"breakout_volume_not_higher_than_pullback: {candles[bo_idx]['volume']} <= {avg_pullback_vol}"
                            return False, report

        # B. Recovery phase tracking (duration = max 5 candles)
        elif recovery_started and recovery_start_idx is not None:
            if idx - recovery_start_idx >= 5:
                break

            # Update latest recovery high
            if curr_high > recovery_high:
                recovery_high = curr_high

            # Trigger condition: completed candle closes above recovery_high * 1.001
            if curr_close > recovery_high * 1.001:
                buyer_confirmed = True
                confirmed_idx = idx
                break

    if pullback_low_idx is None:
        report["failed_at"] = "no_pullback_recorded"
        return False, report

    if not buyer_confirmed or confirmed_idx is None:
        report["failed_at"] = "no_buyer_confirmation_above_recovery_high"
        return False, report

    # Freshness Check
    if confirmed_idx < len(candles) - 2:
        report["failed_at"] = f"confirmation_stale: confirmed at idx {confirmed_idx} vs current {len(candles)-1}"
        return False, report

    # 5. ENTRY, SL, AND TP CALCULATION
    entry = recovery_high * 1.001
    
    if prev_sl_val >= entry:
        report["failed_at"] = f"prev_sl_val_above_entry: {prev_sl_val} >= {entry}"
        return False, report

    sl = prev_sl_val * 0.999
    tp = entry + (entry - sl) * config.RR_RATIO

    report["entry_price"] = entry
    report["stop_loss"] = sl
    report["take_profit"] = tp
    report["overall"] = True
    report["status"] = "CONFIRMED"
    return True, report


# Mock/Disabled functions to satisfy strategy imports
def confirm_sell_watchlist_trigger(candles):
    return False, {"failed_at": "disabled"}


# ═══════════════════════════════════════════════════════════════
# CORE: BEARISH FAILED BREAKOUT SHORT
# ═══════════════════════════════════════════════════════════════

def confirm_sell_failed_breakout(candles):
    report = {"overall": False, "status": "REJECTED"}
    
    # 1. Liquidity check
    if len(candles) < 70:
        report["failed_at"] = "not_enough_candles"
        return False, report

    # 2. Volume check
    vol_ok, vol_msg = check_volume_spike(candles[:-1])
    if not vol_ok:
        report["failed_at"] = f"volume_shock_failed: {vol_msg}"
        return False, report

    # 3. Volatility Check
    atr_ok, atr_msg = check_atr_expansion(candles[:-1])
    if not atr_ok:
        report["failed_at"] = f"atr_expansion_failed: {atr_msg}"
        return False, report

    # 3.1 Overextension Check
    overextended, oe_msg = check_overextension(candles[:-1], "SHORT")
    if overextended:
        report["failed_at"] = f"overextended_trend: {oe_msg}"
        return False, report

    # 4. Detect Breakout Candle index (bo_idx) using completed candles
    lookback = config.BREAKOUT_LOOKBACK
    bo_idx = None
    prev_sl_val = None
    prev_sh_val = None

    for i in range(len(candles) - 2, lookback + 3, -1):
        curr_close = candles[i]["close"]
        window_candles = candles[i - lookback : i]
        highest_high = max(c["high"] for c in window_candles)
        
        if curr_close > highest_high:
            bo_candle = candles[i]
            if bo_candle["close"] <= bo_candle["open"]:
                continue
            bo_range = bo_candle["high"] - bo_candle["low"]
            if bo_range == 0:
                continue
            body = abs(bo_candle["close"] - bo_candle["open"])
            body_ratio = body / bo_range
            upper_wick = bo_candle["high"] - max(bo_candle["open"], bo_candle["close"])
            wick_ratio = upper_wick / bo_range
            
            # Body 40% - 50% and upper wick <= 25%
            if body_ratio < 0.40 or body_ratio > 0.50:
                continue
            if wick_ratio > config.UPPER_WICK_MAX:
                continue
                
            bo_idx = i
            prev_sl_val = min(c["low"] for c in window_candles)
            prev_sh_val = highest_high
            break

    if bo_idx is None:
        report["failed_at"] = "no_valid_hh_breakout"
        return False, report

    # 5. Pullback & Recovery State Machine
    bo_candle = candles[bo_idx]
    bo_high = bo_candle["high"]
    bo_low = bo_candle["low"]
    bo_range = bo_high - bo_low
    bo_midpoint = (bo_high + bo_low) / 2.0

    pullback_low = float('inf')
    pullback_low_idx = None
    recovery_started = False
    recovery_start_idx = None
    recovery_high = -float('inf')
    breakdown_confirmed = False
    breakdown_idx = None

    # Track up to last completed candle (completed candles only)
    for idx in range(bo_idx + 1, len(candles) - 1):
        # Lifespan Check
        if idx - bo_idx > 20:
            break

        curr_candle = candles[idx]
        curr_low = curr_candle["low"]
        curr_high = curr_candle["high"]
        curr_close = curr_candle["close"]
        curr_open = curr_candle["open"]
        curr_range = curr_high - curr_low

        # A. Pullback phase tracking
        if not recovery_started:
            if curr_candle["close"] < bo_high:
                if curr_low < pullback_low:
                    pullback_low = curr_low
                    pullback_low_idx = idx

            # Recovery candle checks
            if pullback_low_idx is not None and idx > pullback_low_idx:
                prev_candle = candles[idx - 1]
                if curr_close > curr_open and curr_range > 0:
                    body_ratio = (curr_close - curr_open) / curr_range
                    close_pos = (curr_close - curr_low) / curr_range
                    curr_atr = calculate_atr(candles[:idx + 1])
                    
                    if (body_ratio >= 0.45 and 
                        curr_close > prev_candle["high"] and 
                        close_pos >= 0.50 and 
                        curr_atr > 0 and curr_range >= 0.50 * curr_atr):
                        
                        # Retracement Check: 65% to 95%
                        retracement = (bo_high - pullback_low) / bo_range * 100
                        if not (65.0 <= retracement <= 95.0):
                            report["failed_at"] = f"pullback_retracement_out_of_bounds: {retracement:.2f}%"
                            return False, report

                        recovery_started = True
                        recovery_start_idx = idx
                        recovery_high = curr_high

        # B. Recovery phase tracking (duration = max 7 candles)
        elif recovery_started and recovery_start_idx is not None and idx < recovery_start_idx + 7:
            # No New High: Price must not print a new high above breakout peak during recovery
            if curr_high >= bo_high:
                break
                
            # Recovery candle closes cannot close above the breakout candle's midpoint
            if curr_close > bo_midpoint:
                break

            if curr_high > recovery_high:
                recovery_high = curr_high

        # C. Breakdown phase tracking
        elif recovery_started and recovery_start_idx is not None and idx >= recovery_start_idx + 7:
            # Expiry limit: Breakdown must trigger within 5 candles after recovery ends
            if idx - (recovery_start_idx + 7) >= 5:
                break

            # Invalidation Check: no new high above recovery_high
            if curr_high > recovery_high:
                break

            # Close below Locked Pullback Low check
            if curr_close < pullback_low:
                if curr_range > 0:
                    body_ratio = abs(curr_close - curr_open) / curr_range
                    close_pos = (curr_close - curr_low) / curr_range
                    
                    # Volume check
                    rec_candles = candles[recovery_start_idx : recovery_start_idx + 7]
                    avg_rec_vol = sum(c["volume"] for c in rec_candles) / len(rec_candles)
                    
                    if body_ratio >= 0.45 and close_pos <= 0.40 and curr_candle["volume"] > avg_rec_vol:
                        breakdown_confirmed = True
                        breakdown_idx = idx
                        break

    if not breakdown_confirmed or breakdown_idx is None:
        report["failed_at"] = "no_breakdown_confirmed"
        return False, report

    # Live Invalidation Check
    if candles[-1]["high"] > recovery_high:
        report["failed_at"] = f"live_invalidation: high {candles[-1]['high']} > recovery_high {recovery_high}"
        return False, report

    # Freshness Check
    if breakdown_idx != len(candles) - 2:
        report["failed_at"] = f"breakdown_not_on_last_completed_candle: idx {breakdown_idx} vs expected {len(candles)-2}"
        return False, report

    # Entry SHORT = pullback_low (retest entry)
    entry = pullback_low
    stop_loss = recovery_high * 1.001
    risk = stop_loss - entry

    if stop_loss <= entry:
        report["failed_at"] = f"invalid_sl_tp_relation: stop_loss {stop_loss} <= entry {entry}"
        return False, report

    if risk / entry > 0.10:
        report["failed_at"] = "risk_exceeds_10_percent"
        return False, report

    take_profit = entry - (risk * config.RR_RATIO)

    report["entry_price"] = entry
    report["stop_loss"] = stop_loss
    report["take_profit"] = take_profit
    report["overall"] = True
    report["status"] = "CONFIRMED"

    return True, report


# ═══════════════════════════════════════════
# SWING LOWS/HIGHS AUDIT TOOLS
# ═══════════════════════════════════════════

def find_swing_lows(candles, count=5, window=3):
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


def find_swing_highs(candles, count=5, window=3):
    swings = []
    for i in range(window, len(candles) - window):
        high = candles[i]["high"]
        is_swing = True
        for j in range(1, window + 1):
            if candles[i - j]["high"] > high or candles[i + j]["high"] > high:
                is_swing = False
                break
        if is_swing:
            swings.append({"index": i, "price": high})
    return swings[-count:] if len(swings) >= count else swings


# ═══════════════════════════════════════════
# REVERSAL PROTECTION (EARLY EXIT)
# ═══════════════════════════════════════════

def is_bearish_engulfing(candles, min_body_ratio=None):
    if min_body_ratio is None:
        min_body_ratio = config.ENGULFING_MIN_BODY_RATIO
    if len(candles) < 2:
        return False, "not enough candles"

    prev = candles[-2]
    curr = candles[-1]

    prev_open, prev_close = prev["open"], prev["close"]
    curr_open, curr_close = curr["open"], curr["close"]
    curr_high, curr_low = curr["high"], curr["low"]

    if prev_close <= prev_open:
        return False, "prev candle not bullish"

    if curr_close >= curr_open:
        return False, "curr candle not bearish"

    curr_range = curr_high - curr_low
    if curr_range == 0:
        return False, "zero range"

    curr_body = abs(curr_open - curr_close)
    body_ratio = curr_body / curr_range

    if body_ratio < min_body_ratio:
        return False, f"body ratio {body_ratio:.2f} < {min_body_ratio}"

    if curr_open < prev_close:
        return False, "curr open doesn't engulf prev close"

    if curr_close > prev_open:
        return False, "curr close doesn't engulf prev open"

    return True, "bearish engulfing confirmed"


def is_bullish_engulfing(candles, min_body_ratio=None):
    if min_body_ratio is None:
        min_body_ratio = config.ENGULFING_MIN_BODY_RATIO
    if len(candles) < 2:
        return False, "not enough candles"

    prev = candles[-2]
    curr = candles[-1]

    prev_open, prev_close = prev["open"], prev["close"]
    curr_open, curr_close = curr["open"], curr["close"]
    curr_high, curr_low = curr["high"], curr["low"]

    if prev_close >= prev_open:
        return False, "prev candle not bearish"

    if curr_close <= curr_open:
        return False, "curr candle not bullish"

    curr_range = curr_high - curr_low
    if curr_range == 0:
        return False, "zero range"

    curr_body = abs(curr_open - curr_close)
    body_ratio = curr_body / curr_range

    if body_ratio < min_body_ratio:
        return False, f"body ratio {body_ratio:.2f} < {min_body_ratio}"

    if curr_open > prev_close:
        return False, "curr open doesn't engulf prev close"

    if curr_close < prev_open:
        return False, "curr close doesn't engulf prev open"

    return True, "bullish engulfing confirmed"


def check_early_exit(candles, direction):
    if len(candles) < 15:
        return False, "Not enough candles"

    if direction == "LONG":
        is_engulf, _ = is_bearish_engulfing(candles)
        if not is_engulf:
            return False, "not bearish engulfing"

        swings = find_swing_lows(candles[:-1], count=3, window=3)
        if len(swings) >= 3:
            lowest_swing_low = min(s["price"] for s in swings)
            curr_close = candles[-1]["close"]
            if curr_close < lowest_swing_low:
                return True, f"Bearish engulfing AND 3-swing low break (< {lowest_swing_low})"
            return False, f"Bearish engulfing but closed {curr_close} above swing low {lowest_swing_low}"
        return False, "not enough swing lows found"

    elif direction == "SHORT":
        is_engulf, _ = is_bullish_engulfing(candles)
        if not is_engulf:
            return False, "not bullish engulfing"

        swings = find_swing_highs(candles[:-1], count=3, window=3)
        if len(swings) >= 3:
            highest_swing_high = max(s["price"] for s in swings)
            curr_close = candles[-1]["close"]
            if curr_close > highest_swing_high:
                return True, f"Bearish engulfing AND 3-swing high break (> {highest_swing_high})"
            return False, f"Bullish engulfing but closed {curr_close} below swing high {highest_swing_high}"
        return False, "not enough swing highs found"

    return False, "invalid direction"


confirm_buy_signal = confirm_buy
ENDOF_CONFIRMATION_PY
echo "[OK] confirmation.py"

cat > trade_manager.py << 'ENDOF_TRADE_MANAGER_PY'
"""
TRADE MANAGER — Fixed Binance API Bugs (SL/TP/Leverage)
"""

import time

_precision_cache = {}


def get_symbol_precision(client, symbol):
    global _precision_cache

    if symbol in _precision_cache:
        return _precision_cache[symbol]

    try:
        info = client.futures_exchange_info()
        for s in info['symbols']:
            if s['symbol'] == symbol:
                price_precision = s.get('pricePrecision', 4)
                qty_precision = s.get('quantityPrecision', 3)
                _precision_cache[symbol] = (price_precision, qty_precision)
                return price_precision, qty_precision
    except Exception as e:
        print(f"[WARN] Precision fetch failed: {e}")

    _precision_cache[symbol] = (4, 3)
    return 4, 3


def round_price(price, precision):
    return round(price, precision)


def round_qty(qty, precision):
    factor = 10 ** precision
    return int(qty * factor) / factor


def safe_order_response(response):
    if isinstance(response, dict):
        return str(response.get('orderId', 'UNKNOWN'))
    return 'UNKNOWN'


def check_existing_sl_tp(client, symbol):
    try:
        open_orders = client.futures_get_open_orders(symbol=symbol)
        
        # Portfolio Margin accounts query
        algo_orders = []
        try:
            algo_orders = client.futures_get_open_algo_orders(symbol=symbol)
            if not isinstance(algo_orders, list):
                algo_orders = []
        except Exception as ae:
            # Silent fallback if not supported or not Portfolio Margin account
            pass

        has_sl = False
        has_tp = False
        sl_order = None
        tp_order = None

        for order in open_orders:
            order_type = order.get('type', '')

            if order_type == 'STOP_MARKET':
                has_sl = True
                sl_order = order
            elif order_type == 'TAKE_PROFIT_MARKET':
                has_tp = True
                tp_order = order
            elif order_type == 'STOP' and order.get('closePosition'):
                has_sl = True
                sl_order = order
            elif order_type == 'TAKE_PROFIT' and order.get('closePosition'):
                has_tp = True
                tp_order = order

        for order in algo_orders:
            order_type = order.get('orderType', '')
            status = order.get('algoStatus', '')
            # Only consider active algo orders
            if status in ['NEW', 'WORKING', 'PARTIALLY_FILLED']:
                if order_type == 'STOP_MARKET':
                    has_sl = True
                    sl_order = order
                elif order_type == 'TAKE_PROFIT_MARKET':
                    has_tp = True
                    tp_order = order
                elif order_type == 'STOP' and order.get('closePosition'):
                    has_sl = True
                    sl_order = order
                elif order_type == 'TAKE_PROFIT' and order.get('closePosition'):
                    has_tp = True
                    tp_order = order

        return {
            'has_sl': has_sl,
            'has_tp': has_tp,
            'sl_order': sl_order,
            'tp_order': tp_order,
            'total_orders': len(open_orders) + len(algo_orders)
        }

    except Exception as e:
        print(f"[ERROR] Check orders failed: {e}")
        return {'has_sl': False, 'has_tp': False, 'sl_order': None, 'tp_order': None, 'total_orders': 0}


def place_limit_order_with_sl_tp(client, symbol, direction, entry, sl, tp, qty, leverage=5):
    side = "BUY" if direction == "LONG" else "SELL"
    opposite_side = "SELL" if direction == "LONG" else "BUY"

    # Use the mathematically calculated entry and tp prices strictly (prevents chasing)
    print(f"[ENTRY] Using calculated structural entry: {entry} | TP: {tp}")

    # Verify that Stop Loss is on the correct side of the new entry price
    if direction == "LONG" and entry <= sl:
        print(f"[BLOCKED] {symbol}: Maker price {entry} is <= SL {sl} | Upside-down SL blocked!")
        return None
    if direction == "SHORT" and entry >= sl:
        print(f"[BLOCKED] {symbol}: Maker price {entry} is >= SL {sl} | Upside-down SL blocked!")
        return None

    price_prec, qty_prec = get_symbol_precision(client, symbol)

    entry = round_price(entry, price_prec)
    sl = round_price(sl, price_prec)
    tp = round_price(tp, price_prec)
    qty = round_qty(qty, qty_prec)

    if qty <= 0:
        print(f"[ERROR] {symbol}: Quantity too small")
        return None

    print(f"\n{'='*50}")
    print(f"[ORDER] {symbol} {direction}")
    print(f"Entry: {entry} | SL: {sl} | TP: {tp} | Qty: {qty}")

    try:
        existing = check_existing_sl_tp(client, symbol)
        if existing['has_sl'] and existing['has_tp']:
            print(f"[SKIP] {symbol}: SL/TP already exists")
            return None

        # FIX 1: Set leverage BEFORE placing the order
        try:
            client.futures_change_leverage(symbol=symbol, leverage=leverage)
            print(f"[LEV] Set leverage to {leverage}x")
        except Exception as e:
            print(f"[WARN] Leverage set failed: {e}")

        # FIX 2: Removed leverage=leverage from order call
        limit_order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type="LIMIT",
            timeInForce="GTC",
            quantity=qty,
            price=entry
        )

        order_id = safe_order_response(limit_order)
        print(f"[LIMIT] Placed | OrderID: {order_id}")

        filled = False
        avg_price = entry
        for i in range(30):
            time.sleep(2)

            try:
                # FIX 3: Convert orderId to int for Binance
                order = client.futures_get_order(symbol=symbol, orderId=int(order_id))
                if order.get('status') == 'FILLED':
                    filled = True
                    avg_price = float(order.get('avgPrice', entry))
                    print(f"[FILL] Filled at {avg_price}")
                    break
            except:
                continue

        if not filled:
            print(f"[CANCEL] Not filled within timeout. Cancelling order {order_id}...")
            try:
                client.futures_cancel_order(symbol=symbol, orderId=int(order_id))
                time.sleep(1) # wait for cancel to propagate
            except Exception as e:
                print(f"[CANCEL] Cancel failed or already filled: {e}")

            # Double check if any quantity was filled before/during cancellation
            try:
                final_order = client.futures_get_order(symbol=symbol, orderId=int(order_id))
                exec_qty = float(final_order.get('executedQty', 0))
                if exec_qty > 0:
                    print(f"[PARTIAL] Order cancelled but filled partially: {exec_qty} units.")
                    qty = exec_qty
                    avg_price = float(final_order.get('avgPrice') or final_order.get('price') or entry)
                    filled = True
            except Exception as e:
                print(f"[ERROR] Failed to check final order status: {e}")

        if not filled:
            return None

        # Proceed with SL and TP placement for filled quantity
        existing = check_existing_sl_tp(client, symbol)
        if not existing['has_sl']:
            # Place SL
            sl_attached = False
            for attempt in range(1, 4):
                print(f"[SL] Attempt {attempt}/3 — attaching at {sl}")
                try:
                    sl_response = client.futures_create_order(
                        symbol=symbol,
                        side=opposite_side,
                        type="STOP_MARKET",
                        stopPrice=sl,
                        quantity=qty,
                        reduceOnly=True
                    )
                    print(f"[SL] ✅ Attached | OrderID: {safe_order_response(sl_response)}")
                    sl_attached = True
                    break
                except Exception as e:
                    print(f"[SL] ❌ Attempt {attempt} failed: {e}")
                    if attempt < 3:
                        time.sleep(1)

            if not sl_attached:
                print(f"[EMERGENCY] SL failed after 3 retries — closing position")
                try:
                    client.futures_create_order(
                        symbol=symbol,
                        side=opposite_side,
                        type="MARKET",
                        quantity=qty,
                        reduceOnly=True
                    )
                    print(f"[EMERGENCY] Position closed via MARKET order")
                except Exception as e:
                    print(f"[EMERGENCY] ❌ Close also failed: {e}")
                return None
        else:
            print(f"[SKIP] SL already exists")

        # FIX 5: TP with retry logic (3 attempts) + no timeInForce
        existing = check_existing_sl_tp(client, symbol)
        if not existing['has_tp']:
            # Place TP
            for attempt in range(1, 4):
                print(f"[TP] Attempt {attempt}/3 — attaching at {tp}")
                try:
                    tp_response = client.futures_create_order(
                        symbol=symbol,
                        side=opposite_side,
                        type="TAKE_PROFIT_MARKET",
                        stopPrice=tp,
                        quantity=qty,
                        reduceOnly=True
                    )
                    print(f"[TP] ✅ Attached | OrderID: {safe_order_response(tp_response)}")
                    break
                except Exception as e:
                    print(f"[TP] ⚠️ Attempt {attempt} failed: {e}")
                    if attempt < 3:
                        time.sleep(1)
        else:
            print(f"[SKIP] TP already exists")

        print(f"{'='*50}")
        return {"symbol": symbol, "direction": direction, "entry": avg_price}
    except Exception as e:
        print(f"[ERROR] {symbol}: {e}")
        return None


def calculate_position_size(account_balance, entry, sl, leverage=5, target_margin_percent=50.0):
    import config
    # 1. Determine desired risk amount (e.g. 1% of wallet balance)
    risk_pct = getattr(config, 'RISK_PER_TRADE_PERCENT', 1.0)
    desired_risk = account_balance * (risk_pct / 100.0)
    
    price_risk = abs(entry - sl)
    if entry == 0 or price_risk == 0:
        return 0, 0, 0, 0, "Price risk or entry 0"
        
    # 2. Calculate quantity required for this risk
    qty = desired_risk / price_risk
    
    # 3. Calculate required notional and margin
    notional = qty * entry
    if notional < 5.0:
        notional = 5.0
        qty = notional / entry
        desired_risk = qty * price_risk
        
    required_margin = notional / leverage
    
    # 4. Enforce max margin cap (e.g. 50% of wallet balance)
    max_allowed_margin = account_balance * (target_margin_percent / 100.0)
    if required_margin > max_allowed_margin:
        required_margin = max_allowed_margin
        notional = required_margin * leverage
        qty = notional / entry
        desired_risk = qty * price_risk
        
    margin_pct = (required_margin / account_balance) * 100 if account_balance > 0 else 0
    return qty, notional, required_margin, desired_risk, f"OK (Risk Sized): Margin {required_margin:.2f} ({margin_pct:.1f}%), Risk {desired_risk:.2f} USDT"

def verify_sl_tp_every_cycle(client, open_positions):
    for pos in open_positions:
        symbol = pos['symbol']
        amt = float(pos['positionAmt'])

        if amt == 0:
            continue

        direction = "LONG" if amt > 0 else "SHORT"
        opposite_side = "SELL" if direction == "LONG" else "BUY"

        existing = check_existing_sl_tp(client, symbol)

        if existing['has_sl'] and existing['has_tp']:
            continue

        # Cancel all open orders for this symbol first to clear any conflicting stop/closePosition orders
        try:
            client.futures_cancel_all_open_orders(symbol=symbol)
            print(f"[CLEANUP] Cancelled existing open orders for {symbol} to prevent conflicts")
            time.sleep(1.5)  # Allow propagation delay on Binance servers
        except Exception as cleanup_err:
            print(f"[CLEANUP] Warning: Could not cancel open orders for {symbol}: {cleanup_err}")

        entry = float(pos['entryPrice'])
        price_prec, _ = get_symbol_precision(client, symbol)

        sl = round_price(entry * 0.98 if direction == "LONG" else entry * 1.02, price_prec)
        tp = round_price(entry * 1.04 if direction == "LONG" else entry * 0.96, price_prec)

        # FIX 6: No timeInForce on STOP_MARKET in verify cycle
        if not existing['has_sl']:
            try:
                sl_resp = client.futures_create_order(
                    symbol=symbol,
                    side=opposite_side,
                    type="STOP_MARKET",
                    stopPrice=sl,
                    quantity=abs(amt),
                    reduceOnly=True
                )
                print(f"[FIX] SL attached: {safe_order_response(sl_resp)}")
            except Exception as e:
                print(f"[ERROR] SL fix failed: {e}")

        # FIX 7: No timeInForce on TAKE_PROFIT_MARKET in verify cycle
        if not existing['has_tp']:
            try:
                tp_resp = client.futures_create_order(
                    symbol=symbol,
                    side=opposite_side,
                    type="TAKE_PROFIT_MARKET",
                    stopPrice=tp,
                    quantity=abs(amt),
                    reduceOnly=True
                )
                print(f"[FIX] TP attached: {safe_order_response(tp_resp)}")
            except Exception as e:
                print(f"[ERROR] TP fix failed: {e}")
ENDOF_TRADE_MANAGER_PY
echo "[OK] trade_manager.py"

cat > strategy.py << 'ENDOF_STRATEGY_PY'
"""
STRATEGY — SCEPTER MOMENTUM BOT v5.0
Systematic: NO trade without ALL confirmations
"""

import config
from confirmation import (
    confirm_buy_signal,
    confirm_sell_failed_breakout,
    find_swing_lows,
    find_swing_highs
)
from trade_manager import (
    calculate_position_size,
    place_limit_order_with_sl_tp,
    verify_sl_tp_every_cycle
)
from exchange_manager import get_spread_percent
from config import MAX_MARGIN_PER_TRADE_PERCENT, LEVERAGE, MAX_SL_PERCENT


def analyze_symbol(candles, symbol, account_balance, open_trades_count=0):
    if open_trades_count >= 2:
        return None

    spread = get_spread_percent(symbol)
    max_spread = getattr(config, "MAX_SPREAD_PERCENT", 0.50)
    if spread > max_spread:
        print(f"[SKIP] {symbol}: spread too high ({spread:.3f}% > {max_spread}%)")
        return None

    buy_ok, buy_report = confirm_buy_signal(candles)
    if buy_ok:
        return prepare_trade(candles, symbol, account_balance, "LONG", buy_report)
    else:
        reason = buy_report.get('failed_at') if isinstance(buy_report, dict) else buy_report
        print(f"[SKIP] {symbol}: buy signal not confirmed | Reason: {reason}")

    sell_ok, sell_report = confirm_sell_failed_breakout(candles)
    if sell_ok:
        return prepare_trade(candles, symbol, account_balance, "SHORT", sell_report)
    else:
        reason = sell_report.get('failed_at') if isinstance(sell_report, dict) else sell_report
        print(f"[SKIP] {symbol}: sell signal not confirmed | Reason: {reason}")

    return None


def prepare_trade(candles, symbol, account_balance, direction, report):
    if direction == "LONG":
        entry = report.get("entry_price", candles[-1]["close"])
        sl = report.get("stop_loss")
        if not sl:
            swings = find_swing_lows(candles, count=1, window=3)
            if swings:
                swing_low = swings[-1]["price"]
                print(f"[SL] Found latest swing low for LONG: {swing_low}")
            else:
                swing_low = min(c["low"] for c in candles[-10:])
                print(f"[SL] No swing low found for LONG, using 10-candle min: {swing_low}")
            sl = swing_low * 0.999  # 0.1% buffer below swing low
        tp = entry + (entry - sl) * 2
    else:
        entry = report.get("entry_price", candles[-1]["low"] * 0.999)
        sl = report.get("stop_loss")
        if not sl:
            swings = find_swing_highs(candles, count=1, window=3)
            if swings:
                swing_high = swings[-1]["price"]
                print(f"[SL] Found latest swing high for SHORT: {swing_high}")
            else:
                swing_high = max(c["high"] for c in candles[-10:])
                print(f"[SL] No swing high found for SHORT, using 10-candle max: {swing_high}")
            sl = swing_high * 1.001  # 0.1% buffer above swing high
        tp = entry - (sl - entry) * 2

    # Check extreme SL distance safety cap (10%)
    sl_dist_pct = abs(entry - sl) / entry * 100
    if sl_dist_pct > 10.0:
        print(f"[BLOCKED] {symbol}: Swing SL distance {sl_dist_pct:.2f}% > 10.0% (too extreme)")
        return None

    qty, notional, margin, risk, msg = calculate_position_size(
        account_balance=account_balance,
        entry=entry,
        sl=sl,
        leverage=LEVERAGE,
        target_margin_percent=MAX_MARGIN_PER_TRADE_PERCENT
    )

    if qty <= 0:
        print(f"[BLOCKED] {symbol}: {msg}")
        return None

    if notional < 5.0:
        print(f"[BLOCKED] {symbol}: notional {notional:.2f} USDT < 5.0 USDT minimum")
        return None

    max_allowed_margin = account_balance * (MAX_MARGIN_PER_TRADE_PERCENT / 100.0)
    if margin > max_allowed_margin * 1.02:
        print(f"[BLOCKED] {symbol}: margin {margin:.2f} > {MAX_MARGIN_PER_TRADE_PERCENT}% of balance {account_balance:.2f}")
        return None

    return {
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "qty": qty,
        "margin": margin,
        "risk": risk,
        "status": "CONFIRMED",
        "report": report
    }


def execute_trade(client, trade):
    if not trade:
        return None

    result = place_limit_order_with_sl_tp(
        client=client,
        symbol=trade["symbol"],
        direction=trade["direction"],
        entry=trade["entry"],
        sl=trade["sl"],
        tp=trade["tp"],
        qty=trade["qty"],
        leverage=LEVERAGE
    )

    return result


def manage_open_trades(client, open_positions):
    # Verify SL/TP orders exist
    verify_sl_tp_every_cycle(client, open_positions)

    # Early exit check for each position
    from confirmation import check_early_exit
    from config import TIMEFRAME

    def _fetch_candles(symbol, timeframe="5m", limit=50):
        try:
            klines = client.futures_klines(symbol=symbol, interval=timeframe, limit=limit)
            return [{
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            } for k in klines]
        except Exception as e:
            print(f"[ERROR] Early exit fetch failed for {symbol}: {e}")
            return []

    for pos in open_positions:
        symbol = pos['symbol']
        amt = float(pos['positionAmt'])
        if amt == 0:
            continue

        direction = "LONG" if amt > 0 else "SHORT"
        opposite_side = "SELL" if direction == "LONG" else "BUY"

        candles = _fetch_candles(symbol, TIMEFRAME, limit=50)
        if len(candles) < 20:
            continue

        should_exit, reason = check_early_exit(candles, direction)
        if should_exit:
            print(f"\n{'!'*50}")
            print(f"[EARLY EXIT] {symbol} ({direction}) Triggered: {reason}")
            print(f"Closing position of {abs(amt)} units...")
            try:
                # Cancel all open orders first to prevent orphan SL/TP orders
                client.futures_cancel_all_open_orders(symbol=symbol)
                # Close the position via MARKET order
                res = client.futures_create_order(
                    symbol=symbol,
                    side=opposite_side,
                    type="MARKET",
                    quantity=abs(amt),
                    reduceOnly=True
                )
                print(f"[EXIT SUCCESS] Position closed successfully. OrderID: {res.get('orderId')}")
            except Exception as e:
                print(f"[EXIT ERROR] Failed to close position: {e}")
            print(f"{'!'*50}\n")
ENDOF_STRATEGY_PY
echo "[OK] strategy.py"

cat > main.py << 'ENDOF_MAIN_PY'
import builtins
import time
import sys
import os
import json

# ═══════════════════════════════════════════
# AUTO-LOGGING SYSTEM (Redirection Proof)
# ═══════════════════════════════════════════
_original_print = builtins.print

def custom_print(*args, **kwargs):
    # Console screen print
    _original_print(*args, **kwargs)
    
    # Write directly to bot.log
    try:
        msg = " ".join(str(arg) for arg in args)
        with open("bot.log", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except:
        pass

builtins.print = custom_print

try:
    from dotenv import load_dotenv
    load_dotenv()
    API_KEY = os.getenv('BINANCE_API_KEY')
    API_SECRET = os.getenv('BINANCE_API_SECRET')
    if not API_KEY or not API_SECRET:
        raise ValueError("API keys not found in .env")
except Exception as e:
    print(f"[ERROR] Failed to load API keys: {e}")
    sys.exit(1)

from config import TIMEFRAME, SLEEP_SECONDS, MAX_OPEN_TRADES, EMERGENCY_DRAWDOWN_PERCENT, MAX_SPREAD_PERCENT
from binance.client import Client
from strategy import analyze_symbol, execute_trade, manage_open_trades
from exchange_manager import get_spread_percent

BLOCKED_KEYWORDS = [
    "BTC", "ETH", "SOL", "BNB", "PAXG",
    "TSLA", "RKLB", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META"
]

client = Client(API_KEY, API_SECRET)

COOLDOWN_MINUTES = 4
LAST_CLOSURE_TIME = 0.0
TRADED_SYMBOLS = set()


def load_cooldown():
    try:
        if os.path.exists("cooldown.json"):
            with open("cooldown.json", "r") as f:
                data = json.load(f)
                # Cleanup old cooldowns on load
                now = time.time()
                clean_data = {}
                for k, v in data.items():
                    if v > now:
                        clean_data[k] = v
                return clean_data
    except Exception as e:
        print(f"[WARN] Failed to load cooldown.json: {e}")
    return {}


def save_cooldown(data):
    try:
        with open("cooldown.json", "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[ERROR] Failed to write cooldown.json: {e}")


def set_cooldown(symbol, cooldown_dict):
    cooldown_dict[symbol] = time.time() + (COOLDOWN_MINUTES * 60)
    save_cooldown(cooldown_dict)
    print(f"[COOLDOWN] {symbol} locked for {COOLDOWN_MINUTES} minutes")


def get_all_balances():
    try:
        acc = client.futures_account()
        wallet_balance = float(acc.get('totalWalletBalance', 0.0))
        margin_balance = float(acc.get('totalMarginBalance', 0.0))
        available_balance = float(acc.get('availableBalance', 0.0))
        positions = acc.get('positions', [])
        return {
            "wallet": wallet_balance,
            "margin": margin_balance,
            "available": available_balance,
            "positions": positions
        }
    except Exception as e:
        print(f"[ERROR] Futures balance fetch: {e}")
        return {"wallet": 0.0, "margin": 0.0, "available": 0.0, "positions": []}


def get_open_positions():
    try:
        acc = client.futures_account()
        positions = [p for p in acc.get('positions', []) if float(p['positionAmt']) != 0]
        return positions
    except Exception as e:
        print(f"[ERROR] Position check failed: {e}")
        raise e


def get_candles(symbol, timeframe="5m", limit=100):
    try:
        klines = client.futures_klines(symbol=symbol, interval=timeframe, limit=limit)
        candles = []
        for k in klines:
            candles.append({
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            })
        return candles
    except Exception as e:
        print(f"[ERROR] {symbol} candles: {e}")
        return []


def get_symbols():
    try:
        info = client.futures_exchange_info()
        trading_symbols = {s['symbol'] for s in info['symbols'] if s['status'] == 'TRADING'}
        
        tickers = client.futures_ticker()
        usdt = [t for t in tickers if t['symbol'].endswith('USDT') and t['symbol'] in trading_symbols]
        usdt.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
        
        # Filter: Ignore all coins ranked 1-70 (strictly trade Rank >= 71)
        allowed_ranks = usdt[70:]
        
        min_volume = 3000000.0  # 3,000,000 USDT quoteVolume check
        active_symbols = []
        for t in allowed_ranks:
            vol = float(t.get('quoteVolume', 0))
            if vol >= min_volume:
                active_symbols.append(t['symbol'])
        
        return active_symbols
    except Exception as e:
        print(f"[ERROR] Symbols fetch: {e}")
        return []


def is_blocked(symbol):
    for kw in BLOCKED_KEYWORDS:
        if kw in symbol:
            return True
    return False


def run():
    global TRADED_SYMBOLS, LAST_CLOSURE_TIME

    print("=" * 50)
    print("SCEPTER MOMENTUM BOT v5.2 — STRICT MODE")
    print(f"MAX TRADES: {MAX_OPEN_TRADES} | COOLDOWN: {COOLDOWN_MINUTES}min")
    print("=" * 50)

    cooldown = load_cooldown()
    print(f"[COOLDOWN] Loaded {len(cooldown)} symbols from file")

    balances = get_all_balances()
    starting_balance = balances["wallet"]
    peak_balance = balances["margin"]
    print(f"[START] Starting balance: {starting_balance:.2f} USDT")

    existing = [p for p in balances["positions"] if float(p['positionAmt']) != 0]
    for p in existing:
        TRADED_SYMBOLS.add(p['symbol'])
        set_cooldown(p['symbol'], cooldown)

    print(f"[POSITIONS] Found {len(existing)} existing: {TRADED_SYMBOLS}")

    cycle = 0

    while True:
        try:
            cycle += 1
            balances = get_all_balances()
            wallet_balance = balances["wallet"]
            margin_balance = balances["margin"]
            available_balance = balances["available"]
            positions = balances["positions"]

            if margin_balance > peak_balance:
                peak_balance = margin_balance

            print(f"\n{'=' * 50}")
            print(f"[CYCLE {cycle}] Wallet: {wallet_balance:.2f} | NAV: {margin_balance:.2f} | Available: {available_balance:.2f}")

            open_positions = [p for p in positions if float(p['positionAmt']) != 0]
            open_count = len(open_positions)
            open_symbols = {p['symbol'] for p in open_positions}

            for sym in open_symbols:
                TRADED_SYMBOLS.add(sym)
            closed = TRADED_SYMBOLS - open_symbols
            if closed:
                LAST_CLOSURE_TIME = time.time()
            for sym in closed:
                TRADED_SYMBOLS.discard(sym)
                print(f"[CLOSED] {sym} position closed, removed from tracking")

            print(f"[Positions] {open_count}/{MAX_OPEN_TRADES} | Tracked: {TRADED_SYMBOLS if TRADED_SYMBOLS else 'none'}")

            if open_positions:
                manage_open_trades(client, open_positions)

            # Reconcile limit orders (cancel unfilled limit entries older than 3 completed candles / 15 mins)
            try:
                open_orders = client.futures_get_open_orders()
                now_ms = time.time() * 1000
                for order in open_orders:
                    if order.get('type') == 'LIMIT' and order.get('reduceOnly') is False:
                        elapsed_mins = (now_ms - float(order.get('time', now_ms))) / 60000.0
                        if elapsed_mins >= 15.0:
                            sym = order.get('symbol')
                            order_id = order.get('orderId')
                            print(f"[CLEANUP] Order {order_id} for {sym} is unfilled for {elapsed_mins:.1f} mins. Cancelling...")
                            try:
                                client.futures_cancel_order(symbol=sym, orderId=order_id)
                            except Exception as ce:
                                print(f"[CLEANUP] Cancel failed for {sym}: {ce}")
            except Exception as e:
                print(f"[WARN] Order reconciliation failed: {e}")

            if open_count >= MAX_OPEN_TRADES:
                print(f"[FULL] {open_count}/{MAX_OPEN_TRADES} positions — NOT scanning")
            elif time.time() - LAST_CLOSURE_TIME < 300:
                remaining = int(300 - (time.time() - LAST_CLOSURE_TIME))
                print(f"[COOLDOWN] Post-trade-closure delay active: {remaining}s remaining — NOT scanning")
            else:
                symbols = get_symbols()
                print(f"[Scan] {len(symbols)} symbols")
                trade_placed = False

                for symbol in symbols:
                    if trade_placed:
                        break

                    try:
                        if symbol in open_symbols:
                            continue

                        if symbol in TRADED_SYMBOLS:
                            continue

                        # Check file-based cooldown
                        now = time.time()
                        if symbol in cooldown and cooldown[symbol] > now:
                            continue

                        if is_blocked(symbol):
                            continue

                        spread = get_spread_percent(symbol)
                        if spread > MAX_SPREAD_PERCENT:
                            continue

                        candles = get_candles(symbol, TIMEFRAME)
                        if len(candles) < 70:
                            continue

                        trade = analyze_symbol(candles, symbol, wallet_balance, open_count)

                        if not trade:
                            continue

                        if trade:
                            fresh_positions = get_open_positions()
                            fresh_count = len(fresh_positions)
                            fresh_symbols = {p['symbol'] for p in fresh_positions}

                            if fresh_count >= MAX_OPEN_TRADES:
                                print(f"[BLOCKED] {symbol}: Fresh check shows {fresh_count}/{MAX_OPEN_TRADES} — SKIPPING")
                                break

                            if symbol in fresh_symbols:
                                print(f"[BLOCKED] {symbol}: Already has position (fresh check)")
                                TRADED_SYMBOLS.add(symbol)
                                continue

                            if trade["margin"] > available_balance:
                                allowed_margin = available_balance * 0.98
                                if allowed_margin < 1.0:
                                    print(f"[BLOCKED] {symbol}: Available balance {available_balance:.2f} too low")
                                    continue
                                ratio = allowed_margin / trade["margin"]
                                trade["qty"] = trade["qty"] * ratio
                                trade["margin"] = allowed_margin
                                trade["risk"] = trade["risk"] * ratio

                            print(f"\n{'=' * 40}")
                            print(f"[SIGNAL] {symbol} {trade['direction']}")
                            print(f"  Entry: {trade['entry']:.6f}")
                            print(f"  SL:    {trade['sl']:.6f}")
                            print(f"  TP:    {trade['tp']:.6f}")
                            print(f"  Qty:   {trade['qty']:.4f}")
                            print(f"  Margin:{trade['margin']:.2f}")

                            TRADED_SYMBOLS.add(symbol)
                            set_cooldown(symbol, cooldown)

                            result = execute_trade(client, trade)

                            if result:
                                print(f"[EXECUTED] Trade placed successfully")
                                open_count += 1
                                trade_placed = True
                            else:
                                print(f"[FAILED] Trade execution failed")

                            break

                    except Exception as e:
                        print(f"[ERROR] {symbol} scan failed: {e}")
                        continue

            print(f"[Sleep] {SLEEP_SECONDS}s")
            time.sleep(SLEEP_SECONDS)

        except KeyboardInterrupt:
            print("\n[STOP] Bot stopped by user")
            break
        except Exception as e:
            print(f"[ERROR] Cycle {cycle}: {e}")
            time.sleep(10)


if __name__ == "__main__":
    run()
ENDOF_MAIN_PY
echo "[OK] main.py"

cat > check_sl_tp.py << 'ENDOF_CHECK_SL_TP_PY'
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
ENDOF_CHECK_SL_TP_PY
echo "[OK] check_sl_tp.py"

cat > check_rejections.py << 'ENDOF_CHECK_REJECTIONS_PY'
# check_rejections.py
# Parse bot.log and display a beautiful report of rejection reasons

import os
import re
from collections import Counter

LOG_FILE = "bot.log"

def analyze_rejections():
    if not os.path.exists(LOG_FILE):
        print(f"[ERROR] '{LOG_FILE}' not found in the current directory.")
        print("Please make sure you are running the bot with output redirected to bot.log:")
        print("Example: source venv/bin/activate && python3 main.py | tee -a bot.log")
        return

    print(f"Reading '{LOG_FILE}'...")
    
    rejections = []
    
    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "buy signal not confirmed" in line or "sell signal not confirmed" in line:
                if "Reason:" in line:
                    reason = line.split("Reason:")[1].strip()
                    rejections.append(reason)

    if not rejections:
        print("[INFO] No rejection reasons found in the log file yet.")
        return

    total = len(rejections)
    counter = Counter(rejections)
    
    print("\n" + "=" * 70)
    print("                 SCEPTER BOT REJECTION STATISTICS")
    print(f"                 Total Scan Rejections Analyzed: {total}")
    print("=" * 70)
    print(f" {'REJECTION REASON':<45} | {'COUNT':<6} | {'PERCENTAGE':<10}")
    print("-" * 70)
    
    for reason, count in counter.most_common():
        percentage = (count / total) * 100
        print(f" {reason:<45} | {count:<6} | {percentage:>8.2f}%")
        
    print("=" * 70 + "\n")

if __name__ == "__main__":
    analyze_rejections()
ENDOF_CHECK_REJECTIONS_PY
echo "[OK] check_rejections.py"

echo "ALL DONE"
echo "Run: source venv/bin/activate && nohup python3 main.py > bot.log 2>&1 &"
