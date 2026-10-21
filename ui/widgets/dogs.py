"""Blitzen y Black en el cielo de Inicio, sacados tal cual de su ilustracion (`docs/art/basePerretes.jpg`).

`tools/build_dogs.py` recorta a cada perro por su contorno crema de pegatina y guarda en `assets/dogs/` sus capas: el perro
con los ojos abiertos y con los ojos cerrados, las orejas aparte, la lengua de Blitzen y los dos durmiendo. Aqui se animan:

* De dia, sentados: parpadean, ladean la cabeza (la imagen se dobla por encima del cuello) y mueven las orejas. Blitzen
  jadea con la lengua y de vez en cuando se relame; Black menea la cola (dibujada con el mismo estilo de pegatina, porque
  la ilustracion no la ensena).
* De noche, acurrucados, tal cual los dibuja su segunda ilustracion (`docs/art/perretesDurmiendo.jpg`), con unas z que
  salen de cada uno.

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
    chin: Point             # la barbilla: por donde se apoya la cabeza al dormir
    ears: tuple[Ear, ...]
    tail: Tail | None = None
    tongue: Point | None = None     # donde nace la lengua (arriba, en la boca)


BLITZEN = Dog(
    "blitzen", (166, 86), (762, 880), (762, 862),
    (Ear("blitzen-oreja-izq", (500, 230), -1), Ear("blitzen-oreja-der", (1024, 230), 1)),
    tongue=(762, 703),
)
BLACK = Dog(
    "black", (1301, 537), (1798, 1175), (1798, 1165),
    (Ear("black-oreja-izq", (1600, 650), -1), Ear("black-oreja-der", (1996, 650), 1)),
    Tail((2090, 1600),
         ((0, 0), (40, -50), (88, -102), (122, -112), (126, -78), (90, -24), (40, 34)),
         (((30, -30), (70, -72)),),
         -6.0),
)

# De noche, la ilustracion de los dos acurrucados (`perretesDurmiendo.jpg`), con sus propias medidas.
SLEEP_ORIGIN = (47, 105)            # esquina de su capa en esa ilustracion
SLEEP_GROUND = 1492.0               # la base de la pegatina
SLEEP_CENTER_X = 1382.0             # su centro: el cielo lo coloca en `center_x`
SLEEP_UNIT = 0.0205                 # unidades del cielo por pixel: ocupan lo mismo de ancho que sentados
SLEEP_ZS = ((1690.0, 300.0, 1.0, 0.0), (2170.0, 780.0, 0.8, 1.7))   # de donde salen las z: (x, y, tamano, desfase)

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
    t = p.worldTransform()
    return math.hypot(t.m11(), t.m12()) * max(ratio, 1.0)


def _sticker(p: QPainter, path: QPainterPath, fill: QColor) -> None:
    """Una forma con el contorno crema de pegatina por fuera, como los perros de la ilustracion."""
    outline = QPen(CREAM, OUTLINE * 2)
    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(outline)
    p.setBrush(CREAM)
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fill)
    p.drawPath(path)


def _strands(p: QPainter, strands, width: float = 9.0) -> None:
    pen = QPen(FUR_LIGHT, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for points in strands:
        p.drawPath(smooth(list(points), closed=False))


def _paint_tail(p: QPainter, tail: Tail, angle: float) -> None:
    """La cola (se pinta antes que el cuerpo, que tapa su nacimiento)."""
    p.save()
    p.translate(*tail.anchor)
    p.rotate(tail.rest + angle)
    _sticker(p, smooth(list(tail.shape)), FUR)
    _strands(p, tail.strands)
    p.restore()


def _compose(dog: Dog, scale: float, closed: bool, ear_angle: float, tongue: tuple[float, float] = (1.0, 0.0)) -> QImage:
    """El perro de esta imagen: su capa (ojos abiertos o cerrados), la lengua (estirada `tongue[0]` veces y girada
    `tongue[1]` grados desde la boca) y, encima, las orejas giradas."""
    base = _layer(dog.name + ("-dormido" if closed else ""), scale)
    frame = QImage(base.size(), QImage.Format.Format_ARGB32_Premultiplied)
    frame.fill(0)
    q = QPainter(frame)
    q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    q.setRenderHint(QPainter.RenderHint.Antialiasing)
    q.drawImage(0, 0, base)
    if dog.tongue is not None and (tongue[0] > 1.001 or abs(tongue[1]) > 0.1):
        tx, ty = (dog.tongue[0] - dog.origin[0]) * scale, (dog.tongue[1] - dog.origin[1]) * scale
        q.save()
        q.translate(tx, ty)
        q.rotate(tongue[1])
        q.scale(1.0 + (tongue[0] - 1.0) * 0.25, tongue[0])
        q.translate(-tx, -ty)
        q.drawImage(0, 0, _layer(f"{dog.name}-lengua", scale))
        q.restore()
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


def _paint_sitting(p: QPainter, dog: Dog, *, closed: bool, tilt: float, ear_angle: float, tail_angle: float = 0.0,
                   tongue: tuple[float, float] = (1.0, 0.0), breath: float = 1.0) -> None:
    p.save()
    p.translate(0, GROUND_Y)                                # respira: el pecho sube desde las patas
    p.scale(1.0, breath)
    p.translate(0, -GROUND_Y)
    if dog.tail is not None:
        _paint_tail(p, dog.tail, tail_angle)
    scale = min(_device_scale(p), STORE * 2)                # nunca mas grande que el doble de lo guardado
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    _paint_bent(p, dog, _compose(dog, scale, closed, ear_angle, tongue), scale, tilt)
    p.restore()


def _paint_zs(p: QPainter, t: float, x: float, y: float, size: float, color: QColor) -> None:
    """Unas z que salen de la cabeza de un perro dormido, una cada poco: suben en diagonal, crecen y se desvanecen (z z Z)."""
    every, life = 1.1, 3.3
    for k in range(3):
        u = ((t + k * every) % life) / life                   # 0 al salir, 1 al desvanecerse
        c = QColor(color)
        c.setAlphaF(0.9 * math.sin(math.pi * u) ** 1.2)
        side = (40 + 90 * u) * size
        pen = QPen(c, side * 0.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = x + u * 260 * size, y - u * 330 * size
        z = QPainterPath()
        z.moveTo(cx - side / 2, cy - side / 2)
        z.lineTo(cx + side / 2, cy - side / 2)
        z.lineTo(cx - side / 2, cy + side / 2)
        z.lineTo(cx + side / 2, cy + side / 2)
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


def _tongue(t: float) -> tuple[float, float]:
    """La lengua de Blitzen: jadea a rachas (sale y entra un poco, deprisa) y cada siete segundos se relame (sale mas y
    barre de un lado a otro). Devuelve (cuanto se estira, cuanto gira)."""
    if t <= 0.0:
        return 1.0, 0.0
    pant = 0.22 * max(0.0, math.sin(t * 7.0)) * max(0.0, math.sin(t * 0.55 + 0.4)) ** 2
    phase = t % 7.0
    lick = math.sin(math.pi * phase / 0.9) if phase < 0.9 else 0.0
    return 1.0 + pant + 0.75 * lick, 16.0 * lick * math.sin(phase * 10.0)


def _place(p: QPainter, ground: float, center_x: float) -> None:
    p.translate(center_x, ground)
    p.scale(UNIT, UNIT)
    p.translate(-PAIR_CENTER_X, -GROUND_Y)


def paint_day(p: QPainter, dark: bool, t: float, ground: float, center_x: float) -> None:
    """Blitzen y Black sentados, de cara a quien mira: parpadean, ladean la cabeza y mueven las orejas; Blitzen jadea y se
    relame, y Black menea la cola."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _place(p, ground, center_x)
    _paint_sitting(p, BLITZEN, closed=_blink(t, 0.0) > 0.5, tilt=_tilt(t, 1.0, -7.0),
                   ear_angle=math.sin(t * 1.3) * 2.2, tongue=_tongue(t))
    ears = math.sin(t * 1.1 + 0.7) * 2.5 + max(0.0, math.sin(t * 0.7 + 2.0)) ** 8 * 7.0
    _paint_sitting(p, BLACK, closed=_blink(t, 1.7) > 0.5, tilt=_tilt(t, 2.7, 8.0), ear_angle=ears,
                   tail_angle=_wag(t, 8.5, 1.5, 20.0))
    p.restore()


def paint_night(p: QPainter, dark: bool, t: float, ground: float, center_x: float) -> None:
    """Los dos acurrucados, tal cual los dibuja su ilustracion, con unas z que salen de cada uno."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.translate(center_x, ground)
    p.scale(SLEEP_UNIT, SLEEP_UNIT)
    p.translate(-SLEEP_CENTER_X, -SLEEP_GROUND)
    scale = min(_device_scale(p), STORE * 2)
    image = _layer("durmiendo", scale)
    p.drawImage(QRectF(SLEEP_ORIGIN[0], SLEEP_ORIGIN[1], image.width() / scale, image.height() / scale), image)
    color = CREAM if dark else QColor("#17191D")
    for x, y, size, offset in SLEEP_ZS:
        _paint_zs(p, t + offset, x, y, size, color)
    p.restore()
