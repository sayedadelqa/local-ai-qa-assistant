@echo off
rem Optional: package the app as a Windows executable with PyInstaller.
rem Ollama and the model are NOT bundled; the exe uses your existing Ollama installation.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call install.bat
".venv\Scripts\python.exe" -m pip install pyinstaller
if exist assets\app.ico (set "ICON=--icon assets\app.ico") else (set "ICON=")
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --windowed --name QAAssistant %ICON% main.py
echo.
echo Output: dist\QAAssistant\QAAssistant.exe  (keep the whole dist\QAAssistant folder together)
pause
