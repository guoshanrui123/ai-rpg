@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import flask, dotenv, websocket" >nul 2>&1
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements-demo.txt
    if errorlevel 1 goto failed
)
echo Open http://127.0.0.1:5000 in your browser.
echo Choose the default story demo to play without API keys.
".venv\Scripts\python.exe" app.py
pause
exit /b
:failed
echo Setup failed. Check Python installation and network access, then retry.
pause
exit /b 1
