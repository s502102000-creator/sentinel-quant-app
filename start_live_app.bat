@echo off
chcp 65001 >nul 2>&1
title Sentinel Quant 即時預警系統 - 一鍵啟動
cd /d "%~dp0"
color 0A

echo ======================================================================
echo    Sentinel Quant 雙均線預警系統 - 一鍵啟動
echo    Yahoo v8 + TradingView + CNN + FRED + AAII 全指標即時直連
echo ======================================================================
echo.

REM ── 伺服器是不是已經在跑了 ──────────────────────────────────────────
curl -s -o nul -m 2 http://localhost:8080/ >nul 2>&1
if not errorlevel 1 (
    echo [i] 偵測到伺服器已在執行，直接開啟瀏覽器。
    start "" "http://localhost:8080"
    goto DONE
)

REM ── 找 Python ────────────────────────────────────────────────────────
set "PY="
py -3 -c "pass" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "pass" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "pass" >nul 2>&1 && set "PY=python3"
if not defined PY goto NOPYTHON

echo [1/3] Python 已就緒：%PY%
echo [2/3] 啟動本機即時數據伺服器 (http://localhost:8080) ...
start "Sentinel 數據伺服器（請勿關閉）" cmd /k "%PY% local_backend_server.py"

echo [3/3] 等待伺服器就緒 ...
set /a TRIES=0
:WAIT
set /a TRIES+=1
curl -s -o nul -m 2 http://localhost:8080/ >nul 2>&1
if not errorlevel 1 goto READY
if %TRIES% GEQ 30 goto SLOW
ping -n 2 127.0.0.1 >nul
goto WAIT

:READY
echo       就緒，開啟瀏覽器 ...
start "" "http://localhost:8080"
echo.
echo ======================================================================
echo   已啟動。首次載入時右上角會顯示「數據抓取中」約 10-15 秒，
echo   之後每 5 分鐘自動更新一次（走快取，不會重複打上游 API）。
echo.
echo   頁面右側「API 診斷」面板會逐項標示：
echo     LIVE 即時  /  備援  ← 若看到「備援」表示該項上游暫時抓不到
echo.
echo   結束系統：關掉另一個「Sentinel 數據伺服器」視窗即可。
echo ======================================================================
goto DONE

:SLOW
echo.
echo [!] 等了 30 秒仍未就緒。可能原因：
echo     - 8080 埠被其他程式佔用
echo     - 防火牆阻擋（第一次執行時請選「允許存取」）
echo     - 系統沒有 curl 指令（Windows 10 1803 以前）
echo   仍然嘗試開啟瀏覽器，並請查看「Sentinel 數據伺服器」視窗的訊息。
start "" "http://localhost:8080"
goto DONE

:NOPYTHON
echo [!] 找不到 Python，無法啟動即時伺服器。
echo.
echo     請安裝 Python 3（安裝時務必勾選 "Add python.exe to PATH"）：
echo       https://www.python.org/downloads/
echo.
echo     ── 先改用離線模式 ──────────────────────────────────────────
echo     現在直接開啟 index.html，會載入內嵌的收盤快照數據。
echo     數值正確但不是即時（每天美股收盤後由 GitHub Actions 更新一次）。
echo.
start "" "index.html"

:DONE
echo.
pause
