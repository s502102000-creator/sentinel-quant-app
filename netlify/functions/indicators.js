const https = require('https');
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const { promisify } = require('util');
const execFileAsync = promisify(execFile);

// ─── 🎭 Browser Impersonation Profiles ───────────────────────────────────────
// Rotate between real Chrome versions on different OSes to avoid fingerprinting
const BROWSER_PROFILES = [
    {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        'sec-ch-ua-platform': '"Windows"',
        'sec-ch-ua-mobile': '?0'
    },
    {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
        'sec-ch-ua-platform': '"macOS"',
        'sec-ch-ua-mobile': '?0'
    },
    {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
        'sec-ch-ua': '"Chromium";v="122", "Microsoft Edge";v="122", "Not(A:Brand";v="24"',
        'sec-ch-ua-platform': '"Windows"',
        'sec-ch-ua-mobile': '?0'
    }
];

function pickProfile() {
    // Pick deterministically per minute so all parallel calls in one request use same profile
    return BROWSER_PROFILES[Math.floor(Date.now() / 60000) % BROWSER_PROFILES.length];
}

// Full realistic browser headers for a given origin/referer context
function browserHeaders(referer = null, origin = null, extra = {}) {
    const profile = pickProfile();
    return {
        'User-Agent': profile['User-Agent'],
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Connection': 'keep-alive',
        'sec-ch-ua': profile['sec-ch-ua'],
        'sec-ch-ua-mobile': profile['sec-ch-ua-mobile'],
        'sec-ch-ua-platform': profile['sec-ch-ua-platform'],
        'Sec-Fetch-Site': origin ? 'same-site' : 'cross-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        ...(referer ? { 'Referer': referer } : {}),
        ...(origin  ? { 'Origin': origin }   : {}),
        ...extra
    };
}

// ─── Read cached snapshot (GitHub Actions daily commit) ───────────────────────
function readSnapshot() {
    try {
        const p = path.join(__dirname, '../../sentinel_live_data.json');
        if (fs.existsSync(p)) return JSON.parse(fs.readFileSync(p, 'utf8'));
    } catch (e) { console.error('Snapshot read:', e.message); }
    return null;
}

// ─── HTTP request helper (handles gzip via Accept-Encoding header) ─────────────
function httpRequest(url, { method = 'GET', headers = {}, body = null, timeout = 9000 } = {}) {
    return new Promise((resolve, reject) => {
        const u = new URL(url);
        const opts = {
            hostname: u.hostname, port: 443,
            path: u.pathname + u.search,
            method,
            headers: { ...headers }
        };
        if (body) {
            opts.headers['Content-Type'] = 'application/json';
            opts.headers['Content-Length'] = Buffer.byteLength(body);
        }

        const req = https.request(opts, res => {
            // Handle redirect (301/302)
            if ([301, 302, 307, 308].includes(res.statusCode) && res.headers.location) {
                const newUrl = res.headers.location.startsWith('http')
                    ? res.headers.location
                    : `https://${u.hostname}${res.headers.location}`;
                return httpRequest(newUrl, { method, headers, body, timeout })
                    .then(resolve).catch(reject);
            }
            const chunks = [];
            res.on('data', c => chunks.push(c));
            res.on('end', () => {
                resolve({ statusCode: res.statusCode, body: Buffer.concat(chunks).toString('utf8') });
            });
        });
        req.on('error', reject);
        req.setTimeout(timeout, () => req.destroy(new Error('timeout')));
        if (body) req.write(body);
        req.end();
    });
}

// ─── 1. TradingView Scanner (Primary Engine) ──────────────────────────────────
const TV_SYMBOLS = {
    qqq:   'NASDAQ:QQQ',
    spy:   'AMEX:SPY',
    vix:   'CBOE:VIX',
    dxy:   'TVC:DXY',
    hyg:   'AMEX:HYG',
    lqd:   'AMEX:LQD',
    us10y: 'TVC:US10Y',
    us02y: 'TVC:US02Y',
    vvix:  'CBOE:VVIX',
    skew:  'CBOE:SKEW'
};

async function fetchTradingView() {
    const tickers = Object.values(TV_SYMBOLS);
    const payload = JSON.stringify({ symbols: { tickers }, columns: ['name', 'close', 'change_abs'] });

    // Retry up to 2 times with different profiles
    for (let attempt = 0; attempt < 2; attempt++) {
        try {
            const hdrs = browserHeaders(
                'https://www.tradingview.com/',
                'https://www.tradingview.com',
                {
                    // TradingView expects this header in scanner requests
                    'X-Language': 'en',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            );
            const res = await httpRequest('https://scanner.tradingview.com/global/scan', {
                method: 'POST', body: payload, headers: hdrs, timeout: 7000
            });
            if (res.statusCode === 200) {
                const d = JSON.parse(res.body);
                const map = {};
                if (d && d.data) {
                    d.data.forEach(item => {
                        if (item.s && item.d && item.d[1] !== null && isFinite(item.d[1])) {
                            map[item.s] = Math.round(item.d[1] * 100) / 100;
                        }
                    });
                }
                const n = Object.keys(map).length;
                console.log(`TradingView attempt ${attempt + 1}: ${n}/${tickers.length} symbols`);
                if (n > 0) return map;
            } else {
                console.log(`TradingView attempt ${attempt + 1}: HTTP ${res.statusCode}`);
            }
        } catch (e) {
            console.error(`TradingView attempt ${attempt + 1}:`, e.message);
        }
        // Small jitter before retry
        await new Promise(r => setTimeout(r, 300 + Math.random() * 400));
    }
    return null;
}

// ─── 2. Yahoo Finance v8 (Per-symbol fallback) ────────────────────────────────
const YAHOO_SYMBOLS = {
    qqq: 'QQQ', spy: 'SPY', vix: '^VIX', dxy: 'DX-Y.NYB',
    hyg: 'HYG', lqd: 'LQD', us10y: '^TNX', us02y: '^IRX',
    vvix: '^VVIX', skew: '^SKEW'
};

async function fetchYahooSingle(sym) {
    try {
        const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=1d&range=1d`;
        const hdrs = browserHeaders('https://finance.yahoo.com/', 'https://finance.yahoo.com');
        const res = await httpRequest(url, { headers: hdrs });
        if (res.statusCode === 200) {
            const d = JSON.parse(res.body);
            const price = d.chart.result[0].meta.regularMarketPrice;
            if (price && isFinite(price)) return Math.round(price * 100) / 100;
        }
    } catch (e) {
        console.error(`Yahoo [${sym}]:`, e.message);
    }
    return null;
}

// ─── 3. All prices: TradingView → Yahoo per-symbol fallback ───────────────────
const FALLBACKS = {
    qqq: 708.69, spy: 757.83, vix: 17.84,  dxy: 99.09,
    hyg: 78.62,  lqd: 104.36, us10y: 4.96, us02y: 4.59,
    vvix: 102.66, skew: 147.02
};

async function fetchAllPrices() {
    const tvData = await fetchTradingView();
    const results = {};

    await Promise.all(Object.keys(TV_SYMBOLS).map(async key => {
        const tvVal = tvData && tvData[TV_SYMBOLS[key]];
        if (tvVal !== undefined && isFinite(tvVal)) {
            results[key] = { value: tvVal, source: 'TradingView Scanner', live: true };
        } else {
            const yahooVal = await fetchYahooSingle(YAHOO_SYMBOLS[key]);
            if (yahooVal !== null) {
                results[key] = { value: yahooVal, source: 'Yahoo Finance v8', live: true };
            } else {
                results[key] = { value: FALLBACKS[key], source: 'fallback', live: false };
            }
        }
    }));

    return results;
}

// ─── 4. CNN Fear & Greed ──────────────────────────────────────────────────────
async function fetchCNNWithCurl() {
    const profile = pickProfile();
    const { stdout } = await execFileAsync('curl', [
        '--silent', '--show-error', '--location', '--compressed', '--http1.1', '--max-time', '10',
        '--user-agent', profile['User-Agent'],
        '--header', 'Accept: application/json, text/plain, */*',
        '--header', 'Referer: https://www.cnn.com/markets/fear-and-greed',
        '--header', 'Origin: https://www.cnn.com',
        'https://production.dataviz.cnn.io/index/fearandgreed/graphdata'
    ], { timeout: 12000, maxBuffer: 1024 * 1024 });
    const data = JSON.parse(stdout);
    if (!data.fear_and_greed || !Number.isFinite(data.fear_and_greed.score)) {
        throw new Error('CNN curl response did not contain a valid score');
    }
    return {
        score: Math.round(data.fear_and_greed.score * 10) / 10,
        rating: data.fear_and_greed.rating,
        live: true,
        source: 'CNN via curl'
    };
}

async function fetchCNN() {
    const errors = [];
    try {
        return await fetchCNNWithCurl();
    } catch (e) {
        errors.push(`curl: ${e.message}`);
        console.error('CNN curl:', e.message);
    }
    try {
        const hdrs = browserHeaders(
            'https://www.cnn.com/markets/fear-and-greed',
            'https://www.cnn.com',
            { 'DNT': '1' }
        );
        const res = await httpRequest('https://production.dataviz.cnn.io/index/fearandgreed/graphdata', { headers: hdrs });
        if (res.statusCode === 200) {
            const d = JSON.parse(res.body);
            if (d.fear_and_greed && d.fear_and_greed.score) {
                return {
                    score: Math.round(d.fear_and_greed.score * 10) / 10,
                    rating: d.fear_and_greed.rating,
                    live: true,
                    source: 'CNN via Node HTTPS'
                };
            }
        }
    } catch (e) {
        errors.push(`node: ${e.message}`);
        console.error('CNN Node HTTPS:', e.message);
    }
    return { score: 31.1, rating: 'fear', live: false, source: 'fallback', error: errors.join(' | ') };
}

// ─── 5. FRED WEI → snapshot fallback ─────────────────────────────────────────
async function fetchWEI(snapshot) {
    try {
        const hdrs = browserHeaders('https://fred.stlouisfed.org/', 'https://fred.stlouisfed.org');
        const res = await httpRequest('https://fred.stlouisfed.org/graph/fredgraph.csv?id=WEI', { headers: hdrs });
        if (res.statusCode === 200) {
            const lines = res.body.trim().split(/\r?\n/).filter(l => /^\d{4}-\d{2}-\d{2},-?[\d.]/.test(l));
            if (lines.length > 0) {
                const val = parseFloat(lines[lines.length - 1].split(',')[1]);
                if (isFinite(val)) return { value: val, source: 'FRED WEI (weekly, live)', live: true };
            }
        }
    } catch (e) { console.error('FRED WEI:', e.message); }

    const cached = snapshot && snapshot.data && snapshot.data.weiVal;
    if (cached !== undefined && isFinite(cached)) {
        return { value: cached, source: `FRED WEI (snapshot ${snapshot.updated_at || ''})`, live: true };
    }
    return { value: 2.15, source: 'fallback', live: false };
}

// ─── 6. AAII Sentiment → snapshot fallback ────────────────────────────────────
async function fetchAAII(snapshot) {
    try {
        const hdrs = browserHeaders('https://www.aaii.com/', 'https://www.aaii.com', { 'DNT': '1' });
        const res = await httpRequest('https://www.aaii.com/sentimentsurvey', { headers: hdrs });
        if (res.statusCode === 200) {
            const text = res.body.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');
            const m = text.match(/Bull[^\d+\-]*Bear[^\d+\-]*Spread[^0-9+\-]*([+\-]?\d+(?:\.\d+)?)/i);
            if (m) {
                const val = parseFloat(m[1]);
                if (isFinite(val)) return { value: val, source: 'AAII weekly survey (live)', live: true };
            }
        }
    } catch (e) { console.error('AAII:', e.message); }

    const cached = snapshot && snapshot.data && snapshot.data.aaiiSpread;
    if (cached !== undefined && isFinite(cached)) {
        return { value: cached, source: `AAII weekly (snapshot ${snapshot.updated_at || ''})`, live: true };
    }
    return { value: 11.4, source: 'fallback', live: false };
}

// ─── Main Handler ─────────────────────────────────────────────────────────────
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
        const snapshot = readSnapshot();

        const [prices, cnnR, weiR, aaiiR] = await Promise.all([
            fetchAllPrices(),
            fetchCNN(),
            fetchWEI(snapshot),
            fetchAAII(snapshot)
        ]);

        const get = k => prices[k].value;
        const qqq = get('qqq'), spy = get('spy'), vix = get('vix'), dxy = get('dxy');
        const hyg = get('hyg'), lqd = get('lqd'), us10y = get('us10y'), us02y = get('us02y');
        const vvix = get('vvix'), skew = get('skew');

        const yieldSpread  = Math.round((us10y - us02y) * 100) / 100;
        const hygLqdRatio  = lqd > 0 ? Math.round((hyg / lqd) * 1000) / 1000 : 0.753;
        const vvixVixRatio = vix > 0 ? Math.round((vvix / vix) * 100) / 100 : 6.0;
        const qqq_60ema = 708.75, spy_60ema = 755.28;
        const qqqDeduct = Math.round(((qqq - qqq_60ema) / qqq_60ema) * 10000) / 100;
        const spyDeduct = Math.round(((spy - spy_60ema) / spy_60ema) * 10000) / 100;

        const allResults = [...Object.values(prices), { live: cnnR.live }, weiR, aaiiR];
        const liveCount = allResults.filter(r => r.live).length;
        const tvCount = Object.values(prices).filter(r => r.source === 'TradingView Scanner').length;
        const yhCount = Object.values(prices).filter(r => r.source === 'Yahoo Finance v8').length;
        const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);

        return {
            statusCode: 200,
            headers: corsHeaders,
            body: JSON.stringify({
                status: 'success',
                source: `TradingView(${tvCount})→Yahoo(${yhCount}) + CNN + FRED/Snapshot (${liveCount}/${allResults.length} live)`,
                updated_at: timestamp,
                snapshot_updated_at: snapshot ? snapshot.updated_at : null,
                diagnostics: {
                    indicators: {
                        ...prices,
                        cnnScore: { value: cnnR.score, source: cnnR.source, live: cnnR.live, error: cnnR.error || null },
                        aaiiSpread: aaiiR,
                        weiVal: weiR
                    }
                },
                data: {
                    qqq, spy, vix, dxy, hyg, lqd, us10y, us02y, vvix, skew,
                    cnnScore: cnnR.score, cnnRating: cnnR.rating,
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
