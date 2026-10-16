"""Cuanto tiempo lleva la persona sin tocar el equipo (teclado o raton), para el bloqueo automatico."""
from __future__ import annotations

import sys


def system_idle_seconds() -> float | None:
    """Segundos desde la ultima pulsacion o movimiento en todo el sistema (Windows). None si no se puede saber."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        ticks = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
        return ((ticks - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except Exception:                                   # pragma: no cover - sin permiso o sin la libreria
        return None
