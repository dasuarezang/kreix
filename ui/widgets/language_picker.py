"""Selector de idioma: tres botones, cada uno con su bandera en un circulo y el nombre del idioma."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from core import i18n
from ui.flags import flag_icon

FLAG_PX = 26


class LanguagePicker(QWidget):
    changed = Signal(str)          # codigo del idioma elegido por el usuario ("es", "ca", "en")

    def __init__(self, current: str = i18n.DEFAULT) -> None:
        super().__init__()
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        for code in i18n.LANGUAGES:
            button = QPushButton(i18n.NAMES[code])
            button.setObjectName("LangButton")
            button.setCheckable(True)
            button.setIcon(flag_icon(code, FLAG_PX))
            button.setIconSize(QSize(FLAG_PX, FLAG_PX))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAccessibleName(i18n.NAMES[code])
            button.clicked.connect(lambda _=False, c=code: self._picked(c))
            self._group.addButton(button)
            self.buttons[code] = button
            row.addWidget(button)
        row.addStretch(1)
        self.set_language(current)

    def language(self) -> str:
        return next((code for code, b in self.buttons.items() if b.isChecked()), i18n.DEFAULT)

    def set_language(self, code: str) -> None:
        """Marca un idioma desde fuera sin emitir cambios."""
        code = i18n.normalize_language(code)
        for c, button in self.buttons.items():
            button.blockSignals(True)
            button.setChecked(c == code)
            button.blockSignals(False)

    def _picked(self, code: str) -> None:
        self.set_language(code)
        self.changed.emit(code)
