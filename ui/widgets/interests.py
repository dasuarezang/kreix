"""Que quiere gestionar el usuario: sus cuentas bancarias, sus inversiones o ambas, con dos interruptores.

Siempre queda al menos uno activado: si se intenta apagar el ultimo, el interruptor vuelve a su sitio y se explica por que.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.widgets.setting_row import SettingRow
from core.i18n import N_, tr

ACCOUNTS_TITLE = N_("Mis cuentas bancarias")
ACCOUNTS_TEXT = N_("Saldo, ingresos y gastos, categorías, presupuestos y pagos recurrentes de tus cuentas (Imagin).")
INVESTMENTS_TITLE = N_("Mis inversiones")
INVESTMENTS_TEXT = N_("Tu cartera de fondos: valor, aportaciones, plusvalía y rentabilidad (MyInvestor).")
AT_LEAST_ONE = N_("Tiene que quedar al menos una activada. Activa la otra antes de desactivar esta.")


class InterestPicker(QWidget):
    changed = Signal(bool, bool)       # (cuentas, inversiones), solo cuando el usuario cambia algo valido

    def __init__(self, accounts: bool = True, investments: bool = True) -> None:
        super().__init__()
        self.accounts = SettingRow(tr(ACCOUNTS_TITLE), tr(ACCOUNTS_TEXT), accounts)
        self.investments = SettingRow(tr(INVESTMENTS_TITLE), tr(INVESTMENTS_TEXT), investments)
        self.hint = QLabel("")
        self.hint.setObjectName("Small")
        self.hint.setWordWrap(True)
        self.hint.hide()
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        col.addWidget(self.accounts)
        col.addWidget(self.investments)
        col.addWidget(self.hint)
        self.accounts.switch.toggled.connect(self._on_accounts)
        self.investments.switch.toggled.connect(self._on_investments)

    def retranslate(self) -> None:
        self.accounts.set_texts(tr(ACCOUNTS_TITLE), tr(ACCOUNTS_TEXT))
        self.investments.set_texts(tr(INVESTMENTS_TITLE), tr(INVESTMENTS_TEXT))
        if not self.hint.isHidden():
            self.hint.setText(tr(AT_LEAST_ONE))

    def values(self) -> tuple[bool, bool]:
        return self.accounts.switch.isChecked(), self.investments.switch.isChecked()

    def set_values(self, accounts: bool, investments: bool) -> None:
        """Refleja unos valores desde fuera sin emitir cambios."""
        for row, value in ((self.accounts, accounts), (self.investments, investments)):
            row.switch.blockSignals(True)
            row.switch.setChecked(value)
            row.switch.blockSignals(False)
            row.switch.update()
        self.hint.hide()

    def _on_accounts(self, on: bool) -> None:
        self._after(self.accounts, on, self.investments)

    def _on_investments(self, on: bool) -> None:
        self._after(self.investments, on, self.accounts)

    def _after(self, row: SettingRow, on: bool, other: SettingRow) -> None:
        if not on and not other.switch.isChecked():          # no se puede quedar sin ningun interes
            row.switch.blockSignals(True)
            row.switch.setChecked(True)
            row.switch.blockSignals(False)
            row.switch.update()
            self.hint.setText(tr(AT_LEAST_ONE))
            self.hint.show()
            return
        self.hint.hide()
        self.changed.emit(*self.values())
