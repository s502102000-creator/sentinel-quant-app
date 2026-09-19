from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import datetime
import os
import threading

import sentinel_fetch as sf

PORT = 8080

# 單執行緒 HTTPServer 會讓一次冷抓取（最久約 15 秒）把整台伺服器堵住，
# 連 index.html 都拿不到 → 改用 ThreadingHTTPServer。
# 抓取本身仍用鎖序列化，避免多個分頁同時打爆上游 API。
_fetch_lock = threading.Lock()

class SentinelAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/indicators') or self.path.startswith('/.netlify/functions/indicators'):
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

            data = self.fetch_live_data()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        else:
            filepath = self.path.split('?')[0].lstrip('/')
            if not filepath:
                filepath = 'index.html'
            
            if os.path.exists(filepath) and os.path.isfile(filepath):
                self.send_response(200)
                if filepath.endswith('.html'):
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                elif filepath.endswith('.json'):
                    self.send_header('Content-type', 'application/json; charset=utf-8')
                elif filepath.endswith('.jpg') or filepath.endswith('.jpeg'):
                    self.send_header('Content-type', 'image/jpeg')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()

    def fetch_live_data(self):
        """全指標即時抓取（邏輯與 update_data.py 共用 sentinel_fetch）。

        報價快取 45 秒、日/週頻資料（60EMA、WEI、AAII）快取 30 分鐘，
        避免頁面每次重整都把上游 API 打爆。
        """
        with _fetch_lock:
            data, diag, live_count, total = sf.fetch_all(price_ttl=45, slow_ttl=1800)
        stale = [k for k, v in diag.items() if not v["live"]]
        if stale:
            print(f"⚠️  備援值: {', '.join(stale)}")

        return {
            "status": "success",
            "source": f"Yahoo v8 + TradingView + CNN + FRED/AAII ({live_count}/{total} live)",
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "diagnostics": {"indicators": diag},
            "data": data,
        }


def warm_up():
    """開機先抓一輪填快取，讓使用者第一次開頁就是秒開。"""
    print("⏳ 首次抓取全指標（約 10-15 秒，之後走快取秒回）...")
    try:
        with _fetch_lock:
            _, diag, live_count, total = sf.fetch_all(price_ttl=45, slow_ttl=1800)
        stale = [k for k, v in diag.items() if not v["live"]]
        print(f"✅ 預熱完成：{live_count}/{total} 項即時"
              + (f"，備援：{', '.join(stale)}" if stale else "，無備援"))
    except Exception as e:
        print(f"⚠️  預熱失敗（不影響啟動，開頁時會重試）: {e}")


if __name__ == '__main__':
    # 先在背景預熱，主執行緒立刻開始服務：瀏覽器能馬上載入頁面，
    # 第一次 /api/indicators 會等在鎖上直到預熱那輪抓完（不會重複抓）。
    threading.Thread(target=warm_up, daemon=True).start()
    server = ThreadingHTTPServer(('0.0.0.0', PORT), SentinelAPIHandler)
    print(f"==================================================")
    print(f"🚀 Sentinel Quant 雙均線預警系統 - 本機即時數據伺服器已啟動")
    print(f"🌐 網址: http://localhost:{PORT}")
    print(f"⚡ Yahoo v8 + TradingView + CNN + FRED/AAII，零 CORS 阻擋！")
    print(f"⛔ 關閉方式：直接關掉這個視窗，或按 Ctrl+C")
    print(f"==================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        server.server_close()
