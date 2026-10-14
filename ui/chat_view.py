"""Scrollable conversation area with welcome screen and message bubbles."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from storage.database import Message
from ui.message_widgets import ErrorBubble, MessageBubble

EXAMPLES = [
    ("Negative test cases", "Write five negative test cases for SauceDemo login."),
    ("Playwright (Python)", "Write a Playwright test in Python that logs in to SauceDemo and adds an item to the cart."),
    ("Debug a failure", "Help me debug this failing pytest test. I will paste the stack trace next."),
    ("Flaky tests", "What are the most common causes of flaky Selenium tests and how do I fix each one?"),
    ("API testing", "Create a pytest + requests suite for a REST /users endpoint with positive, negative and boundary checks."),
    ("Release readiness", "Give me a Go/No-Go checklist for a release with 3 open medium-severity bugs."),
]


class ChatView(QScrollArea):
    suggestion_clicked = Signal(str)
    regenerate_requested = Signal()
    continue_requested = Signal()
    retry_requested = Signal()

    def __init__(self, colors: dict[str, str], parent=None):
        super().__init__(parent)
        self.colors = colors
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.container.setObjectName("chatContainer")
        self.layout_ = QVBoxLayout(self.container)
        self.layout_.setContentsMargins(28, 20, 28, 20)
        self.layout_.setSpacing(14)
        self.layout_.addStretch(1)  # keeps messages at the top
        self.setWidget(self.container)
        self._rows: list[tuple[QWidget, QWidget]] = []  # (row, content)
        self._welcome: QWidget | None = None
        self._stick = True
        bar = self.verticalScrollBar()
        bar.valueChanged.connect(lambda v: setattr(self, "_stick", v >= bar.maximum() - 40))
        bar.rangeChanged.connect(lambda *_: self._stick and self.scroll_to_bottom())

    # -- helpers ----------------------------------------------------------
    def set_colors(self, colors: dict[str, str]) -> None:
        self.colors = colors

    def scroll_to_bottom(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _add_row(self, widget: QWidget, align_right: bool = False) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(widget, 1)
        h.setAlignment(widget, Qt.AlignmentFlag.AlignRight if align_right else Qt.AlignmentFlag.AlignLeft)
        self.layout_.insertWidget(self.layout_.count() - 1, row)
        self._rows.append((row, widget))
        return row

    def clear(self) -> None:
        for row, _ in self._rows:
            self.layout_.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()
        self.hide_welcome()
        self._stick = True

    # -- welcome -------------------------------------------------------------
    def show_welcome(self) -> None:
        self.clear()
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 40, 0, 0)
        v.setSpacing(10)
        title = QLabel("QA AI Assistant")
        title.setObjectName("welcomeTitle")
        sub = QLabel("Your local AI partner for test design, Selenium/Playwright automation,manual testing وbug analysis, API testing, "
                     "debugging and QA decisions. Everything runs on this computer.")
        sub.setObjectName("welcomeSub")
        sub.setWordWrap(True)
        v.addWidget(title)
        v.addWidget(sub)
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (name, prompt) in enumerate(EXAMPLES):
            btn = QPushButton(f"{name}\n{prompt}")
            btn.setObjectName("suggestion")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.clicked.connect(lambda _=False, p=prompt: self.suggestion_clicked.emit(p))
            grid.addWidget(btn, i // 2, i % 2)
        v.addLayout(grid)
        w.setMaximumWidth(980)
        self.layout_.insertWidget(0, w)
        self._welcome = w

    def hide_welcome(self) -> None:
        if self._welcome is not None:
            self.layout_.removeWidget(self._welcome)
            self._welcome.setParent(None)
            self._welcome.deleteLater()
            self._welcome = None

    # -- messages --------------------------------------------------------------
    def add_message(self, m: Message) -> MessageBubble:
        self.hide_welcome()
        b = MessageBubble(m.role, m.content, m.created_at, self.colors, m.attachments)
        self._wire(b)
        self._add_row(b, align_right=(m.role == "user"))
        self.refresh_actions()
        return b

    def add_stream_bubble(self) -> MessageBubble:
        self.hide_welcome()
        b = MessageBubble("assistant", "", "", self.colors)
        b.start_thinking()
        self._wire(b)
        self._add_row(b)
        self._stick = True
        self.scroll_to_bottom()
        return b

    def _wire(self, b: MessageBubble) -> None:
        b.regenerate_clicked.connect(self.regenerate_requested)
        b.continue_clicked.connect(self.continue_requested)

    def add_notice(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("noticeLabel")
        lbl.setWordWrap(True)
        self._add_row(lbl)
        return lbl

    def add_error(self, message: str) -> ErrorBubble:
        self.hide_welcome()
        e = ErrorBubble(message)
        e.retry_clicked.connect(self.retry_requested)
        self._add_row(e)
        self._stick = True
        self.scroll_to_bottom()
        return e

    def remove_widget(self, widget: QWidget) -> None:
        for i, (row, content) in enumerate(self._rows):
            if content is widget:
                self.layout_.removeWidget(row)
                row.setParent(None)
                row.deleteLater()
                self._rows.pop(i)
                break
        self.refresh_actions()

    def bubbles(self) -> list[MessageBubble]:
        return [c for _, c in self._rows if isinstance(c, MessageBubble)]

    def refresh_actions(self) -> None:
        """Only the last assistant message offers Regenerate / Continue."""
        assistants = [b for b in self.bubbles() if b.role == "assistant"]
        for i, b in enumerate(assistants):
            last = i == len(assistants) - 1
            b.set_actions(last, last)
