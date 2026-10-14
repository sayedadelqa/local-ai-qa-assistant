@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  QA AI Assistant - one-time setup
echo ============================================

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3.12"
) else (
    set "PY=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo.
        echo Could not create the virtual environment. Check that Python 3.12 is installed
        echo and on PATH, then run install.bat again.
        pause
        exit /b 1
    )
)

echo Installing dependencies (needs internet this one time)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Dependency installation failed. See the messages above.
    pause
    exit /b 1
)

echo Creating the app icon...
".venv\Scripts\python.exe" make_icon.py

echo Creating the desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"

echo.
echo Done. Use the "QA AI Assistant" shortcut on your desktop (or run.bat).
pause
