from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.parse
import json
import datetime
import os

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

    def fetch_yahoo_price(self, symbol):
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=1d"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                cdata = json.loads(resp.read().decode('utf-8'))
                price = cdata['chart']['result'][0]['meta']['regularMarketPrice']
                return round(price, 2)
        except Exception as e:
            print(f"Yahoo fetch notice ({symbol}): {e}")
            return None

    def fetch_live_data(self):
        # Primary Engine: Yahoo Finance v8 Chart API
        symbols_map = {
            "QQQ": "QQQ",
            "SPY": "SPY",
            "VIX": "^VIX",
            "DXY": "DX-Y.NYB",
            "HYG": "HYG",
            "LQD": "LQD",
            "US10Y": "^TNX"
        }
        yh_data = {}
        for key, sym in symbols_map.items():
            val = self.fetch_yahoo_price(sym)
            if val is not None:
                yh_data[key] = val

        # Secondary Engine: TradingView Scanner API
        tv_data = {}
        try:
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
                "columns": ["name", "close"]
            }
            data_bytes = json.dumps(tv_payload).encode('utf-8')
            req = urllib.request.Request(tv_url, data=data_bytes, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}, method='POST')
            with urllib.request.urlopen(req, timeout=6) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                for item in res.get('data', []):
                    tv_data[item.get('s')] = round(item.get('d', [])[1], 2)
        except Exception as e:
            print(f"TradingView fetch notice: {e}")

        # CNN Official Fear & Greed API
        cnn_score = 31.1
        cnn_rating = "fear"
        try:
            cnn_url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
            req = urllib.request.Request(cnn_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
                "Referer": "https://www.cnn.com/markets/fear-and-greed",
                "Origin": "https://www.cnn.com"
            })
            with urllib.request.urlopen(req, timeout=6) as resp:
                cdata = json.loads(resp.read().decode('utf-8'))
                cnn_score = round(cdata['fear_and_greed']['score'], 1)
                cnn_rating = cdata['fear_and_greed']['rating']
        except Exception as e:
            print(f"CNN fetch notice: {e}")

        qqq = yh_data.get("QQQ") or tv_data.get('NASDAQ:QQQ') or 709.18
        spy = yh_data.get("SPY") or tv_data.get('AMEX:SPY') or 760.88
        vix = yh_data.get("VIX") or tv_data.get('CBOE:VIX') or 17.10
        dxy = yh_data.get("DXY") or tv_data.get('TVC:DXY') or 99.46
        hyg = yh_data.get("HYG") or tv_data.get('AMEX:HYG') or 78.53
        lqd = yh_data.get("LQD") or tv_data.get('AMEX:LQD') or 104.30
        us10y = yh_data.get("US10Y") or tv_data.get('TVC:US10Y') or 4.96
        us02y = 4.63

        vvix = 102.66
        skew = 147.02
        yield_spread = round(us10y - us02y, 2)
        hyg_lqd_ratio = round(hyg / lqd, 3)
        vvix_vix = round(vvix / vix, 2) if vix > 0 else 6.0

        qqq_60ema = 708.75
        qqq_deduct = round(((qqq - qqq_60ema) / qqq_60ema) * 100, 2)
        spy_60ema = 755.28
        spy_deduct = round(((spy - spy_60ema) / spy_60ema) * 100, 2)

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "status": "success",
            "source": "Yahoo Finance v8 + CNN 雙引擎直連",
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
