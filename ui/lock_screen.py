"""Pantalla de bloqueo: pide la Contrasena Maestra antes de abrir (o crear) el almacen cifrado.

Es la primera cara de Kreix, asi que lleva su marca: el logotipo, las cuatro franjas de la K y el mismo fondo con
resplandor que la ventana principal. Al acertar la contrasena la pantalla no se cierra a ciegas: se queda con un
"Abriendo Kreix..." mientras la ventana principal se prepara y se cierra solo cuando esta lista (sin parpadeos).
"""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from core.i18n import tr, trn
from core.throttle import AttemptThrottle
from data.vault import MIN_PASSWORD
from ui import assets, theme
from ui.widgets.brand_dialog import BrandDialog
from ui.widgets.cards import StripeMark
from ui.widgets.strength_meter import StrengthMeter


class LockMode(Enum):
    UNLOCK = "unlock"          # ya hay un almacen: pedir la contrasena
    CREATE = "create"          # primera vez: elegir contrasena
    MIGRATE = "migrate"        # hay datos de una version anterior sin cifrar: elegir contrasena para cifrarlos


# Intenta abrir/crear con la contrasena: devuelve None si todo fue bien o el mensaje de error que hay que mostrar.
Attempt = Callable[[str], str | None]


class LockDialog(BrandDialog):
    def __init__(self, mode: LockMode, attempt: Attempt, parent: QWidget | None = None,
                 finish: Callable[[], None] | None = None, note: str = "", allow_reset: bool = True,
                 throttle: AttemptThrottle | None = None) -> None:
        """`finish` se ejecuta con la pantalla aun a la vista, una vez aceptada la contrasena (aqui se prepara la ventana).
        `note` es un aviso extra bajo la explicacion (p. ej. "Se bloqueo por inactividad"); `allow_reset` ofrece o no borrar
        los datos si se olvido la contrasena; `throttle` impone espera tras varios fallos (se comparte entre bloqueos)."""
        super().__init__(parent)
        self._mode = mode
        self._attempt = attempt
        self._finish = finish
        self._note = note
        self._throttle = throttle if throttle is not None else AttemptThrottle()
        self._cooldown = QTimer(self)
        self._cooldown.setInterval(250)
        self._cooldown.timeout.connect(self._tick)
        self.reset_requested = False          # el usuario eligio borrar los datos y empezar de cero
        self.setWindowTitle("Kreix")
        self.setWindowIcon(assets.app_icon())
        self.setFixedWidth(520)
        self.setModal(True)
        creating = mode is not LockMode.UNLOCK

        brand = QLabel()
        brand.setPixmap(assets.wordmark(theme.current(), 46))
        brand.setAccessibleName("Kreix")
        head = QHBoxLayout()
        head.addWidget(brand)
        head.addStretch(1)
        head.addWidget(StripeMark(78, 40), 0, Qt.AlignmentFlag.AlignTop)

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
        self.meter = StrengthMeter()
        self.password.textChanged.connect(self.meter.set_password)
        if not creating:
            self.confirm.hide()              # nunca setVisible(True) sin padre: abriria una ventana suelta
            self.meter.hide()
        self.error = QLabel()
        self.error.setObjectName("LockError")
        self.error.setWordWrap(True)
        self.error.hide()
        self.status = QLabel(tr("Abriendo Kreix…"))
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        self.status.hide()

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
        if mode is not LockMode.UNLOCK or not allow_reset:
            self.forgot.hide()
        self.forgot.clicked.connect(self._forgot)

        row = QHBoxLayout()
        row.addWidget(self.forgot)
        row.addStretch(1)
        row.addWidget(self.quit)
        row.addWidget(self.ok)

        card = QFrame()
        card.setObjectName("Card")
        form = QVBoxLayout(card)
        form.setContentsMargins(28, 26, 28, 22)
        form.setSpacing(12)
        form.addWidget(title)
        form.addWidget(intro)
        form.addSpacing(4)
        form.addWidget(self.password)
        form.addWidget(self.meter)
        form.addWidget(self.confirm)
        form.addWidget(self.error)
        form.addWidget(self.status)
        form.addSpacing(4)
        form.addLayout(row)

        footer = QLabel(tr("Todo se queda en este equipo, cifrado. Kreix no envía nada a ningún servidor."))
        footer.setObjectName("Small")
        footer.setWordWrap(True)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        col = QVBoxLayout(self)
        col.setContentsMargins(34, 30, 34, 24)
        col.setSpacing(22)
        col.addLayout(head)
        col.addWidget(card)
        col.addWidget(footer)
        self.password.setFocus()
        if self._throttle.wait_left() > 0:                  # un bloqueo anterior dejo una espera pendiente
            self._start_cooldown()

    def _intro_text(self) -> str:
        if self._mode is LockMode.UNLOCK:
            text = tr("Tus datos están cifrados en este equipo. Escribe la contraseña maestra para abrirlos.")
            return f"{self._note} {text}" if self._note else text
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

    def _busy(self, busy: bool) -> None:
        """Mientras se descifra y se prepara la ventana, la pantalla no cambia: solo se congela y avisa."""
        for widget in (self.password, self.confirm, self.ok, self.quit, self.forgot):
            widget.setEnabled(not busy)
        self.status.setVisible(busy)
        if busy:
            self.error.hide()
            QApplication.processEvents()

    # ------------------------------------------------------------------ espera tras varios fallos
    def _start_cooldown(self) -> None:
        for widget in (self.password, self.ok):
            widget.setEnabled(False)
        self.status.setVisible(True)
        self._tick()
        self._cooldown.start()

    def _tick(self) -> None:
        left = self._throttle.wait_left()
        if left <= 0:
            self._cooldown.stop()
            self.status.hide()
            for widget in (self.password, self.ok):
                widget.setEnabled(True)
            self.password.setFocus()
            return
        seconds = max(1, round(left + 0.49))
        self.status.setText(trn("Demasiados intentos. Podrás probar de nuevo en {n} segundo.",
                                "Demasiados intentos. Podrás probar de nuevo en {n} segundos.", seconds).format(n=seconds))
        self._fit_height()

    def _submit(self) -> None:
        if self._throttle.wait_left() > 0:
            return
        text = self.password.text()
        if self._mode is not LockMode.UNLOCK:
            if len(text) < MIN_PASSWORD:
                return self._show_error(tr("Usa al menos {n} caracteres.").format(n=MIN_PASSWORD))
            if text != self.confirm.text():
                return self._show_error(tr("Las contraseñas no coinciden."))
        elif not text:
            return self._show_error(tr("Escribe la contraseña maestra."))
        self._busy(True)
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)       # derivar la clave tarda una fracción de segundo
        try:
            message = self._attempt(text)
            if message is None and self._finish is not None:
                self._finish()                                              # con la pantalla aun a la vista
        finally:
            QGuiApplication.restoreOverrideCursor()
        if message is None:
            self._throttle.succeeded()
            self.accept()
            return
        self._busy(False)
        self._show_error(message)
        if self._mode is LockMode.UNLOCK and self._throttle.failed() > 0:
            self._start_cooldown()
