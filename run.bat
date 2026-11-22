@echo off
REM Start PhotoBooth Mailer in development mode
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py %*
