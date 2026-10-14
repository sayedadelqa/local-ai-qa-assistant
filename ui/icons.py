"""Programmatically drawn app icon (no binary assets required)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap


def make_pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor("#4f8cff"))
    grad.setColorAt(1, QColor("#7c4dff"))
    p.setBrush(grad)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(size * 0.05, size * 0.05, size * 0.9, size * 0.9), size * 0.22, size * 0.22)
    pen = QPen(QColor("white"), size * 0.08, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    path = QPainterPath()
    path.moveTo(size * 0.27, size * 0.53)
    path.lineTo(size * 0.44, size * 0.70)
    path.lineTo(size * 0.74, size * 0.32)
    p.drawPath(path)
    p.setBrush(QColor("white"))
    p.setPen(Qt.PenStyle.NoPen)
    for cx, cy in ((0.27, 0.27), (0.73, 0.73)):
        p.drawEllipse(QRectF(size * (cx - 0.045), size * (cy - 0.045), size * 0.09, size * 0.09))
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_pixmap(s))
    return icon
