@echo off
setlocal
cd /d "%~dp0\.."

echo ==========================================================
echo   定时截屏（雷电模拟器窗口 到 images\雷电模拟器.png）
echo ==========================================================
echo   本窗口会持续运行：每 5 秒截一次「雷电模拟器」窗口。
echo   请保持雷电模拟器窗口可见、不要最小化或被遮挡。
echo   停止：在本题窗口按 Ctrl+C。
echo.
echo   重要：必须和「手动搜题.bat」或「2-开始自动搜题.bat」
echo         同时开着，截屏与搜题两个窗口一起跑才顺畅。
echo ==========================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "powershell\定时截屏.ps1" -WindowTitle "雷电模拟器" -OutputName "雷电模拟器" -IntervalSeconds 5
endlocal
