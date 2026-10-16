"""Bloqueo automatico: tras unos minutos sin tocar el equipo (o al minimizar) Kreix esconde todo y vuelve a pedir la
contrasena maestra. Los datos ya estan en memoria, asi que desbloquear solo compara la contrasena con la del almacen.

Se vigila con un reloj de un segundo (nada de filtros de eventos: no cuestan rendimiento). La inactividad es la del
sistema (teclado y raton en cualquier programa); si el sistema no la da, se usa el movimiento del cursor.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget

from core.i18n import tr
from core.throttle import AttemptThrottle
from services.settings_service import AppSettings
from ui import idle
from ui.lock_screen import LockDialog, LockMode

CHECK_MS = 1000


class AutoLock(QObject):
    def __init__(self, store, settings: Callable[[], AppSettings], main_window: Callable[[], QMainWindow | None],
                 parent: QObject | None = None, clock: Callable[[], float] = time.monotonic,
                 idle_seconds: Callable[[], float | None] = idle.system_idle_seconds) -> None:
        super().__init__(parent)
        self._store = store
        self._settings = settings
        self._main_window = main_window
        self._clock = clock
        self._idle_seconds = idle_seconds
        self._throttle = AttemptThrottle()
        self._last_cursor = QCursor.pos()
        self._last_activity = clock()
        self._was_minimized = False
        self.locked = False
        self.lock_count = 0
        self.last_reason = ""
        self._timer = QTimer(self)
        self._timer.setInterval(CHECK_MS)
        self._timer.timeout.connect(self.check)
        self._deferred = QTimer(self)                  # el aviso de Windows llega dentro de su filtro: se bloquea un instante despues
        self._deferred.setSingleShot(True)
        self._deferred.timeout.connect(self._lock_for_session)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def session_event(self) -> None:
        """Windows se ha bloqueado o el equipo se suspende: si esta activado, Kreix tambien se bloquea."""
        if self._settings().lock_on_session and not self.locked:
            self._deferred.start(0)

    def _lock_for_session(self) -> None:
        self.lock("session")

    # ------------------------------------------------------------------ cuando bloquear
    def idle_for(self) -> float:
        """Segundos sin actividad."""
        seconds = self._idle_seconds()
        if seconds is not None:
            return seconds
        cursor = QCursor.pos()
        if cursor != self._last_cursor:
            self._last_cursor = cursor
            self._last_activity = self._clock()
        return self._clock() - self._last_activity

    def check(self) -> None:
        """Un vistazo: bloquea si lleva demasiado quieto o si la ventana acaba de minimizarse."""
        if self.locked:
            return
        window = self._main_window()
        settings = self._settings()
        minimized = window is not None and window.isMinimized()
        just_minimized = minimized and not self._was_minimized
        self._was_minimized = minimized
        if just_minimized and settings.lock_on_minimize:
            return self.lock("minimize")
        minutes = settings.auto_lock_minutes
        if minutes and self.idle_for() >= minutes * 60:
            self.lock("idle")

    # ------------------------------------------------------------------ bloquear / desbloquear
    def _attempt(self, password: str) -> str | None:
        if self._store.verify_password(password):
            return None
        return tr("Contraseña incorrecta. Inténtalo de nuevo.")

    def _hide_everything(self, keep: QWidget) -> list[QWidget]:
        """Cierra los menus y cuadros abiertos y esconde las ventanas, para que no se vea nada tras el bloqueo.
        Devuelve las ventanas que hay que volver a mostrar (los cuadros no: se cancelan)."""
        app = QApplication.instance()
        while (popup := app.activePopupWidget()) is not None:
            popup.close()
        hidden: list[QWidget] = []
        for widget in app.topLevelWidgets():
            if widget is keep or not widget.isVisible():
                continue
            if isinstance(widget, QDialog):
                widget.reject()                         # un cuadro a medias se descarta; esconderlo lo dejaria colgado
            else:
                widget.hide()
                hidden.append(widget)
        return hidden

    def lock(self, reason: str = "manual") -> bool:
        """Pide la contrasena. Devuelve True si se desbloqueo; si se pulsa Salir, cierra Kreix y devuelve False."""
        if self.locked:
            return False
        self.locked = True
        self.lock_count += 1
        self.last_reason = reason
        try:
            self._store.flush()                         # lo ultimo en disco antes de esconderlo todo
        except Exception:                               # pragma: no cover - disco lleno: el bloqueo no debe fallar por eso
            pass
        notes = {"idle": tr("Kreix se bloqueó porque llevabas un rato sin usarlo."),
                 "minimize": tr("Kreix se bloqueó al minimizarlo."),
                 "session": tr("Kreix se bloqueó porque Windows se bloqueó o el equipo se suspendió."), "manual": ""}
        window = self._main_window()
        was_minimized = window is not None and window.isMinimized()
        dialog = LockDialog(LockMode.UNLOCK, self._attempt, None, note=notes.get(reason, ""), allow_reset=False,
                            throttle=self._throttle)
        hidden = self._hide_everything(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            for widget in hidden:
                if widget is window and was_minimized:
                    widget.showNormal()
                else:
                    widget.show()
            if window is not None:
                window.raise_()
                window.activateWindow()
        else:
            QApplication.instance().quit()
        self._was_minimized = False
        self._last_activity = self._clock()
        self._last_cursor = QCursor.pos()
        self.locked = False
        return accepted
