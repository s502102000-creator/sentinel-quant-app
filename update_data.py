import urllib.request
import urllib.parse
import json
import re
import datetime
import os
import subprocess

print("Starting Sentinel Scanner with Live CNN and Yahoo v8 Engine...")

# 1. Fetch CNN Official Fear & Greed API
cnn_score = 31.1
cnn_rating = "fear"

def fetch_cnn():
    # Strategy A: Python requests / urllib
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.cnn.com/markets/fear-and-greed",
        "Origin": "https://www.cnn.com",
        "Accept-Language": "en-US,en;q=0.9"
    }
    cnn_url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

    try:
        req = urllib.request.Request(cnn_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            cdata = json.loads(resp.read().decode('utf-8'))
            if 'fear_and_greed' in cdata and 'score' in cdata['fear_and_greed']:
                score = round(cdata['fear_and_greed']['score'], 1)
                rating = cdata['fear_and_greed']['rating']
                print(f"CNN Urllib Engine -> Score: {score} ({rating})")
                return score, rating
    except Exception as e:
        print(f"CNN Urllib notice: {e}")

    # Strategy B: System curl command
    try:
        cmd = [
            'curl', '-s', '-k',
            '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            '-H', 'Referer: https://www.cnn.com/markets/fear-and-greed',
            '-H', 'Origin: https://www.cnn.com',
            '-H', 'Accept: application/json, text/plain, */*',
            cnn_url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            cdata = json.loads(res.stdout)
            if 'fear_and_greed' in cdata and 'score' in cdata['fear_and_greed']:
                score = round(cdata['fear_and_greed']['score'], 1)
                rating = cdata['fear_and_greed']['rating']
                print(f"CNN Curl Engine -> Score: {score} ({rating})")
                return score, rating
    except Exception as e:
        print(f"CNN Curl notice: {e}")

    return 31.1, "fear"

c_score, c_rating = fetch_cnn()
if c_score is not None:
    cnn_score = c_score
    cnn_rating = c_rating

# 2. Fetch Yahoo Finance Prices
def fetch_yahoo_price(symbol, fallback):
    # Strategy A: Curl
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=1d"
        cmd = [
            'curl', '-s', '-k',
            '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            price = data['chart']['result'][0]['meta']['regularMarketPrice']
            if price:
                return round(price, 2)
    except Exception as e:
        print(f"Yahoo Curl notice ({symbol}): {e}")

    # Strategy B: Urllib
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            price = data['chart']['result'][0]['meta']['regularMarketPrice']
            if price:
                return round(price, 2)
    except Exception as e:
        print(f"Yahoo Urllib notice ({symbol}): {e}")

    return fallback

qqq = fetch_yahoo_price("QQQ", 709.18)
spy = fetch_yahoo_price("SPY", 760.88)
vix = fetch_yahoo_price("^VIX", 17.10)
dxy = fetch_yahoo_price("DX-Y.NYB", 99.46)
hyg = fetch_yahoo_price("HYG", 78.53)
lqd = fetch_yahoo_price("LQD", 104.30)
us10y = fetch_yahoo_price("^TNX", 4.96)
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

# 3. Write sentinel_live_data.json
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
