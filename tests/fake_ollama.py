"""A tiny fake Ollama server for tests (no real model needed)."""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPLY_TESTCASES = (
    "Here are five negative test cases:\n\n"
    "1. TC-001 Empty username\n2. TC-002 Empty password\n3. TC-003 Locked-out user\n"
    "4. TC-004 Wrong password\n5. TC-005 SQL injection in username\n"
)
REPLY_CODE = (
    "Here is the Playwright test:\n\n```python\n"
    "def test_locked_out(page):\n    page.goto('https://www.saucedemo.com')\n"
    "    page.fill('#user-name', 'locked_out_user')\n```\n\nDone."
)


class FakeOllama:
    def __init__(self, models=("qwen-coder-cpu:latest",), token_delay=0.0):
        self.models = list(models)
        self.token_delay = token_delay
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def _json(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/version":
                    self._json(200, {"version": "0.40.4"})
                elif self.path == "/api/tags":
                    self._json(200, {"models": [{"name": m} for m in outer.models]})
                else:
                    self._json(404, {"error": "nope"})

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(n))
                outer.requests.append(req)
                if req["model"] not in outer.models:
                    return self._json(404, {"error": f"model '{req['model']}' not found"})
                last = req["messages"][-1]["content"]
                reply = REPLY_CODE if "Playwright" in last else REPLY_TESTCASES
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                try:
                    words = reply.split(" ")
                    for i, w in enumerate(words):
                        tok = w + ("" if i == len(words) - 1 else " ")
                        line = {"model": req["model"], "message": {"role": "assistant", "content": tok}, "done": False}
                        self.wfile.write((json.dumps(line) + "\n").encode())
                        self.wfile.flush()
                        if outer.token_delay:
                            time.sleep(outer.token_delay)
                    done = {"model": req["model"], "message": {"role": "assistant", "content": ""},
                            "done": True, "eval_count": len(words), "eval_duration": 1_000_000_000}
                    self.wfile.write((json.dumps(done) + "\n").encode())
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
