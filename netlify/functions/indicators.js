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
                try {
                    resolve(JSON.parse(body));
                } catch (e) {
                    reject(e);
                }
            });
        });
        req.on('error', reject);
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
                try {
                    resolve(JSON.parse(body));
                } catch (e) {
                    reject(e);
                }
            });
        });
        req.on('error', reject);
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
            console.error("TradingView server fetch error:", e.message);
        }

        // 2. Fetch CNN Official Fear & Greed API Server-to-Server
        let cnnScore = 33.3;
        let cnnRating = "fear";
        try {
            const cnnRes = await httpGet("https://production.dataviz.cnn.io/index/fearandgreed/graphdata", {
                'Referer': 'https://www.cnn.com/markets/fear-and-greed',
                'Origin': 'https://www.cnn.com'
            });
            if (cnnRes && cnnRes.fear_and_greed && cnnRes.fear_and_greed.score) {
                cnnScore = Math.round(cnnRes.fear_and_greed.score * 10) / 10;
                cnnRating = cnnRes.fear_and_greed.rating;
            }
        } catch (e) {
            console.error("CNN server fetch error:", e.message);
        }

        // Extract Values & Calculations
        const qqq = tvData['NASDAQ:QQQ'] || 708.69;
        const spy = tvData['AMEX:SPY'] || 757.83;
        const vix = tvData['CBOE:VIX'] || 17.84;
        const dxy = tvData['TVC:DXY'] || 99.09;
        const hyg = tvData['AMEX:HYG'] || 78.62;
        const lqd = tvData['AMEX:LQD'] || 104.36;
        const us10y = tvData['TVC:US10Y'] || 4.96;
        const us02y = tvData['TVC:US02Y'] || 4.59;
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
