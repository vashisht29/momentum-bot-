import urllib.request
import json
import sys

def get_symbol_rank(target_symbol):
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            tickers = json.loads(response.read().decode())
            
        usdt_tickers = [t for t in tickers if t['symbol'].endswith('USDT')]
        usdt_tickers.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
        
        target_normalized = target_symbol.upper()
        if not target_normalized.endswith("USDT"):
            target_normalized += "DT" # Handle 1000SHIBUS -> 1000SHIBUSDT
            
        found_rank = -1
        found_vol = 0
        total_pairs = len(usdt_tickers)
        
        for rank, t in enumerate(usdt_tickers, 1):
            symbol = t['symbol']
            if symbol == target_normalized:
                found_rank = rank
                found_vol = float(t['quoteVolume'])
                break
                
        if found_rank != -1:
            print(f"SYMBOL: {target_normalized}")
            print(f"RANK: {found_rank} out of {total_pairs}")
            print(f"VOLUME: {found_vol/1_000_000:.2f}M USDT")
        else:
            # Try fuzzy search
            matches = [t for t in usdt_tickers if target_symbol.upper() in t['symbol']]
            if matches:
                print(f"Symbol {target_symbol} not found directly, but found matches:")
                for m in matches:
                    # find rank of m
                    for r, t in enumerate(usdt_tickers, 1):
                        if t['symbol'] == m['symbol']:
                            print(f"- {m['symbol']}: Rank #{r} ({float(m['quoteVolume'])/1_000_000:.2f}M USDT)")
            else:
                print(f"Symbol {target_symbol} not found in USDT perpetuals!")
    except Exception as e:
        print(f"Error fetching rank: {e}")

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "1000SHIBUSDT"
    get_symbol_rank(symbol)
