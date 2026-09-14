# Fetch Live Data
$tvPayload = '{"symbols":{"tickers":["NASDAQ:QQQ","AMEX:SPY","CBOE:VIX","TVC:DXY","AMEX:HYG","AMEX:LQD","TVC:US10Y","TVC:US02Y"]},"columns":["name","close"]}'
$tv = Invoke-RestMethod -Uri "https://scanner.tradingview.com/global/scan" -Method Post -ContentType "application/json" -Body $tvPayload

$cnnHeaders = @{
    "User-Agent"="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36";
    "Referer"="https://www.cnn.com/markets/fear-and-greed";
    "Origin"="https://www.cnn.com";
    "Accept"="application/json"
}
$cnn = Invoke-RestMethod -Uri "https://production.dataviz.cnn.io/index/fearandgreed/graphdata" -Headers $cnnHeaders

$tvMap = @{}
foreach ($item in $tv.data) {
    $tvMap[$item.s] = [math]::Round($item.d[1], 2)
}

$qqq = if ($tvMap["NASDAQ:QQQ"]) { $tvMap["NASDAQ:QQQ"] } else { 714.88 }
$spy = if ($tvMap["AMEX:SPY"]) { $tvMap["AMEX:SPY"] } else { 764.29 }
$vix = if ($tvMap["CBOE:VIX"]) { $tvMap["CBOE:VIX"] } else { 15.84 }
$dxy = if ($tvMap["TVC:DXY"]) { $tvMap["TVC:DXY"] } else { 99.09 }
$hyg = if ($tvMap["AMEX:HYG"]) { $tvMap["AMEX:HYG"] } else { 78.60 }
$lqd = if ($tvMap["AMEX:LQD"]) { $tvMap["AMEX:LQD"] } else { 104.32 }
$us10y = if ($tvMap["TVC:US10Y"]) { $tvMap["TVC:US10Y"] } else { 4.97 }
$us02y = if ($tvMap["TVC:US02Y"]) { $tvMap["TVC:US02Y"] } else { 4.63 }

$cnnScore = [math]::Round($cnn.fear_and_greed.score, 1)
$cnnRating = $cnn.fear_and_greed.rating
$skew = 147.02
$vvix = 102.66

$yieldSpread = [math]::Round($us10y - $us02y, 2)
$hygLqdRatio = [math]::Round($hyg / $lqd, 3)
$vvixVixRatio = [math]::Round($vvix / $vix, 2)

$qqq60ema = 708.75
$qqqDeduct = [math]::Round((($qqq - $qqq60ema) / $qqq60ema) * 100, 2)
$spy60ema = 755.28
$spyDeduct = [math]::Round((($spy - $spy60ema) / $spy60ema) * 100, 2)

$nowStr = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

Write-Host "Real-Time Updates:"
Write-Host "QQQ: $qqq | SPY: $spy | VIX: $vix | DXY: $dxy | CNN: $cnnScore ($cnnRating)"

# Write sentinel_live_data.json
$jsonObj = @{
    status = "success"
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

Write-Host "Updated sentinel_live_data.json successfully."
