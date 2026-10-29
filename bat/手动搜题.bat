@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "%~dp0\.."
:: 使用的 Python 解释器。默认取 PATH 中的 python（需已安装 selenium）。
:: 若你的 Python 不在 PATH，把下面一行改成它的完整路径，例如：
:: set "PYEXE=C:\Python312\python.exe"
set "PYEXE=python"

"%PYEXE%" --version >nul 2>nul
if errorlevel 1 (
    echo.
    echo [错误] 没找到 Python 命令。
    echo        请安装 Python 3.9+，或者把本文件里的 set "PYEXE=python"
    echo        改成 python.exe 的完整路径，例如：
    echo        set "PYEXE=D:\Python312\python.exe"
    echo.
    pause
    exit /b 1
)

echo ==========================================================
echo   夸克手动搜题（CLI 交互：回车搜下一题）
echo ==========================================================
echo   运行后程序常驻命令行：
echo   · 按回车              -^> 搜索当前这一题
echo   · 输入 q / quit / exit -^> 退出（浏览器默认保留）
echo   运行前请确认：
echo   1. 已用 1-登录夸克.bat 完成登录（夸克 Chrome 窗口已关闭）
echo   2. 截屏窗口（A-开始定时截屏.bat）已开着并截下当前这题
echo   频率提醒：两题之间至少隔 8 秒，别连按回车，连点容易触发风控。
echo ==========================================================
"%PYEXE%" src\手动搜题.py %*
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" echo [退出码 %RC%] 程序异常结束，请把上面的报错复制出来看。
echo 已退出。若浏览器还开着，看完结果请手动关掉，下次才能再运行。
pause
endlocal
