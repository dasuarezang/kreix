"""Tarjetas: indicador (KPI) y contenedor de grafico."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


def repolish(widget: QWidget) -> None:
    """Reaplica la hoja de estilos tras cambiar una propiedad dinamica."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ElidedLabel(QLabel):
    """Etiqueta de una linea que acaba en puntos suspensivos si no cabe (y no impone su ancho)."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:  # noqa: N802 (API de Qt)
        super().setText(text)
        self.setToolTip(text)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        self.style().drawItemText(
            painter, self.rect(), int(self.alignment()) | Qt.TextFlag.TextSingleLine, self.palette(),
            self.isEnabled(), text, QPalette.ColorRole.WindowText,
        )


class StatCard(QFrame):
    """Titulo, valor grande y subtitulo, con una barra de acento a la izquierda."""

    def __init__(self, title: str, accent: str = "yellow", compact: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        bar = QFrame()
        bar.setObjectName("AccentBar")
        bar.setProperty("tone", accent)
        bar.setFixedWidth(4)

        self._title = QLabel(title.upper())
        self._title.setObjectName("CardTitle")
        self._value = ElidedLabel("—")
        self._value.setObjectName("MiniValue" if compact else "CardValue")
        self._sub = QLabel("")
        self._sub.setObjectName("CardSub")
        self._sub.setWordWrap(True)

        col = QVBoxLayout()
        col.setSpacing(4)
        for w in (self._title, self._value, self._sub):
            col.addWidget(w)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12 if compact else 16, 20, 12 if compact else 16)
        row.setSpacing(14)
        row.addWidget(bar)
        row.addLayout(col, 1)
        self.setAccessibleName(title)

    def set_title(self, title: str) -> None:
        self._title.setText(title.upper())
        self.setAccessibleName(title)

    def set_content(self, value: str, subtitle: str = "", negative: bool = False) -> None:
        self._value.setText(value)
        self._value.setProperty("tone", "negative" if negative else "normal")
        repolish(self._value)
        self._sub.setText(subtitle)
        self._sub.setVisible(bool(subtitle))
        self.setAccessibleDescription(f"{value}. {subtitle}")


class ChartCard(QFrame):
    """Tarjeta con titulo y un grafico dentro."""

    def __init__(self, title: str, subtitle: str, content: QWidget, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        heading = QLabel(title)
        heading.setObjectName("H2")
        sub = QLabel(subtitle)
        sub.setObjectName("Small")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(2)
        layout.addWidget(heading)
        layout.addWidget(sub)
        layout.addSpacing(6)
        layout.addWidget(content, 1)
        self.setAccessibleName(title)
