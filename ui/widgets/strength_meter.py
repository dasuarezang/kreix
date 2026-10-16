"""Medidor de fuerza de la contrasena: cuatro franjas (las de la K de la marca) que se llenan, la palabra y un consejo."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.i18n import tr
from core.password_strength import assess
from ui import theme

SEGMENTS = 4


class _Bars(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.filled = 0                                   # franjas llenas (0..4)
        self.level = 0
        self.setFixedHeight(6)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def color(self) -> QColor:
        pal = theme.current()
        return QColor((pal.red, pal.red, pal.accent, pal.green, pal.green)[self.level])

    def paintEvent(self, _event) -> None:
        pal = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        gap = 6
        width = (self.width() - gap * (SEGMENTS - 1)) / SEGMENTS
        for i in range(SEGMENTS):
            painter.setBrush(self.color() if i < self.filled else QColor(pal.border))
            painter.drawRoundedRect(QRectF(i * (width + gap), 0, width, self.height()), 3, 3)


class StrengthMeter(QWidget):
    """`set_password(texto)` lo actualiza. Es un aviso, no una regla: no bloquea nada."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bars = _Bars()
        self.word = QLabel()
        self.word.setObjectName("Small")
        self.hint = QLabel()
        self.hint.setObjectName("Small")
        self.hint.setWordWrap(True)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self._bars, 1, Qt.AlignmentFlag.AlignVCenter)
        head.addSpacing(12)
        head.addWidget(self.word)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)
        col.addLayout(head)
        col.addWidget(self.hint)
        self.level = 0
        self.set_password("")

    def set_password(self, password: str) -> None:
        result = assess(password)
        self.level = result.level
        self._bars.level = result.level
        self._bars.filled = 0 if not password else max(1, result.level)
        self.word.setText(tr("Seguridad: {level}").format(level=tr(result.label)) if password else tr("Seguridad de la contraseña"))
        self.hint.setText(tr(result.hint) if result.hint else "")
        self.hint.setVisible(bool(result.hint))
        window = self.window()
        if window is not self and hasattr(window, "_fit_height"):          # el consejo cambia la altura: el cuadro se ajusta
            window._fit_height()
        self.setAccessibleName(self.word.text())
        self._bars.update()
