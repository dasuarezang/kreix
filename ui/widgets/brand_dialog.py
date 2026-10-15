"""Base de los cuadros de dialogo de Kreix: mismo fondo con resplandor que la ventana, titulo y una tarjeta con el contenido."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QVBoxLayout, QWidget

from ui import theme


class BrandDialog(QDialog):
    """Todos los cuadros comparten la misma cara: fondo de la app, titulo grande, explicacion y una tarjeta redondeada."""

    def paintEvent(self, _event) -> None:
        pal = theme.current()
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(pal.bg))
        gradient = QRadialGradient(self.width() * 0.95, -self.height() * 0.05, max(self.width(), self.height()) * 0.95)
        start = QColor(pal.glow)
        start.setAlpha(pal.glow_alpha + 20)
        end = QColor(pal.glow)
        end.setAlpha(0)
        gradient.setColorAt(0.0, start)
        gradient.setColorAt(1.0, end)
        painter.fillRect(self.rect(), gradient)

    def frame(self, title: str, intro: str = "", extra_top: QWidget | None = None) -> QVBoxLayout:
        """Monta titulo, explicacion y tarjeta; devuelve la capa de la tarjeta, donde va el contenido."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 28, 30, 26)
        outer.setSpacing(16)
        if extra_top is not None:
            outer.addWidget(extra_top)
        self.heading = QLabel(title)
        self.heading.setObjectName("H1")
        self.heading.setWordWrap(True)
        outer.addWidget(self.heading)
        if intro:
            self.intro_label = QLabel(intro)
            self.intro_label.setObjectName("Muted")
            self.intro_label.setWordWrap(True)
            outer.addWidget(self.intro_label)
        card = QFrame()
        card.setObjectName("Card")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(26, 24, 26, 22)
        inner.setSpacing(12)
        outer.addWidget(card)
        return inner
