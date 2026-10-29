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

echo 正在打开夸克登录页面...
echo （在弹出的 Chrome 里登录夸克，登录完直接关掉这个 Chrome 窗口）
"%PYEXE%" src\登录.py %*
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" echo [退出码 %RC%] 登录程序异常结束，请看上面的报错。
pause
endlocal
