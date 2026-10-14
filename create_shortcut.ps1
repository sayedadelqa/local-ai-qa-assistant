# Creates a desktop shortcut that starts the app with pythonw.exe (no console window).
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
$main = Join-Path $root "main.py"
$icon = Join-Path $root "assets\app.ico"

if (-not (Test-Path $pythonw)) {
    Write-Host "Virtual environment not found. Run install.bat first."
    exit 1
}

$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "QA AI Assistant.lnk"
$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($lnk)
$sc.TargetPath = $pythonw
$sc.Arguments = "`"$main`""
$sc.WorkingDirectory = $root
$sc.Description = "Local QA AI Assistant (Ollama)"
if (Test-Path $icon) { $sc.IconLocation = $icon }
$sc.Save()
Write-Host "Shortcut created: $lnk"
