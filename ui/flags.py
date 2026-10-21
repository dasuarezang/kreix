"""Banderas redondas de los idiomas: Espana (castellano), Cataluna (catalan, la senyera) y Reino Unido (ingles).

Se dibujan con QPainter sobre un cuadrado y se recortan en circulo, asi que son nitidas a cualquier tamano.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap

SPAIN_RED = QColor("#AA151B")
SPAIN_YELLOW = QColor("#F1BF00")
SENYERA_RED = QColor("#DA121A")
SENYERA_YELLOW = QColor("#FCDD09")
UK_BLUE = QColor("#012169")
UK_RED = QColor("#C8102E")
WHITE = QColor("#FFFFFF")

_cache: dict[tuple[str, int, float], QPixmap] = {}


def _paint_spain(p: QPainter, s: float) -> None:
    """Rojo, amarillo, rojo en franjas horizontales 1:2:1."""
    p.fillRect(QRectF(0, 0, s, s), SPAIN_RED)
    p.fillRect(QRectF(0, s / 4, s, s / 2), SPAIN_YELLOW)


def _paint_catalonia(p: QPainter, s: float) -> None:
    """La senyera: cuatro franjas rojas sobre oro (nueve franjas en total, cinco doradas y cuatro rojas)."""
    p.fillRect(QRectF(0, 0, s, s), SENYERA_YELLOW)
    stripe = s / 9
    for i in (1, 3, 5, 7):
        p.fillRect(QRectF(0, i * stripe, s, stripe), SENYERA_RED)


def _paint_uk(p: QPainter, s: float) -> None:
    """Union Jack: cruz de San Andres (blanca con la roja fina), cruz de San Jorge y fondo azul."""
    p.fillRect(QRectF(0, 0, s, s), UK_BLUE)
    center = s / 2
    for color, width in ((WHITE, s * 0.20), (UK_RED, s * 0.08)):
        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        p.drawLine(QPointF(-s, -s), QPointF(2 * s, 2 * s))
        p.drawLine(QPointF(2 * s, -s), QPointF(-s, 2 * s))
    p.setPen(Qt.PenStyle.NoPen)
    p.fillRect(QRectF(center - s * 0.17, 0, s * 0.34, s), WHITE)
    p.fillRect(QRectF(0, center - s * 0.17, s, s * 0.34), WHITE)
    p.fillRect(QRectF(center - s * 0.10, 0, s * 0.20, s), UK_RED)
    p.fillRect(QRectF(0, center - s * 0.10, s, s * 0.20), UK_RED)


PAINTERS = {"es": _paint_spain, "ca": _paint_catalonia, "en": _paint_uk}


def flag_pixmap(code: str, size: int = 24) -> QPixmap:
    """La bandera del idioma dentro de un circulo, con un aro fino para que se vea sobre cualquier fondo."""
    screen = QGuiApplication.primaryScreen()
    dpr = max(screen.devicePixelRatio(), 1.0) if screen else 1.0
    key = (code, size, dpr)
    if key in _cache:
        return _cache[key]
    pixel = round(size * dpr)
    pix = QPixmap(pixel, pixel)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    circle = QPainterPath()
    circle.addRoundedRect(QRectF(0.5, 0.5, pixel - 1, pixel - 1), pixel * 0.14, pixel * 0.14)
    p.setClipPath(circle)
    PAINTERS.get(code, _paint_spain)(p, float(pixel))
    p.setClipping(False)
    rim = QPen(QColor(0, 0, 0, 60), max(1.0, pixel / 24))
    p.setPen(rim)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(0.5, 0.5, pixel - 1, pixel - 1), pixel * 0.14, pixel * 0.14)
    p.end()
    pix.setDevicePixelRatio(dpr)
    _cache[key] = pix
    return pix


def flag_icon(code: str, size: int = 24) -> QIcon:
    return QIcon(flag_pixmap(code, size))
