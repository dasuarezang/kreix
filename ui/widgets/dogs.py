"""Blitzen y Black de frente, en ilustracion plana de linea redondeada (el diseno de la propuesta 2, con los retoques finales).

Estilo (el de la referencia `estilo.jpg`): contorno redondeado de un solo trazo, rellenos planos y pocas lineas de detalle,
con la cara y las proporciones de cada perro:

* Blitzen, cavalier king charles negro y fuego: cabeza redondeada, orejas largas y onduladas, ojos grandes, cejas de fuego,
  mejillas de fuego y la sonrisa con la puntita de la lengua.
* Black, un perrito negro y fuego esbelto: orejas cortas plegadas hacia delante, ojos grandes con las cejas inclinadas, hocico
  de fuego y el collar crema con su anilla.

Cada cabeza se dibuja con una sola funcion (origen en el centro de la cabeza) y se usa igual de pie y durmiendo: las orejas son
las mismas, solo se tumban hacia los lados cuando duermen. Como los perros son negros, el contorno toma el color del texto del tema
(crema en oscuro, casi negro en claro) y el pelo es un carbon algo mas claro que el fondo.

Unidades: el suelo es y=0 y arriba es negativo. Blitzen mide unas 52 unidades de alto sentado; Black, unas 36.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
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
class Look:
    line: QColor        # el contorno
    coat: QColor        # pelo negro
    coat_ear: QColor    # el pelo de las orejas, un poco mas claro
    shade: QColor       # sombra suave (bajo las orejas y la barbilla)
    fire: QColor        # manchas de fuego
    fire_soft: QColor   # fuego mas claro (mejillas, hocico)
    cream: QColor       # collar y mechon blanco de Blitzen
    eye: QColor
    nose: QColor
    paw: QColor         # la punta clara de las patas de Black
    tongue: QColor
    grey: QColor        # la perilla gris de Black


def look(dark: bool) -> Look:
    if dark:
        return Look(QColor("#F1E8D8"), QColor("#2A2F38"), QColor("#3C424E"), QColor("#1D2128"), QColor("#E5652B"), QColor("#F08A4B"),
                    QColor("#F4EEDF"), QColor("#14110F"), QColor("#0B0B0D"), QColor("#D8DCE3"), QColor("#E98A8A"), QColor("#9AA0AB"))
    return Look(QColor("#17191D"), QColor("#2A2E36"), QColor("#474D59"), QColor("#1E2127"), QColor("#D4571F"), QColor("#E8793A"),
                QColor("#F8F2E4"), QColor("#14110F"), QColor("#0B0B0D"), QColor("#E4E7EC"), QColor("#E98A8A"), QColor("#9097A3"))


LINE_W = 1.0


def sym(right: list[Point]) -> list[Point]:
    """Una forma simetrica: se da la mitad derecha, de arriba a abajo (acabando en el eje), y se completa con la izquierda."""
    left = [(-x, y) for x, y in reversed(right)]
    return right + [pt for pt in left if abs(pt[0]) > 1e-6]


class Pen:
    """Pinta formas con el contorno de la ilustracion."""

    def __init__(self, p: QPainter, lk: Look, width: float = LINE_W) -> None:
        self.p, self.lk, self.width = p, lk, width

    def _stroke(self, width: float | None, color: QColor | None = None) -> QPen:
        pen = QPen(color or self.lk.line, width or self.width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def shape(self, points: list[Point], fill: QColor | None, outline: bool = True, width: float | None = None) -> None:
        self.p.setBrush(fill if fill is not None else Qt.BrushStyle.NoBrush)
        self.p.setPen(self._stroke(width) if outline else Qt.PenStyle.NoPen)
        self.p.drawPath(smooth(points, closed=True))

    def line(self, points: list[Point], width: float | None = None, color: QColor | None = None) -> None:
        self.p.setPen(self._stroke(width or self.width * 0.7, color))
        self.p.setBrush(Qt.BrushStyle.NoBrush)
        self.p.drawPath(smooth(points, closed=False))

    def ellipse(self, x: float, y: float, rx: float, ry: float, fill: QColor, outline: bool = False, width: float | None = None,
                angle: float = 0.0) -> None:
        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), rx, ry)
        self.p.save()
        self.p.translate(x, y)
        self.p.rotate(angle)
        self.p.setBrush(fill)
        self.p.setPen(self._stroke(width) if outline else Qt.PenStyle.NoPen)
        self.p.drawPath(path)
        self.p.restore()

    def eye(self, x: float, y: float, r: float, closed: float = 0.0) -> None:
        """Un ojo redondo con parpado superior y dos brillos. `closed` de 0 (abierto) a 1 (cerrado: un arco, como en la referencia)."""
        if closed >= 0.85:
            self.line([(x - r * 1.05, y + 0.1), (x, y + r * 0.7), (x + r * 1.05, y + 0.1)], width=self.width * 0.85)
            return
        ry = r * (1 - closed * 0.85)
        self.ellipse(x, y, r, ry, self.lk.eye)
        self.ellipse(x - r * 0.3, y - ry * 0.35, r * 0.3, r * 0.3, QColor("#FFFFFF"))
        self.ellipse(x + r * 0.4, y + ry * 0.33, r * 0.13, r * 0.13, QColor(255, 255, 255, 170))
        self.line([(x - r * 1.12, y - ry * 0.3), (x - r * 0.4, y - ry * 1.12), (x + r * 0.5, y - ry * 1.12), (x + r * 1.12, y - ry * 0.3)],
                  width=self.width * 0.8)


# ======================================================================================= cabezas (origen: el centro de la cabeza)
# La oreja larga de Blitzen: el mismo dibujo de pie y durmiendo. Se da la derecha; el origen es el centro de la cabeza.
_BLITZEN_EAR = [(7.0, -9.0), (11.2, -6.4), (14.2, -0.4), (15.4, 7.0), (16.0, 13.6), (14.6, 19.2), (12.4, 17.4), (11.0, 20.0),
                (9.6, 16.6), (8.6, 9.4), (8.0, 1.0), (7.4, -5.0)]
_BLITZEN_EAR_LINES = [[(11.2, -2.6), (12.4, 4.6), (12.0, 11.6)], [(9.8, 1.0), (10.2, 8.0)]]


def blitzen_head(pen: Pen, lk: Look, blink: float = 0.0, smile: float = 1.0, ear_swing: float = 0.0, ear_lay: float = 0.0) -> None:
    """Cabeza redondeada con las orejas largas. `ear_lay` (grados) tumba las orejas hacia los lados, como al dormir."""
    p = pen.p
    for sx in (-1, 1):
        p.save()
        p.translate(sx * 7.4, -7.0)                              # las orejas giran desde donde nacen
        p.rotate(sx * (ear_swing - ear_lay))
        p.translate(-sx * 7.4, 7.0)
        pen.shape([(sx * x, y) for x, y in _BLITZEN_EAR], lk.coat_ear)
        for line in _BLITZEN_EAR_LINES:
            pen.line([(sx * x, y) for x, y in line], width=0.5)
        p.restore()
    # cabeza redondeada
    pen.shape(sym([(0, -9.8), (6.4, -8.4), (9.1, -3.2), (9.0, 2.6), (6.6, 7.2), (3.4, 9.4), (0, 9.8)]), lk.coat)
    # mejillas y hocico de fuego
    pen.shape(sym([(0, 2.0), (2.8, 2.6), (5.2, 4.4), (5.6, 7.2), (3.6, 9.2), (0, 9.8)]), lk.fire_soft, outline=False)
    # cejas de fuego y ojos grandes
    for sx in (-1, 1):
        pen.ellipse(sx * 4.4, -3.6, 1.85, 1.1, lk.fire, angle=sx * -10)
        pen.eye(sx * 3.9, -0.6, 1.8, blink)
    # nariz, philtrum y boca con la lengua
    pen.shape([(-2.7, 3.6), (0, 2.8), (2.7, 3.6), (2.0, 5.8), (0, 6.6), (-2.0, 5.8)], lk.nose, outline=False)
    pen.ellipse(-0.8, 3.8, 0.6, 0.34, QColor(255, 255, 255, 150))
    pen.line([(0, 6.6), (0, 7.8)], width=0.5)
    pen.line([(-3.6, 7.4), (-2.0, 9.0), (0, 7.8), (2.0, 9.0), (3.6, 7.4)], width=0.55)
    if smile > 0.4:
        pen.shape([(-1.1, 8.6), (-0.9, 10.2), (0, 10.8), (0.9, 10.2), (1.1, 8.6)], lk.tongue, width=0.5)
        pen.line([(0, 8.8), (0, 10.2)], width=0.3)


def black_head(pen: Pen, lk: Look, blink: float = 0.0, ear_swing: float = 0.0) -> None:
    """Cabeza de Black: orejas cortas plegadas hacia delante, cejas inclinadas hacia dentro, ojos grandes y la perilla gris."""
    p = pen.p
    for sx in (-1, 1):
        p.save()
        p.translate(sx * 5.4, -6.0)
        p.rotate(sx * ear_swing)
        p.translate(-sx * 5.4, 6.0)
        pen.shape([(sx * 5.4, -6.8), (sx * 9.6, -5.6), (sx * 11.0, -0.8), (sx * 9.4, 2.0), (sx * 7.2, -0.2), (sx * 6.0, -3.8)], lk.coat_ear)
        pen.line([(sx * 7.2, -6.0), (sx * 9.0, -2.2), (sx * 9.6, 0.4)], width=0.4)
        p.restore()
    pen.shape(sym([(0, -7.6), (5.6, -6.6), (8.6, -2.0), (8.0, 3.4), (4.6, 6.8), (0, 7.6)]), lk.coat)
    pen.line([(-2.2, -5.2), (0, -5.8), (2.2, -5.2)], width=0.4)                  # arruga de la frente
    # hocico de fuego
    pen.shape(sym([(0, -0.6), (3.6, 0.2), (5.0, 3.0), (3.6, 5.8), (0, 6.8)]), lk.fire_soft, outline=False)
    for sx in (-1, 1):
        p.save()
        p.translate(sx * 3.4, -4.0)
        p.rotate(sx * -12)
        pen.ellipse(0, 0, 1.5, 0.95, lk.fire)
        p.restore()
        pen.eye(sx * 3.5, -2.0, 1.7, blink)
    pen.shape([(-2.4, 0.4), (0, -0.4), (2.4, 0.4), (1.7, 2.4), (0, 3.1), (-1.7, 2.4)], lk.nose, outline=False)
    pen.ellipse(-0.6, 0.6, 0.55, 0.32, QColor(255, 255, 255, 150))
    pen.line([(0, 3.1), (0, 4.2)], width=0.5)
    pen.line([(-2.6, 4.0), (-1.3, 5.0), (0, 4.2), (1.3, 5.0), (2.6, 4.0)], width=0.5)


# ======================================================================================= Blitzen, sentado, de frente
def blitzen_sitting(p: QPainter, lk: Look, t: float = 0.0, blink: float = 0.0, tilt: float = 0.0) -> None:
    pen = Pen(p, lk)
    wag = math.sin(t * 8.0) * 12.0 * max(0.0, math.sin(t * 0.9)) ** 0.5
    # cola, asomando por el lado
    p.save()
    p.translate(12.0, -2.5)
    p.rotate(-22 + wag)
    pen.shape([(0, 0), (3.5, -2.4), (8.5, -2.6), (12.5, -0.6), (9.5, 1.8), (4, 2.2)], lk.coat)
    pen.line([(4.5, -0.4), (8.5, -0.8)], width=0.5)
    p.restore()
    # cuerpo sentado: cuello, hombros, costillas y grupa
    pen.shape([(-5.6, -28), (-9.0, -23), (-11.0, -15), (-13.6, -5), (-12.6, -0.4), (0, 0.6), (12.6, -0.4), (13.6, -5), (11.0, -15), (9.0, -23), (5.6, -28)], lk.coat)
    # el pelo largo del pecho: tres mechones
    for dx, h in ((-5.2, 4.2), (0.0, 5.0), (5.2, 4.2)):
        pen.line([(dx - 1.9, -17.5), (dx - 0.7, -17.5 + h * 0.85), (dx, -17.5 + h), (dx + 0.7, -17.5 + h * 0.85), (dx + 1.9, -17.5)], width=0.55)
    # patas delanteras de fuego
    for sx in (-1, 1):
        pen.shape([(sx * 1.8, -15), (sx * 5.8, -15), (sx * 6.4, -6), (sx * 6.5, -1.6), (sx * 5.2, 0.2), (sx * 2.2, 0.2), (sx * 1.2, -1.6), (sx * 1.0, -6)], lk.fire)
        pen.line([(sx * 2.8, -1.0), (sx * 2.8, 0.1)], width=0.45)
        pen.line([(sx * 4.4, -1.0), (sx * 4.4, 0.1)], width=0.45)
    # cabeza (con la inclinacion curiosa de un cavalier)
    p.save()
    p.translate(0, -28.0)
    p.rotate(tilt)
    p.translate(0, 28.0)
    pen.shape([(-6.0, -29.5), (0, -27.4), (6.0, -29.5), (4.6, -27.0), (0, -25.6), (-4.6, -27.0)], lk.shade, outline=False)   # sombra bajo la barbilla
    p.translate(0, -39.0)
    blitzen_head(pen, lk, blink=blink, smile=1.0, ear_swing=math.sin(t * 1.3) * 1.8)
    p.restore()


# ======================================================================================= Black, sentado, de frente
def black_sitting(p: QPainter, lk: Look, t: float = 0.0, blink: float = 0.0, tilt: float = 0.0) -> None:
    pen = Pen(p, lk)
    wag = math.sin(t * 8.5) * 14.0 * max(0.0, math.sin(t * 0.7 + 1.5)) ** 0.5
    p.save()
    p.translate(-8.5, -2.0)
    p.rotate(20 - wag)
    pen.shape([(0, 0), (-3, -2.6), (-6.5, -2.4), (-8.2, 0.2), (-4.5, 1.7)], lk.coat)
    p.restore()
    # cuerpo compacto con el pecho ancho
    pen.shape([(-5.4, -19), (-8.4, -13.5), (-10.0, -6.5), (-9.2, -0.4), (0, 0.6), (9.2, -0.4), (10.0, -6.5), (8.4, -13.5), (5.4, -19)], lk.coat)
    # manchas de fuego del pecho
    for sx in (-1, 1):
        pen.shape([(sx * 1.0, -18.8), (sx * 5.2, -18.2), (sx * 6.2, -13.2), (sx * 3.4, -11.2), (sx * 1.0, -13.4)], lk.fire, outline=False)
    # patas de fuego con la punta clara
    for sx in (-1, 1):
        pen.shape([(sx * 1.5, -11.5), (sx * 5.0, -11.5), (sx * 5.5, -2.4), (sx * 4.8, 0.1), (sx * 1.4, 0.1), (sx * 1.0, -2.4)], lk.fire)
        pen.shape([(sx * 1.1, -2.4), (sx * 5.3, -2.4), (sx * 5.5, -0.2), (sx * 4.6, 0.3), (sx * 1.4, 0.3)], lk.paw, outline=False)
        pen.line([(sx * 3.1, -2.3), (sx * 3.1, 0.2)], width=0.4)
    # cabeza
    p.save()
    p.translate(0, -17.0)
    p.rotate(tilt)
    p.translate(0, 17.0)
    p.translate(0, -24.8)
    black_head(pen, lk, blink=blink, ear_swing=math.sin(t * 1.1 + 0.7) * 2.2 + max(0.0, math.sin(t * 0.7 + 2.0)) ** 8 * 6.0)
    p.restore()
    # collar claro con su anilla
    pen.shape([(-6.6, -18.4), (-3.4, -16.4), (0, -15.8), (3.4, -16.4), (6.6, -18.4), (6.3, -16.2), (3.2, -14.2), (0, -13.6), (-3.2, -14.2), (-6.3, -16.2)],
              lk.cream, width=0.8)
    pen.ellipse(0.6, -13.4, 1.0, 1.0, QColor(0, 0, 0, 0), outline=True, width=0.6)


# ======================================================================================= los dos durmiendo, juntos
def sleeping_pair(p: QPainter, lk: Look, t: float = 0.0) -> None:
    """Hechos un ovillo, uno contra otro: la misma cabeza de pie y durmiendo, con las orejas de Blitzen tumbadas. Ojos cerrados."""
    pen = Pen(p, lk)
    big = 1.0 + 0.02 * math.sin(t * 1.2)
    small = 1.0 + 0.028 * math.sin(t * 1.5 + 1.1)
    # cuerpos: dos cupulas detras de las cabezas (el de Black, delante del de Blitzen)
    p.save()
    p.scale(1.0, big)
    pen.shape([(-27, 0), (-28.5, -7), (-23, -14.5), (-14, -17), (-4, -14.5), (0, -7), (-0.5, 0)], lk.coat)
    p.restore()
    p.save()                                                                            # la cola de Blitzen, asomando a la izquierda
    p.translate(-26.0, -2.0)
    p.rotate(-math.sin(t * 1.2) * 3.0)
    pen.shape([(0, 0), (-3.4, -1.6), (-7.0, -0.4), (-6.4, 2.0), (-2.4, 2.4)], lk.coat)
    p.restore()
    p.save()
    p.scale(1.0, small)
    pen.shape([(-5, 0), (-5.5, -6), (-1, -11.5), (7, -13.5), (15, -11), (19.5, -5.5), (19, 0)], lk.coat)
    p.restore()
    # Blitzen: la cabeza apoyada encima del lomo de Black, con sus orejas largas colgando (las mismas de pie) hacia el suelo
    p.save()
    p.translate(-4.0, -17.0)
    p.rotate(-5)
    p.scale(0.85, 0.85)
    blitzen_head(pen, lk, blink=1.0, smile=0.0, ear_lay=8.0)
    p.restore()
    # Black: delante y abajo, con su collar
    p.save()
    p.translate(10.0, -8.2)
    p.scale(0.8, 0.8)
    black_head(pen, lk, blink=1.0)
    p.restore()
    pen.shape([(3.4, -2.6), (7.0, -1.8), (10.0, -1.5), (13.0, -1.8), (16.6, -2.6), (16.2, -0.6), (10.0, 0.0), (3.8, -0.6)], lk.cream, width=0.7)
    # unas z que suben
    for k, (size, delay) in enumerate(((2.4, 0.0), (3.4, 1.6))):
        phase = (t * 0.35 + delay / 3.2) % 1.0
        alpha = math.sin(math.pi * phase) ** 1.5
        c = QColor(lk.line)
        c.setAlphaF(0.8 * alpha)
        pen_z = QPen(c, 0.7)
        pen_z.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen_z.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen_z)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = 6 + phase * 6 + k * 3, -30 - phase * 10
        z = QPainterPath()
        z.moveTo(cx - size / 2, cy - size / 2)
        z.lineTo(cx + size / 2, cy - size / 2)
        z.lineTo(cx - size / 2, cy + size / 2)
        z.lineTo(cx + size / 2, cy + size / 2)
        p.drawPath(z)


# ======================================================================================= la escena del cielo de Inicio
SIZE = 0.8          # cuanto se reducen los dibujos (unidades de dibujo -> unidades del cielo) para que quepan en el horizonte
SLEEP_SIZE = 1.0


def _blink(t: float, offset: float) -> float:
    """Un parpadeo rapido cada cuatro segundos y pico (0 con el cielo quieto: t = 0 es la imagen sin animar)."""
    if t <= 0.0:
        return 0.0
    return 1.0 if ((t + offset) % 4.3) < 0.14 else 0.0


def _tilt(t: float, offset: float, amount: float) -> float:
    """Inclina la cabeza de vez en cuando, con calma, y la devuelve a su sitio."""
    return amount * max(0.0, math.sin(t * 0.45 + offset)) ** 3


def paint_day(p: QPainter, dark: bool, t: float, ground: float, center_x: float) -> None:
    """Blitzen y Black sentados, de cara a quien mira: parpadean, mueven la cola, las orejas y ladean la cabeza."""
    lk = look(dark)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for dx, draw, off, amount in ((-14.0, blitzen_sitting, 0.0, -7.0), (14.0, black_sitting, 1.7, 8.0)):
        p.save()
        p.translate(center_x + dx * SIZE, ground)
        p.scale(SIZE, SIZE)
        draw(p, lk, t, _blink(t, off), _tilt(t, off + 1.0, amount))
        p.restore()
    p.restore()


def paint_night(p: QPainter, dark: bool, t: float, ground: float, center_x: float) -> None:
    """Los dos hechos un ovillo, Blitzen con la cabeza sobre Black, respirando y con sus z."""
    lk = look(dark)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(center_x, ground)
    p.scale(SLEEP_SIZE, SLEEP_SIZE)
    sleeping_pair(p, lk, t)
    p.restore()
