@echo off
REM Build dist\PhotoBoothShare.exe (one file, no console window).
REM Run from a terminal where Python is available (the conda env, or the .venv folder).
setlocal
cd /d "%~dp0"

set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

echo === 1/4  Installing what the build needs
%PY% -m pip install --disable-pip-version-check -q -r requirements.txt "pyinstaller>=6.10" || goto :error

echo === 2/4  Getting the online-link tool (cloudflared.exe)
if not exist "vendor" mkdir vendor
if not exist "vendor\cloudflared.exe" (
    curl -L --fail -o "vendor\cloudflared.exe" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    if errorlevel 1 (
        echo     Could not download it. The app will download it itself the first time it goes online.
        if exist "vendor\cloudflared.exe" del "vendor\cloudflared.exe"
    )
)
set EXTRA=
if exist "vendor\cloudflared.exe" set EXTRA=--add-binary "vendor\cloudflared.exe;."

echo === 3/4  Building
REM Conda keeps the Tcl/Tk DLLs (needed for the app window) in Library\bin, where PyInstaller doesn't
REM look by itself. Without this the .exe fails with "DLL load failed while importing _tkinter".
for /f "delims=" %%P in ('%PY% -c "import sys; print(sys.base_prefix)"') do set PYBASE=%%P
if exist "%PYBASE%\Library\bin\tk86t.dll" set "PATH=%PYBASE%\Library\bin;%PATH%"
if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\Library\bin\tk86t.dll" set "PATH=%CONDA_PREFIX%\Library\bin;%PATH%"
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name PhotoBoothShare ^
    --icon assets\app.ico ^
    --add-data "assets;assets" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --collect-data customtkinter ^
    --collect-submodules uvicorn ^
    %EXTRA% ^
    main.py || goto :error

echo === 4/4  Saving a copy of this version
for /f "delims=" %%V in ('%PY% -c "import config; print(config.APP_VERSION)"') do set VERSION=%%V
if not exist "releases" mkdir releases
copy /y "dist\PhotoBoothShare.exe" "releases\PhotoBoothShare-%VERSION%.exe" >nul || goto :error
REM PyInstaller's scratch files are not needed once the .exe exists.
if exist "build" rmdir /s /q "build"
if exist "PhotoBoothShare.spec" del /q "PhotoBoothShare.spec"
echo.
echo     dist\PhotoBoothShare.exe is ready (version %VERSION%). Copy it to the event laptop and double-click it.
echo     A copy is kept as releases\PhotoBoothShare-%VERSION%.exe
echo     Its settings and database are saved next to it.
echo.
exit /b 0

:error
echo.
echo Build failed. Scroll up to see what went wrong.
exit /b 1
