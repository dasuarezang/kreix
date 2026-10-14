"""Tarjetas: indicador (KPI) y contenedor de grafico."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


def repolish(widget: QWidget) -> None:
    """Reaplica la hoja de estilos tras cambiar una propiedad dinamica."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class StatCard(QFrame):
    """Titulo, valor grande y subtitulo, con una barra de acento a la izquierda."""

    def __init__(self, title: str, accent: str = "yellow", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        bar = QFrame()
        bar.setObjectName("AccentBar")
        bar.setProperty("tone", accent)
        bar.setFixedWidth(4)

        self._title = QLabel(title.upper())
        self._title.setObjectName("CardTitle")
        self._value = QLabel("—")
        self._value.setObjectName("CardValue")
        self._sub = QLabel("")
        self._sub.setObjectName("CardSub")
        self._sub.setWordWrap(True)

        col = QVBoxLayout()
        col.setSpacing(4)
        for w in (self._title, self._value, self._sub):
            col.addWidget(w)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 16, 20, 16)
        row.setSpacing(14)
        row.addWidget(bar)
        row.addLayout(col, 1)
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
