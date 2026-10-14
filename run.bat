@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo First run: setting things up...
    call install.bat
)
rem pythonw has no console window; "start" lets this script close immediately.
start "" ".venv\Scripts\pythonw.exe" "%~dp0main.py"
