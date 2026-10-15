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
        if not description:
            self.description_label.hide()   # no setVisible(True) sin padre: abriria una ventana suelta
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


class GroupCard(QFrame):
    """Una sola tarjeta para varios ajustes: cada uno es una fila (titulo, explicacion y su control) y las filas se separan con
    una linea fina. Menos cajas que una tarjeta por ajuste y mas facil de recorrer."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("GroupCard")
        self._col = QVBoxLayout(self)
        self._col.setContentsMargins(0, 0, 0, 0)
        self._col.setSpacing(0)
        self._rows = 0

    def _row(self, widget: QWidget) -> QWidget:
        """Envuelve una fila con su relleno y, salvo la primera, su linea superior (asi, al ocultar la fila se va tambien la linea)."""
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        if self._rows:
            rule = divider()
            lay.addWidget(rule)
        inner = QVBoxLayout()
        inner.setContentsMargins(32, 22, 32, 22)
        inner.addWidget(widget)
        lay.addLayout(inner)
        self._col.addWidget(holder)
        self._rows += 1
        return holder

    def add_setting(self, widget: QWidget) -> QWidget:
        """Una fila ya hecha (un interruptor con su texto)."""
        return self._row(widget)

    def add_field(self, title: str, description: str = "", control: QWidget | None = None) -> QWidget:
        """Una fila con titulo, explicacion y, debajo, su control."""
        box = QWidget()
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)
        heading = QLabel(title)
        heading.setObjectName("FieldTitle")
        col.addWidget(heading)
        if description:
            text = QLabel(description)
            text.setObjectName("Small")
            text.setWordWrap(True)
            col.addWidget(text)
        if control is not None:
            col.addSpacing(8)
            col.addWidget(control)
        box.title_label = heading
        return self._row(box)
