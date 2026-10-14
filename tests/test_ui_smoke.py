"""Headless end-to-end smoke test: real MainWindow + fake Ollama server.

Run with:  pytest tests/test_ui_smoke.py   (needs PySide6; skipped otherwise)
"""
import os
import time

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from services.model_manager import ModelManager  # noqa: E402
from storage.database import Database  # noqa: E402
from tests.fake_ollama import FakeOllama  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from utils.config import Settings  # noqa: E402


def wait_for(cond, timeout=15.0):
    app = QApplication.instance()
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_ASSISTANT_HOME", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    fake = FakeOllama().start()
    settings = Settings(base_url=fake.url)
    db = Database(tmp_path / "t.db")
    yield app, fake, settings, db, tmp_path
    fake.stop()


def make_window(settings, db):
    return MainWindow(settings, db, ModelManager(settings.base_url))


def test_chat_flow_copy_and_persistence(env):
    app, fake, settings, db, tmp = env
    w = make_window(settings, db)
    w.show()
    assert wait_for(lambda: w.status is not None and w.status.state == "ready")

    w.send_message("Write five negative test cases for SauceDemo login.")
    assert wait_for(lambda: w.worker is None and len(db.get_messages(w.current_conv_id)) == 2)
    w.send_message("Convert the third test case into a Playwright test using Python.")
    assert wait_for(lambda: w.worker is None and len(db.get_messages(w.current_conv_id)) == 4)

    # follow-up carried the earlier turns to the model (conversation memory)
    sent = fake.requests[-1]["messages"]
    assert sent[0]["role"] == "system"
    assert any("TC-003" in m["content"] for m in sent)
    assert fake.requests[-1]["options"]["num_gpu"] == 0

    # code block rendered with copy button, clipboard really receives the code
    last = [b for b in w.chat.bubbles() if b.role == "assistant"][-1]
    blocks = last.code_blocks()
    assert len(blocks) == 1 and blocks[0].lang_label.text() == "python"
    blocks[0].copy_btn.click()
    assert "def test_locked_out" in QApplication.clipboard().text()
    last.copy_btn.click()
    assert QApplication.clipboard().text() == last.text()

    # new chat keeps the old conversation; reopening the app shows it again
    w.new_chat()
    assert len(db.list_conversations()) == 1
    w.close()
    db2 = Database(tmp / "t.db")
    w2 = make_window(settings, db2)
    assert w2.sidebar.list.count() == 1
    w2.open_conversation(w2.sidebar.current_id() or db2.list_conversations()[0].id)
    assert len(w2.chat.bubbles()) == 4
    w2.close()


def test_model_missing_shows_banner_and_error_has_retry(env):
    app, fake, settings, db, _ = env
    settings.model = "does-not-exist:latest"
    w = make_window(settings, db)
    w.show()
    assert wait_for(lambda: w.status is not None)
    assert w.status.state == "model_missing"
    assert not w.banner.isHidden() and "does-not-exist" in w.banner_text.text()
    w.send_message("hello")
    assert wait_for(lambda: w.worker is None and w.error_bubble is not None)
    assert db.get_messages(w.current_conv_id)[0].content == "hello"  # user text is not lost
    w.close()


def test_server_down_shows_recovery(env):
    app, fake, settings, db, _ = env
    settings.base_url = "http://127.0.0.1:9"
    settings.auto_start_ollama = False
    w = make_window(settings, db)
    w.show()
    assert wait_for(lambda: w.status is not None)
    assert w.status.state == "server_down" and not w.banner.isHidden()
    w.close()
