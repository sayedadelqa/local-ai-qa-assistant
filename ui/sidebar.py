"""Left sidebar: branding, conversations, model status."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QPushButton, QVBoxLayout)

from storage.database import Conversation
from ui.icons import make_pixmap
from utils.text import format_ts

STATUS_COLORS = {"ok": "#3ecf8e", "checking": "#f5b94c", "error": "#ff6b6b"}


class Sidebar(QFrame):
    new_chat_requested = Signal()
    conversation_selected = Signal(int)
    rename_requested = Signal(int)
    delete_requested = Signal(int)
    search_changed = Signal(str)
    settings_requested = Signal()
    model_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(300)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 16, 14, 14)
        v.setSpacing(10)

        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(make_pixmap(64).scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))
        title = QLabel("QA AI\nAssistant")
        title.setObjectName("appTitle")
        brand.addWidget(logo)
        brand.addWidget(title, 1)
        v.addLayout(brand)

        self.new_btn = QPushButton("+  New chat")
        self.new_btn.setObjectName("primaryBtn")
        self.new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_btn.clicked.connect(self.new_chat_requested)
        v.addWidget(self.new_btn)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search conversations…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.search_changed)
        v.addWidget(self.search)

        lbl = QLabel("CONVERSATIONS")
        lbl.setObjectName("sectionLabel")
        v.addWidget(lbl)

        self.list = QListWidget()
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.list.itemClicked.connect(lambda it: self.conversation_selected.emit(it.data(Qt.ItemDataRole.UserRole)))
        self.list.itemActivated.connect(lambda it: self.conversation_selected.emit(it.data(Qt.ItemDataRole.UserRole)))
        v.addWidget(self.list, 1)

        row = QHBoxLayout()
        self.rename_btn = QPushButton("Rename")
        self.delete_btn = QPushButton("Delete")
        self.rename_btn.clicked.connect(lambda: self._emit_current(self.rename_requested))
        self.delete_btn.clicked.connect(lambda: self._emit_current(self.delete_requested))
        row.addWidget(self.rename_btn)
        row.addWidget(self.delete_btn)
        v.addLayout(row)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: rgba(128,128,128,0.25);")
        v.addWidget(line)

        mlabel = QLabel("MODEL")
        mlabel.setObjectName("sectionLabel")
        v.addWidget(mlabel)
        self.model_combo = QComboBox()
        self.model_combo.activated.connect(lambda i: self.model_selected.emit(self.model_combo.itemData(i)))
        v.addWidget(self.model_combo)

        st = QHBoxLayout()
        self.dot = QLabel("●")
        self.status_label = QLabel("Checking Ollama…")
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        st.addWidget(self.dot)
        st.addWidget(self.status_label, 1)
        v.addLayout(st)

        self.local_label = QLabel("🔒 Runs 100% locally. Nothing leaves this PC.")
        self.local_label.setObjectName("localBadge")
        self.local_label.setWordWrap(True)
        v.addWidget(self.local_label)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.settings_requested)
        v.addWidget(self.settings_btn)
        self.set_status("checking", "Checking Ollama…")

    # -- API --------------------------------------------------------------
    def set_conversations(self, convs: list[Conversation], selected_id: int | None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for c in convs:
            it = QListWidgetItem(c.title)
            it.setData(Qt.ItemDataRole.UserRole, c.id)
            it.setToolTip(f"{c.title}\nLast activity: {format_ts(c.updated_at)}")
            self.list.addItem(it)
            if c.id == selected_id:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)

    def current_id(self) -> int | None:
        it = self.list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def set_locked(self, locked: bool) -> None:
        """Disable conversation switching while a reply is being generated."""
        for w in (self.list, self.new_btn, self.rename_btn, self.delete_btn):
            w.setEnabled(not locked)

    def set_status(self, state: str, text: str) -> None:
        self.dot.setStyleSheet(f"color: {STATUS_COLORS.get(state, '#888')}; font-size: 12pt;")
        self.status_label.setText(text)

    def set_models(self, models: list[str], current: str) -> None:
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        names = list(models)
        for m in names:
            self.model_combo.addItem(m, m)
        if current not in names:
            suffix = "  (not found)" if names else "  (configured)"
            self.model_combo.addItem(current + suffix, current)
        idx = self.model_combo.findData(current)
        self.model_combo.setCurrentIndex(max(idx, 0))
        self.model_combo.blockSignals(False)

    # -- internals ---------------------------------------------------------
    def _emit_current(self, signal) -> None:
        cid = self.current_id()
        if cid is not None:
            signal.emit(cid)

    def _menu(self, pos: QPoint) -> None:
        it = self.list.itemAt(pos)
        if it is None:
            return
        cid = it.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        a_ren = menu.addAction("Rename")
        a_del = menu.addAction("Delete")
        chosen = menu.exec(self.list.mapToGlobal(pos))
        if chosen is a_ren:
            self.rename_requested.emit(cid)
        elif chosen is a_del:
            self.delete_requested.emit(cid)
