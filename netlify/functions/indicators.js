const https = require('https');

function httpGet(url, headers = {}) {
    return new Promise((resolve, reject) => {
        const u = new URL(url);
        const options = {
            hostname: u.hostname,
            port: 443,
            path: u.pathname + u.search,
            method: 'GET',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                ...headers
            }
        };
        const req = https.request(options, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => resolve({ statusCode: res.statusCode, body }));
        });
        req.on('error', reject);
        req.setTimeout(10000, () => req.destroy(new Error('timeout')));
        req.end();
    });
}

async function fetchYahoo(symbol, fallback) {
    try {
        const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=1d`;
        const res = await httpGet(url);
        if (res.statusCode === 200) {
            const d = JSON.parse(res.body);
            const price = d.chart.result[0].meta.regularMarketPrice;
            if (price) return { value: Math.round(price * 100) / 100, source: 'Yahoo Finance v8', live: true };
        }
    } catch (e) {
        console.error(`Yahoo [${symbol}] error:`, e.message);
    }
    return { value: fallback, source: 'fallback', live: false };
}

async function fetchCNN() {
    try {
        const res = await httpGet('https://production.dataviz.cnn.io/index/fearandgreed/graphdata', {
            'Referer': 'https://www.cnn.com/markets/fear-and-greed',
            'Origin': 'https://www.cnn.com'
        });
        if (res.statusCode === 200) {
            const d = JSON.parse(res.body);
            if (d.fear_and_greed && d.fear_and_greed.score) {
                return {
                    score: Math.round(d.fear_and_greed.score * 10) / 10,
                    rating: d.fear_and_greed.rating,
                    live: true
                };
            }
        }
    } catch (e) {
        console.error('CNN error:', e.message);
    }
    return { score: 31.1, rating: 'fear', live: false };
}

async function fetchFredWEI() {
    try {
        const res = await httpGet('https://fred.stlouisfed.org/graph/fredgraph.csv?id=WEI');
        if (res.statusCode === 200) {
            const lines = res.body.trim().split(/\r?\n/).filter(l => /^\d{4}-\d{2}-\d{2},-?[\d.]/.test(l));
            if (lines.length > 0) {
                const val = parseFloat(lines[lines.length - 1].split(',')[1]);
                if (isFinite(val)) return { value: val, source: 'FRED WEI (weekly)', live: true };
            }
        }
    } catch (e) {
        console.error('FRED WEI error:', e.message);
    }
    return { value: 2.15, source: 'fallback', live: false };
}

async function fetchAAII() {
    try {
        const res = await httpGet('https://www.aaii.com/sentimentsurvey');
        if (res.statusCode === 200) {
            const text = res.body.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');
            const m = text.match(/Bull[^\d+\-]*Bear[^\d+\-]*Spread[^0-9+\-]*([+\-]?\d+(?:\.\d+)?)/i);
            if (m) {
                const val = parseFloat(m[1]);
                if (isFinite(val)) return { value: val, source: 'AAII weekly survey', live: true };
            }
        }
    } catch (e) {
        console.error('AAII error:', e.message);
    }
    return { value: 11.4, source: 'fallback', live: false };
}

exports.handler = async function(event, context) {
    const corsHeaders = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type': 'application/json; charset=utf-8'
    };

    if (event.httpMethod === 'OPTIONS') {
        return { statusCode: 200, headers: corsHeaders, body: '' };
    }

    try {
        const [
            qqqR, spyR, vixR, dxyR, hygR, lqdR,
            us10yR, us02yR, vvixR, skewR,
            cnnR, weiR, aaiiR
        ] = await Promise.all([
            fetchYahoo('QQQ',       708.69),
            fetchYahoo('SPY',       757.83),
            fetchYahoo('^VIX',      17.84),
            fetchYahoo('DX-Y.NYB',  99.09),
            fetchYahoo('HYG',       78.62),
            fetchYahoo('LQD',      104.36),
            fetchYahoo('^TNX',       4.96),
            fetchYahoo('^IRX',       4.59),
            fetchYahoo('^VVIX',    102.66),
            fetchYahoo('^SKEW',    147.02),
            fetchCNN(),
            fetchFredWEI(),
            fetchAAII()
        ]);

        const qqq   = qqqR.value,   spy    = spyR.value;
        const vix   = vixR.value,   dxy    = dxyR.value;
        const hyg   = hygR.value,   lqd    = lqdR.value;
        const us10y = us10yR.value, us02y  = us02yR.value;
        const vvix  = vvixR.value,  skew   = skewR.value;

        const yieldSpread   = Math.round((us10y - us02y) * 100) / 100;
        const hygLqdRatio   = lqd > 0 ? Math.round((hyg / lqd) * 1000) / 1000 : 0.753;
        const vvixVixRatio  = vix > 0 ? Math.round((vvix / vix) * 100) / 100 : 6.0;
        const qqq_60ema     = 708.75;
        const qqqDeduct     = Math.round(((qqq - qqq_60ema) / qqq_60ema) * 10000) / 100;
        const spy_60ema     = 755.28;
        const spyDeduct     = Math.round(((spy - spy_60ema) / spy_60ema) * 10000) / 100;

        const liveCount = [qqqR, spyR, vixR, dxyR, hygR, lqdR, us10yR, us02yR, vvixR, skewR,
                           { live: cnnR.live }, weiR, aaiiR].filter(r => r.live).length;

        const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);

        return {
            statusCode: 200,
            headers: corsHeaders,
            body: JSON.stringify({
                status: 'success',
                source: `Yahoo v8 + CNN + FRED (${liveCount}/13 live)`,
                updated_at: timestamp,
                diagnostics: {
                    indicators: {
                        qqq: qqqR, spy: spyR, vix: vixR, dxy: dxyR,
                        hyg: hygR, lqd: lqdR, us10y: us10yR, us02y: us02yR,
                        vvix: vvixR, skew: skewR,
                        cnnScore: { value: cnnR.score, source: cnnR.live ? 'CNN Fear & Greed' : 'fallback', live: cnnR.live },
                        aaiiSpread: aaiiR,
                        weiVal: weiR
                    }
                },
                data: {
                    qqq, spy, vix, dxy, hyg, lqd,
                    us10y, us02y, vvix, skew,
                    cnnScore: cnnR.score,
                    cnnRating: cnnR.rating,
                    yieldSpread, hygLqdRatio, vvixVixRatio,
                    qqqDeduct, spyDeduct,
                    aaiiSpread: aaiiR.value,
                    weiVal: weiR.value
                }
            })
        };

    } catch (err) {
        return {
            statusCode: 500,
            headers: corsHeaders,
            body: JSON.stringify({ status: 'error', message: err.message })
        };
    }
};
