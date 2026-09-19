import urllib.request
import urllib.parse
import json
import re
import datetime
import os
import subprocess
import struct

print("Starting Sentinel Scanner with Full Live Engine v3...")

# ─── Strategy Helper ──────────────────────────────────────────────────────────

def curl_get(url, extra_headers=None):
    """Run system curl and return response text."""
    cmd = [
        'curl', '-s', '-k',
        '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        '-H', 'Accept: application/json, text/plain, */*',
        '--max-time', '10'
    ]
    if extra_headers:
        for k, v in extra_headers.items():
            cmd += ['-H', f'{k}: {v}']
    cmd.append(url)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception as e:
        print(f"curl_get error: {e}")
    return None

def urllib_get(url, headers=None):
    """Run Python urllib and return response text."""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*"
    }
    if headers:
        default_headers.update(headers)
    try:
        req = urllib.request.Request(url, headers=default_headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode('utf-8')
    except Exception as e:
        print(f"urllib_get error: {e}")
    return None

# ─── 1. Yahoo Finance Price Fetcher ──────────────────────────────────────────

def fetch_yahoo_price(symbol, fallback):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=1d"
    for attempt, raw in enumerate([curl_get(url), urllib_get(url)]):
        if raw:
            try:
                data = json.loads(raw)
                price = data['chart']['result'][0]['meta']['regularMarketPrice']
                if price:
                    val = round(float(price), 2)
                    print(f"  [{symbol}] {'curl' if attempt==0 else 'urllib'} -> {val}")
                    return val, True
            except Exception as e:
                print(f"  [{symbol}] parse error: {e}")
    print(f"  [{symbol}] fallback -> {fallback}")
    return fallback, False

# ─── 2. CNN Fear & Greed ─────────────────────────────────────────────────────

def fetch_cnn():
    cnn_url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    extra = {"Referer": "https://www.cnn.com/markets/fear-and-greed", "Origin": "https://www.cnn.com"}

    # Try curl_cffi first (Chrome TLS impersonation)
    try:
        from curl_cffi import requests as c_requests
        r = c_requests.get(cnn_url, headers={**extra}, impersonate="chrome120", timeout=10)
        if r.status_code == 200:
            d = r.json()
            if 'fear_and_greed' in d and 'score' in d['fear_and_greed']:
                score = round(d['fear_and_greed']['score'], 1)
                rating = d['fear_and_greed']['rating']
                print(f"  [CNN] curl_cffi -> {score} ({rating})")
                return score, rating, True
    except Exception as e:
        print(f"  [CNN] curl_cffi notice: {e}")

    # System curl
    raw = curl_get(cnn_url, extra_headers=extra)
    if raw:
        try:
            d = json.loads(raw)
            if 'fear_and_greed' in d and 'score' in d['fear_and_greed']:
                score = round(d['fear_and_greed']['score'], 1)
                rating = d['fear_and_greed']['rating']
                print(f"  [CNN] system curl -> {score} ({rating})")
                return score, rating, True
        except Exception as e:
            print(f"  [CNN] parse error: {e}")

    print("  [CNN] fallback -> 31.1 fear")
    return 31.1, "fear", False

# ─── 3. FRED Weekly Economic Index ───────────────────────────────────────────

def fetch_fred_wei():
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=WEI"
    raw = curl_get(url) or urllib_get(url)
    if raw:
        try:
            lines = [l.strip() for l in raw.strip().split('\n') if l.strip() and not l.startswith('DATE')]
            if lines:
                last_line = lines[-1]
                date_str, val_str = last_line.split(',')
                val = float(val_str)
                print(f"  [WEI] FRED -> {val} (as of {date_str})")
                return round(val, 2), True
        except Exception as e:
            print(f"  [WEI] parse error: {e}")
    print("  [WEI] fallback -> 2.15")
    return 2.15, False

# ─── 4. AAII Investor Sentiment Spread ───────────────────────────────────────

def fetch_aaii_spread():
    """Download AAII XLS and extract latest Bullish%-Bearish% spread."""
    url = "https://www.aaii.com/files/surveys/sentiment.xls"
    try:
        raw = curl_get(url)
        if not raw:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw_bytes = resp.read()
        else:
            raw_bytes = raw.encode('latin1') if isinstance(raw, str) else raw

        # Save temp file for parsing
        tmp_path = 'tmp_aaii.xls'
        if isinstance(raw_bytes, bytes):
            with open(tmp_path, 'wb') as f:
                f.write(raw_bytes)
        else:
            # if curl returned text, write via subprocess output
            cmd = ['curl', '-s', '-k', '-o', tmp_path, url]
            subprocess.run(cmd, timeout=15, capture_output=True)

        # Try xlrd first
        try:
            import xlrd
            wb = xlrd.open_workbook(tmp_path)
            ws = wb.sheet_by_index(0)
            # Find last row with bullish/bearish data (typically columns 1,3 = bullish,bearish)
            last_row = ws.nrows - 1
            while last_row > 0:
                try:
                    bullish = float(ws.cell_value(last_row, 1))
                    bearish = float(ws.cell_value(last_row, 3))
                    if 0 < bullish < 1 and 0 < bearish < 1:
                        spread = round((bullish - bearish) * 100, 1)
                        print(f"  [AAII] xlrd -> Bull:{bullish*100:.1f}% Bear:{bearish*100:.1f}% Spread:{spread}")
                        return spread, True
                except:
                    pass
                last_row -= 1
        except ImportError:
            print("  [AAII] xlrd not installed, trying openpyxl...")
        except Exception as e:
            print(f"  [AAII] xlrd error: {e}")

        # Try openpyxl
        try:
            import openpyxl
            wb = openpyxl.load_workbook(tmp_path, read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            for row in reversed(rows):
                try:
                    if row[1] and row[3] and 0 < float(row[1]) < 1 and 0 < float(row[3]) < 1:
                        spread = round((float(row[1]) - float(row[3])) * 100, 1)
                        print(f"  [AAII] openpyxl -> Spread: {spread}")
                        return spread, True
                except:
                    pass
        except Exception as e:
            print(f"  [AAII] openpyxl error: {e}")

    except Exception as e:
        print(f"  [AAII] fetch error: {e}")

    print("  [AAII] fallback -> 11.4")
    return 11.4, False

# ─── Fetch All Data ───────────────────────────────────────────────────────────
print("\n📡 Fetching CNN Fear & Greed...")
cnn_score, cnn_rating, cnn_live = fetch_cnn()

print("\n📡 Fetching Yahoo Finance Prices...")
qqq, qqq_live      = fetch_yahoo_price("QQQ",       709.18)
spy, spy_live      = fetch_yahoo_price("SPY",        760.88)
vix, vix_live      = fetch_yahoo_price("^VIX",       17.10)
dxy, dxy_live      = fetch_yahoo_price("DX-Y.NYB",   99.46)
hyg, hyg_live      = fetch_yahoo_price("HYG",        78.53)
lqd, lqd_live      = fetch_yahoo_price("LQD",       104.30)
us10y, us10y_live  = fetch_yahoo_price("^TNX",        4.96)
us02y, us02y_live  = fetch_yahoo_price("^IRX",        4.63)
vvix, vvix_live    = fetch_yahoo_price("^VVIX",     102.66)
skew, skew_live    = fetch_yahoo_price("^SKEW",     147.02)

print("\n📡 Fetching FRED Weekly Economic Index...")
wei, wei_live = fetch_fred_wei()

print("\n📡 Fetching AAII Sentiment Spread...")
aaii_spread, aaii_live = fetch_aaii_spread()

# ─── Derived Calculations ─────────────────────────────────────────────────────
yield_spread    = round(us10y - us02y, 2)
hyg_lqd_ratio   = round(hyg / lqd, 3) if lqd > 0 else 0.753
vvix_vix        = round(vvix / vix, 2) if vix > 0 else 6.0
qqq_60ema       = 708.75
qqq_deduct      = round(((qqq - qqq_60ema) / qqq_60ema) * 100, 2)
spy_60ema       = 755.28
spy_deduct      = round(((spy - spy_60ema) / spy_60ema) * 100, 2)
now_str         = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

live_count = sum([cnn_live, qqq_live, spy_live, vix_live, vvix_live, skew_live, us10y_live, us02y_live, wei_live, aaii_live])
print(f"\n✅ Live: {live_count}/10 indicators fetched successfully at {now_str}")

# ─── 3. Write sentinel_live_data.json ─────────────────────────────────────────
json_payload = {
    "status": "success",
    "source": f"Yahoo v8 + CNN curl_cffi + FRED ({live_count}/10 live)",
    "updated_at": now_str,
    "data": {
        "qqq":          qqq,
        "spy":          spy,
        "vix":          vix,
        "dxy":          dxy,
        "hyg":          hyg,
        "lqd":          lqd,
        "us10y":        us10y,
        "us02y":        us02y,
        "vvix":         vvix,
        "skew":         skew,
        "cnnScore":     cnn_score,
        "cnnRating":    cnn_rating,
        "yieldSpread":  yield_spread,
        "hygLqdRatio":  hyg_lqd_ratio,
        "vvixVixRatio": vvix_vix,
        "qqqDeduct":    qqq_deduct,
        "spyDeduct":    spy_deduct,
        "aaiiSpread":   aaii_spread,
        "weiVal":       wei
    }
}

with open('sentinel_live_data.json', 'w', encoding='utf-8') as f:
    json.dump(json_payload, f, indent=4, ensure_ascii=False)

# ─── 4. Patch index.html ──────────────────────────────────────────────────────
if os.path.exists('index.html'):
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(r'id="last-update-time">[^<]+<', f'id="last-update-time">⚡ 最後更新：{now_str} (CNN {cnn_score} 恐慌指數 · {live_count}/10 即時)<', content)
    content = re.sub(r'id="rem-cnn">[^<]+<', f'id="rem-cnn">{cnn_score:.1f}<', content)
    content = re.sub(r'id="macro-cnn-alert">[^<]+<', f'id="macro-cnn-alert">{cnn_score:.1f} ({cnn_rating.upper()})<', content)
    content = re.sub(r'"cnnScore":\s*[0-9\.]+', f'"cnnScore": {cnn_score:.1f}', content)
    content = re.sub(r'"updated_at":\s*"[^"]+"', f'"updated_at": "{now_str}"', content)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)

print(f"\n🚀 Done! sentinel_live_data.json & index.html updated with {live_count}/10 live indicators.")
