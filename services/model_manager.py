"""Ollama server readiness: detect, optionally start in the background, check the model."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from services.ollama_client import OllamaClient, OllamaError, model_available

log = logging.getLogger(__name__)

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


@dataclass
class StartupStatus:
    state: str  # ready | server_down | no_ollama | start_failed | model_missing
    message: str
    version: str | None = None
    models: list[str] = field(default_factory=list)
    warning: str = ""
    started_by_app: bool = False


def find_ollama_exe() -> str | None:
    exe = shutil.which("ollama")
    if exe:
        return exe
    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "Ollama" / "ollama.exe")
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            candidates.append(Path(base) / "Ollama" / "ollama.exe")
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


class ModelManager:
    def __init__(self, base_url: str):
        self._lock = threading.RLock()
        self._abort = threading.Event()
        self._proc: subprocess.Popen | None = None
        self.base_url = base_url.rstrip("/")
        self.client = OllamaClient(self.base_url)

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = OllamaClient(self.base_url)

    def is_up(self) -> bool:
        return self.client.version() is not None

    def abort(self) -> None:
        """Interrupt any waiting loop (used on shutdown)."""
        self._abort.set()

    def ensure_ready(self, model: str, auto_start: bool = True, wait_timeout: float = 45.0) -> StartupStatus:
        with self._lock:  # serialises callers so only one server is ever started
            self._abort.clear()
            started = False
            version = self.client.version()
            if version is None:
                if not auto_start:
                    return StartupStatus(
                        "server_down",
                        "Ollama is not running. Click “Start Ollama” to launch it in the background.",
                    )
                exe = find_ollama_exe()
                if exe is None:
                    return StartupStatus(
                        "no_ollama",
                        "Ollama.exe was not found. Install Ollama from https://ollama.com (one-time), "
                        "then click Retry. Normal chatting needs no internet afterwards.",
                    )
                try:
                    self._spawn(exe)
                except OSError as e:
                    log.exception("Failed to start Ollama")
                    return StartupStatus("start_failed", f"Ollama could not be started: {e}")
                started = True
                deadline = time.monotonic() + wait_timeout
                while time.monotonic() < deadline:
                    version = self.client.version()
                    if version:
                        break
                    if self._proc is not None and self._proc.poll() is not None:
                        code = self._proc.returncode
                        self._proc = None
                        return StartupStatus(
                            "start_failed",
                            f"Ollama exited immediately (code {code}). Another Ollama instance may be "
                            "starting or the port is in use. Wait a few seconds and press Retry.",
                        )
                    if self._abort.wait(0.5):
                        return StartupStatus("server_down", "Startup check was cancelled.")
                if not version:
                    return StartupStatus(
                        "start_failed",
                        f"Ollama did not respond within {int(wait_timeout)} seconds. Press Retry, "
                        "or start Ollama manually (run: ollama serve).",
                    )
            try:
                models = self.client.list_models()
            except OllamaError as e:
                return StartupStatus(
                    "ready", "Connected (model list unavailable).", version, [],
                    warning=f"Could not discover local models ({e.message}). "
                            f"Keeping the configured model '{model}'.",
                    started_by_app=started,
                )
            if not model_available(model, models):
                installed = ", ".join(models) if models else "none"
                return StartupStatus(
                    "model_missing",
                    f"Model '{model}' was not found in Ollama. Installed models: {installed}.\n"
                    "Fix: pick an installed model in Settings, or re-create the model the same way you "
                    f"originally did (check with: ollama list).",
                    version, models, started_by_app=started,
                )
            return StartupStatus("ready", f"Connected to Ollama {version}", version, models,
                                 started_by_app=started)

    def _spawn(self, exe: str) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return  # we already started one that is still booting
        env = os.environ.copy()
        parsed = urlparse(self.base_url)
        if parsed.hostname and parsed.port:
            env["OLLAMA_HOST"] = f"{parsed.hostname}:{parsed.port}"
        log.info("Starting Ollama in the background")
        self._proc = subprocess.Popen(
            [exe, "serve"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
            env=env,
        )

    def shutdown(self) -> None:
        """Stop Ollama only if this app started it."""
        self.abort()
        proc = self._proc
        self._proc = None
        if proc is None or proc.poll() is not None:
            return
        log.info("Stopping the Ollama process started by this app")
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=10)
            else:
                proc.terminate()
                try:
                    proc.wait(5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:  # noqa: BLE001
            log.exception("Error while stopping Ollama")
