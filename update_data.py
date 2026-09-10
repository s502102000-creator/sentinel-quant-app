import urllib.request
import json
import re
import datetime
import os

print("Starting Sentinel Market Close Automated Scanner...")

symbols = ['QQQ', 'SPY', '^VIX', '^VVIX', '^SKEW', 'DX-Y.NYB', 'HYG', 'LQD']
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
quotes = {}

for s in symbols:
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{s}?interval=1d&range=5d'
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            meta = data['chart']['result'][0]['meta']
            quotes[s] = round(meta['regularMarketPrice'], 2)
            print(f"Fetched {s}: {quotes[s]}")
    except Exception as e:
        print(f"Error fetching {s}: {e}")

now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Check Alert Conditions
alerts = []
qqq = quotes.get('QQQ', 708.69)
spy = quotes.get('SPY', 757.83)
vix = quotes.get('^VIX', 17.84)
vvix = quotes.get('^VVIX', 102.66)
skew = quotes.get('^SKEW', 147.02)
dxy = quotes.get('DX-Y.NYB', 99.08)
hyg = quotes.get('HYG', 78.62)
lqd = quotes.get('LQD', 104.36)

vvix_vix = round(vvix / vix, 2) if vix > 0 else 5.75

if skew > 135:
    alerts.append(f"🟡 [黃燈頂部背離預警] SKEW 黑天鵝避險指數達 {skew} (突破 135 警戒區)！機構正大量購買 OTM Put 保險。")

if vix > 35:
    alerts.append(f"🔵 [藍燈倒掛抄底警報] VIX 恐慌指數飆升至 {vix} (突破 35.0)！觸發 1.5x 抄底加碼訊號。")

if dxy > 105:
    alerts.append(f"⚠️ [美元流動性抽乾] DXY 美元指數高達 {dxy} (突破 105)！注意全球資金緊縮風險。")

print("--- ALERT ENGINE EVALUATION ---")
if alerts:
    for a in alerts:
        print(a)
else:
    print("🟢 所有指標體質健康，無觸發警戒訊號。")

# Update index.html
if os.path.exists('index.html'):
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(r'⚡ 最後更新：.*\(.*\)', f'⚡ 最後更新：{now_str} (GitHub Actions 美股收盤自動同步)', content)

    content = re.sub(r'<div class="price-main" id="price-qqq-main">\$[0-9\.]+</div>', f'<div class="price-main" id="price-qqq-main">${qqq:.2f}</div>', content)
    content = re.sub(r'<div class="price-main" id="price-spy-main">\$[0-9\.]+</div>', f'<div class="price-main" id="price-spy-main">${spy:.2f}</div>', content)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Successfully updated index.html at {now_str}")
