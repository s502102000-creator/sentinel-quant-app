@echo off
title 雙均線預警系統 - 即時自動更新服務器
color 0A
echo ======================================================================
echo  🚀 雙均線預警系統 - 即時自動更新伺服器 (Sentinel Quant Server)
echo  ⚡ 採用伺服器對伺服器直連，自動即時抓取 Yahoo v8 與 CNN 官方數據！
echo ======================================================================
echo.
echo 正在自動開啟瀏覽器頁面 (http://localhost:8080)...
start "" "http://localhost:8080"
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0local_backend_server.ps1"
pause
