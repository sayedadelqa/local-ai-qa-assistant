import threading

import pytest

from services.context import build_context
from services.model_manager import ModelManager
from services.ollama_client import OllamaClient, OllamaError, model_available
from services.project_context import ProjectSelection, read_selected, scan_folder
from storage.database import Database
from tests.fake_ollama import FakeOllama
from utils.config import Settings, load_settings, save_settings, validate
from utils.markdown_split import split_markdown
from utils.text import make_title, shorten


@pytest.fixture()
def fake():
    f = FakeOllama().start()
    yield f
    f.stop()


# ---- config -----------------------------------------------------------
def test_defaults_valid_and_roundtrip(tmp_path):
    s = Settings()
    assert validate(s) == []
    assert s.model == "qwen-coder-cpu:latest" and s.cpu_only
    p = tmp_path / "s.json"
    s.temperature = 0.5
    save_settings(s, p)
    assert load_settings(p).temperature == 0.5


def test_validation_blocks_remote_urls_and_bad_values():
    assert validate(Settings(base_url="http://example.com:11434"))
    assert validate(Settings(base_url="localhost"))
    assert validate(Settings(temperature=5))
    assert validate(Settings(max_tokens=9000))
    assert validate(Settings(max_tokens=2048, num_ctx=1024))
    assert validate(Settings(base_url="http://localhost:11434")) == []


def test_corrupt_settings_fall_back(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not json")
    assert load_settings(p) == Settings()


# ---- database ---------------------------------------------------------
def test_database_persistence_and_search(tmp_path):
    path = tmp_path / "t.db"
    db = Database(path)
    c = db.create_conversation("Login tests")
    db.add_message(c.id, "user", "write negative cases", context="CTX", attachments=["a.py"])
    db.add_message(c.id, "assistant", "ok 100% done")
    db.close()
    db = Database(path)  # reopened = persistence
    assert [x.title for x in db.list_conversations()] == ["Login tests"]
    msgs = db.get_messages(c.id)
    assert msgs[0].context == "CTX" and msgs[0].attachments == ["a.py"]
    assert db.list_conversations("100%") and not db.list_conversations("zzz")
    db.rename_conversation(c.id, "Renamed")
    assert db.get_conversation(c.id).title == "Renamed"
    db.delete_messages_from(c.id, msgs[1].id)
    assert len(db.get_messages(c.id)) == 1
    db.delete_conversation(c.id)
    assert db.list_conversations() == [] and db.get_messages(c.id) == []


# ---- context ----------------------------------------------------------
def test_context_keeps_recent_and_reports_dropped():
    hist = [{"role": "user" if i % 2 == 0 else "assistant", "content": "x" * 3000} for i in range(10)]
    hist.append({"role": "user", "content": "latest question"})
    r = build_context("SYS", hist, num_ctx=4096, max_tokens=512)
    assert r.messages[0]["role"] == "system" and r.messages[0]["content"].startswith("SYS")
    assert r.messages[-1]["content"] == "latest question"
    assert r.dropped > 0 and "omitted" in r.messages[0]["content"]
    assert r.messages[1]["role"] == "user"


def test_context_no_drop_and_truncates_huge_last():
    r = build_context("SYS", [{"role": "user", "content": "hi"}], 8192, 1024)
    assert r.dropped == 0 and "omitted" not in r.messages[0]["content"]
    r = build_context("SYS", [{"role": "user", "content": "y" * 100000}], 4096, 512)
    assert r.truncated_last and len(r.messages[-1]["content"]) < 100000


def test_title_and_shorten():
    assert make_title("```\n\n  Write five   negative test cases for SauceDemo login and more words here") .startswith("Write five negative")
    assert make_title("   ") == "New chat"
    assert len(shorten("a" * 1000, 200)) <= 200


# ---- markdown ---------------------------------------------------------
def test_markdown_split():
    segs = split_markdown("Intro\n\n```python\nprint(1)\n```\nOutro\n```json\n{\"a\": 1}")
    kinds = [(s.kind, s.lang, s.closed) for s in segs]
    assert kinds == [("text", "", True), ("code", "python", True), ("text", "", True), ("code", "json", False)]
    assert segs[1].content == "print(1)"


# ---- client / manager ---------------------------------------------------
def test_client_streams_and_sends_options(fake):
    c = OllamaClient(fake.url, 10)
    assert c.version() == "0.40.4"
    assert c.list_models() == ["qwen-coder-cpu:latest"]
    chunks = list(c.chat_stream("qwen-coder-cpu:latest", [{"role": "user", "content": "hi"}],
                                {"num_gpu": 0}, threading.Event()))
    assert chunks[-1].done and "".join(x.text for x in chunks).startswith("Here are five")
    assert fake.requests[0]["options"]["num_gpu"] == 0


def test_client_errors(fake):
    c = OllamaClient(fake.url, 10)
    with pytest.raises(OllamaError) as e:
        list(c.chat_stream("nope:latest", [], {}, threading.Event()))
    assert e.value.kind == "model_missing"
    dead = OllamaClient("http://127.0.0.1:9", 2)
    assert dead.version() is None
    with pytest.raises(OllamaError) as e:
        list(dead.chat_stream("m", [], {}, threading.Event()))
    assert e.value.kind == "connection"


def test_client_cancel(fake):
    fake.token_delay = 0.05
    c = OllamaClient(fake.url, 10)
    cancel = threading.Event()
    got = []
    for ch in c.chat_stream("qwen-coder-cpu:latest", [{"role": "user", "content": "x"}], {}, cancel):
        got.append(ch)
        if len(got) == 2:
            cancel.set()
            c.cancel_current()
    assert not got[-1].done  # stopped early, no error raised


def test_model_manager_states(fake):
    mm = ModelManager(fake.url)
    assert mm.ensure_ready("qwen-coder-cpu").state == "ready"  # ':latest' optional
    st = mm.ensure_ready("other-model:1b")
    assert st.state == "model_missing" and "qwen-coder-cpu:latest" in st.message
    down = ModelManager("http://127.0.0.1:9")
    assert down.ensure_ready("m", auto_start=False).state == "server_down"
    assert model_available("a", ["a:latest"])
    mm.shutdown()  # must not touch a server we did not start
    assert fake.server  # still alive


# ---- project context --------------------------------------------------
def test_project_scan_and_read(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / ".venv").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("assert True")
    (tmp_path / "node_modules" / "x.js").write_text("bad")
    (tmp_path / ".venv" / "y.py").write_text("bad")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    (tmp_path / "big.txt").write_text("z" * 300_000)
    files = scan_folder(str(tmp_path))
    rels = {f.rel for f in files}
    assert rels == {"tests/test_a.py", "big.txt"}
    sel = ProjectSelection(str(tmp_path), files)
    ctx = read_selected(sel)
    assert ctx.included == ["tests/test_a.py"]
    assert "untrusted" in ctx.text and any("too large" in n for n in ctx.notes)
