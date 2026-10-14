"""Small text helpers."""
from __future__ import annotations

import re
from datetime import datetime, timezone

DEFAULT_TITLE = "New chat"


def make_title(prompt: str, limit: int = 48) -> str:
    for line in prompt.splitlines():
        line = re.sub(r"[`*_#>]+", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"
    return DEFAULT_TITLE


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def format_ts(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso).astimezone()
    except ValueError:
        return ""
    if dt.date() == datetime.now().astimezone().date():
        return dt.strftime("%H:%M")
    return dt.strftime("%b %d, %H:%M")


def shorten(text: str, limit: int) -> str:
    """Shorten text to ~limit chars keeping the head (60%) and the tail (40%)."""
    if len(text) <= limit:
        return text
    marker = "\n[... truncated to fit the context window ...]\n"
    keep = max(limit - len(marker), 0)
    head = int(keep * 0.6)
    tail = keep - head
    return text[:head] + marker + (text[-tail:] if tail else "")
