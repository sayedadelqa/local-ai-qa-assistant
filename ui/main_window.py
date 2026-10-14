"""Main window: wires the sidebar, chat view, composer and background workers together."""
from __future__ import annotations

import logging
from dataclasses import replace

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from services.assistant import AssistantService
from services.model_manager import ModelManager, StartupStatus
from services.project_context import ProjectSelection, read_selected
from storage.database import Database
from ui.chat_view import ChatView
from ui.composer import Composer
from ui.icons import app_icon
from ui.message_widgets import ErrorBubble, MessageBubble
from ui.project_dialog import ProjectDialog
from ui.settings_dialog import SettingsDialog
from ui.sidebar import Sidebar
from ui.theme import stylesheet, tokens
from ui.workers import FunctionWorker, GenerationWorker
from utils.config import Settings, data_dir, save_settings
from utils.text import DEFAULT_TITLE, make_title, now_iso

log = logging.getLogger(__name__)

CONTINUE_PROMPT = "Please continue from where you stopped, or go deeper on your previous answer."


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, db: Database, manager: ModelManager):
        super().__init__()
        self.settings = settings
        self.db = db
        self.mm = manager
        self.assistant = AssistantService(db, settings)
        self.current_conv_id: int | None = None
        self.worker: GenerationWorker | None = None
        self.startup_worker: FunctionWorker | None = None
        self.stream_bubble: MessageBubble | None = None
        self.error_bubble: ErrorBubble | None = None
        self.project_sel: ProjectSelection | None = None
        self.status: StartupStatus | None = None
        self._buf = ""
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(60)
        self._flush_timer.timeout.connect(self._flush_stream)
        self._closing = False

        self.setWindowTitle("QA AI Assistant")
        self.setWindowIcon(app_icon())
        self.resize(1280, 820)
        self.setMinimumSize(960, 620)
        self._build_ui()
        self._build_shortcuts()
        self._apply_theme()
        self._restore_geometry()
        self.refresh_conversations()
        self.new_chat()
        QTimer.singleShot(0, self.run_startup_check)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("root")
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.new_chat_requested.connect(self.new_chat)
        self.sidebar.conversation_selected.connect(self.open_conversation)
        self.sidebar.rename_requested.connect(self.rename_conversation)
        self.sidebar.delete_requested.connect(self.delete_conversation)
        self.sidebar.search_changed.connect(lambda _: self.refresh_conversations())
        self.sidebar.settings_requested.connect(self.open_settings)
        self.sidebar.model_selected.connect(self.select_model)
        h.addWidget(self.sidebar)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        self.banner = QFrame()
        self.banner.setObjectName("banner")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(20, 10, 20, 10)
        self.banner_text = QLabel("")
        self.banner_text.setObjectName("bannerText")
        self.banner_text.setWordWrap(True)
        self.banner_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.banner_retry = QPushButton("Retry / Start Ollama")
        self.banner_retry.setObjectName("primaryBtn")
        self.banner_retry.clicked.connect(lambda: self.run_startup_check(force_start=True))
        self.banner_settings = QPushButton("Open settings")
        self.banner_settings.clicked.connect(self.open_settings)
        bl.addWidget(self.banner_text, 1)
        bl.addWidget(self.banner_retry)
        bl.addWidget(self.banner_settings)
        self.banner.hide()
        rv.addWidget(self.banner)

        self.chat = ChatView(tokens(self.settings.theme))
        self.chat.suggestion_clicked.connect(self.send_message)
        self.chat.regenerate_requested.connect(self.regenerate)
        self.chat.continue_requested.connect(lambda: self.send_message(CONTINUE_PROMPT))
        self.chat.retry_requested.connect(self.retry)
        rv.addWidget(self.chat, 1)

        self.composer = Composer()
        self.composer.submitted.connect(self.send_message)
        self.composer.stop_requested.connect(self.stop_generation)
        self.composer.attach_requested.connect(self.pick_project_files)
        self.composer.attachments_cleared.connect(self.clear_project_files)
        rv.addWidget(self.composer)
        h.addWidget(right, 1)
        self.setCentralWidget(central)

        self.sidebar.set_models([], self.settings.model)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().hide()

    def _build_shortcuts(self) -> None:
        def sc(seq: str, fn) -> None:
            QShortcut(QKeySequence(seq), self, activated=fn)

        sc("Ctrl+N", self.new_chat)
        sc("Ctrl+F", lambda: self.sidebar.search.setFocus())
        sc("Ctrl+L", self.composer.focus)
        sc("Ctrl+,", self.open_settings)
        sc("Esc", self.stop_generation)
        sc("Ctrl+Shift+C", self._copy_last_response)

    def _apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(stylesheet(self.settings.theme))
        self.chat.set_colors(tokens(self.settings.theme))

    def _restore_geometry(self) -> None:
        qs = QSettings(str(data_dir() / "window.ini"), QSettings.Format.IniFormat)
        geo = qs.value("geometry")
        if geo:
            self.restoreGeometry(geo)

    # -------------------------------------------------------- startup check
    def run_startup_check(self, force_start: bool = False) -> None:
        if self.startup_worker is not None and self.startup_worker.isRunning():
            return
        s = self.settings
        self.mm.set_base_url(s.base_url)
        self.sidebar.set_status("checking", "Checking Ollama…")
        auto = s.auto_start_ollama or force_start
        w = FunctionWorker(lambda: self.mm.ensure_ready(s.model, auto))
        w.result.connect(self._on_startup_status)
        w.failed.connect(lambda m: self._on_startup_status(StartupStatus("start_failed", m)))
        self.startup_worker = w
        w.start()

    def _on_startup_status(self, st: StartupStatus) -> None:
        if self._closing:
            return
        self.status = st
        self.sidebar.set_models(st.models, self.settings.model)
        if st.state == "ready":
            self.sidebar.set_status("ok", st.message)
            if st.warning:
                self._show_banner(st.warning, retry=False)
            else:
                self.banner.hide()
        else:
            self.sidebar.set_status("error", {
                "model_missing": "Model not found", "no_ollama": "Ollama not installed",
                "server_down": "Ollama not running", "start_failed": "Could not start Ollama",
            }.get(st.state, "Not connected"))
            self._show_banner(st.message, retry=True)

    def _show_banner(self, text: str, retry: bool) -> None:
        self.banner_text.setText(text)
        self.banner_retry.setVisible(retry)
        self.banner.show()

    # ---------------------------------------------------------- conversations
    def refresh_conversations(self) -> None:
        convs = self.db.list_conversations(self.sidebar.search.text())
        self.sidebar.set_conversations(convs, self.current_conv_id)

    def new_chat(self) -> None:
        if self.worker is not None:
            return
        self.current_conv_id = None
        self.error_bubble = None
        self.chat.show_welcome()
        self.refresh_conversations()
        self.composer.focus()

    def open_conversation(self, conv_id: int) -> None:
        if self.worker is not None:
            return
        self.current_conv_id = conv_id
        self._render_conversation()
        self.refresh_conversations()
        self.composer.focus()

    def _render_conversation(self) -> None:
        self.chat.clear()
        self.error_bubble = None
        msgs = self.db.get_messages(self.current_conv_id) if self.current_conv_id else []
        if not msgs:
            self.chat.show_welcome()
            return
        for m in msgs:
            self.chat.add_message(m)
        if msgs[-1].role == "user":
            self.error_bubble = self.chat.add_error("This message has no reply yet. Press Retry to ask the model.")
        self.chat.scroll_to_bottom()

    def rename_conversation(self, conv_id: int) -> None:
        conv = self.db.get_conversation(conv_id)
        if conv is None:
            return
        title, ok = QInputDialog.getText(self, "Rename conversation", "Title:", text=conv.title)
        title = title.strip()
        if ok and title:
            self.db.rename_conversation(conv_id, title[:120])
            self.refresh_conversations()

    def delete_conversation(self, conv_id: int) -> None:
        conv = self.db.get_conversation(conv_id)
        if conv is None:
            return
        r = QMessageBox.question(self, "Delete conversation", f"Delete “{conv.title}”? This cannot be undone.")
        if r != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_conversation(conv_id)
        if conv_id == self.current_conv_id:
            self.new_chat()
        else:
            self.refresh_conversations()

    # --------------------------------------------------------------- sending
    def send_message(self, text: str) -> None:
        text = text.strip()
        if not text or self.worker is not None:
            return
        if self.current_conv_id is None:
            self.current_conv_id = self.db.create_conversation(make_title(text)).id
        else:
            conv = self.db.get_conversation(self.current_conv_id)
            if conv and conv.title == DEFAULT_TITLE:
                self.db.rename_conversation(conv.id, make_title(text))
        context = None
        attachments = None
        if self.project_sel and self.project_sel.files:
            pc = read_selected(self.project_sel)
            if pc.included:
                context, attachments = pc.text, pc.included
            if pc.notes:
                log.info("Project context notes: %d", len(pc.notes))
        if self.error_bubble is not None:
            self.chat.remove_widget(self.error_bubble)
            self.error_bubble = None
        msg = self.db.add_message(self.current_conv_id, "user", text, context, attachments)
        self.chat.add_message(msg)
        self.composer.clear()
        self.clear_project_files()
        self.refresh_conversations()
        self._start_generation()

    def _start_generation(self) -> None:
        if self.current_conv_id is None or self.worker is not None:
            return
        prepared = self.assistant.prepare(self.current_conv_id)
        if prepared.dropped:
            self.chat.add_notice(
                f"Context limit: {prepared.dropped} earlier message(s) are not sent to the model. "
                "It cannot see them. Increase the context window in Settings if needed.")
        if prepared.truncated:
            self.chat.add_notice("Your last message was too long for the context window and was shortened.")
        self._buf = ""
        self.stream_bubble = self.chat.add_stream_bubble()
        w = GenerationWorker(self.assistant, self.mm, prepared, self.settings.auto_start_ollama)
        w.token.connect(self._on_token)
        w.status.connect(lambda s: self.sidebar.set_status("checking", s))
        w.done.connect(self._on_done)
        w.cancelled.connect(self._on_cancelled)
        w.failed.connect(self._on_failed)
        self.worker = w
        self.composer.set_busy(True)
        self.sidebar.set_locked(True)
        self.sidebar.set_status("checking", "Generating…")
        w.start()

    def _on_token(self, text: str) -> None:
        self._buf += text
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush_stream(self) -> None:
        if self.stream_bubble is not None and self._buf:
            self.stream_bubble.stop_thinking()
            self.stream_bubble.set_text(self._buf)
            if self.worker is not None:
                self.sidebar.set_status("checking", "Generating…")

    def _finish_worker(self) -> None:
        self._flush_timer.stop()
        w, self.worker = self.worker, None
        if w is not None:
            w.wait(3000)
            w.deleteLater()
        self.composer.set_busy(False)
        self.sidebar.set_locked(False)
        if self.status and self.status.state == "ready":
            self.sidebar.set_status("ok", self.status.message)
        else:
            self.sidebar.set_status("ok", "Connected")

    def _on_done(self, text: str, stats: dict) -> None:
        self._buf = text
        bubble = self.stream_bubble
        self._finish_worker()
        if bubble is None or self.current_conv_id is None:
            return
        bubble.set_text(text)
        msg = self.db.add_message(self.current_conv_id, "assistant", text)
        eval_count, eval_dur = stats.get("eval_count"), stats.get("eval_duration")
        info = ""
        if eval_count and eval_dur:
            info = f"{eval_count} tokens · {eval_count / (eval_dur / 1e9):.1f} tok/s"
        bubble.finalize(msg.created_at, info)
        self.stream_bubble = None
        self.chat.refresh_actions()
        self.refresh_conversations()
        self.composer.focus()

    def _on_cancelled(self, partial: str) -> None:
        partial = partial or self._buf
        bubble = self.stream_bubble
        self.stream_bubble = None
        self._finish_worker()
        if bubble is None or self.current_conv_id is None:
            return
        if partial.strip():
            text = partial.rstrip() + "\n\n*(generation stopped)*"
            bubble.set_text(text)
            msg = self.db.add_message(self.current_conv_id, "assistant", text)
            bubble.finalize(msg.created_at, "stopped")
        else:
            self.chat.remove_widget(bubble)
            self.error_bubble = self.chat.add_error("Generation was stopped before any text arrived. Press Retry to try again.")
        self.chat.refresh_actions()
        self.refresh_conversations()

    def _on_failed(self, kind: str, message: str) -> None:
        bubble = self.stream_bubble
        self.stream_bubble = None
        self._finish_worker()
        if bubble is not None:
            self.chat.remove_widget(bubble)
        log.warning("Generation failed: %s", kind)
        self.error_bubble = self.chat.add_error(message)
        self.sidebar.set_status("error", "Request failed")
        if kind in ("connection", "server_down", "no_ollama", "start_failed", "model_missing"):
            self._show_banner(message, retry=kind != "model_missing")
        self.chat.refresh_actions()

    def stop_generation(self) -> None:
        if self.worker is not None:
            self.worker.cancel()

    def retry(self) -> None:
        if self.worker is not None or self.current_conv_id is None:
            return
        if self.error_bubble is not None:
            self.chat.remove_widget(self.error_bubble)
            self.error_bubble = None
        self._start_generation()

    def regenerate(self) -> None:
        if self.worker is not None or self.current_conv_id is None:
            return
        msgs = self.db.get_messages(self.current_conv_id)
        if msgs and msgs[-1].role == "assistant":
            self.db.delete_messages_from(self.current_conv_id, msgs[-1].id)
            self._render_conversation_without_error()
            self._start_generation()

    def _render_conversation_without_error(self) -> None:
        self.chat.clear()
        self.error_bubble = None
        for m in self.db.get_messages(self.current_conv_id):
            self.chat.add_message(m)

    def _copy_last_response(self) -> None:
        assistants = [b for b in self.chat.bubbles() if b.role == "assistant"]
        if assistants:
            assistants[-1].copy_response()

    # ------------------------------------------------------- project context
    def pick_project_files(self) -> None:
        dlg = ProjectDialog(self, self.project_sel)
        if dlg.exec() and dlg.selection is not None:
            self.project_sel = dlg.selection
            self.composer.set_attachment_count(len(dlg.selection.files))

    def clear_project_files(self) -> None:
        self.project_sel = None
        self.composer.set_attachment_count(0)

    # --------------------------------------------------------------- settings
    def select_model(self, model: str) -> None:
        if model and model != self.settings.model:
            self._apply_settings(replace(self.settings, model=model))

    def open_settings(self) -> None:
        models = self.status.models if self.status else []
        dlg = SettingsDialog(self.settings, models, self)
        dlg.clear_history_requested.connect(self._clear_history)
        if dlg.exec() and dlg.result_settings is not None:
            self._apply_settings(dlg.result_settings)

    def _apply_settings(self, new: Settings) -> None:
        old = self.settings
        self.settings = new
        try:
            save_settings(new)
        except OSError:
            log.exception("Could not save settings")
            QMessageBox.warning(self, "Settings", "Settings could not be saved to disk.")
        self.assistant.update_settings(new)
        if new.theme != old.theme:
            self._apply_theme()
            if self.worker is None:
                if self.current_conv_id is None:
                    self.chat.show_welcome()
                else:
                    self._render_conversation()
        if (new.base_url, new.model) != (old.base_url, old.model):
            self.run_startup_check()
        else:
            self.sidebar.set_models(self.status.models if self.status else [], new.model)

    def _clear_history(self) -> None:
        if self.worker is not None:
            self.stop_generation()
            self.worker.wait(3000)
        self.db.clear_all()
        self.current_conv_id = None
        self.new_chat()

    # ------------------------------------------------------------------ close
    def closeEvent(self, event) -> None:  # noqa: N802
        self._closing = True
        try:
            qs = QSettings(str(data_dir() / "window.ini"), QSettings.Format.IniFormat)
            qs.setValue("geometry", self.saveGeometry())
        except Exception:  # noqa: BLE001
            log.exception("Could not save window geometry")
        if self.worker is not None:
            self.worker.cancel()
            self.worker.wait(3000)
        self.mm.abort()
        if self.startup_worker is not None and self.startup_worker.isRunning():
            self.startup_worker.wait(3000)
        self.mm.shutdown()  # only stops an Ollama that this app started itself
        self.db.close()
        super().closeEvent(event)
