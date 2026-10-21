"""Blitzen y Black en el cielo de Inicio, sacados tal cual de su ilustracion (`docs/art/basePerretes.jpg`).

`tools/build_dogs.py` recorta a cada perro por su contorno crema de pegatina y guarda en `assets/dogs/` sus capas: el perro
con los ojos abiertos, el mismo con los ojos cerrados (parpados del color de su pelo) y, en Black, las dos orejas aparte.
Aqui se animan:

* Parpadean (de dia) y duermen con los ojos cerrados (de noche).
* Ladean la cabeza: la imagen se dobla por encima del cuello, por franjas finas, y el cuerpo se queda quieto.
* Black mueve las orejas (giran desde donde nacen) y las dos colas, dibujadas con el mismo estilo de pegatina porque la
  ilustracion no las enseña, se menean por detras del cuerpo.
* Respiran: de dia, apenas; de noche, mas hondo y despacio, cabeceando, con unas z que suben.

Coordenadas: las de la ilustracion original en pixeles (2400 x 1792). El cielo las reduce con `UNIT` y las apoya en el
horizonte por la base de las patas (`GROUND_Y`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

from ui.assets import BASE

DOG_DIR = BASE / "assets" / "dogs"
STORE = 0.35                # escala a la que tools/build_dogs.py guarda las capas
UNIT = 0.025                # unidades del cielo por pixel de la ilustracion: Blitzen mide unas 41 de alto
GROUND_Y = 1759.0           # la base de las patas en la ilustracion
PAIR_CENTER_X = 1221.0      # el centro de la pareja en la ilustracion: el cielo lo coloca en su `center_x`

FUR = QColor(49, 49, 57)            # el pelo negro de la ilustracion
FUR_LIGHT = QColor(88, 92, 108)     # sus mechones claros
CREAM = QColor(232, 216, 192)       # el contorno de pegatina
OUTLINE = 23.0                      # su grosor en la ilustracion


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
class Ear:
    layer: str
    pivot: Point            # donde nace la oreja (gira desde ahi)
    side: int               # -1 izquierda, 1 derecha: las dos se abren a la vez


@dataclass(frozen=True, slots=True)
class Tail:
    anchor: Point           # donde nace, escondida detras del cuerpo
    shape: tuple[Point, ...]    # el contorno, relativo al nacimiento
    strands: tuple[tuple[Point, ...], ...]     # mechones claros
    rest: float             # angulo de reposo (grados)


@dataclass(frozen=True, slots=True)
class Dog:
    name: str
    origin: Point           # esquina del lienzo de sus capas, en la ilustracion
    neck: Point             # por encima de aqui se ladea la cabeza
    ears: tuple[Ear, ...]
    tail: Tail


BLITZEN = Dog(
    "blitzen", (166, 86), (762, 880), (),
    Tail((330, 1560),                                       # el penacho del cavalier, hacia arriba y con flecos por debajo
         ((0, 0), (-40, -80), (-90, -160), (-150, -215), (-205, -232), (-218, -198), (-248, -186), (-208, -160),
          (-228, -130), (-182, -116), (-192, -80), (-142, -62), (-122, -12), (-60, 40)),
         (((-50, -60), (-100, -140), (-160, -190)), ((-90, -40), (-140, -100), (-185, -140))),
         0.0),
)
BLACK = Dog(
    "black", (1301, 537), (1798, 1175),
    (Ear("black-oreja-izq", (1600, 650), -1), Ear("black-oreja-der", (1996, 650), 1)),
    Tail((2090, 1600),
         ((0, 0), (40, -50), (88, -102), (122, -112), (126, -78), (90, -24), (40, 34)),
         (((30, -30), (70, -72)),),
         -6.0),
)

_layers: dict[str, QImage] = {}
_scaled: dict[tuple[str, int], QImage] = {}


def _layer(name: str, scale: float) -> QImage:
    """Una capa a `scale` pixeles de pantalla por pixel de la ilustracion (se guarda escalada: se reescala solo si cambia)."""
    key = (name, round(scale * 1000))
    if key not in _scaled:
        if name not in _layers:
            image = QImage(str(DOG_DIR / f"{name}.png"))
            _layers[name] = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        image = _layers[name]
        factor = scale / STORE
        _scaled[key] = image.scaled(max(1, round(image.width() * factor)), max(1, round(image.height() * factor)),
                                    Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return _scaled[key]


def _device_scale(p: QPainter) -> float:
    """Pixeles reales de pantalla por unidad del pintor en este momento (con la escala del monitor)."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return abs(p.worldTransform().m11()) * max(ratio, 1.0)


def _paint_tail(p: QPainter, tail: Tail, angle: float) -> None:
    """La cola, con el contorno crema de pegatina por fuera (se pinta antes que el cuerpo, que tapa su nacimiento)."""
    p.save()
    p.translate(*tail.anchor)
    p.rotate(tail.rest + angle)
    path = smooth(list(tail.shape))
    outline = QPen(CREAM, OUTLINE * 2)
    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(outline)
    p.setBrush(CREAM)
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(FUR)
    p.drawPath(path)
    strand = QPen(FUR_LIGHT, 9)
    strand.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(strand)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for points in tail.strands:
        p.drawPath(smooth(list(points), closed=False))
    p.restore()


def _compose(dog: Dog, scale: float, closed: bool, ear_angle: float) -> QImage:
    """El perro de esta imagen: su capa (ojos abiertos o cerrados) y, encima, las orejas giradas."""
    base = _layer(dog.name + ("-dormido" if closed else ""), scale)
    if not dog.ears:
        return base
    frame = QImage(base.size(), QImage.Format.Format_ARGB32_Premultiplied)
    frame.fill(0)
    q = QPainter(frame)
    q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    q.setRenderHint(QPainter.RenderHint.Antialiasing)
    q.drawImage(0, 0, base)
    for ear in dog.ears:
        px, py = (ear.pivot[0] - dog.origin[0]) * scale, (ear.pivot[1] - dog.origin[1]) * scale
        q.save()
        q.translate(px, py)
        q.rotate(ear.side * ear_angle)
        q.translate(-px, -py)
        q.drawImage(0, 0, _layer(ear.layer, scale))
        q.restore()
    q.end()
    return frame


def _paint_bent(p: QPainter, dog: Dog, image: QImage, scale: float, tilt: float) -> None:
    """Pinta la imagen ladeando la cabeza: por encima del cuello cada fila se desplaza en proporcion a su altura (de 0 en
    el cuello al ladeo entero un poco mas arriba), y por debajo el cuerpo queda tal cual.

    Las filas se mueven en una imagen intermedia, de pixel entero en pixel entero (sin reescalar en vertical: asi no quedan
    juntas entre filas), y esa imagen se pinta de una vez."""
    ox, oy = dog.origin
    width, height = image.width(), image.height()
    pivot = (dog.neck[1] - oy) * scale
    ramp = 90 * scale                                       # la transicion entre cuerpo quieto y cabeza ladeada
    slope = math.tan(math.radians(tilt))
    if abs(slope) < 1e-4:
        p.drawImage(QRectF(ox, oy, width / scale, height / scale), image)
        return
    still = min(height, math.ceil(pivot + ramp))            # desde aqui hacia abajo, el cuerpo quieto
    pad = math.ceil(abs(pivot * slope)) + 1
    bent = QImage(width + 2 * pad, height, QImage.Format.Format_ARGB32_Premultiplied)
    bent.fill(0)
    q = QPainter(bent)
    q.drawImage(pad, still, image, 0, still, width, height - still)
    for y in range(still):
        f = max(0.0, min(1.0, (pivot + ramp - y - 0.5) / (2 * ramp)))
        dx = round((pivot - y - 0.5) * slope * f * f * (3 - 2 * f))
        q.drawImage(pad + dx, y, image, 0, y, width, 1)
    q.end()
    p.drawImage(QRectF(ox - pad / scale, oy, bent.width() / scale, height / scale), bent)


def _paint_dog(p: QPainter, dog: Dog, *, closed: bool, tilt: float, ear_angle: float, tail_angle: float, breath: float) -> None:
    p.save()
    p.translate(0, GROUND_Y)                                # respira: el pecho sube desde las patas
    p.scale(1.0, breath)
    p.translate(0, -GROUND_Y)
    _paint_tail(p, dog.tail, tail_angle)
    scale = min(_device_scale(p), STORE * 2)                # nunca mas grande que el doble de lo guardado
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    _paint_bent(p, dog, _compose(dog, scale, closed, ear_angle), scale, tilt)
    p.restore()


def _paint_zs(p: QPainter, t: float, x: float, y: float, color: QColor) -> None:
    """Unas z que suben y se desvanecen."""
    for k, (size, delay) in enumerate(((60.0, 0.0), (85.0, 1.6))):
        phase = (t * 0.35 + delay / 3.2) % 1.0
        c = QColor(color)
        c.setAlphaF(0.85 * math.sin(math.pi * phase) ** 1.5)
        pen = QPen(c, 18)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = x + phase * 150 + k * 75, y - phase * 250
        z = QPainterPath()
        z.moveTo(cx - size / 2, cy - size / 2)
        z.lineTo(cx + size / 2, cy - size / 2)
        z.lineTo(cx - size / 2, cy + size / 2)
        z.lineTo(cx + size / 2, cy + size / 2)
        p.drawPath(z)


# ======================================================================================= la escena del cielo de Inicio
def _blink(t: float, offset: float) -> float:
    """Un parpadeo rapido cada cuatro segundos y pico (0 con el cielo quieto: t = 0 es la imagen sin animar)."""
    if t <= 0.0:
        return 0.0
    return 1.0 if ((t + offset) % 4.3) < 0.14 else 0.0


def _tilt(t: float, offset: float, amount: float) -> float:
    """Inclina la cabeza de vez en cuando, con calma, y la devuelve a su sitio."""
    return amount * max(0.0, math.sin(t * 0.45 + offset)) ** 3


def _wag(t: float, speed: float, offset: float, amount: float) -> float:
    """La cola se menea a rachas: un rato rapido y luego descansa."""
    return math.sin(t * speed) * amount * max(0.0, math.sin(t * 0.8 + offset)) ** 0.5


def _place(p: QPainter, ground: float, center_x: float) -> None:
    p.translate(center_x, ground)
    p.scale(UNIT, UNIT)
    p.translate(-PAIR_CENTER_X, -GROUND_Y)


def paint_day(p: QPainter, dark: bool, t: float, ground: float, center_x: float) -> None:
    """Blitzen y Black sentados, de cara a quien mira: parpadean, ladean la cabeza, Black mueve las orejas y los dos la cola."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _place(p, ground, center_x)
    _paint_dog(p, BLITZEN, closed=_blink(t, 0.0) > 0.5, tilt=_tilt(t, 1.0, -6.0), ear_angle=0.0,
               tail_angle=_wag(t, 8.0, 0.0, 14.0), breath=1.0 + 0.008 * math.sin(t * 1.7))
    ears = math.sin(t * 1.1 + 0.7) * 2.5 + max(0.0, math.sin(t * 0.7 + 2.0)) ** 8 * 7.0
    _paint_dog(p, BLACK, closed=_blink(t, 1.7) > 0.5, tilt=_tilt(t, 2.7, 7.0), ear_angle=ears,
               tail_angle=_wag(t, 8.5, 1.5, 18.0), breath=1.0 + 0.008 * math.sin(t * 1.9 + 1.0))
    p.restore()


def paint_night(p: QPainter, dark: bool, t: float, ground: float, center_x: float) -> None:
    """Los dos dormidos, sentados uno junto al otro: ojos cerrados, respiracion lenta y honda, cabeceo suave y sus z."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _place(p, ground, center_x)
    nod = math.sin(t * 0.6)
    _paint_dog(p, BLITZEN, closed=True, tilt=4.0 + 1.5 * nod, ear_angle=0.0, tail_angle=0.0,
               breath=1.0 + 0.016 * math.sin(t * 1.2))
    _paint_dog(p, BLACK, closed=True, tilt=-5.0 - 1.5 * math.sin(t * 0.6 + 1.3), ear_angle=-3.0,
               tail_angle=0.0, breath=1.0 + 0.02 * math.sin(t * 1.5 + 1.1))
    _paint_zs(p, t, 2120.0, 470.0, QColor("#F1E8D8") if dark else QColor("#17191D"))
    p.restore()
