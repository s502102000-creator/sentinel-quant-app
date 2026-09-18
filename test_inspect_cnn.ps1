$rawCnn = curl.exe -k --ssl-no-revoke -s -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" -H "Referer: https://www.cnn.com/markets/fear-and-greed" -H "Origin: https://www.cnn.com" "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
$cnnObj = $rawCnn | ConvertFrom-Json
$cnnObj.fear_and_greed | ConvertTo-Json -Depth 5 | Out-File -FilePath "cnn_dump.json" -Encoding utf8
Write-Host "CNN Dumped."
