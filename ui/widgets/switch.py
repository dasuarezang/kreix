"""Interruptor accesible (teclado, foco visible y nombre accesible)."""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QRectF, QSize, Qt, Property
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy

from ui import theme
from core.i18n import tr


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
            painter.drawRoundedRect(QRectF(1, 1, self.WIDTH - 2, self.HEIGHT - 2), 12, 12)


class ThemeToggle(QAbstractButton):
    """Conmutador claro/oscuro: una pildora con sol y luna, y una bola que indica el modo activo.

    Marcado == modo oscuro. No lleva texto visible; el nombre accesible lo describe."""

    WIDTH, HEIGHT = 96, 44

    def __init__(self, dark: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(dark)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(tr("Modo oscuro"))
        self._pos = 1.0 if dark else 0.0
        self._anim = QPropertyAnimation(self, b"knobPosition", self)
        self._anim.setDuration(180)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:
        return QSize(self.WIDTH, self.HEIGHT)

    def set_dark(self, dark: bool) -> None:
        """Pone el conmutador en un modo sin emitir `toggled` (la ventana ya aplico el tema): la bola salta a su sitio."""
        if self.isChecked() == dark:                      # ya esta asi (p. ej. lo acaba de pulsar el usuario): la animacion sigue
            return
        self.blockSignals(True)
        self.setChecked(dark)
        self.blockSignals(False)
        self._anim.stop()
        self._pos = 1.0 if dark else 0.0
        self.update()

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
        from ui import icons

        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h, w = self.HEIGHT, self.WIDTH
        # La pildora se dibuja un poco metida: el aro de foco queda DENTRO del widget (fuera se recortaba).
        inset = 3
        body = QRectF(inset + 0.5, inset + 0.5, w - 2 * inset - 1, h - 2 * inset - 1)
        painter.setPen(QPen(QColor(p.border), 1))
        painter.setBrush(QColor(p.surface_alt))
        painter.drawRoundedRect(body, body.height() / 2, body.height() / 2)

        pad = inset + 4
        knob = h - 2 * pad
        x = pad + (w - 2 * pad - knob) * self._pos
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p.accent))
        painter.drawEllipse(QRectF(x, pad, knob, knob))

        size = 20
        for name, center_x, active in (("sun", pad + knob / 2, not self.isChecked()),
                                       ("moon", w - pad - knob / 2, self.isChecked())):
            color = p.on_accent if active else p.muted
            painter.drawPixmap(int(center_x - size / 2), int((h - size) / 2), icons.pixmap(name, color, size, 2.0))
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(p.accent), 2))
            painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), (h - 2) / 2, (h - 2) / 2)
