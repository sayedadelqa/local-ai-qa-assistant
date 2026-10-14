"""QA Automation Assistant - application entry point."""
from __future__ import annotations

import logging
import os
import sys
import tempfile
import traceback


def main() -> int:
    from utils.config import data_dir, load_settings
    from utils.logging_setup import setup_logging

    setup_logging()
    log = logging.getLogger("main")

    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication(sys.argv)
    app.setApplicationName("QA AI Assistant")

    def excepthook(exc_type, exc, tb):
        log.error("Unhandled exception:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        try:
            QMessageBox.critical(None, "Unexpected error",
                                 f"{exc_type.__name__}: {exc}\n\nDetails were written to the log file in\n{data_dir() / 'logs'}")
        except Exception:  # noqa: BLE001
            pass

    sys.excepthook = excepthook

    lock = QLockFile(os.path.join(tempfile.gettempdir(), "qa_automation_assistant.lock"))
    lock.setStaleLockTime(0)
    if not os.environ.get("QA_ASSISTANT_NO_LOCK") and not lock.tryLock(200):
        QMessageBox.information(None, "Already running", "QA AI Assistant is already open.")
        return 0

    from services.model_manager import ModelManager
    from storage.database import Database
    from ui.icons import app_icon
    from ui.main_window import MainWindow

    settings = load_settings()
    db = Database(data_dir() / "conversations.db")
    manager = ModelManager(settings.base_url)
    app.setWindowIcon(app_icon())
    window = MainWindow(settings, db, manager)
    window.show()
    log.info("Application started")
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
