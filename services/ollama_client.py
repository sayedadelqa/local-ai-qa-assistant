"""Minimal client for the local Ollama HTTP API.

Only long-stable endpoints/parameters are used, so it is safe for old Ollama builds:
  GET  /api/version
  GET  /api/tags
  POST /api/chat   (stream=true, options: temperature, num_predict, num_ctx, num_gpu)
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Iterator

import requests

log = logging.getLogger(__name__)


class OllamaError(Exception):
    """kind: connection | timeout | http | model_missing | malformed |
    server_down | no_ollama | start_failed | unexpected"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass
class ChatChunk:
    text: str = ""
    done: bool = False
    stats: dict = field(default_factory=dict)


def normalize_model(name: str) -> str:
    name = name.strip()
    return name if ":" in name else name + ":latest"


def model_available(model: str, models: list[str]) -> bool:
    return normalize_model(model) in {normalize_model(m) for m in models}


class OllamaClient:
    def __init__(self, base_url: str, timeout_s: float = 180):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._session = requests.Session()
        self._session.trust_env = False  # never route loopback calls through a proxy
        self._lock = threading.Lock()
        self._resp: requests.Response | None = None

    def _url(self, path: str) -> str:
        return self.base_url + path

    def version(self, timeout: float = 3.0) -> str | None:
        try:
            r = self._session.get(self._url("/api/version"), timeout=timeout)
            if r.status_code != 200:
                return None
            data = r.json()
            v = data.get("version") if isinstance(data, dict) else None
            return str(v) if v else None
        except (requests.RequestException, ValueError):
            return None

    def list_models(self, timeout: float = 5.0) -> list[str]:
        try:
            r = self._session.get(self._url("/api/tags"), timeout=timeout)
        except requests.RequestException as e:
            raise OllamaError("connection", f"Could not list models: {e}") from e
        if r.status_code != 200:
            raise OllamaError("http", f"Model list request failed (HTTP {r.status_code}).")
        try:
            data = r.json()
        except ValueError as e:
            raise OllamaError("malformed", "Ollama returned an unreadable model list.") from e
        if not isinstance(data, dict):
            raise OllamaError("malformed", "Ollama returned an unexpected model list.")
        return sorted({m["name"] for m in data.get("models", []) if isinstance(m, dict) and m.get("name")})

    def cancel_current(self) -> None:
        with self._lock:
            resp = self._resp
        if resp is not None:
            try:
                resp.close()
            except Exception:  # noqa: BLE001 - closing is best effort
                pass

    def chat_stream(self, model: str, messages: list[dict], options: dict,
                    cancel: threading.Event) -> Iterator[ChatChunk]:
        payload = {"model": model, "messages": messages, "stream": True, "options": options}
        try:
            resp = self._session.post(
                self._url("/api/chat"), json=payload, stream=True, timeout=(5, self.timeout_s)
            )
        except requests.ConnectTimeout as e:
            raise OllamaError("connection", f"Timed out connecting to Ollama at {self.base_url}.") from e
        except requests.ReadTimeout as e:
            raise OllamaError("timeout", self._timeout_msg()) from e
        except requests.ConnectionError as e:
            raise OllamaError("connection", f"Cannot reach Ollama at {self.base_url}.") from e
        except requests.RequestException as e:
            raise OllamaError("http", f"Request to Ollama failed: {e}") from e

        with self._lock:
            self._resp = resp
        try:
            if cancel.is_set():
                return
            if resp.status_code != 200:
                detail = self._error_detail(resp)
                if resp.status_code == 404 or "not found" in detail.lower():
                    raise OllamaError("model_missing", f"Model '{model}' was not found. {detail}".strip())
                raise OllamaError("http", f"Ollama returned HTTP {resp.status_code}. {detail}".strip())

            seen_done = False
            try:
                for line in resp.iter_lines():
                    if cancel.is_set():
                        return
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError as e:
                        raise OllamaError("malformed", "Ollama sent a response that could not be parsed.") from e
                    if not isinstance(obj, dict):
                        raise OllamaError("malformed", "Ollama sent an unexpected response.")
                    if "error" in obj:
                        err = str(obj["error"])
                        kind = "model_missing" if "not found" in err.lower() else "http"
                        raise OllamaError(kind, err)
                    msg = obj.get("message") or {}
                    text = msg.get("content", "") if isinstance(msg, dict) else ""
                    done = bool(obj.get("done"))
                    stats = {}
                    if done:
                        seen_done = True
                        stats = {k: obj.get(k) for k in
                                 ("eval_count", "eval_duration", "total_duration", "prompt_eval_count")}
                    yield ChatChunk(text=text, done=done, stats=stats)
            except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError,
                    requests.exceptions.ReadTimeout) as e:
                if cancel.is_set():
                    return
                if "timed out" in str(e).lower() or isinstance(e, requests.exceptions.ReadTimeout):
                    raise OllamaError("timeout", self._timeout_msg()) from e
                raise OllamaError("connection", "The connection to Ollama was lost during generation.") from e
            if not seen_done and not cancel.is_set():
                raise OllamaError("malformed", "The response from Ollama ended unexpectedly.")
        finally:
            with self._lock:
                self._resp = None
            try:
                resp.close()
            except Exception:  # noqa: BLE001
                pass

    def _timeout_msg(self) -> str:
        return (f"The model did not respond within {int(self.timeout_s)} seconds. "
                "On a slow CPU the first reply can take long; increase the timeout in Settings.")

    @staticmethod
    def _error_detail(resp: requests.Response) -> str:
        try:
            data = resp.json()
            if isinstance(data, dict) and data.get("error"):
                return str(data["error"])
        except ValueError:
            pass
        return ""
