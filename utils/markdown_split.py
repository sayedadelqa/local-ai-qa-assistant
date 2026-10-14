"""Split a Markdown reply into prose segments and fenced code segments."""
from __future__ import annotations

import re
from dataclasses import dataclass

FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*([^\s`]*)[^`]*$")


@dataclass
class Segment:
    kind: str  # "text" or "code"
    content: str
    lang: str = ""
    closed: bool = True


def split_markdown(text: str) -> list[Segment]:
    text = text.replace("\r\n", "\n")
    segments: list[Segment] = []
    buf: list[str] = []
    code: list[str] = []
    in_code = False
    fence = ""
    lang = ""

    def flush_text() -> None:
        body = "\n".join(buf).strip("\n")
        if body.strip():
            segments.append(Segment("text", body))
        buf.clear()

    for line in text.split("\n"):
        if not in_code:
            m = FENCE_OPEN.match(line)
            if m:
                flush_text()
                in_code = True
                fence = m.group(1)
                lang = m.group(2).lower().strip("{}.")
                code = []
            else:
                buf.append(line)
        else:
            s = line.strip()
            if s and set(s) == {fence[0]} and len(s) >= len(fence):
                segments.append(Segment("code", "\n".join(code), lang, True))
                in_code = False
            else:
                code.append(line)
    if in_code:
        segments.append(Segment("code", "\n".join(code), lang, False))
    else:
        flush_text()
    return segments
