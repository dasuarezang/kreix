"""Boton «?» junto a una cifra: abre su explicacion en la Ayuda."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from core.i18n import tr


class InfoButton(QPushButton):
    """Un circulo con «?». `term` es el termino del glosario en castellano (la clave original de la Ayuda)."""

    def __init__(self, term: str) -> None:
        super().__init__("?")
        self.term = term
        self.setObjectName("InfoButton")
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr("Qué significa esto"))
        self.setAccessibleName(tr("Qué significa esto"))
        self.clicked.connect(self._open)

    def _open(self) -> None:
        window = self.window()
        if hasattr(window, "open_help_term"):
            window.open_help_term(self.term)
