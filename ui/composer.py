"""Message input area."""
from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class ComposerEdit(QPlainTextEdit):
    submit = Signal()

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(e)  # newline
            else:
                self.submit.emit()
            return
        super().keyPressEvent(e)

    def insertFromMimeData(self, source: QMimeData) -> None:  # noqa: N802
        if source.hasText():  # plain text only: keeps pasted code, logs and stack traces intact
            self.insertPlainText(source.text())


class Composer(QFrame):
    submitted = Signal(str)
    stop_requested = Signal()
    attach_requested = Signal()
    attachments_cleared = Signal()

    MIN_H, MAX_H = 52, 220

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("composer")
        self._busy = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 12, 28, 12)
        outer.setSpacing(6)

        box = QFrame()
        box.setObjectName("composerBox")
        bl = QHBoxLayout(box)
        bl.setContentsMargins(10, 6, 8, 6)
        bl.setSpacing(8)

        self.edit = ComposerEdit()
        self.edit.setObjectName("composerEdit")
        self.edit.setPlaceholderText(
            "Ask anything about software testing & test automation…  (Enter to send, Shift+Enter for a new line)")
        self.edit.setFrameShape(QFrame.Shape.NoFrame)
        self.edit.setTabChangesFocus(False)
        self.edit.submit.connect(self._on_submit)
        self.edit.document().documentLayout().documentSizeChanged.connect(lambda *_: self._resize())
        bl.addWidget(self.edit, 1)

        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("primaryBtn")
        self.send_btn.setMinimumWidth(80)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self._on_send_clicked)
        bl.addWidget(self.send_btn, 0, Qt.AlignmentFlag.AlignBottom)
        outer.addWidget(box)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.attach_btn = QPushButton("Project files…")
        self.attach_btn.setObjectName("ghostBtn")
        self.attach_btn.setToolTip("Choose a local folder and pick files for the assistant to read")
        self.attach_btn.clicked.connect(self.attach_requested)
        self.attach_label = QLabel("")
        self.attach_label.setObjectName("mutedLabel")
        self.clear_attach_btn = QPushButton("Remove")
        self.clear_attach_btn.setObjectName("ghostBtn")
        self.clear_attach_btn.clicked.connect(self.attachments_cleared)
        self.hint = QLabel("Enter to send · Shift+Enter new line · Esc to stop · Ctrl+N new chat")
        self.hint.setObjectName("mutedLabel")
        row.addWidget(self.attach_btn)
        row.addWidget(self.attach_label)
        row.addWidget(self.clear_attach_btn)
        row.addStretch(1)
        row.addWidget(self.hint)
        outer.addLayout(row)
        self.set_attachment_count(0)
        self._resize()

    # -- behaviour -------------------------------------------------------
    def _resize(self) -> None:
        doc = self.edit.document()
        fm = QFontMetrics(self.edit.font())
        lines = max(1, int(doc.size().height()))
        h = lines * fm.lineSpacing() + int(doc.documentMargin() * 2) + 16
        self.edit.setFixedHeight(max(self.MIN_H, min(self.MAX_H, h)))

    def _on_submit(self) -> None:
        if self._busy:
            return  # prevents duplicate submissions while generating
        text = self.edit.toPlainText().strip()
        if text:
            self.submitted.emit(text)

    def _on_send_clicked(self) -> None:
        if self._busy:
            self.stop_requested.emit()
        else:
            self._on_submit()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.send_btn.setText("Stop" if busy else "Send")
        self.send_btn.setObjectName("dangerBtn" if busy else "primaryBtn")
        self.send_btn.style().unpolish(self.send_btn)
        self.send_btn.style().polish(self.send_btn)
        self.hint.setText("Generating… press Esc or Stop to cancel" if busy else
                          "Enter to send · Shift+Enter new line · Esc to stop · Ctrl+N new chat")

    def set_attachment_count(self, n: int) -> None:
        self.attach_label.setText(f"{n} file(s) will be sent with your next message" if n else "")
        self.clear_attach_btn.setVisible(n > 0)

    def text(self) -> str:
        return self.edit.toPlainText()

    def set_text(self, text: str) -> None:
        self.edit.setPlainText(text)

    def clear(self) -> None:
        self.edit.clear()

    def focus(self) -> None:
        self.edit.setFocus()
