@echo off
REM Start PhotoBooth Share in development mode
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py %*
