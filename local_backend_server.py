from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import datetime
import os

import sentinel_fetch as sf

PORT = 8080

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


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), SentinelAPIHandler)
    print(f"==================================================")
    print(f"🚀 Sentinel Quant 雙均線預警系統 - 本機即時數據伺服器已啟動")
    print(f"🌐 網址: http://localhost:{PORT}")
    print(f"⚡ 採用 Yahoo Finance v8 + CNN 雙引擎，零 CORS 阻擋！")
    print(f"==================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        server.server_close()
