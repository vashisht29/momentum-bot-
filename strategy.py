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
