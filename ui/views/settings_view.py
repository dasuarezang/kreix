"""Pantalla de ajustes."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from services.settings_service import AppSettings
from ui.widgets.switch import SwitchToggle

VERSION = "0.1.0"


class SettingRow(QWidget):
    def __init__(self, title: str, description: str, checked: bool) -> None:
        super().__init__()
        self.switch = SwitchToggle(checked)
        self.switch.setAccessibleName(title)
        name = QLabel(title)
        name.setObjectName("H2")
        desc = QLabel(description)
        desc.setObjectName("Small")
        desc.setWordWrap(True)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(name)
        col.addWidget(desc)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 6, 0, 6)
        row.setSpacing(18)
        row.addLayout(col, 1)
        row.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)


class SettingsView(QWidget):
    settings_changed = Signal(object)

    def __init__(self, settings: AppSettings, db_path: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._settings = settings

        title = QLabel("Ajustes")
        title.setObjectName("H1")

        self.p2p = SettingRow(
            "Contar Bizum como ingresos y gastos",
            "Si lo desactivas, los Bizum no entran en el cálculo de la tasa de ahorro.",
            settings.include_p2p,
        )
        self.transfers = SettingRow(
            "Contar traspasos entrantes como ingresos",
            "Útil si tu dinero llega por traspasos desde otra cuenta. Los traspasos salientes nunca cuentan.",
            settings.transfers_in_as_income,
        )
        self.p2p.switch.toggled.connect(lambda v: self._update(include_p2p=v))
        self.transfers.switch.toggled.connect(lambda v: self._update(transfers_in_as_income=v))

        calc = self._card("Cálculo del ahorro", self.p2p, self.transfers)

        path = QLabel(db_path)
        path.setObjectName("Muted")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path.setWordWrap(True)
        privacy = QLabel("Todo se guarda solo en este equipo. Kreix no envía datos a ningún servidor.")
        privacy.setObjectName("Small")
        privacy.setWordWrap(True)
        data = self._card("Tus datos", path, privacy)

        about = self._card("Acerca de", QLabel(f"Kreix {VERSION}"))

        col = QVBoxLayout(self)
        col.setContentsMargins(32, 28, 32, 32)
        col.setSpacing(16)
        col.addWidget(title)
        col.addWidget(calc)
        col.addWidget(data)
        col.addWidget(about)
        col.addStretch(1)

    @staticmethod
    def _card(title: str, *widgets: QWidget) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(8)
        heading = QLabel(title.upper())
        heading.setObjectName("CardTitle")
        lay.addWidget(heading)
        for w in widgets:
            lay.addWidget(w)
        return card

    def _update(self, **changes: bool) -> None:
        self._settings = replace(self._settings, **changes)
        self.settings_changed.emit(self._settings)

    def set_theme(self, theme_name: str) -> None:
        self._settings = replace(self._settings, theme=theme_name)
