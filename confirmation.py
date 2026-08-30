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
