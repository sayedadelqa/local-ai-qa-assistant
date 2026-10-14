# QA AI Assistant (local, Windows)

One conversational AI assistant for all your QA / test-automation work, running entirely on your PC
through your existing **Ollama** + `qwen-coder-cpu:latest`. No cloud, no API keys, no subscriptions.

## Requirements
- Windows 10, **Python 3.12** (installed and on PATH, or the `py` launcher)
- **Ollama installed** and the model **`qwen-coder-cpu:latest` already present** (check: `ollama list`).
  The app does not download or bundle Ollama or any model.
- Internet only for the one-time `pip install` of PySide6 and requests.

## Install and launch (no PowerShell needed day to day)
1. Unzip the folder anywhere (for example `C:\Tools\qa_automation_assistant`).
2. Double-click **`install.bat`** once. It creates `.venv`, installs dependencies, creates the icon and a
   **desktop shortcut "QA Automation Assistant"**.
3. From then on, double-click the desktop shortcut (or `run.bat`). The window opens immediately; the
   Ollama check runs in the background and, if Ollama is not running, starts it **hidden** (no console window).

## Using it
- Type a question; **Enter** sends, **Shift+Enter** adds a new line. Paste code, logs and stack traces freely.
- Follow-ups use the whole conversation ("convert the third test case to Playwright" works).
- Each answer has **Copy response**; each code block has its own **Copy code** button and language label.
  The newest answer also has **Regenerate** and **Continue**.
- **Stop** (or Esc) cancels a running generation. If a request fails, an error appears with **Retry**; your message is kept.
- Sidebar: New chat, search, rename, delete (also right-click), model selector, connection status.
- **Project files…** (below the input): pick a folder, tick the files to share. Only `.py .js .ts .json .yaml
  .yml .xml .feature .md .txt .ini .toml` are listed; `.git`, `node_modules`, virtual envs, build output, etc.
  are skipped; large files are limited. Files are read-only, never executed, and sent to the model as untrusted
  reference data. They attach to your next message only.
- Shortcuts: Ctrl+N new chat, Ctrl+F search, Ctrl+L focus input, Ctrl+, settings, Esc stop, Ctrl+Shift+C copy last answer.

## Settings
Server URL (local addresses only), default model, CPU-only (`num_gpu: 0`), temperature, max tokens, context
window, timeout, theme, auto-start Ollama, Test connection, Reset to defaults, Clear history.
Defaults suit a 16 GB / older-CPU machine: temperature 0.2, 1536 max tokens, 8192 context, 180 s timeout.
If replies are slow, lower the context window to 4096 in Settings.

## Context management
The system prompt is always sent in full. Recent messages are kept until the context budget
(`context window - max tokens - system prompt`) is used; older ones are dropped, the model is told they were
omitted, and the chat shows a notice. Nothing is silently summarised.

## Data and privacy
Everything is stored in `%APPDATA%\QAAutomationAssistant\` (`conversations.db`, `settings.json`, `logs\`).
Logs are rotated (1 MB x 4 files) and never contain your messages or file contents. The app only talks to your
local Ollama; the settings reject non-local server URLs. No credentials are stored.

## Ollama compatibility (0.40.4)
Only long-standing API pieces are used: `GET /api/version`, `GET /api/tags`, `POST /api/chat` (streaming) with
options `temperature`, `num_predict`, `num_ctx`, `num_gpu`. If model discovery fails, the configured model is kept
and a warning is shown. I could not test against a real Ollama 0.40.4 in my build environment; see "What was verified".

## Optional: standalone .exe
Run **`build_exe.bat`** -> `dist\QAAssistant\QAAssistant.exe` (keep the whole folder). It still uses your installed Ollama.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Banner "Ollama.exe was not found" | Install Ollama, or add it to PATH, then press **Retry / Start Ollama**. |
| Banner "Model ... was not found" | Run `ollama list`; pick an installed model in the sidebar/Settings, or re-create `qwen-coder-cpu` the way you originally did. |
| "Ollama did not respond within 45 s" | Press Retry; or run `ollama serve` once and check port 11434 is free. |
| First reply very slow | Normal on CPU while the model loads. Raise the timeout in Settings if it times out. |
| Gibberish output | Keep "CPU-only" enabled in Settings. |
| App won't start | Look at `%APPDATA%\QAAutomationAssistant\logs\assistant.log`. |
| Shortcut missing | Run `powershell -ExecutionPolicy Bypass -File create_shortcut.ps1`. |

## Developer notes
Layout: `main.py`, `ui/`, `services/` (ollama_client, model_manager, assistant, context, project_context, prompts),
`storage/database.py`, `utils/`, `tests/`.
Tests: `.venv\Scripts\python -m pip install pytest` then `.venv\Scripts\python -m pytest`
(uses a fake Ollama server; the UI smoke test runs headless).

## What was verified
See the delivery message: the core layer was tested; the GUI was not run in the build environment.
Run `pytest` after installing to execute everything on your machine.

## Installation & Setup

### Prerequisites

Before running the application, make sure you have:

- Windows 10 or later.
- Python 3.12 or a compatible version.
- [Ollama](https://ollama.com/download) installed on your computer.

### 1. Install Ollama

Download and install Ollama from the official website:

https://ollama.com/download

Ollama runs the AI model locally on your machine.

### 2. Download the AI Model

Open a terminal and run:

```bash
ollama pull qwen2.5-coder:1.5b
```

This downloads the base model required by the assistant.

**Note:** If you are using a custom Ollama model such as `qwen-coder-cpu:latest`, make sure it has been created locally before launching the application. Otherwise, update the application's model setting to a model that is already available.

### 3. Verify Ollama

Run:

```bash
ollama list
```

Make sure the model you intend to use appears in the list.

### 4. Download the Project

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/local-ai-qa-assistant.git
cd local-ai-qa-assistant
```

Alternatively, download the repository as a ZIP file from GitHub and extract it.

### 5. Install Dependencies

Run the provided installation script:

```bat
install.bat
```

This installs the application's Python dependencies. An internet connection is required for the initial installation.

### 6. Launch the Assistant

After installation, launch the application using the provided desktop shortcut or startup script.

The assistant connects to your local Ollama instance and uses the configured model.

## Privacy

Conversations are processed using the local Ollama model. No paid AI API or cloud account is required.

AI-generated test cases, code, and recommendations should be reviewed before use in real projects.