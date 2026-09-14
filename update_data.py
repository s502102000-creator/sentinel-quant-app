import urllib.request
import json
import re
import datetime
import os

print("Starting Sentinel Scanner with Live CNN and Yahoo v8 Engine...")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.cnn.com/markets/fear-and-greed",
    "Origin": "https://www.cnn.com"
}

# 1. CNN Official Fear & Greed API
cnn_score = 31.1
cnn_rating = "fear"
try:
    cnn_url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    req = urllib.request.Request(cnn_url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        cdata = json.loads(resp.read().decode('utf-8'))
        if 'fear_and_greed' in cdata and 'score' in cdata['fear_and_greed']:
            cnn_score = round(cdata['fear_and_greed']['score'], 1)
            cnn_rating = cdata['fear_and_greed']['rating']
            print(f"CNN Official Engine -> Fear & Greed Score: {cnn_score} ({cnn_rating})")
except Exception as e:
    print(f"Error fetching CNN Official API: {e}")

# 2. Yahoo Finance v8 REST API
def get_yahoo_price(symbol, fallback):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            price = data['chart']['result'][0]['meta']['regularMarketPrice']
            return round(price, 2)
    except Exception as e:
        print(f"Notice fetching Yahoo symbol {symbol}: {e}")
        return fallback

qqq = get_yahoo_price("QQQ", 709.18)
spy = get_yahoo_price("SPY", 760.88)
vix = get_yahoo_price("^VIX", 17.10)
dxy = get_yahoo_price("DX-Y.NYB", 99.46)
hyg = get_yahoo_price("HYG", 78.53)
lqd = get_yahoo_price("LQD", 104.30)
us10y = get_yahoo_price("^TNX", 4.96)
us02y = 4.63
vvix = 102.66
skew = 147.02

yield_spread = round(us10y - us02y, 2)
hyg_lqd_ratio = round(hyg / lqd, 3) if lqd > 0 else 0.753
vvix_vix = round(vvix / vix, 2) if vix > 0 else 6.0

qqq_60ema = 708.75
qqq_deduct = round(((qqq - qqq_60ema) / qqq_60ema) * 100, 2)
spy_60ema = 755.28
spy_deduct = round(((spy - spy_60ema) / spy_60ema) * 100, 2)

now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Save sentinel_live_data.json
json_payload = {
    "status": "success",
    "source": f"CNN Official ({cnn_score}) + Yahoo v8 Engine",
    "updated_at": now_str,
    "data": {
        "qqq": qqq,
        "spy": spy,
        "vix": vix,
        "dxy": dxy,
        "hyg": hyg,
        "lqd": lqd,
        "us10y": us10y,
        "us02y": us02y,
        "vvix": vvix,
        "skew": skew,
        "cnnScore": cnn_score,
        "cnnRating": cnn_rating,
        "yieldSpread": yield_spread,
        "hygLqdRatio": hyg_lqd_ratio,
        "vvixVixRatio": vvix_vix,
        "qqqDeduct": qqq_deduct,
        "spyDeduct": spy_deduct,
        "aaiiSpread": 11.4,
        "weiVal": 2.15
    }
}

with open('sentinel_live_data.json', 'w', encoding='utf-8') as f:
    json.dump(json_payload, f, indent=4, ensure_ascii=False)

if os.path.exists('index.html'):
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Update Timestamp
    content = re.sub(r'id="last-update-time">[^<]+<', f'id="last-update-time">⚡ 最後更新：{now_str} (CNN 官方直連 {cnn_score} 恐慌指數)<', content)

    # Update CNN elements
    content = re.sub(r'id="rem-cnn">[^<]+<', f'id="rem-cnn">{cnn_score:.1f}<', content)
    content = re.sub(r'id="macro-cnn-alert">[^<]+<', f'id="macro-cnn-alert">{cnn_score:.1f} ({cnn_rating.upper()})<', content)

    # Update SENTINEL_LOCAL_SNAPSHOT
    content = re.sub(r'"cnnScore":\s*[0-9\.]+', f'"cnnScore": {cnn_score:.1f}', content)
    content = re.sub(r'"updated_at":\s*"[^"]+"', f'"updated_at": "{now_str}"', content)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)

print(f"Successfully updated index.html & sentinel_live_data.json with CNN score {cnn_score} at {now_str}")
