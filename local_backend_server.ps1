# Native PowerShell HTTP Server for Sentinel Quant App
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:8080/")

try {
    $listener.Start()
    Write-Host "=================================================="
    Write-Host "🚀 Sentinel Quant Backend Server Running on http://localhost:8080/"
    Write-Host "=================================================="
} catch {
    Write-Host "Error starting HttpListener: $_"
    exit 1
}

while ($listener.IsListening) {
    try {
        $context = $listener.GetContext()
        $request = $context.Request
        $response = $context.Response

        $urlPath = $request.Url.AbsolutePath
        
        # Add CORS Headers
        $response.Headers.Add("Access-Control-Allow-Origin", "*")
        $response.Headers.Add("Access-Control-Allow-Headers", "Content-Type")

        if ($urlPath -eq "/api/indicators" -or $urlPath -eq "/.netlify/functions/indicators") {
            # Execute live fetcher update
            & powershell -ExecutionPolicy Bypass -File update_all_live_now.ps1 | Out-Null
            
            $jsonContent = [System.IO.File]::ReadAllText("$PSScriptRoot\sentinel_live_data.json", [System.Text.Encoding]::UTF8)
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($jsonContent)
            $response.ContentType = "application/json; charset=utf-8"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        else {
            $fileName = $urlPath.TrimStart('/')
            if ([string]::IsNullOrWhiteSpace($fileName)) {
                $fileName = "index.html"
            }
            $filePath = Join-Path $PSScriptRoot $fileName

            if (Test-Path $filePath -PathType Leaf) {
                if ($fileName.EndsWith(".html")) {
                    $response.ContentType = "text/html; charset=utf-8"
                } elseif ($fileName.EndsWith(".json")) {
                    $response.ContentType = "application/json; charset=utf-8"
                } elseif ($fileName.EndsWith(".jpg") -or $fileName.EndsWith(".jpeg")) {
                    $response.ContentType = "image/jpeg"
                } elseif ($fileName.EndsWith(".js")) {
                    $response.ContentType = "application/javascript"
                } elseif ($fileName.EndsWith(".css")) {
                    $response.ContentType = "text/css"
                }

                $bytes = [System.IO.File]::ReadAllBytes($filePath)
                $response.ContentLength64 = $bytes.Length
                $response.OutputStream.Write($bytes, 0, $bytes.Length)
            } else {
                $response.StatusCode = 404
            }
        }
        $response.Close()
    } catch {
        Write-Host "Request handling notice: $_"
    }
}
