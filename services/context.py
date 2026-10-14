"""Context-window management.

Strategy (simple and transparent):
  * The system prompt is always sent intact.
  * Messages are kept newest-first until the token budget is used up.
  * Older messages that do not fit are dropped (never silently summarised).
  * If anything was dropped, a note is appended to the system prompt so the model
    does not pretend to remember it, and the UI shows a notice too.
  * The newest message is always kept; if it alone is too large it is shortened
    (head + tail) and the UI is told.
"""
from __future__ import annotations

from dataclasses import dataclass

from utils.text import shorten

CHARS_PER_TOKEN = 3.0  # conservative for code / mixed Arabic-English text
OMITTED_NOTE = (
    "\n\nNote: {n} earlier message(s) of this conversation were omitted because of the "
    "context window limit. You cannot see them; if the user refers to them, say so and ask "
    "them to repeat the relevant details."
)


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


@dataclass
class ContextResult:
    messages: list[dict]
    included: int
    dropped: int
    truncated_last: bool


def render_for_model(item: dict) -> str:
    ctx = item.get("context")
    content = item["content"]
    return f"{ctx}\n\n{content}" if ctx else content


def build_context(system_prompt: str, history: list[dict], num_ctx: int, max_tokens: int) -> ContextResult:
    budget = num_ctx - max_tokens - estimate_tokens(system_prompt) - 96
    budget = max(budget, 512)
    items = [(m["role"], render_for_model(m)) for m in history]

    kept: list[tuple[str, str]] = []
    used = 0
    truncated = False
    for role, text in reversed(items):
        cost = estimate_tokens(text)
        if not kept:
            if cost > budget:
                text = shorten(text, int(budget * CHARS_PER_TOKEN))
                cost = estimate_tokens(text)
                truncated = True
            kept.append((role, text))
            used += cost
            continue
        if used + cost > budget:
            break
        kept.append((role, text))
        used += cost
    kept.reverse()
    while len(kept) > 1 and kept[0][0] == "assistant":
        kept.pop(0)

    dropped = len(items) - len(kept)
    system = system_prompt + (OMITTED_NOTE.format(n=dropped) if dropped else "")
    messages = [{"role": "system", "content": system}]
    messages += [{"role": r, "content": t} for r, t in kept]
    return ContextResult(messages, len(kept), dropped, truncated)
