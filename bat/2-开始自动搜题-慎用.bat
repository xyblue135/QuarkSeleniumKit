@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "%~dp0\.."
:: 使用的 Python 解释器。默认取 PATH 中的 python（需已安装 selenium）。
:: 若你的 Python 不在 PATH，把下面一行改成它的完整路径，例如：
:: set "PYEXE=C:\Python312\python.exe"
set "PYEXE=python"

echo 开始自动搜题（默认频率 8-12 秒）...
"%PYEXE%" src\自动搜题.py

echo.
pause
endlocal
