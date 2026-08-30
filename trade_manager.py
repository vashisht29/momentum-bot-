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
