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
}


def _svg(name: str, color: str, stroke: float) -> bytes:
    body = _SHAPES[name].replace("currentColor", color)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    ).encode("utf-8")


def pixmap(name: str, color: str, size: int = 20, stroke: float = 1.9) -> QPixmap:
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


def button_icon(name: str, palette: Palette, size: int = 20) -> QIcon:
    """Icono para un boton checkable: apagado (gris), encendido (sobre el acento) y al pasar el raton."""
    icon = QIcon()
    off, hover, on = palette.muted, palette.text, palette.on_accent
    icon.addPixmap(pixmap(name, off, size), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(pixmap(name, hover, size), QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(pixmap(name, on, size), QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(pixmap(name, on, size), QIcon.Mode.Active, QIcon.State.On)
    return icon


NAMES = tuple(_SHAPES)
