"""Los dos perros del cielo de Inicio: Blitzen (un cavalier king charles negro y fuego, de orejas largas) y Black (un perrito
negro y fuego de orejas cortas caidas y collar claro).

De dia estan junto al horizonte, mirando al sol: Blitzen sentado, meneando la cola, y Black tumbado con la cabeza levantada,
parpadeando. De noche duermen hechos un ovillo, juntos, con la oreja de Blitzen por encima de Black, y respiran despacio.

Son siluetas de trazo suave, pequenas y con los colores de la marca (el rojo fuego del logotipo es el fuego de sus manchas):
lo justo para reconocerlos sin que parezca otra aplicacion. Todo el dibujo es geometria propia (curvas), sin imagenes.
Las coordenadas son locales (el suelo en y=0, hacia arriba es negativo) y los perros miran a la derecha; el cielo los refleja.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

Point = tuple[float, float]


def smooth(points: list[Point], closed: bool = True, tension: float = 1.0) -> QPainterPath:
    """Una curva suave que pasa por todos los puntos (Catmull-Rom convertida a curvas de Bezier)."""
    n = len(points)
    path = QPainterPath()
    path.moveTo(*points[0])
    last = n if closed else n - 1
    for i in range(last):
        p0 = points[(i - 1) % n] if (closed or i > 0) else points[0]
        p1, p2 = points[i % n], points[(i + 1) % n]
        p3 = points[(i + 2) % n] if (closed or i + 2 < n) else points[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6 * tension, p1[1] + (p2[1] - p0[1]) / 6 * tension)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6 * tension, p2[1] - (p3[1] - p1[1]) / 6 * tension)
        path.cubicTo(QPointF(*c1), QPointF(*c2), QPointF(*p2))
    if closed:
        path.closeSubpath()
    return path


@dataclass(frozen=True, slots=True)
class DogColors:
    coat: QColor            # el negro del pelo
    coat_soft: QColor       # un negro algo mas claro, para separar la oreja del cuerpo
    rim: QColor             # filo claro que los separa del fondo oscuro
    fire: QColor            # el fuego de sus manchas: el rojo anaranjado de la marca
    collar: QColor          # el collar claro de Black
    eye: QColor
    nose: QColor


def colors(dark: bool) -> DogColors:
    if dark:
        return DogColors(QColor("#0B0D10"), QColor("#161A20"), QColor(150, 165, 185, 85), QColor("#E5652B"), QColor("#EADFC8"),
                         QColor("#FFD9A0"), QColor("#06070A"))
    return DogColors(QColor("#16191E"), QColor("#262B33"), QColor(255, 255, 255, 0), QColor("#C9501B"), QColor("#F4EAD5"),
                     QColor("#FFD9A0"), QColor("#0A0B0D"))


def _fill(p: QPainter, path: QPainterPath, color: QColor, rim: QColor | None = None, width: float = 0.4) -> None:
    p.setBrush(color)
    if rim is not None and rim.alpha() > 0:
        pen = QPen(rim, width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
    else:
        p.setPen(Qt.PenStyle.NoPen)
    p.drawPath(path)


def _dot(p: QPainter, x: float, y: float, rx: float, ry: float | None, color: QColor) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(x, y), rx, ry if ry is not None else rx)


# ======================================================================================= Blitzen (cavalier sentado)
_BLITZEN = {
    "tail": [(-5.0, -2.6), (-8.4, -3.8), (-10.6, -2.4), (-9.6, -0.7), (-6.0, -0.4)],
    "body": [(-6.2, 0.0), (-6.9, -4.0), (-5.6, -8.2), (-3.0, -11.0), (0.6, -12.0), (2.9, -10.4), (3.7, -7.0), (3.9, -3.0), (3.5, 0.0)],
    "hind": [(-5.8, 0.0), (-6.0, -2.6), (-4.2, -4.2), (-2.4, -3.2), (-2.0, 0.0)],
    "neck": [(0.2, -13.6), (3.8, -13.4), (4.4, -9.5), (3.0, -7.5), (0.0, -8.5)],
    "foreleg": [(2.3, -6.0), (3.8, -5.9), (3.95, 0.0), (2.1, 0.0)],
    "head": [(-1.0, -16.2), (0.8, -19.0), (4.4, -19.4), (6.8, -17.2), (7.2, -14.8), (6.3, -13.0), (3.6, -12.2), (0.6, -12.8), (-1.3, -14.4)],
    "muzzle": [(4.6, -15.8), (6.8, -15.5), (7.2, -14.0), (6.4, -12.9), (4.2, -12.7), (3.7, -14.2)],
    "ear": [(0.6, -18.2), (-2.2, -16.6), (-3.8, -12.4), (-3.6, -8.4), (-2.2, -6.4), (-0.4, -7.6), (1.0, -11.0), (2.0, -14.4), (1.8, -17.2)],
}


def draw_blitzen_sitting(p: QPainter, c: DogColors, t: float = 0.0) -> None:
    """t: segundos. Mueve la cola (con rachas), respira y balancea un poco la oreja."""
    breathe = 1.0 + 0.012 * math.sin(t * 1.9)
    wag_on = max(0.0, math.sin(t * 0.9 - 0.4)) ** 0.5              # rachas: menea unos segundos, descansa otros
    wag = math.sin(t * 9.0) * 14.0 * wag_on
    p.save()
    p.translate(0, 0)
    p.save()                                                       # cola, detras de todo, con pivote en la grupa
    p.translate(-5.2, -1.6)
    p.rotate(wag)
    p.translate(5.2, 1.6)
    _fill(p, smooth(_BLITZEN["tail"]), c.coat, c.rim)
    p.restore()
    p.save()
    p.scale(1.0, breathe)                                          # el torso sube y baja un poquito
    _fill(p, smooth(_BLITZEN["body"]), c.coat, c.rim)
    _fill(p, smooth(_BLITZEN["neck"]), c.coat)
    _fill(p, smooth(_BLITZEN["hind"]), c.fire)
    _fill(p, smooth(_BLITZEN["foreleg"]), c.fire)
    p.restore()
    _fill(p, smooth(_BLITZEN["head"]), c.coat, c.rim)
    _fill(p, smooth(_BLITZEN["muzzle"]), c.fire)
    _dot(p, 7.2, -15.2, 1.05, 0.9, c.nose)
    _dot(p, 3.4, -18.1, 0.85, 0.6, c.fire)                         # la ceja de fuego
    _dot(p, 4.9, -16.6, 0.6, 0.6, c.eye)
    p.save()                                                       # la oreja larga, con un balanceo suave
    p.translate(0.6, -18.0)
    p.rotate(math.sin(t * 1.3) * 1.6)
    p.translate(-0.6, 18.0)
    _fill(p, smooth(_BLITZEN["ear"]), c.coat_soft, c.rim)
    p.restore()
    p.restore()


# ======================================================================================= Black (tumbado, cabeza alta)
_BLACK = {
    "tail": [(-9.2, -2.4), (-11.6, -4.2), (-12.2, -6.4), (-10.6, -6.0), (-10.0, -4.0), (-8.6, -1.4)],
    "body": [(-9.4, 0.0), (-10.0, -3.4), (-7.6, -6.6), (-2.5, -7.4), (1.8, -6.4), (3.6, -3.0), (3.2, 0.0)],
    "foreleg": [(3.4, -1.8), (8.4, -1.9), (9.5, -0.9), (8.7, 0.0), (3.4, 0.0)],
    "head": [(2.0, -9.6), (4.2, -11.8), (7.6, -11.4), (9.8, -9.0), (10.0, -6.9), (8.6, -5.2), (5.4, -4.8), (2.8, -6.2)],
    "muzzle": [(6.6, -8.6), (9.6, -8.4), (10.0, -6.8), (8.7, -5.3), (6.0, -5.2), (5.4, -6.8)],
    "ear": [(2.8, -11.2), (1.5, -9.4), (2.0, -7.4), (3.6, -7.6), (4.6, -9.4), (4.4, -11.0)],
    "paw": [(8.1, -1.4), (9.7, -1.0), (9.0, 0.0), (7.9, 0.0)],
    "collar": [(2.7, -6.6), (4.7, -7.0), (5.6, -5.0), (3.5, -4.2)],
}


def draw_black_lying(p: QPainter, c: DogColors, t: float = 0.0) -> None:
    """Parpadea de vez en cuando, mueve la oreja y respira."""
    breathe = 1.0 + 0.018 * math.sin(t * 2.1 + 1.0)
    blink = ((t + 1.7) % 4.3) < 0.14                                        # un parpadeo corto cada ~4 s
    twitch = max(0.0, math.sin(t * 0.7 + 2.0)) ** 8 * 6.0           # la oreja se mueve de tarde en tarde
    wag = math.sin(t * 7.0) * 9.0 * (max(0.0, math.sin(t * 0.55 + 1.2)) ** 6)
    p.save()
    p.save()
    p.translate(-9.0, -2.2)
    p.rotate(wag)
    p.translate(9.0, 2.2)
    _fill(p, smooth(_BLACK["tail"]), c.coat, c.rim)
    p.restore()
    p.save()
    p.scale(1.0, breathe)
    _fill(p, smooth(_BLACK["body"]), c.coat, c.rim)
    p.restore()
    _fill(p, smooth(_BLACK["foreleg"]), c.fire)
    _fill(p, smooth(_BLACK["paw"]), QColor("#C9CED6"))
    _fill(p, smooth(_BLACK["head"]), c.coat, c.rim)
    _fill(p, smooth(_BLACK["muzzle"]), c.fire)
    _fill(p, smooth(_BLACK["collar"]), c.collar)
    _dot(p, 9.9, -7.9, 0.95, 0.8, c.nose)
    _dot(p, 6.4, -10.0, 0.7, 0.5, c.fire)
    if not blink:
        _dot(p, 7.6, -9.0, 0.5, 0.5, c.eye)
    else:
        p.setPen(QPen(c.eye, 0.35))
        p.drawLine(QPointF(7.1, -9.0), QPointF(8.1, -9.0))
    p.save()
    p.translate(3.0, -10.4)
    p.rotate(twitch)
    p.translate(-3.0, 10.4)
    _fill(p, smooth(_BLACK["ear"]), c.coat_soft, c.rim)
    p.restore()
    p.restore()


# ======================================================================================= los dos durmiendo, juntos
_NIGHT = {
    "blitzen_body": [(-13.0, 0.0), (-14.0, -3.6), (-11.2, -7.2), (-5.4, -8.8), (0.6, -7.8), (3.8, -4.6), (3.6, 0.0)],
    "blitzen_head": [(-0.2, -4.6), (1.8, -6.4), (5.0, -6.0), (6.6, -4.2), (6.2, -2.0), (3.6, -1.4), (0.6, -2.2)],
    "blitzen_muzzle": [(3.6, -3.6), (6.4, -3.8), (6.7, -2.4), (5.8, -1.5), (3.8, -1.5)],
    "blitzen_ear": [(0.6, -5.8), (-1.2, -4.0), (-1.6, -0.9), (0.2, -0.5), (2.4, -1.2), (3.0, -3.6), (2.2, -5.4)],
    "blitzen_paw": [(5.0, -0.9), (8.4, -1.0), (8.8, 0.0), (5.0, 0.0)],
    "black_body": [(2.0, 0.0), (1.6, -3.0), (3.6, -6.2), (8.2, -7.6), (13.0, -6.2), (15.4, -3.0), (15.2, 0.0)],
    "black_head": [(13.4, -1.6), (14.6, -3.6), (17.4, -3.8), (18.6, -2.0), (18.0, -0.3), (15.4, 0.0), (13.8, -0.6)],
    "black_muzzle": [(16.4, -1.9), (18.5, -1.9), (18.8, -0.6), (17.4, 0.0), (15.8, 0.0)],
    "black_ear": [(14.4, -3.6), (13.4, -2.4), (13.8, -0.8), (15.0, -1.2), (15.6, -2.8)],
    "black_collar": [(11.6, -7.0), (13.6, -5.4), (14.0, -3.4), (12.4, -3.8), (11.2, -5.4)],
    "black_tail": [(2.6, -1.8), (0.6, -2.6), (-0.4, -1.2), (1.4, -0.2)],
}


def draw_sleeping(p: QPainter, c: DogColors, t: float = 0.0) -> None:
    """Los dos hechos un ovillo, uno contra otro; respiran despacio, cada uno a su ritmo."""
    big = 1.0 + 0.022 * math.sin(t * 1.2)
    small = 1.0 + 0.028 * math.sin(t * 1.5 + 1.1)
    p.save()
    p.save()
    p.scale(1.0, small)                                             # Black, delante, pegado a Blitzen
    _fill(p, smooth(_NIGHT["black_body"]), c.coat, c.rim)
    _fill(p, smooth(_NIGHT["black_tail"]), c.coat, c.rim)
    p.restore()
    _fill(p, smooth(_NIGHT["black_collar"]), c.collar)
    _fill(p, smooth(_NIGHT["black_head"]), c.coat, c.rim)
    _fill(p, smooth(_NIGHT["black_muzzle"]), c.fire)
    _dot(p, 18.6, -1.1, 0.7, 0.55, c.nose)
    _dot(p, 15.9, -3.1, 0.55, 0.4, c.fire)
    _fill(p, smooth(_NIGHT["black_ear"]), c.coat_soft, c.rim)
    p.save()
    p.scale(1.0, big)                                               # Blitzen
    _fill(p, smooth(_NIGHT["blitzen_body"]), c.coat, c.rim)
    p.restore()
    _fill(p, smooth(_NIGHT["blitzen_paw"]), c.fire)
    _fill(p, smooth(_NIGHT["blitzen_head"]), c.coat, c.rim)
    _fill(p, smooth(_NIGHT["blitzen_muzzle"]), c.fire)
    _dot(p, 6.5, -2.7, 0.8, 0.65, c.nose)
    _dot(p, 3.6, -5.2, 0.65, 0.45, c.fire)
    _fill(p, smooth(_NIGHT["blitzen_ear"]), c.coat_soft, c.rim)
    p.restore()


# ======================================================================================= escena
SIZE = 1.3          # cuanto se amplian los dibujos en el cielo (lo justo para que se reconozcan)


def paint_day(p: QPainter, dark: bool, t: float, ground: float, blitzen_x: float, black_x: float) -> None:
    """Blitzen sentado y Black tumbado, mirando a la izquierda (hacia el saludo y el amanecer)."""
    c = colors(dark)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for x, draw in ((black_x, draw_black_lying), (blitzen_x, draw_blitzen_sitting)):
        p.save()
        p.translate(x, ground)
        p.scale(-SIZE, SIZE)                                       # los dibujos miran a la derecha: se reflejan
        draw(p, c, t)
        p.restore()
    p.restore()


def paint_night(p: QPainter, dark: bool, t: float, ground: float, center_x: float) -> None:
    c = colors(dark)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(center_x, ground)
    p.scale(-SIZE, SIZE)
    draw_sleeping(p, c, t)
    p.restore()
    _paint_zzz(p, dark, t, center_x - 2, ground - 15)


def _paint_zzz(p: QPainter, dark: bool, t: float, x: float, y: float) -> None:
    """Dos z pequenas que suben y se desvanecen, una detras de otra."""
    color = QColor("#B9C4FF" if dark else "#5B67B8")
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for k, (size, delay) in enumerate(((2.2, 0.0), (3.2, 1.6))):
        phase = ((t * 0.35 + delay / 3.2) % 1.0)
        alpha = math.sin(math.pi * phase) ** 1.5
        if alpha <= 0.02:
            continue
        c = QColor(color)
        c.setAlphaF(0.85 * alpha)
        pen = QPen(c, 0.5)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        cx, cy = x - phase * 4.0 - k * 1.5, y - phase * 9.0
        path = QPainterPath()
        path.moveTo(cx - size / 2, cy - size / 2)
        path.lineTo(cx + size / 2, cy - size / 2)
        path.lineTo(cx - size / 2, cy + size / 2)
        path.lineTo(cx + size / 2, cy + size / 2)
        p.drawPath(path)
    p.restore()
