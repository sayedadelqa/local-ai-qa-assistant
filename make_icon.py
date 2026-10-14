"""Create assets/app.ico (used by the desktop shortcut and PyInstaller)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from ui.icons import make_pixmap  # noqa: E402


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841 (needed for QPixmap)
    out = Path(__file__).parent / "assets"
    out.mkdir(exist_ok=True)
    target = out / "app.ico"
    ok = make_pixmap(256).save(str(target), "ICO")
    print(f"Icon written to {target}" if ok else "Could not write the .ico (the app still works without it).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
