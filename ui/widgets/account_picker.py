"""Selector de cuentas con casillas: una, varias combinadas o todas a la vez.

Es un boton que abre un panel con "Todas las cuentas" y una casilla por cuenta. El panel se queda abierto mientras
marcas y desmarcas (se cierra al pulsar fuera o con Escape). Marcar todas, o ninguna, equivale a "Todas las cuentas".
"""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QMenu, QPushButton, QWidget, QWidgetAction

from ui.popups import Menu
from core.i18n import tr, trn


class AccountPicker(QPushButton):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("AccountPicker")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(230)
        self.setAccessibleName(tr("Cuenta"))
        self._accounts: list[tuple[int, str]] = []
        self._ids: set[int] | None = None                  # None = todas
        self._boxes: dict[int, QCheckBox] = {}
        self._all_box: QCheckBox | None = None
        self._menu = Menu(self)
        self.setMenu(self._menu)
        self._refresh_label()

    # ------------------------------------------------------------------ cuentas disponibles
    def set_accounts(self, accounts: list[tuple[int, str]]) -> None:
        """Reconstruye las casillas conservando la seleccion que siga existiendo."""
        if list(accounts) == self._accounts and self._all_box is not None:
            return                                          # nada que reconstruir (y no se toca el panel mientras esta abierto)
        self._accounts = list(accounts)
        valid = {i for i, _ in accounts}
        if self._ids is not None:
            self._ids &= valid
            if not self._ids or self._ids == valid:
                self._ids = None
        self._menu.clear()
        self._boxes = {}
        self._all_box = self._add_box(tr("Todas las cuentas"))
        self._all_box.toggled.connect(self._on_all)
        for account_id, name in accounts:
            box = self._add_box(name)
            box.toggled.connect(partial(self._on_one_toggled, account_id))
            self._boxes[account_id] = box
        self._sync_boxes()
        self._refresh_label()

    def _add_box(self, text: str) -> QCheckBox:
        box = QCheckBox(text)
        box.setObjectName("PickerBox")
        box.setCursor(Qt.CursorShape.PointingHandCursor)
        action = QWidgetAction(self._menu)
        action.setDefaultWidget(box)
        self._menu.addAction(action)
        return box

    # ------------------------------------------------------------------ seleccion
    def selected_ids(self) -> list[int] | None:
        """None = todas las cuentas; si no, los ids marcados."""
        return None if self._ids is None else sorted(self._ids)

    def single_id(self) -> int | None:
        return next(iter(self._ids)) if self._ids is not None and len(self._ids) == 1 else None

    def single_name(self) -> str:
        sid = self.single_id()
        return next((n for i, n in self._accounts if i == sid), "")

    def select_all(self) -> None:
        self._set(None)

    def select_only(self, account_id: int) -> None:
        self._set({account_id} if any(i == account_id for i, _ in self._accounts) else None)

    def select(self, ids: list[int]) -> None:
        self._set(set(ids))

    def _set(self, ids: set[int] | None) -> None:
        valid = {i for i, _ in self._accounts}
        if ids is not None:
            ids = ids & valid
            if not ids or ids == valid:
                ids = None
        if ids == self._ids:
            self._sync_boxes()
            return
        self._ids = ids
        self._sync_boxes()
        self._refresh_label()
        self.changed.emit()

    def _on_all(self, on: bool) -> None:
        if on:
            self._set(None)
        else:
            self._sync_boxes()                              # "Todas" no se puede desmarcar sin elegir otra cuenta

    def _on_one_toggled(self, account_id: int, _on: bool) -> None:
        self._on_one(account_id)

    def _on_one(self, account_id: int) -> None:
        box = self._boxes[account_id]
        current = set(self._ids) if self._ids is not None else {i for i, _ in self._accounts}
        if box.isChecked():
            current.add(account_id)
        else:
            current.discard(account_id)
        self._set(current)

    def _sync_boxes(self) -> None:
        """Pone las casillas como dice la seleccion, sin disparar sus senales."""
        everything = self._ids is None
        if self._all_box is not None:
            self._all_box.blockSignals(True)
            self._all_box.setChecked(everything)
            self._all_box.blockSignals(False)
        for account_id, box in self._boxes.items():
            box.blockSignals(True)
            box.setChecked(everything or account_id in (self._ids or set()))
            box.blockSignals(False)

    # ------------------------------------------------------------------ texto
    def label_text(self) -> str:
        total = len(self._accounts)
        if self._ids is None:
            return tr("Todas las cuentas")
        if len(self._ids) == 1:
            return self.single_name()
        return tr("{n} de {total} cuentas").format(n=len(self._ids), total=total)

    def description(self) -> str:
        """Para el subtitulo de la pagina: el nombre de la cuenta, o cuantas cuentas se suman."""
        if self._ids is not None and len(self._ids) == 1:
            return self.single_name()
        n = len(self._accounts) if self._ids is None else len(self._ids)
        return trn("{n} cuenta", "{n} cuentas", n).format(n=n)

    def _refresh_label(self) -> None:
        self.setText(self.label_text())
