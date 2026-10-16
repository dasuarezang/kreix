"""Cuadro para cambiar la contrasena maestra."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from core.i18n import tr
from ui.widgets.brand_dialog import BrandDialog
from ui.widgets.strength_meter import StrengthMeter
from data.vault import MIN_PASSWORD

# Aplica el cambio: devuelve None si fue bien o el mensaje de error que hay que mostrar.
Apply = Callable[[str, str], str | None]


def _field(placeholder: str) -> QLineEdit:
    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    edit.setPlaceholderText(placeholder)
    edit.setAccessibleName(placeholder)
    return edit


class ChangePasswordDialog(BrandDialog):
    def __init__(self, apply: Apply, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._apply = apply
        self.setWindowTitle(tr("Cambiar contraseña maestra"))
        self.setMinimumWidth(460)
        self.current = _field(tr("Contraseña actual"))
        self.new = _field(tr("Contraseña nueva"))
        self.again = _field(tr("Repite la contraseña nueva"))
        self.meter = StrengthMeter()
        self.new.textChanged.connect(self.meter.set_password)
        self.error = QLabel()
        self.error.setObjectName("LockError")
        self.error.setWordWrap(True)
        self.error.hide()
        self.ok = QPushButton(tr("Cambiar contraseña"))
        self.ok.setObjectName("Primary")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._submit)
        cancel = QPushButton(tr("Cancelar"))
        cancel.clicked.connect(self.reject)
        for edit in (self.current, self.new, self.again):
            edit.returnPressed.connect(self._submit)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        col = self.frame(tr("Cambiar contraseña maestra"),
                         tr("Tus datos se vuelven a cifrar con la contraseña nueva. Si la olvidas, no hay forma de recuperarlos."))
        for w in (self.current, self.new, self.meter, self.again, self.error):
            col.addWidget(w)
        col.addSpacing(4)
        col.addLayout(row)
        self.current.setFocus()

    def _fail(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()

    def _submit(self) -> None:
        if not self.current.text():
            return self._fail(tr("Escribe la contraseña actual."))
        if len(self.new.text()) < MIN_PASSWORD:
            return self._fail(tr("Usa al menos {n} caracteres.").format(n=MIN_PASSWORD))
        if self.new.text() != self.again.text():
            return self._fail(tr("Las contraseñas no coinciden."))
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            message = self._apply(self.current.text(), self.new.text())
        finally:
            QGuiApplication.restoreOverrideCursor()
        if message is None:
            self.accept()
        else:
            self._fail(message)
