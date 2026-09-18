@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "%~dp0\.."
:: 使用的 Python 解释器。默认取 PATH 中的 python（需已安装 selenium）。
:: 若你的 Python 不在 PATH，把下面一行改成它的完整路径，例如：
:: set "PYEXE=C:\Python312\python.exe"
set "PYEXE=python"

echo ==========================================================
echo   夸克手动搜题（CLI 交互：回车搜下一题）
echo ==========================================================
echo   运行后程序常驻命令行：
echo   · 按回车              -^> 搜索当前这一题
echo   · 输入 q / quit / exit -^> 退出（浏览器默认保留）
echo   运行前请确认：
echo   1. 已用 1-登录夸克.bat 完成登录（夸克 Chrome 窗口已关闭）
echo   2. 截图程序已截下当前这题的画面
echo ==========================================================
"%PYEXE%" src\手动搜题.py %*

echo.
echo 已退出。若浏览器还开着，看完结果请手动关掉，下次才能再运行。
pause
endlocal
