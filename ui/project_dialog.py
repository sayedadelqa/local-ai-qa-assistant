"""Pick a local folder and explicitly choose files to share with the assistant."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QVBoxLayout)

from services.context import estimate_tokens
from services.project_context import (EXCLUDED_DIRS, MAX_FILE_CHARS, MAX_TOTAL_CHARS, FileEntry,
                                      ProjectSelection, scan_folder)


class ProjectDialog(QDialog):
    def __init__(self, parent=None, initial: ProjectSelection | None = None):
        super().__init__(parent)
        self.setWindowTitle("Project files")
        self.resize(640, 560)
        self.selection: ProjectSelection | None = None
        self._root = ""
        self._entries: list[FileEntry] = []

        v = QVBoxLayout(self)
        info = QLabel(
            "Choose a folder, then tick the files the assistant may read. Files are only read, never "
            "executed, and stay on this computer. Their text is added to your next message as untrusted "
            "reference data. Avoid files that contain passwords or tokens.")
        info.setWordWrap(True)
        info.setObjectName("mutedLabel")
        v.addWidget(info)

        top = QHBoxLayout()
        self.folder_label = QLabel("No folder selected")
        pick = QPushButton("Choose folder…")
        pick.clicked.connect(self._pick)
        top.addWidget(self.folder_label, 1)
        top.addWidget(pick)
        v.addLayout(top)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter files…")
        self.filter.textChanged.connect(self._apply_filter)
        v.addWidget(self.filter)

        self.list = QListWidget()
        self.list.itemChanged.connect(lambda *_: self._update_summary())
        v.addWidget(self.list, 1)

        row = QHBoxLayout()
        all_btn = QPushButton("Tick visible")
        none_btn = QPushButton("Untick all")
        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn.clicked.connect(lambda: self._set_all(False))
        row.addWidget(all_btn)
        row.addWidget(none_btn)
        row.addStretch(1)
        v.addLayout(row)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        v.addWidget(self.summary)
        ex = QLabel("Skipped automatically: " + ", ".join(sorted(EXCLUDED_DIRS)[:8]) + ", …")
        ex.setObjectName("mutedLabel")
        ex.setWordWrap(True)
        v.addWidget(ex)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Attach to next message")
        self.ok.setObjectName("primaryBtn")
        self.ok.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addWidget(self.ok)
        v.addLayout(btns)

        if initial and initial.root:
            self._load(initial.root, {f.rel for f in initial.files})

    def _pick(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a project folder", self._root or "")
        if folder:
            self._load(folder, set())

    def _load(self, folder: str, checked: set[str]) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._root = folder
            self._entries = scan_folder(folder)
        finally:
            QApplication.restoreOverrideCursor()
        self.folder_label.setText(folder)
        self.list.blockSignals(True)
        self.list.clear()
        for fe in self._entries:
            kb = max(1, fe.size // 1024)
            it = QListWidgetItem(f"{fe.rel}   ({kb} KB)" + ("  — too large" if fe.too_large else ""))
            flags = it.flags() | Qt.ItemFlag.ItemIsUserCheckable
            if fe.too_large:
                flags &= ~Qt.ItemFlag.ItemIsEnabled
            it.setFlags(flags)
            it.setCheckState(Qt.CheckState.Checked if fe.rel in checked and not fe.too_large
                             else Qt.CheckState.Unchecked)
            it.setData(Qt.ItemDataRole.UserRole, fe.rel)
            self.list.addItem(it)
        self.list.blockSignals(False)
        self._update_summary()

    def _apply_filter(self, text: str) -> None:
        t = text.lower().strip()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(t) and t not in it.data(Qt.ItemDataRole.UserRole).lower())

    def _set_all(self, on: bool) -> None:
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.isHidden() or not (it.flags() & Qt.ItemFlag.ItemIsEnabled):
                continue
            it.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        self.list.blockSignals(False)
        self._update_summary()

    def _checked(self) -> list[FileEntry]:
        by_rel = {f.rel: f for f in self._entries}
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(by_rel[it.data(Qt.ItemDataRole.UserRole)])
        return out

    def _update_summary(self) -> None:
        files = self._checked()
        chars = sum(min(f.size, MAX_FILE_CHARS) for f in files)
        capped = min(chars, MAX_TOTAL_CHARS)
        msg = f"{len(files)} file(s) selected · about {estimate_tokens('x' * capped)} tokens will be sent."
        if chars > MAX_TOTAL_CHARS:
            msg += f" Limit {MAX_TOTAL_CHARS:,} characters: later files will be cut."
        self.summary.setText(msg)

    def _accept(self) -> None:
        files = self._checked()
        self.selection = ProjectSelection(self._root, files) if files else None
        self.accept()
