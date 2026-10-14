"""Settings dialog with validation, connection test and reset."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout)

from services.model_manager import ModelManager
from ui.workers import FunctionWorker
from utils.config import Settings, validate


class SettingsDialog(QDialog):
    clear_history_requested = Signal()

    def __init__(self, settings: Settings, models: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self._original = settings
        self.result_settings: Settings | None = None
        self._worker: FunctionWorker | None = None

        self.url = QLineEdit()
        self.model = QComboBox()
        self.model.setEditable(True)
        self.cpu = QCheckBox("CPU-only generation (recommended for this machine)")
        self.temp = QDoubleSpinBox()
        self.temp.setRange(0.0, 2.0)
        self.temp.setSingleStep(0.1)
        self.temp.setDecimals(2)
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(64, 8192)
        self.max_tokens.setSingleStep(128)
        self.num_ctx = QSpinBox()
        self.num_ctx.setRange(1024, 32768)
        self.num_ctx.setSingleStep(1024)
        self.timeout = QSpinBox()
        self.timeout.setRange(10, 1800)
        self.timeout.setSuffix(" s")
        self.theme = QComboBox()
        self.theme.addItems(["dark", "light"])
        self.autostart = QCheckBox("Start Ollama in the background if it is not running")

        form = QFormLayout()
        form.addRow("Ollama server URL", self.url)
        form.addRow("Default model", self.model)
        form.addRow("", self.cpu)
        form.addRow("Temperature", self.temp)
        form.addRow("Max generated tokens", self.max_tokens)
        form.addRow("Context window (tokens)", self.num_ctx)
        form.addRow("Request timeout", self.timeout)
        form.addRow("Theme", self.theme)
        form.addRow("", self.autostart)

        self.test_btn = QPushButton("Test connection")
        self.test_btn.clicked.connect(self._test)
        self.reset_btn = QPushButton("Reset to defaults")
        self.reset_btn.clicked.connect(self._reset)
        self.clear_btn = QPushButton("Clear conversation history…")
        self.clear_btn.setObjectName("dangerBtn")
        self.clear_btn.clicked.connect(self._clear_history)
        self.test_result = QLabel("")
        self.test_result.setWordWrap(True)

        tools = QHBoxLayout()
        tools.addWidget(self.test_btn)
        tools.addWidget(self.reset_btn)
        tools.addStretch(1)
        tools.addWidget(self.clear_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addLayout(tools)
        root.addWidget(self.test_result)
        root.addWidget(buttons)

        self._models = models
        self._load(settings)

    def _load(self, s: Settings) -> None:
        self.url.setText(s.base_url)
        self.model.clear()
        names = list(self._models)
        if s.model not in names:
            names.insert(0, s.model)
        self.model.addItems(names)
        self.model.setCurrentText(s.model)
        self.cpu.setChecked(s.cpu_only)
        self.temp.setValue(s.temperature)
        self.max_tokens.setValue(s.max_tokens)
        self.num_ctx.setValue(s.num_ctx)
        self.timeout.setValue(s.timeout_s)
        self.theme.setCurrentText(s.theme)
        self.autostart.setChecked(s.auto_start_ollama)

    def _collect(self) -> Settings:
        return replace(
            self._original,
            base_url=self.url.text().strip().rstrip("/"),
            model=self.model.currentText().strip(),
            cpu_only=self.cpu.isChecked(),
            temperature=round(self.temp.value(), 2),
            max_tokens=self.max_tokens.value(),
            num_ctx=self.num_ctx.value(),
            timeout_s=self.timeout.value(),
            theme=self.theme.currentText(),
            auto_start_ollama=self.autostart.isChecked(),
        )

    def _reset(self) -> None:
        self._load(Settings())
        self.test_result.setText("Defaults restored. Press Save to keep them.")

    def _save(self) -> None:
        s = self._collect()
        errors = validate(s)
        if errors:
            QMessageBox.warning(self, "Invalid settings", "\n".join("• " + e for e in errors))
            return
        self.result_settings = s
        self.accept()

    def _clear_history(self) -> None:
        r = QMessageBox.question(self, "Clear history",
                                 "Delete ALL saved conversations? This cannot be undone.")
        if r == QMessageBox.StandardButton.Yes:
            self.clear_history_requested.emit()
            self.test_result.setText("All conversations were deleted.")

    def _test(self) -> None:
        s = self._collect()
        errors = validate(s)
        if errors:
            self.test_result.setText("<span style='color:#ff6b6b'>" + "<br>".join(errors) + "</span>")
            return
        self.test_btn.setEnabled(False)
        self.test_result.setText("Testing…")
        mm = ModelManager(s.base_url)
        self._worker = FunctionWorker(lambda: mm.ensure_ready(s.model, auto_start=False))
        self._worker.result.connect(self._test_done)
        self._worker.failed.connect(lambda m: self._test_done(None, m))
        self._worker.start()

    def _test_done(self, status, error: str = "") -> None:
        self.test_btn.setEnabled(True)
        if status is None:
            self.test_result.setText(f"<span style='color:#ff6b6b'>Test failed: {error}</span>")
            return
        ok = status.state == "ready"
        color = "#3ecf8e" if ok else "#ff6b6b"
        text = status.message.replace("\n", "<br>")
        if status.warning:
            text += "<br>" + status.warning
        if status.models and ok:
            text += "<br>Models: " + ", ".join(status.models)
        self.test_result.setText(f"<span style='color:{color}'>{text}</span>")
