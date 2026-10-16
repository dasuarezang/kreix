"""Selector de periodo: todo el historial o un mes concreto, con flechas para moverse."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ui.popups import Combo
from ui.format import month_long
from core.i18n import tr, N_

GLOBAL_LABEL = N_("Todo el historial")


class PeriodBar(QWidget):
    changed = Signal(object)    # date (primer dia del mes) o None si es global

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._months: list[date] = []
        self.older = QPushButton("‹")
        self.newer = QPushButton("›")
        for button, tip in ((self.older, tr("Mes anterior")), (self.newer, tr("Mes siguiente"))):
            button.setObjectName("Arrow")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(tip)
            button.setAccessibleName(tip)
            button.setFixedWidth(38)
        self.combo = Combo()
        self.combo.setMinimumWidth(190)
        self.combo.setAccessibleName(tr("Periodo"))
        self.combo.addItem(tr(GLOBAL_LABEL), None)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.older)
        row.addWidget(self.combo)
        row.addWidget(self.newer)

        self.combo.currentIndexChanged.connect(self._on_changed)
        self.older.clicked.connect(lambda: self._step(+1))
        self.newer.clicked.connect(lambda: self._step(-1))
        self._sync_arrows()

    def current_month(self) -> date | None:
        return self.combo.currentData()

    def _index_of(self, month: date | None) -> int:
        """Qt convierte las fechas guardadas como dato del combo, y findData no las reconoce:
        se busca comparando los valores de Python."""
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == month:
                return i
        return -1

    def set_months(self, months: list[date]) -> None:
        """`months` va del mas reciente al mas antiguo. Conserva la seleccion si sigue existiendo."""
        keep = self.current_month()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem(tr(GLOBAL_LABEL), None)
        for m in months:
            self.combo.addItem(month_long(m).capitalize(), m)
        self._months = list(months)
        index = self._index_of(keep) if keep is not None else 0
        self.combo.setCurrentIndex(index if index >= 0 else 0)
        self.combo.blockSignals(False)
        self._sync_arrows()

    def select_month(self, month: date | None) -> None:
        index = self._index_of(month)
        if index >= 0:
            self.combo.setCurrentIndex(index)

    def _step(self, direction: int) -> None:
        """direction=+1 va al mes anterior (mas antiguo); -1 al siguiente."""
        index = self.combo.currentIndex()
        if index <= 0:
            if direction == -1 and self._months:          # desde "global", la flecha 'siguiente' no hace nada
                return
            if direction == +1 and self._months:
                self.combo.setCurrentIndex(1)
            return
        target = index + direction
        if 1 <= target <= len(self._months):
            self.combo.setCurrentIndex(target)

    def _on_changed(self, _index: int) -> None:
        self._sync_arrows()
        self.changed.emit(self.current_month())

    def _sync_arrows(self) -> None:
        index = self.combo.currentIndex()
        self.older.setEnabled(bool(self._months) and index < len(self._months))
        self.newer.setEnabled(index > 1)
