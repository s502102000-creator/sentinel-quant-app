const https = require('https');

function httpPost(url, data, headers = {}) {
    return new Promise((resolve, reject) => {
        const u = new URL(url);
        const reqData = JSON.stringify(data);
        const options = {
            hostname: u.hostname,
            port: 443,
            path: u.pathname + u.search,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(reqData),
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                ...headers
            }
        };

        const req = https.request(options, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => {
                if (res.statusCode < 200 || res.statusCode >= 300) {
                    reject(new Error(`HTTP ${res.statusCode} from ${u.hostname}`));
                    return;
                }
                try {
                    resolve(JSON.parse(body));
                } catch (e) {
                    reject(e);
                }
            });
        });
        req.on('error', reject);
        req.setTimeout(10000, () => req.destroy(new Error(`Request to ${u.hostname} timed out`)));
        req.write(reqData);
        req.end();
    });
}

function httpGet(url, headers = {}) {
    return new Promise((resolve, reject) => {
        const u = new URL(url);
        const options = {
            hostname: u.hostname,
            port: 443,
            path: u.pathname + u.search,
            method: 'GET',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Referer': 'https://www.cnn.com/markets/fear-and-greed',
                'Origin': 'https://www.cnn.com',
                'Accept': 'application/json',
                ...headers
            }
        };

        const req = https.request(options, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => {
                if (res.statusCode < 200 || res.statusCode >= 300) {
                    reject(new Error(`HTTP ${res.statusCode} from ${u.hostname}`));
                    return;
                }
                try {
                    resolve(JSON.parse(body));
                } catch (e) {
                    reject(e);
                }
            });
        });
        req.on('error', reject);
        req.setTimeout(10000, () => req.destroy(new Error(`Request to ${u.hostname} timed out`)));
        req.end();
    });
}

exports.handler = async function(event, context) {
    const corsHeaders = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type': 'application/json; charset=utf-8'
    };

    try {
        // 1. Fetch TradingView Official API Server-to-Server
        const tvPayload = {
            symbols: {
                tickers: [
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
            columns: ["name", "close", "change"]
        };

        let tvData = {};
        let tradingViewError = null;
        try {
            const tvRes = await httpPost("https://scanner.tradingview.com/global/scan", tvPayload);
            if (tvRes && tvRes.data) {
                tvRes.data.forEach(item => {
                    if (item.s && item.d && item.d.length > 1) {
                        tvData[item.s] = Math.round(item.d[1] * 100) / 100;
                    }
                });
            }
        } catch (e) {
            tradingViewError = e.message;
            console.error("TradingView server fetch error:", e.message);
        }

        // 2. Fetch CNN Official Fear & Greed API Server-to-Server
        let cnnScore = 33.3;
        let cnnRating = "fear";
        let cnnLive = false;
        let cnnError = null;
        try {
            const cnnRes = await httpGet("https://production.dataviz.cnn.io/index/fearandgreed/graphdata", {
                'Referer': 'https://www.cnn.com/markets/fear-and-greed',
                'Origin': 'https://www.cnn.com'
            });
            if (cnnRes && cnnRes.fear_and_greed && cnnRes.fear_and_greed.score) {
                cnnScore = Math.round(cnnRes.fear_and_greed.score * 10) / 10;
                cnnRating = cnnRes.fear_and_greed.rating;
                cnnLive = true;
            }
        } catch (e) {
            cnnError = e.message;
            console.error("CNN server fetch error:", e.message);
        }

        // Extract Values & Calculations
        const fromTradingView = (ticker, fallback) => {
            const live = Number.isFinite(tvData[ticker]);
            return { value: live ? tvData[ticker] : fallback, source: live ? 'TradingView' : 'fallback', live };
        };
        const qqqResult = fromTradingView('NASDAQ:QQQ', 708.69);
        const spyResult = fromTradingView('AMEX:SPY', 757.83);
        const vixResult = fromTradingView('CBOE:VIX', 17.84);
        const dxyResult = fromTradingView('TVC:DXY', 99.09);
        const hygResult = fromTradingView('AMEX:HYG', 78.62);
        const lqdResult = fromTradingView('AMEX:LQD', 104.36);
        const us10yResult = fromTradingView('TVC:US10Y', 4.96);
        const us02yResult = fromTradingView('TVC:US02Y', 4.59);
        const qqq = qqqResult.value;
        const spy = spyResult.value;
        const vix = vixResult.value;
        const dxy = dxyResult.value;
        const hyg = hygResult.value;
        const lqd = lqdResult.value;
        const us10y = us10yResult.value;
        const us02y = us02yResult.value;
        const vvix = 102.66;
        const skew = 147.02;

        const yieldSpread = Math.round((us10y - us02y) * 100) / 100;
        const hygLqdRatio = Math.round((hyg / lqd) * 1000) / 1000;
        const vvixVixRatio = Math.round((vvix / vix) * 100) / 100;

        const qqq_60ema = 708.75;
        const qqqDeduct = Math.round(((qqq - qqq_60ema) / qqq_60ema) * 10000) / 100;
        const spy_60ema = 755.28;
        const spyDeduct = Math.round(((spy - spy_60ema) / spy_60ema) * 10000) / 100;

        const now = new Date();
        const timestamp = now.toISOString().replace('T', ' ').substring(0, 19);

        const responsePayload = {
            status: "success",
            source: "backend-serverless-primary-publishers",
            updated_at: timestamp,
            diagnostics: {
                providers: {
                    tradingview: {
                        status: Object.keys(tvData).length ? 'ok' : 'failed',
                        received: Object.keys(tvData).length,
                        expected: 8,
                        error: tradingViewError
                    },
                    cnn: {
                        status: cnnLive ? 'ok' : 'failed',
                        error: cnnError
                    }
                },
                indicators: {
                    qqq: qqqResult, spy: spyResult, vix: vixResult, dxy: dxyResult,
                    hyg: hygResult, lqd: lqdResult, us10y: us10yResult, us02y: us02yResult,
                    cnnScore: { value: cnnScore, source: cnnLive ? 'CNN Fear & Greed' : 'fallback', live: cnnLive },
                    vvix: { value: vvix, source: 'static snapshot', live: false },
                    skew: { value: skew, source: 'static snapshot', live: false },
                    aaiiSpread: { value: 11.4, source: 'static snapshot', live: false },
                    weiVal: { value: 2.15, source: 'static snapshot', live: false }
                }
            },
            data: {
                qqq,
                spy,
                vix,
                dxy,
                hyg,
                lqd,
                us10y,
                us02y,
                vvix,
                skew,
                cnnScore,
                cnnRating,
                yieldSpread,
                hygLqdRatio,
                vvixVixRatio,
                qqqDeduct,
                spyDeduct,
                aaiiSpread: 11.4,
                weiVal: 2.15
            }
        };

        return {
            statusCode: 200,
            headers: corsHeaders,
            body: JSON.stringify(responsePayload)
        };

    } catch (err) {
        return {
            statusCode: 500,
            headers: corsHeaders,
            body: JSON.stringify({ status: "error", message: err.message })
        };
    }
};
