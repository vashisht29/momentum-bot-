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
