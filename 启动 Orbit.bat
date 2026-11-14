@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Orbit virtual environment was not found.
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" -m orbit.app
endlocal
