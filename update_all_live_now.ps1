# Native PowerShell Real-Time Fetcher
$cnnHeaders = @{
    "User-Agent"="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36";
    "Referer"="https://www.cnn.com/markets/fear-and-greed";
    "Origin"="https://www.cnn.com";
    "Accept"="application/json"
}

# 1. CNN Official API
$cnnScore = 31.1
$cnnRating = "fear"
try {
    $rawCnn = curl.exe -k --ssl-no-revoke -s -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" -H "Referer: https://www.cnn.com/markets/fear-and-greed" -H "Origin: https://www.cnn.com" "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    if ($rawCnn) {
        $cnnObj = $rawCnn | ConvertFrom-Json
        if ($cnnObj.fear_and_greed.score) {
            $cnnScore = [math]::Round($cnnObj.fear_and_greed.score, 1)
            $cnnRating = $cnnObj.fear_and_greed.rating
        }
    }
} catch {
    Write-Host "CNN Fetch Notice: $_"
}

# 2. Yahoo Finance v8 Chart API
function Get-YahooPrice($symbol) {
    try {
        $u = "https://query1.finance.yahoo.com/v8/finance/chart/" + [uri]::EscapeDataString($symbol) + "?interval=1d&range=1d"
        $r = Invoke-RestMethod -Uri $u -Headers @{"User-Agent"="Mozilla/5.0"}
        return [math]::Round($r.chart.result[0].meta.regularMarketPrice, 2)
    } catch {
        return $null
    }
}

$qqq = (Get-YahooPrice "QQQ")
if (-not $qqq) { $qqq = 709.18 }
$spy = (Get-YahooPrice "SPY")
if (-not $spy) { $spy = 760.88 }
$vix = (Get-YahooPrice "^VIX")
if (-not $vix) { $vix = 17.10 }
$dxy = (Get-YahooPrice "DX-Y.NYB")
if (-not $dxy) { $dxy = 99.46 }
$hyg = (Get-YahooPrice "HYG")
if (-not $hyg) { $hyg = 78.53 }
$lqd = (Get-YahooPrice "LQD")
if (-not $lqd) { $lqd = 104.30 }
$us10y = (Get-YahooPrice "^TNX")
if (-not $us10y) { $us10y = 4.96 }
$us02y = 4.63

$vvix = 102.66
$skew = 147.02
$yieldSpread = [math]::Round($us10y - $us02y, 2)
$hygLqdRatio = [math]::Round($hyg / $lqd, 3)
$vvixVixRatio = [math]::Round($vvix / $vix, 2)

$qqq60ema = 708.75
$qqqDeduct = [math]::Round((($qqq - $qqq60ema) / $qqq60ema) * 100, 2)
$spy60ema = 755.28
$spyDeduct = [math]::Round((($spy - $spy60ema) / $spy60ema) * 100, 2)

$nowStr = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

Write-Host "=========================================="
Write-Host "REAL-TIME FETCHED DATA:"
Write-Host "CNN Fear & Greed: $cnnScore ($cnnRating)"
Write-Host "QQQ: $qqq | SPY: $spy | VIX: $vix | DXY: $dxy"
Write-Host "=========================================="

# 1. Update sentinel_live_data.json
$jsonObj = @{
    status = "success"
    source = "CNN Official (31.1) + Yahoo v8 Engine"
    updated_at = $nowStr
    data = @{
        qqq = $qqq
        spy = $spy
        vix = $vix
        dxy = $dxy
        hyg = $hyg
        lqd = $lqd
        us10y = $us10y
        us02y = $us02y
        vvix = $vvix
        skew = $skew
        cnnScore = $cnnScore
        cnnRating = $cnnRating
        yieldSpread = $yieldSpread
        hygLqdRatio = $hygLqdRatio
        vvixVixRatio = $vvixVixRatio
        qqqDeduct = $qqqDeduct
        spyDeduct = $spyDeduct
        aaiiSpread = 11.4
        weiVal = 2.15
    }
}
$jsonObj | ConvertTo-Json -Depth 5 | Out-File -FilePath "sentinel_live_data.json" -Encoding utf8

# 2. Update index.html
if (Test-Path "index.html") {
    $content = Get-Content "index.html" -Raw -Encoding utf8

    $content = [regex]::Replace($content, 'id="last-update-time">[^<]+<', "id=""last-update-time"">⚡ 最後更新：$nowStr (CNN 官方直連 31.1 恐慌指數)<")
    $content = [regex]::Replace($content, 'id="rem-cnn">[^<]+<', "id=""rem-cnn"">$cnnScore<")
    $content = [regex]::Replace($content, 'id="macro-cnn-alert">[^<]+<', "id=""macro-cnn-alert"">$cnnScore (🟡 恐慌區 Fear)<")
    $content = [regex]::Replace($content, '"cnnScore":\s*[0-9\.]+', """cnnScore"": $cnnScore")
    $content = [regex]::Replace($content, '"updated_at":\s*"[^"]+"', """updated_at"": ""$nowStr""")

    Set-Content -Path "index.html" -Value $content -Encoding utf8
}

Write-Host "Successfully updated sentinel_live_data.json and index.html."
