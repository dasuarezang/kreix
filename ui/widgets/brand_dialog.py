"""Base de los cuadros de dialogo de Kreix: mismo fondo con resplandor que la ventana, titulo y una tarjeta con el contenido."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QVBoxLayout, QWidget

from ui import theme
from ui.widgets.cards import BrandRule


class BrandDialog(QDialog):
    """Todos los cuadros comparten la misma cara: fondo de la app, titulo grande, explicacion y una tarjeta redondeada."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if parent is None:                                  # un cuadro suelto (sin ventana madre) no hereda el estilo de nadie
            self.setStyleSheet(theme.stylesheet(theme.current()))

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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fit_height()

    def _fit_height(self) -> None:
        """Los textos se parten en lineas segun el ancho: la altura la da el contenido (si no, algo quedaria recortado)."""
        layout = self.layout()
        if layout is not None:
            needed = layout.totalHeightForWidth(self.width())
            if needed > self.height():
                self.resize(self.width(), needed)

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
        card = QFrame()                              # el cuadro ya es una superficie: dentro, sin otra caja, solo el filo de marca
        card.setObjectName("Section")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(12)
        inner.addWidget(BrandRule())
        outer.addWidget(card)
        return inner
