@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo 找不到项目虚拟环境：.venv\Scripts\pythonw.exe
    echo 请先在 orbit 仓库中安装依赖。
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" -m orbit.app
endlocal
