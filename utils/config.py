"""Application settings: defaults, validation, and JSON persistence."""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger(__name__)

APP_NAME = "QA AI Assistant"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen-coder-cpu:latest"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def data_dir() -> Path:
    """Folder for settings, database and logs (all local)."""
    override = os.environ.get("QA_ASSISTANT_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        base = Path(appdata) / APP_NAME
    else:
        base = Path.home() / ".local" / "share" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass
class Settings:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    cpu_only: bool = True
    temperature: float = 0.2
    max_tokens: int = 1536
    num_ctx: int = 8192
    timeout_s: int = 180
    theme: str = "dark"
    auto_start_ollama: bool = True

    def normalized(self) -> "Settings":
        data = asdict(self)
        data["base_url"] = self.base_url.strip().rstrip("/")
        data["model"] = self.model.strip()
        return Settings(**data)


def validate(s: Settings) -> list[str]:
    """Return a list of human-readable problems (empty list = valid)."""
    errors: list[str] = []
    url = urlparse(s.base_url.strip())
    if url.scheme not in ("http", "https") or not url.hostname:
        errors.append("Ollama server URL must look like http://127.0.0.1:11434")
    elif url.hostname.lower() not in LOOPBACK_HOSTS:
        errors.append(
            "For privacy, only a local Ollama server (127.0.0.1 or localhost) is allowed."
        )
    if not s.model.strip():
        errors.append("Model name must not be empty.")
    if not 0.0 <= s.temperature <= 2.0:
        errors.append("Temperature must be between 0.0 and 2.0.")
    if not 64 <= s.max_tokens <= 8192:
        errors.append("Maximum generated tokens must be between 64 and 8192.")
    if not 1024 <= s.num_ctx <= 32768:
        errors.append("Context window must be between 1024 and 32768 tokens.")
    if s.max_tokens >= s.num_ctx:
        errors.append("Maximum generated tokens must be smaller than the context window.")
    if not 10 <= s.timeout_s <= 1800:
        errors.append("Request timeout must be between 10 and 1800 seconds.")
    if s.theme not in ("dark", "light"):
        errors.append("Theme must be 'dark' or 'light'.")
    return errors


def settings_path() -> Path:
    return data_dir() / "settings.json"


def load_settings(path: Path | None = None) -> Settings:
    path = path or settings_path()
    s = Settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return s
    except (OSError, ValueError):
        log.warning("Could not read settings file; using defaults.")
        return s
    if not isinstance(raw, dict):
        return s
    for f in fields(Settings):
        if f.name not in raw:
            continue
        default = getattr(s, f.name)
        val = raw[f.name]
        try:
            if isinstance(default, bool):
                if not isinstance(val, bool):
                    raise ValueError
            elif isinstance(default, int):
                val = int(val)
            elif isinstance(default, float):
                val = float(val)
            else:
                val = str(val)
        except (TypeError, ValueError):
            continue
        setattr(s, f.name, val)
    s = s.normalized()
    if validate(s):
        log.warning("Stored settings were invalid; using defaults.")
        return Settings()
    return s


def save_settings(s: Settings, path: Path | None = None) -> None:
    path = path or settings_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(s.normalized()), indent=2), encoding="utf-8")
    os.replace(tmp, path)
