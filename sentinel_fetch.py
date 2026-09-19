"""Sentinel 共用即時抓取引擎 — update_data.py / local_backend_server.py 共用同一份邏輯。

每個 fetch_* 回傳 (value, live, source)；抓不到才退回 fallback 並標記 live=False。
"""
import json
import subprocess
import time
import urllib.parse
import urllib.request
import re

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


# ─── HTTP Helpers ─────────────────────────────────────────────────────────────

BROWSER_ACCEPT = ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                  "image/avif,image/webp,*/*;q=0.8")


def curl_get(url, extra_headers=None, accept="application/json, text/plain, */*",
             timeout=10, ua=UA):
    """System curl。

    - 強制 HTTP/1.1：FRED / AAII 在 HTTP/2 下會回 stream error (rc 92)。
    - ua=None 時不送 User-Agent（改用 curl 預設）：FRED 會 tarpit 偽造的
      Chrome UA（裸 curl 0.6 秒回 200，帶 Chrome UA 則逾時 rc 28）。
    """
    cmd = ['curl', '-s', '-k', '-L', '--http1.1',
           '-H', f'Accept: {accept}', '--max-time', str(timeout)]
    if ua:
        cmd += ['-H', f'User-Agent: {ua}']
    for k, v in (extra_headers or {}).items():
        cmd += ['-H', f'{k}: {v}']
    cmd.append(url)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout
        print(f"  curl rc={res.returncode} url={url}")
    except Exception as e:
        print(f"  curl_get error: {e}")
    return None


def urllib_get(url, headers=None, timeout=10, ua=UA):
    hdrs = {"Accept": "application/json, text/plain, */*"}
    if ua:
        hdrs["User-Agent"] = ua
    hdrs.update(headers or {})
    try:
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', 'replace')
    except Exception as e:
        print(f"  urllib_get error: {e}")
    return None


def http_get(url, extra_headers=None, accept="application/json, text/plain, */*",
             timeout=10, ua=UA):
    """curl 先行，失敗改走 urllib。"""
    return (curl_get(url, extra_headers, accept, timeout, ua)
            or urllib_get(url, extra_headers, timeout, ua))


# ─── Yahoo Finance v8 ─────────────────────────────────────────────────────────

def _yahoo_chart(symbol, rng="1d", interval="1d"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(symbol)}?interval={interval}&range={rng}")
    raw = http_get(url)
    if not raw:
        return None
    try:
        return json.loads(raw)['chart']['result'][0]
    except Exception as e:
        print(f"  [{symbol}] parse error: {e}")
    return None


def fetch_yahoo_price(symbol, fallback):
    res = _yahoo_chart(symbol)
    if res:
        price = res.get('meta', {}).get('regularMarketPrice')
        if price:
            val = round(float(price), 2)
            print(f"  [{symbol}] Yahoo v8 -> {val}")
            return val, True, "Yahoo Finance v8"
    print(f"  [{symbol}] fallback -> {fallback}")
    return fallback, False, "fallback"


def fetch_ema(symbol, period=60, fallback=None):
    """由 Yahoo 日線實算 EMA，取代硬編碼扣抵價。"""
    res = _yahoo_chart(symbol, rng="1y")
    if res:
        try:
            closes = [c for c in res['indicators']['quote'][0]['close'] if c is not None]
            if len(closes) >= period:
                k = 2 / (period + 1)
                ema = sum(closes[:period]) / period
                for c in closes[period:]:
                    ema = c * k + ema * (1 - k)
                val = round(ema, 2)
                print(f"  [{symbol}] EMA{period} -> {val} ({len(closes)} bars)")
                return val, True, f"Yahoo {period}EMA (live)"
        except Exception as e:
            print(f"  [{symbol}] EMA parse error: {e}")
    print(f"  [{symbol}] EMA{period} fallback -> {fallback}")
    return fallback, False, "fallback"


# ─── TradingView Scanner (備援) ───────────────────────────────────────────────

def fetch_tradingview(tickers):
    """回傳 {ticker: close}。"""
    payload = json.dumps({"symbols": {"tickers": tickers}, "columns": ["name", "close"]})
    try:
        req = urllib.request.Request(
            "https://scanner.tradingview.com/global/scan",
            data=payload.encode('utf-8'),
            headers={"Content-Type": "application/json", "User-Agent": UA,
                     "Referer": "https://www.tradingview.com/"},
            method='POST')
        with urllib.request.urlopen(req, timeout=8) as resp:
            res = json.loads(resp.read().decode('utf-8'))
        out = {}
        for item in res.get('data', []):
            d = item.get('d') or []
            if len(d) > 1 and isinstance(d[1], (int, float)):
                out[item['s']] = round(float(d[1]), 3)
        if out:
            print(f"  [TradingView] -> {out}")
        return out
    except Exception as e:
        print(f"  [TradingView] notice: {e}")
    return {}


# ─── FRED CSV ─────────────────────────────────────────────────────────────────

def fetch_fred_series(series_id, fallback, label=None):
    """取 FRED 序列最後一筆有效值（FRED 以 '.' 表示缺值）。"""
    label = label or series_id
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    # FRED 會 tarpit 偽造的瀏覽器 UA → ua=None 走 curl 預設 UA
    raw = http_get(url, accept="text/csv, text/plain, */*", ua=None)
    if raw:
        try:
            rows = re.findall(r'^(\d{4}-\d{2}-\d{2}),(-?\d+(?:\.\d+)?)\s*$',
                              raw, re.MULTILINE)
            if rows:
                date_str, val_str = rows[-1]
                val = round(float(val_str), 2)
                print(f"  [{label}] FRED {series_id} -> {val} (as of {date_str})")
                return val, True, f"FRED {series_id} ({date_str})"
        except Exception as e:
            print(f"  [{label}] parse error: {e}")
    print(f"  [{label}] fallback -> {fallback}")
    return fallback, False, "fallback"


def fetch_us02y(fallback=4.76):
    """2年期公債殖利率。

    注意：Yahoo 沒有 2 年期代碼，^IRX 是 13 週國庫券，不可當 2Y 使用
    （舊版誤用 ^IRX，導致 10Y-2Y 殖利率差整段算錯）。
    TradingView 即時優先，FRED DGS2（日頻官方、落後約一日）為備援。
    """
    tv = fetch_tradingview(["TVC:US02Y"]).get("TVC:US02Y")
    if tv:
        print(f"  [US02Y] TradingView -> {tv}")
        return round(tv, 2), True, "TradingView TVC:US02Y"
    val, live, src = fetch_fred_series("DGS2", None, label="US02Y")
    if live:
        return val, live, src
    print(f"  [US02Y] fallback -> {fallback}")
    return fallback, False, "fallback"


def fetch_wei(fallback=3.07):
    return fetch_fred_series("WEI", fallback, label="WEI")


# ─── CNN Fear & Greed ─────────────────────────────────────────────────────────

def fetch_cnn(fallback_score=29.1, fallback_rating="fear"):
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    extra = {"Referer": "https://www.cnn.com/markets/fear-and-greed",
             "Origin": "https://www.cnn.com"}

    try:
        from curl_cffi import requests as c_requests
        r = c_requests.get(url, headers=extra, impersonate="chrome120", timeout=10)
        if r.status_code == 200:
            fg = r.json().get('fear_and_greed', {})
            if 'score' in fg:
                score, rating = round(fg['score'], 1), fg['rating']
                print(f"  [CNN] curl_cffi -> {score} ({rating})")
                return score, rating, True, "CNN curl_cffi"
    except Exception as e:
        print(f"  [CNN] curl_cffi notice: {e}")

    raw = http_get(url, extra_headers=extra)
    if raw:
        try:
            fg = json.loads(raw).get('fear_and_greed', {})
            if 'score' in fg:
                score, rating = round(fg['score'], 1), fg['rating']
                print(f"  [CNN] curl -> {score} ({rating})")
                return score, rating, True, "CNN dataviz API"
        except Exception as e:
            print(f"  [CNN] parse error: {e}")

    print(f"  [CNN] fallback -> {fallback_score} {fallback_rating}")
    return fallback_score, fallback_rating, False, "fallback"


# ─── AAII Investor Sentiment ──────────────────────────────────────────────────

def fetch_aaii_spread(fallback=-24.5):
    """AAII 官方調查頁抓 Bull-Bear Spread。
    舊的 files/surveys/sentiment.xls 已回 403，不再使用。"""
    # 需要完整的瀏覽器 Accept / Accept-Language 才能通過 aaii.com 的機器人牆
    raw = http_get("https://www.aaii.com/sentimentsurvey",
                   extra_headers={"Accept-Language": "en-US,en;q=0.9"},
                   accept=BROWSER_ACCEPT, timeout=15)
    if raw:
        text = re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', ' ', raw).replace('&nbsp;', ' '))
        m = re.search(r'Bear\s*(?:&[a-z]+;)?\s*Spread:?\s*([+\-−]?\d+(?:\.\d+)?)\s*pp', text, re.I)
        if not m:
            m = re.search(r'Spread:?\s*([+\-−]?\d+(?:\.\d+)?)\s*pp', text, re.I)
        if m:
            spread = round(float(m.group(1).replace('−', '-')), 1)
            wk = re.search(r'Week ending ([A-Z][a-z]+ \d{1,2}, \d{4})', text)
            bull = re.search(r'Bullish ([\d.]+)%', text)
            bear = re.search(r'Bearish ([\d.]+)%', text)
            detail = []
            if bull: detail.append(f"Bull {bull.group(1)}%")
            if bear: detail.append(f"Bear {bear.group(1)}%")
            print(f"  [AAII] aaii.com -> Spread {spread} pp "
                  f"({', '.join(detail)}{', ' if detail else ''}{wk.group(1) if wk else 'n/a'})")
            return spread, True, f"AAII survey ({wk.group(1) if wk else 'live'})"
        print("  [AAII] spread pattern not found on page")
    print(f"  [AAII] fallback -> {fallback}")
    return fallback, False, "fallback"


# ─── 快取（供常駐伺服器使用，一次性腳本傳 ttl=0 即停用） ────────────────────

_CACHE = {}


def _cached(key, ttl, fn, *args, **kwargs):
    if ttl <= 0:
        return fn(*args, **kwargs)
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn(*args, **kwargs)
    _CACHE[key] = (now, val)
    return val


# ─── 全指標彙整 ───────────────────────────────────────────────────────────────

def fetch_all(price_ttl=0, slow_ttl=0, weekly_ttl=None):
    """回傳 (data dict, diagnostics dict, live_count, total)。

    price_ttl   報價類快取秒數（常駐伺服器建議 45）。
    slow_ttl    日頻資料（60EMA）快取秒數（建議 1800）。
    weekly_ttl  週頻資料（WEI、AAII）快取秒數，預設 slow_ttl 的 12 倍（約 6 小時）。
                AAII 每週只更新一次，且對頻繁請求會回機器人牆，不該常抓。
    """
    if weekly_ttl is None:
        weekly_ttl = slow_ttl * 12
    diag = {}

    def rec(key, value, live, source):
        diag[key] = {"value": value, "live": live, "source": source}
        return value

    def price(key, symbol, fallback):
        return rec(key, *_cached(f"px:{symbol}", price_ttl,
                                 fetch_yahoo_price, symbol, fallback))

    print("\n📡 CNN Fear & Greed...")
    cnn_score, cnn_rating, cnn_live, cnn_src = _cached("cnn", price_ttl, fetch_cnn)
    rec("cnnScore", cnn_score, cnn_live, cnn_src)

    print("\n📡 Yahoo Finance v8 報價...")
    qqq   = price("qqq",   "QQQ",      721.45)
    spy   = price("spy",   "SPY",      761.69)
    vix   = price("vix",   "^VIX",      14.81)
    dxy   = price("dxy",   "DX-Y.NYB", 100.22)
    hyg   = price("hyg",   "HYG",       78.53)
    lqd   = price("lqd",   "LQD",      104.70)
    us10y = price("us10y", "^TNX",       5.00)
    vvix  = price("vvix",  "^VVIX",     87.38)
    skew  = price("skew",  "^SKEW",    148.10)

    print("\n📡 2年期公債殖利率 (TradingView → FRED DGS2)...")
    us02y = rec("us02y", *_cached("us02y", price_ttl, fetch_us02y))

    print("\n📡 60日 EMA 扣抵價實算...")
    qqq_60ema = rec("qqq60ema", *_cached("ema:QQQ", slow_ttl, fetch_ema, "QQQ", 60, 708.95))
    spy_60ema = rec("spy60ema", *_cached("ema:SPY", slow_ttl, fetch_ema, "SPY", 60, 756.04))

    print("\n📡 FRED Weekly Economic Index...")
    wei = rec("weiVal", *_cached("wei", weekly_ttl, fetch_wei))

    print("\n📡 AAII Sentiment Spread...")
    aaii = rec("aaiiSpread", *_cached("aaii", weekly_ttl, fetch_aaii_spread))

    data = {
        "qqq": qqq, "spy": spy, "vix": vix, "dxy": dxy, "hyg": hyg, "lqd": lqd,
        "us10y": us10y, "us02y": us02y, "vvix": vvix, "skew": skew,
        "cnnScore": cnn_score, "cnnRating": cnn_rating,
        "yieldSpread":  round(us10y - us02y, 2),
        "hygLqdRatio":  round(hyg / lqd, 3) if lqd else 0.753,
        "vvixVixRatio": round(vvix / vix, 2) if vix else 6.0,
        "qqq60ema": qqq_60ema,
        "spy60ema": spy_60ema,
        "qqqDeduct": round(((qqq - qqq_60ema) / qqq_60ema) * 100, 2) if qqq_60ema else 0.0,
        "spyDeduct": round(((spy - spy_60ema) / spy_60ema) * 100, 2) if spy_60ema else 0.0,
        "aaiiSpread": aaii,
        "weiVal": wei,
    }
    live_count = sum(1 for v in diag.values() if v["live"])
    return data, diag, live_count, len(diag)
