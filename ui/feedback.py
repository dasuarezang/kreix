"""Confirmaciones y "Deshacer": cada cambio importante avisa con un mensaje breve y se puede revertir.

Deshacer se apoya en una instantanea de la base de datos tomada justo antes del cambio (la base es
pequena, asi que es instantaneo y vale para cualquier operacion: importar, reglas, presupuestos, borrados...).
Solo se puede deshacer el ultimo cambio, mientras su aviso siga en pantalla: un cambio nuevo sustituye al anterior.
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from services.transfer_service import TransferService
from ui.widgets.toast import Toast


class Feedback(QObject):
    restored = Signal()        # se ha deshecho un cambio: las vistas deben recargarse

    def __init__(self, transfer: TransferService, toast: Toast, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._transfer = transfer
        self._toast = toast
        self._pending: Path | None = None
        toast.undo_clicked.connect(self.undo)

    def snapshot(self) -> Path | None:
        """Copia de seguridad de los datos justo antes de un cambio. Si falla, el cambio sigue sin 'Deshacer'."""
        try:
            return self._transfer.snapshot()
        except Exception:                      # noqa: BLE001 - deshacer es un extra: nunca debe impedir la accion
            return None

    def notify(self, message: str, snapshot: Path | None = None) -> None:
        self._discard()
        self._pending = snapshot
        self._toast.show_message(message, undoable=snapshot is not None)

    def undo(self) -> bool:
        snapshot, self._pending = self._pending, None
        if snapshot is None:
            return False
        try:
            self._transfer.restore_snapshot(snapshot)
        finally:
            self.remove(snapshot)
        self._toast.show_message("Cambio deshecho")
        self.restored.emit()
        return True

    @property
    def can_undo(self) -> bool:
        return self._pending is not None

    def close(self) -> None:
        self._discard()

    def _discard(self) -> None:
        pending, self._pending = self._pending, None
        if pending is not None:
            self.remove(pending)

    @staticmethod
    def remove(path: Path) -> None:
        for suffix in ("", "-wal", "-shm"):
            with contextlib.suppress(OSError):
                os.remove(str(path) + suffix)


def snapshot_of(feedback: Feedback | None) -> Path | None:
    return feedback.snapshot() if feedback is not None else None


def tell(feedback: Feedback | None, message: str, snapshot: Path | None = None) -> None:
    if feedback is not None:
        feedback.notify(message, snapshot)
