"""GitHub Actions 每日快照：抓全指標寫入 sentinel_live_data.json 並回填 index.html。

所有抓取邏輯集中在 sentinel_fetch.py，與 local_backend_server.py 共用同一份，
避免各頻道數字互相漂移。
"""
import json
import re
import datetime
import os

import sentinel_fetch as sf

print("Starting Sentinel Scanner with Full Live Engine v4 (shared engine)...")

data, diag, live_count, total = sf.fetch_all()
now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
cnn_score = data["cnnScore"]
cnn_rating = data["cnnRating"]

stale = [k for k, v in diag.items() if not v["live"]]
print(f"\n✅ Live: {live_count}/{total} indicators fetched successfully at {now_str}")
if stale:
    print(f"⚠️  使用備援值的指標: {', '.join(stale)}")

# ─── 1. Write sentinel_live_data.json ─────────────────────────────────────────
json_payload = {
    "status": "success",
    "source": f"Yahoo v8 + TradingView + CNN + FRED/AAII ({live_count}/{total} live)",
    "updated_at": now_str,
    "diagnostics": {"indicators": diag},
    "data": data,
}

with open('sentinel_live_data.json', 'w', encoding='utf-8') as f:
    json.dump(json_payload, f, indent=4, ensure_ascii=False)

# ─── 2. Patch index.html ──────────────────────────────────────────────────────
if os.path.exists('index.html'):
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(r'id="last-update-time">[^<]+<',
                     f'id="last-update-time">⚡ 最後更新：{now_str} '
                     f'(CNN {cnn_score} 恐慌指數 · {live_count}/{total} 即時)<', content)
    content = re.sub(r'id="rem-cnn">[^<]+<', f'id="rem-cnn">{cnn_score:.1f}<', content)
    content = re.sub(r'id="macro-cnn-alert">[^<]+<',
                     f'id="macro-cnn-alert">{cnn_score:.1f} ({cnn_rating.upper()})<', content)
    content = re.sub(r'"cnnScore":\s*[0-9.]+', f'"cnnScore": {cnn_score:.1f}', content)
    content = re.sub(r'"updated_at":\s*"[^"]+"', f'"updated_at": "{now_str}"', content)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)

print(f"\n🚀 Done! sentinel_live_data.json & index.html updated "
      f"with {live_count}/{total} live indicators.")
