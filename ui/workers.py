"""Background threads so the GUI never blocks."""
from __future__ import annotations

import logging
import threading
from typing import Callable

from PySide6.QtCore import QThread, Signal

from services.assistant import AssistantService, Prepared
from services.model_manager import ModelManager
from services.ollama_client import OllamaError

log = logging.getLogger(__name__)


class FunctionWorker(QThread):
    """Run a callable off the GUI thread and emit its result."""
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], object], parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.result.emit(self._fn())
        except Exception as e:  # noqa: BLE001
            log.exception("Background task failed")
            self.failed.emit(str(e))


class GenerationWorker(QThread):
    token = Signal(str)
    status = Signal(str)
    done = Signal(str, dict)       # full text, stats
    cancelled = Signal(str)        # partial text
    failed = Signal(str, str)      # kind, message

    def __init__(self, assistant: AssistantService, manager: ModelManager, prepared: Prepared,
                 auto_start: bool, parent=None):
        super().__init__(parent)
        self._assistant = assistant
        self._manager = manager
        self._prepared = prepared
        self._auto_start = auto_start
        self._cancel = threading.Event()
        self._client = assistant.new_client()
        self._parts: list[str] = []

    def cancel(self) -> None:
        self._cancel.set()
        self._manager.abort()
        self._client.cancel_current()

    def _on_token(self, text: str) -> None:
        self._parts.append(text)
        self.token.emit(text)

    def run(self) -> None:
        try:
            if not self._manager.is_up():
                self.status.emit("Starting Ollama in the background…")
                st = self._manager.ensure_ready(self._prepared.model, self._auto_start)
                if st.state not in ("ready", "model_missing"):
                    raise OllamaError(st.state, st.message)
            if self._cancel.is_set():
                self.cancelled.emit("")
                return
            self.status.emit("Waiting for the model (first reply can be slow on CPU)…")
            result = self._assistant.generate(self._prepared, self._client, self._cancel, self._on_token)
            if result.cancelled:
                self.cancelled.emit(result.text)
            else:
                self.done.emit(result.text, result.stats)
        except OllamaError as e:
            if self._cancel.is_set():
                self.cancelled.emit("".join(self._parts))
            else:
                self.failed.emit(e.kind, e.message)
        except Exception as e:  # noqa: BLE001
            log.exception("Unexpected generation error")
            if self._cancel.is_set():
                self.cancelled.emit("".join(self._parts))
            else:
                self.failed.emit("unexpected", f"Unexpected error: {e}")
