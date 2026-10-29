@echo off
setlocal
cd /d "%~dp0\.."

echo ==========================================================
echo   定时截屏（雷电模拟器窗口 到 images\雷电模拟器.png）
echo ==========================================================
echo   本窗口会持续运行：每 5 秒截一次「雷电模拟器」窗口。
echo   请保持雷电模拟器窗口可见、不要最小化或被遮挡。
echo   停止：在本窗口按 Ctrl+C。
echo.
echo   用法：本窗口常开。在模拟器里换题后，回到「手动搜题.bat」的窗口
echo         按回车，它就会读这张最新的截图。
echo   注意：本窗口只截屏、不上传，不碰夸克，不会引发风控；
echo         真正上传的只有「手动搜题.bat」，按一次回车才传一次。
echo ==========================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "powershell\定时截屏.ps1" -WindowTitle "雷电模拟器" -OutputName "雷电模拟器" -IntervalSeconds 5
if errorlevel 1 (
    echo.
    echo [出错了] 上面就是报错原因，别关窗口先看一眼。按任意键退出...
    pause >nul
)
endlocal
