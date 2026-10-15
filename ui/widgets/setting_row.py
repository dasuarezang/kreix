"""Fila de ajuste: titulo, explicacion y un interruptor a la derecha."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.widgets.switch import SwitchToggle


class SettingRow(QWidget):
    def __init__(self, title: str, description: str, checked: bool) -> None:
        super().__init__()
        self.switch = SwitchToggle(checked)
        self.switch.setAccessibleName(title)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("H2")
        self.desc_label = QLabel(description)
        self.desc_label.setObjectName("Small")
        self.desc_label.setWordWrap(True)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(self.title_label)
        col.addWidget(self.desc_label)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 6, 0, 6)
        row.setSpacing(18)
        row.addLayout(col, 1)
        row.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_texts(self, title: str, description: str) -> None:
        self.title_label.setText(title)
        self.desc_label.setText(description)
        self.switch.setAccessibleName(title)
