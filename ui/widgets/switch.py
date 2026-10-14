"""Interruptor accesible (teclado, foco visible y nombre accesible)."""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QRectF, QSize, Qt, Property
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy

from ui import theme


class SwitchToggle(QAbstractButton):
    WIDTH, HEIGHT = 46, 26

    def __init__(self, checked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knobPosition", self)
        self._anim.setDuration(140)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:
        return QSize(self.WIDTH, self.HEIGHT)

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, value: float) -> None:
        self._pos = value
        self.update()

    knobPosition = Property(float, _get_pos, _set_pos)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, _event) -> None:
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QColor(p.accent) if self.isChecked() else QColor(p.border)
        if not self.isEnabled():
            track.setAlpha(110)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 0, self.WIDTH, self.HEIGHT), self.HEIGHT / 2, self.HEIGHT / 2)
        margin, d = 3, self.HEIGHT - 6
        x = margin + (self.WIDTH - 2 * margin - d) * self._pos
        painter.setBrush(QColor(p.on_accent) if self.isChecked() else QColor(p.text))
        painter.drawEllipse(QRectF(x, margin, d, d))
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(p.accent), 2))
            painter.drawRoundedRect(QRectF(-1, -1, self.WIDTH + 2, self.HEIGHT + 2), 14, 14)
