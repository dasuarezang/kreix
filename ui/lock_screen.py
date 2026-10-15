"""Pantalla de bloqueo: pide la Contrasena Maestra antes de abrir (o crear) el almacen cifrado."""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

from core.i18n import tr
from data.vault import MIN_PASSWORD
from ui import assets


class LockMode(Enum):
    UNLOCK = "unlock"          # ya hay un almacen: pedir la contrasena
    CREATE = "create"          # primera vez: elegir contrasena
    MIGRATE = "migrate"        # hay datos de una version anterior sin cifrar: elegir contrasena para cifrarlos


# Intenta abrir/crear con la contrasena: devuelve None si todo fue bien o el mensaje de error que hay que mostrar.
Attempt = Callable[[str], str | None]


class LockDialog(QDialog):
    def __init__(self, mode: LockMode, attempt: Attempt, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = mode
        self._attempt = attempt
        self.reset_requested = False          # el usuario eligio borrar los datos y empezar de cero
        self.setWindowTitle("Kreix")
        self.setWindowIcon(assets.app_icon())
        self.setMinimumWidth(460)
        self.setModal(True)
        creating = mode is not LockMode.UNLOCK

        title = QLabel(tr("Crea tu contraseña maestra") if creating else tr("Kreix está bloqueado"))
        title.setObjectName("H1")
        title.setWordWrap(True)
        intro = QLabel(self._intro_text())
        intro.setObjectName("Muted")
        intro.setWordWrap(True)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText(tr("Contraseña maestra"))
        self.password.setAccessibleName(tr("Contraseña maestra"))
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm.setPlaceholderText(tr("Repite la contraseña"))
        self.confirm.setAccessibleName(tr("Repite la contraseña"))
        self.confirm.setVisible(creating)
        self.error = QLabel()
        self.error.setObjectName("LockError")
        self.error.setWordWrap(True)
        self.error.hide()

        self.ok = QPushButton(tr("Crear y abrir") if creating else tr("Desbloquear"))
        self.ok.setObjectName("Primary")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._submit)
        self.quit = QPushButton(tr("Salir"))
        self.quit.clicked.connect(self.reject)
        self.password.returnPressed.connect(self._submit)
        self.confirm.returnPressed.connect(self._submit)

        self.forgot = QPushButton(tr("He olvidado la contraseña"))
        self.forgot.setObjectName("LinkButton")
        self.forgot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forgot.setVisible(mode is LockMode.UNLOCK)
        self.forgot.clicked.connect(self._forgot)

        row = QHBoxLayout()
        row.addWidget(self.forgot)
        row.addStretch(1)
        row.addWidget(self.quit)
        row.addWidget(self.ok)
        col = QVBoxLayout(self)
        col.setContentsMargins(34, 30, 34, 26)
        col.setSpacing(12)
        col.addWidget(title)
        col.addWidget(intro)
        col.addSpacing(6)
        col.addWidget(self.password)
        col.addWidget(self.confirm)
        col.addWidget(self.error)
        col.addSpacing(6)
        col.addLayout(row)
        self.password.setFocus()

    def _intro_text(self) -> str:
        if self._mode is LockMode.UNLOCK:
            return tr("Tus datos están cifrados en este equipo. Escribe la contraseña maestra para abrirlos.")
        base = tr("Cifraremos todos tus datos con ella. Solo tú podrás abrirlos y no hay forma de recuperarla: si la olvidas, los datos no se pueden recuperar.")
        if self._mode is LockMode.MIGRATE:
            return tr("Kreix ha encontrado datos sin cifrar de una versión anterior.") + " " + base
        return base

    def _forgot(self) -> None:
        """Sin la contrasena los datos no se pueden descifrar: la unica salida es borrarlos y empezar de cero."""
        answer = QMessageBox.warning(
            self, tr("Borrar todos los datos"),
            tr("Sin la contraseña maestra no hay forma de recuperar tus datos. Si sigues, se borrarán para siempre "
               "los movimientos, cuentas e inversiones guardados y podrás empezar de cero con una contraseña nueva "
               "e importar de nuevo tus extractos. ¿Quieres borrarlos?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.reset_requested = True
            self.reject()

    def _show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()
        self.password.selectAll()
        self.password.setFocus()

    def _submit(self) -> None:
        text = self.password.text()
        if self._mode is not LockMode.UNLOCK:
            if len(text) < MIN_PASSWORD:
                return self._show_error(tr("Usa al menos {n} caracteres.").format(n=MIN_PASSWORD))
            if text != self.confirm.text():
                return self._show_error(tr("Las contraseñas no coinciden."))
        elif not text:
            return self._show_error(tr("Escribe la contraseña maestra."))
        self.ok.setEnabled(False)
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)       # derivar la clave tarda una fracción de segundo
        try:
            message = self._attempt(text)
        finally:
            QGuiApplication.restoreOverrideCursor()
            self.ok.setEnabled(True)
        if message is None:
            self.password.clear()
            self.confirm.clear()
            self.accept()
        else:
            self._show_error(message)
