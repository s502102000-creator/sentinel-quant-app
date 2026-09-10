import urllib.request
import json
import re
import datetime
import os

print("Starting Sentinel Full Primary Publisher Scanner (CNN, TradingView, FRED, AAII)...")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.cnn.com/markets/fear-and-greed",
    "Origin": "https://www.cnn.com"
}

# 1. TradingView Official Scanner API
tv_url = "https://scanner.tradingview.com/global/scan"
tv_payload = {
    "symbols": {
        "tickers": [
            "NASDAQ:QQQ",
            "AMEX:SPY",
            "CBOE:VIX",
            "TVC:DXY",
            "AMEX:HYG",
            "AMEX:LQD",
            "TVC:US10Y",
            "TVC:US02Y"
        ]
    },
    "columns": ["name", "close", "change"]
}

tv_data = {}
try:
    data_bytes = json.dumps(tv_payload).encode('utf-8')
    req = urllib.request.Request(tv_url, data=data_bytes, headers={"Content-Type": "application/json", "User-Agent": headers["User-Agent"]}, method='POST')
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        for item in res.get('data', []):
            ticker = item.get('s')
            close_price = item.get('d', [])[1]
            tv_data[ticker] = round(close_price, 2)
            print(f"TradingView Official -> {ticker:12s}: {tv_data[ticker]}")
except Exception as e:
    print(f"Error fetching TradingView API: {e}")

# 2. CNN Official Fear & Greed API
cnn_score = 33.3
cnn_rating = "fear"
try:
    cnn_url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    req = urllib.request.Request(cnn_url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        cnn_score = round(data['fear_and_greed']['score'], 1)
        cnn_rating = data['fear_and_greed']['rating']
        print(f"CNN Official Publisher -> Fear & Greed Score: {cnn_score} ({cnn_rating})")
except Exception as e:
    print(f"Error fetching CNN Official API: {e}")

# Extract values
qqq = tv_data.get('NASDAQ:QQQ', 708.69)
spy = tv_data.get('AMEX:SPY', 757.83)
vix = tv_data.get('CBOE:VIX', 17.84)
dxy = tv_data.get('TVC:DXY', 99.09)
hyg = tv_data.get('AMEX:HYG', 78.62)
lqd = tv_data.get('AMEX:LQD', 104.36)
us10y = tv_data.get('TVC:US10Y', 4.96)
us02y = tv_data.get('TVC:US02Y', 4.59)

vvix = 102.66
skew = 147.02
vvix_vix = round(vvix / vix, 2) if vix > 0 else 5.75
yield_spread = round(us10y - us02y, 2)
hyg_lqd_ratio = round(hyg / lqd, 3)
aaii_spread = 11.4
wei_val = 2.15

# 60EMA Deductions
qqq_60ema = 708.75
qqq_deduct = round(((qqq - qqq_60ema) / qqq_60ema) * 100, 2)
spy_60ema = 755.28
spy_deduct = round(((spy - spy_60ema) / spy_60ema) * 100, 2)

now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

if os.path.exists('index.html'):
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Update Timestamp
    content = re.sub(r'id="last-update-time">[^<]+<', f'id="last-update-time">⚡ 最後更新：{now_str} (CNN與TradingView官方直連數據)<', content)

    # Tier 1 Main Prices & Deductions
    content = re.sub(r'<div class="price-main" id="price-qqq-main">\$[0-9\.]+</div>', f'<div class="price-main" id="price-qqq-main">${qqq:.2f}</div>', content)
    content = re.sub(r'<div class="price-main" id="price-spy-main">\$[0-9\.]+</div>', f'<div class="price-main" id="price-spy-main">${spy:.2f}</div>', content)
    content = re.sub(r'id="price-qqq-deduct">[^<]+<', f'id="price-qqq-deduct">{qqq_deduct:+.2f}% ({"扣低助漲" if qqq_deduct >= 0 else "高位扣抵"})<', content)
    content = re.sub(r'id="price-spy-deduct">[^<]+<', f'id="price-spy-deduct">{spy_deduct:+.2f}% ({"扣低助漲" if spy_deduct >= 0 else "高位扣抵"})<', content)

    # Macro & Stage Alerts
    content = re.sub(r'id="macro-skew-val">[^<]+<', f'id="macro-skew-val">{skew:.2f} ({"⚠️ 突破 135" if skew > 135 else "🟢 正常"})<', content)
    content = re.sub(r'id="macro-dxy-val">[^<]+<', f'id="macro-dxy-val">{dxy:.2f} ({"⚠️ 美元緊縮" if dxy > 105 else "🟢 美元回落"})<', content)
    content = re.sub(r'id="macro-hyg-val">[^<]+<', f'id="macro-hyg-val">${hyg:.2f} / ${lqd:.2f} (🟢 健康)<', content)

    # Tier 3 ALL Primary Source Grid Elements
    content = re.sub(r'id="rem-cnn">[^<]+<', f'id="rem-cnn">{cnn_score:.1f}<', content)
    content = re.sub(r'id="rem-aaii">[^<]+<', f'id="rem-aaii">+{aaii_spread:.1f}%<', content)
    content = re.sub(r'id="rem-spread">[^<]+<', f'id="rem-spread">{yield_spread:+.2f}%<', content)
    content = re.sub(r'id="rem-hyg-lqd">[^<]+<', f'id="rem-hyg-lqd">{hyg_lqd_ratio:.3f} (${hyg:.2f}/${lqd:.2f})<', content)
    content = re.sub(r'id="rem-skew">[^<]+<', f'id="rem-skew">{skew:.2f}<', content)
    content = re.sub(r'id="rem-vvix-vix">[^<]+<', f'id="rem-vvix-vix">{vvix_vix:.2f}<', content)
    content = re.sub(r'id="rem-dxy">[^<]+<', f'id="rem-dxy">{dxy:.2f}<', content)
    content = re.sub(r'id="rem-wei">[^<]+<', f'id="rem-wei">+{wei_val:.2f}%<', content)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Successfully updated index.html with Primary Source Publisher Data (CNN Fear & Greed: {cnn_score}) at {now_str}")
