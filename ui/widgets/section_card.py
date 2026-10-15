"""Bloques visuales para Ajustes y Ayuda: tarjeta con cabecera tintada, separadores y rotulos de grupo.

Cada bloque tematico queda aislado: una tarjeta con una cabecera de fondo ligeramente distinto (titulo y, opcional, una
linea de explicacion) y un cuerpo con las opciones separadas por lineas finas. Los rotulos de grupo (con una linea que
se extiende a su derecha) agrupan varias tarjetas.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


class GroupHeading(QWidget):
    """Rotulo de un grupo de tarjetas: texto y una linea fina que llena el resto del ancho."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.label = QLabel(text)
        self.label.setObjectName("GroupTitle")
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 6, 0, 0)
        row.setSpacing(16)
        row.addWidget(self.label)
        line = divider()
        row.addWidget(line, 1, Qt.AlignmentFlag.AlignVCenter)


class SectionCard(QFrame):
    """Tarjeta con cabecera propia. `add` anade contenido al cuerpo; `add_row` lo anade precedido de un separador."""

    def __init__(self, title: str, description: str = "", tone: str = "") -> None:
        super().__init__()
        self.setObjectName("SectionCard")
        self.setProperty("tone", tone)
        self._head = QFrame()
        self._head.setObjectName("SectionHead")
        self._head.setProperty("tone", tone)
        head = QVBoxLayout(self._head)
        head.setContentsMargins(32, 20, 32, 18)
        head.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("SectionHeadTitle")
        head.addWidget(self.title_label)
        self.description_label = QLabel(description)
        self.description_label.setObjectName("Small")
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(description))
        head.addWidget(self.description_label)

        self._body = QVBoxLayout()
        self._body.setContentsMargins(32, 22, 32, 26)
        self._body.setSpacing(14)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._head)
        outer.addLayout(self._body)
        self._count = 0

    def add(self, widget: QWidget) -> None:
        self._body.addWidget(widget)
        self._count += 1

    def add_row(self, widget: QWidget) -> None:
        """Contenido separado del anterior por una linea fina."""
        if self._count:
            self._body.addWidget(divider())
        self.add(widget)
