"""Conversation orchestration: builds model requests from stored history and streams replies."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable

from services.context import ContextResult, build_context
from services.ollama_client import OllamaClient, OllamaError
from services.prompts import SYSTEM_PROMPT
from storage.database import Database
from utils.config import Settings

log = logging.getLogger(__name__)


@dataclass
class Prepared:
    model: str
    messages: list[dict]
    options: dict
    dropped: int
    truncated: bool


@dataclass
class GenerationResult:
    text: str
    cancelled: bool
    stats: dict = field(default_factory=dict)


class AssistantService:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings

    def options(self) -> dict:
        s = self.settings
        opts = {"temperature": s.temperature, "num_predict": s.max_tokens, "num_ctx": s.num_ctx}
        if s.cpu_only:
            opts["num_gpu"] = 0  # long-standing option; forces CPU inference
        return opts

    def new_client(self) -> OllamaClient:
        return OllamaClient(self.settings.base_url, self.settings.timeout_s)

    def prepare(self, conversation_id: int) -> Prepared:
        msgs = self.db.get_messages(conversation_id)
        history = [{"role": m.role, "content": m.content, "context": m.context} for m in msgs]
        ctx: ContextResult = build_context(SYSTEM_PROMPT, history, self.settings.num_ctx,
                                           self.settings.max_tokens)
        log.info("Prepared request: %d messages, %d dropped", ctx.included, ctx.dropped)
        return Prepared(self.settings.model, ctx.messages, self.options(), ctx.dropped, ctx.truncated_last)

    def generate(self, prepared: Prepared, client: OllamaClient, cancel: threading.Event,
                 on_token: Callable[[str], None]) -> GenerationResult:
        parts: list[str] = []
        stats: dict = {}
        for chunk in client.chat_stream(prepared.model, prepared.messages, prepared.options, cancel):
            if chunk.text:
                parts.append(chunk.text)
                on_token(chunk.text)
            if chunk.done:
                stats = chunk.stats
        text = "".join(parts)
        if not text.strip() and not cancel.is_set():
            raise OllamaError("malformed", "The model returned an empty response. Try again.")
        return GenerationResult(text, cancel.is_set(), stats)
