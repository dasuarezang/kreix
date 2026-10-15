"""Iconos vectoriales propios (trazo redondeado), con el color que se les pida.

Se dibujan como SVG y se rasterizan a la densidad de la pantalla, asi se ven nitidos
y cambian de color con el tema. Sin emojis ni dependencias externas.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ui.theme import Palette


def _gear() -> str:
    """Engranaje de 8 dientes: contorno + circulo central."""
    teeth, outer, inner = 8, 10.2, 7.4
    points: list[str] = []
    for i in range(teeth):
        base = 2 * math.pi * i / teeth
        step = 2 * math.pi / teeth
        for frac, radius in ((0.0, inner), (0.18, outer), (0.50 - 0.18, outer), (0.50, inner)):
            angle = base + step * frac - step / 4
            points.append(f"{12 + radius * math.cos(angle):.2f},{12 + radius * math.sin(angle):.2f}")
    return f'<polygon points="{" ".join(points)}"/><circle cx="12" cy="12" r="3.2"/>'


_SHAPES = {
    "gear": _gear(),
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.1 9.2a3 3 0 0 1 5.8 1c0 2-2.9 2.6-2.9 4.4"/>'
            '<circle cx="12" cy="18" r="0.6" fill="currentColor"/>',
    "upload": '<path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/><path d="M8 8l4-4 4 4"/><path d="M12 4v12"/>',
    "download": '<path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/><path d="M8 11l4 4 4-4"/><path d="M12 3v12"/>',
    "sun": '<circle cx="12" cy="12" r="4"/>'
           + "".join(
               f'<path d="M{12 + 7.2 * math.cos(a):.2f} {12 + 7.2 * math.sin(a):.2f}'
               f'L{12 + 9.6 * math.cos(a):.2f} {12 + 9.6 * math.sin(a):.2f}"/>'
               for a in (math.radians(d) for d in range(0, 360, 45))
           ),
    "moon": '<path d="M20.5 14.2A8.5 8.5 0 1 1 9.8 3.5a6.7 6.7 0 0 0 10.7 10.7z"/>',
    # secciones de la ayuda
    "pie": '<circle cx="12" cy="12" r="9.5"/><path d="M12 2.5V12h9.5"/><path d="M12 12l-6.7 6.7"/>',
    "card": '<rect x="2.5" y="5" width="19" height="14" rx="2.5"/><path d="M2.5 10h19"/><path d="M6.5 15h4"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "percent": '<path d="M19 5L5 19"/><circle cx="6.8" cy="6.8" r="2.6"/><circle cx="17.2" cy="17.2" r="2.6"/>',
    "alert": '<path d="M10.3 4L2.5 17.5A2 2 0 0 0 4.2 20.5h15.6a2 2 0 0 0 1.7-3L13.7 4a2 2 0 0 0-3.4 0z"/>'
             '<path d="M12 9.5v4"/><circle cx="12" cy="17" r="0.6" fill="currentColor"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2.5H20v19H6.5A2.5 2.5 0 0 1 4 19V5a2.5 2.5 0 0 1 2.5-2.5z"/>',
    "back": '<path d="M19 12H5"/><path d="M11 5l-7 7 7 7"/>',
    "chevron": '<path d="M9 5l7 7-7 7"/>',
    # grupo "Datos": una pila de discos (almacen de tus datos)
    "home": '<path d="M4 11.2L12 4l8 7.2"/><path d="M6.2 9.8V19h11.6V9.8"/>',
    "database": '<ellipse cx="12" cy="5.5" rx="8" ry="3"/><path d="M4 5.5v6.5c0 1.7 3.6 3 8 3s8-1.3 8-3V5.5"/>'
                '<path d="M4 12v6.5c0 1.7 3.6 3 8 3s8-1.3 8-3V12"/>',
}


def _svg(name: str, color: str, stroke: float) -> bytes:
    body = _SHAPES[name].replace("currentColor", color)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    ).encode("utf-8")


def pixmap(name: str, color: str, size: int = 20, stroke: float = 1.35) -> QPixmap:
    screen = QGuiApplication.primaryScreen()
    dpr = max(screen.devicePixelRatio(), 1.0) if screen else 1.0
    pix = QPixmap(int(size * dpr), int(size * dpr))
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(_svg(name, color, stroke))).render(painter, QRectF(0, 0, size * dpr, size * dpr))
    painter.end()
    pix.setDevicePixelRatio(dpr)
    return pix


def button_icon(name: str, palette: Palette, size: int = 18) -> QIcon:
    """Icono para un boton checkable: apagado (gris), encendido (sobre el acento) y al pasar el raton."""
    icon = QIcon()
    off, hover, on = palette.muted, palette.text, palette.on_accent
    icon.addPixmap(pixmap(name, off, size), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(pixmap(name, hover, size), QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(pixmap(name, on, size), QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(pixmap(name, on, size), QIcon.Mode.Active, QIcon.State.On)
    return icon


NAMES = tuple(_SHAPES)
