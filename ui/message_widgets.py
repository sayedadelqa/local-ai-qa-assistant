"""Message bubbles, Markdown prose, and code blocks with copy buttons."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy,
                               QTextBrowser, QVBoxLayout, QWidget)

from ui.highlighter import CodeHighlighter, normalize_lang
from utils.markdown_split import split_markdown
from utils.text import format_ts


def copy_to_clipboard(text: str) -> None:
    QGuiApplication.clipboard().setText(text)


def flash_copied(button: QPushButton, original: str) -> None:
    button.setText("Copied!")
    QTimer.singleShot(1500, lambda: button.setText(original))


def code_font() -> QFont:
    f = QFont()
    f.setFamilies(["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier New"])
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setPointSize(10)
    return f


class AutoTextBrowser(QTextBrowser):
    """Read-only rich text whose height follows its content (no inner scrollbars)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setOpenLinks(False)
        self.anchorClicked.connect(self._open_link)
        self.document().setDocumentMargin(2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._fitting = False
        self.document().documentLayout().documentSizeChanged.connect(lambda *_: self._fit())
        self._last = None

    @staticmethod
    def _open_link(url: QUrl) -> None:
        if url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)

    def set_markdown(self, text: str) -> None:
        if text != self._last:
            self._last = text
            self.setMarkdown(text)
            self._fit()

    def set_plain(self, text: str) -> None:
        if text != self._last:
            self._last = text
            self.setPlainText(text)
            self._fit()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._fit()

    def _fit(self) -> None:
        if self._fitting:
            return
        w = self.viewport().width()
        if w <= 0:
            return
        self._fitting = True
        try:
            self.document().setTextWidth(w)
            h = int(self.document().size().height()) + 6
            if h != self.height():
                self.setFixedHeight(h)
        finally:
            self._fitting = False


class _CodeEdit(QPlainTextEdit):
    def wheelEvent(self, e) -> None:  # noqa: N802
        # Let the chat scroll when this block has nothing to scroll vertically.
        if self.verticalScrollBar().maximum() == 0:
            e.ignore()
        else:
            super().wheelEvent(e)


class CodeBlockWidget(QFrame):
    MAX_HEIGHT = 520

    def __init__(self, lang: str, code: str, colors: dict[str, str], parent=None):
        super().__init__(parent)
        self.setObjectName("codeFrame")
        self._colors = colors
        self._code = code
        self._lang = normalize_lang(lang)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QFrame()
        header.setObjectName("codeHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(12, 6, 8, 6)
        self.lang_label = QLabel((lang or "code").lower())
        self.lang_label.setObjectName("codeLang")
        self.copy_btn = QPushButton("Copy code")
        self.copy_btn.setObjectName("copyBtn")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self.copy_code)
        h.addWidget(self.lang_label)
        h.addStretch(1)
        h.addWidget(self.copy_btn)
        v.addWidget(header)

        self.editor = _CodeEdit()
        self.editor.setObjectName("codeEdit")
        self.editor.setReadOnly(True)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.setFont(code_font())
        self.editor.setFrameShape(QFrame.Shape.NoFrame)
        self.editor.setTabStopDistance(QFontMetrics(self.editor.font()).horizontalAdvance(" ") * 4)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.editor.document().setDocumentMargin(10)
        self._highlighter = CodeHighlighter(self.editor.document(), self._lang, colors)
        v.addWidget(self.editor)
        self.set_code(code, lang)

    def set_code(self, code: str, lang: str | None = None) -> None:
        self._code = code
        if code != self.editor.toPlainText():
            self.editor.setPlainText(code)
        lines = max(1, code.count("\n") + 1)
        fm = QFontMetrics(self.editor.font())
        height = lines * fm.lineSpacing() + 2 * 10 + 14  # margins + horizontal scrollbar room
        self.editor.setFixedHeight(min(height, self.MAX_HEIGHT))

    @property
    def code(self) -> str:
        return self._code

    def copy_code(self) -> None:
        copy_to_clipboard(self._code)
        flash_copied(self.copy_btn, "Copy code")


class MessageBubble(QFrame):
    regenerate_clicked = Signal()
    continue_clicked = Signal()

    def __init__(self, role: str, text: str, ts_iso: str, colors: dict[str, str],
                 attachments: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.role = role
        self._colors = colors
        self._text = ""
        self._parts: list[tuple[str, QWidget]] = []
        self.setObjectName("bubbleUser" if role == "user" else "bubbleAI")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMaximumWidth(980 if role == "assistant" else 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 10)
        root.setSpacing(8)

        head = QHBoxLayout()
        self.role_label = QLabel("You" if role == "user" else "Assistant")
        self.role_label.setObjectName("roleLabel")
        self.time_label = QLabel(format_ts(ts_iso) if ts_iso else "")
        self.time_label.setObjectName("timeLabel")
        head.addWidget(self.role_label)
        head.addWidget(self.time_label)
        head.addStretch(1)
        root.addLayout(head)

        self.thinking = QLabel("Thinking")
        self.thinking.setObjectName("thinkingLabel")
        self.thinking.hide()
        self._dots = 0
        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._tick)
        root.addWidget(self.thinking)

        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        root.addLayout(self.body)

        if attachments:
            lbl = QLabel("Attached: " + ", ".join(attachments))
            lbl.setObjectName("mutedLabel")
            lbl.setWordWrap(True)
            root.addWidget(lbl)

        self.footer = QWidget()
        f = QHBoxLayout(self.footer)
        f.setContentsMargins(0, 0, 0, 0)
        f.setSpacing(6)
        self.copy_btn = QPushButton("Copy response")
        self.copy_btn.setObjectName("copyBtn")
        self.copy_btn.clicked.connect(self.copy_response)
        self.regen_btn = QPushButton("Regenerate")
        self.regen_btn.setObjectName("copyBtn")
        self.regen_btn.clicked.connect(self.regenerate_clicked)
        self.cont_btn = QPushButton("Continue")
        self.cont_btn.setObjectName("copyBtn")
        self.cont_btn.clicked.connect(self.continue_clicked)
        self.stats_label = QLabel("")
        self.stats_label.setObjectName("statsLabel")
        for b in (self.copy_btn, self.regen_btn, self.cont_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            f.addWidget(b)
        f.addStretch(1)
        f.addWidget(self.stats_label)
        root.addWidget(self.footer)
        self.footer.setVisible(role == "assistant")

        if role == "user":
            self.set_text(text)
        elif text:
            self.set_text(text)

    # -- state ----------------------------------------------------------
    def text(self) -> str:
        return self._text

    def start_thinking(self) -> None:
        self.thinking.show()
        self.footer.hide()
        self._timer.start()

    def stop_thinking(self) -> None:
        self._timer.stop()
        self.thinking.hide()

    def _tick(self) -> None:
        self._dots = (self._dots + 1) % 4
        self.thinking.setText("Thinking" + "." * self._dots)

    def finalize(self, ts_iso: str, stats_text: str = "") -> None:
        self.stop_thinking()
        if ts_iso:
            self.time_label.setText(format_ts(ts_iso))
        self.stats_label.setText(stats_text)
        self.footer.show()

    def set_actions(self, regenerate: bool, cont: bool) -> None:
        self.regen_btn.setVisible(regenerate)
        self.cont_btn.setVisible(cont)

    def copy_response(self) -> None:
        copy_to_clipboard(self._text)
        flash_copied(self.copy_btn, "Copy response")

    def code_blocks(self) -> list[CodeBlockWidget]:
        return [w for k, w in self._parts if k == "code"]  # type: ignore[misc]

    # -- content --------------------------------------------------------
    def set_text(self, text: str) -> None:
        self._text = text
        if self.role == "user":
            fm = QFontMetrics(self.font())
            longest = max((fm.horizontalAdvance(line) for line in text.split("\n")), default=0)
            has_code = "```" in text
            self.setMaximumWidth(720 if has_code else max(160, min(720, longest + 64)))
        segs = split_markdown(text)
        for i, seg in enumerate(segs):
            if i < len(self._parts):
                kind, widget = self._parts[i]
                if kind == seg.kind:
                    self._update_part(widget, seg)
                    continue
                self._remove_from(i)
            self._add_part(seg)
        self._remove_from(len(segs))

    def _update_part(self, widget: QWidget, seg) -> None:
        if seg.kind == "code":
            widget.set_code(seg.content)  # type: ignore[attr-defined]
        elif self.role == "user":
            widget.set_plain(seg.content)  # type: ignore[attr-defined]
        else:
            widget.set_markdown(seg.content)  # type: ignore[attr-defined]

    def _add_part(self, seg) -> None:
        if seg.kind == "code":
            w: QWidget = CodeBlockWidget(seg.lang, seg.content, self._colors)
        else:
            w = AutoTextBrowser()
            if self.role == "user":
                w.set_plain(seg.content)
            else:
                w.set_markdown(seg.content)
        self.body.addWidget(w)
        self._parts.append((seg.kind, w))

    def _remove_from(self, index: int) -> None:
        while len(self._parts) > index:
            _, w = self._parts.pop()
            self.body.removeWidget(w)
            w.setParent(None)
            w.deleteLater()


class ErrorBubble(QFrame):
    retry_clicked = Signal()

    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.setObjectName("bubbleError")
        self.setMaximumWidth(980)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        title = QLabel("Something went wrong")
        title.setObjectName("roleLabel")
        self.msg = QLabel(message)
        self.msg.setWordWrap(True)
        self.msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setObjectName("primaryBtn")
        self.retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_btn.clicked.connect(self.retry_clicked)
        row = QHBoxLayout()
        row.addWidget(self.retry_btn)
        row.addStretch(1)
        v.addWidget(title)
        v.addWidget(self.msg)
        v.addLayout(row)
