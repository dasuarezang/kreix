"""Bloquear Kreix cuando Windows se bloquea (Win+L, cerrar sesion) o el equipo se suspende.

Windows avisa de ambas cosas con mensajes a las ventanas: `WM_POWERBROADCAST` (suspension, a todas las ventanas) y
`WM_WTSSESSION_CHANGE` (bloqueo de la sesion, solo a quien se registra). Se escuchan con un filtro de eventos nativos de Qt
y una ventana oculta que se registra para el segundo. Fuera de Windows no hace nada.
"""
from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, Qt
from PySide6.QtWidgets import QWidget

WM_POWERBROADCAST = 0x0218
PBT_APMSUSPEND = 0x0004
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
NOTIFY_FOR_THIS_SESSION = 0


def should_lock(message: int, wparam: int) -> bool:
    """True si el mensaje de Windows es "el equipo se suspende" o "la sesion se ha bloqueado"."""
    return (message == WM_POWERBROADCAST and wparam == PBT_APMSUSPEND) or (
        message == WM_WTSSESSION_CHANGE and wparam == WTS_SESSION_LOCK)


class SessionWatcher(QAbstractNativeEventFilter):
    """`on_event()` se llama (sin argumentos) cuando hay que bloquear. Debe instalarse con `app.installNativeEventFilter`."""

    def __init__(self, on_event: Callable[[], None]) -> None:
        super().__init__()
        self._on_event = on_event
        self._anchor: QWidget | None = None
        self._registered = False

    def start(self) -> None:
        """Se registra para recibir los avisos de bloqueo de la sesion (la suspension llega sin registrarse)."""
        if sys.platform != "win32" or self._registered:
            return
        try:
            self._anchor = QWidget()
            self._anchor.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            hwnd = int(self._anchor.winId())                     # ventana nativa que nunca se ve
            self._registered = bool(ctypes.windll.wtsapi32.WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION))
        except Exception:                                        # pragma: no cover - sin permiso o sin la biblioteca
            self._registered = False

    def stop(self) -> None:
        if self._registered and self._anchor is not None and sys.platform == "win32":
            try:
                ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(int(self._anchor.winId()))
            except Exception:                                    # pragma: no cover
                pass
        self._registered = False
        if self._anchor is not None:
            self._anchor.deleteLater()
            self._anchor = None

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if should_lock(msg.message, msg.wParam):
                self._on_event()
        return False, 0
