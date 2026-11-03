@echo off
rem Double-click to open Quote Studio in your browser. Close this window to stop it.
cd /d "%~dp0"
python quote-calculator\app.py
if errorlevel 1 (
  echo.
  echo Quote Studio could not start. Check that Python is installed, then try again.
  pause
)
