"""Recorta a Blitzen y Black de sus ilustraciones (`docs/art/`) y genera las capas que anima el cielo de Inicio.

Uso:  python tools/build_dogs.py            (necesita Pillow, numpy y scipy: solo para regenerar, la app no los usa)
Salida: assets/dogs/*.png

* La silueta de cada perro es lo que encierra su contorno crema de pegatina (el fondo de la ilustracion es casi negro).
* Cada perro sale con los ojos abiertos y con los ojos cerrados (los parpados se pintan del color del pelo de alrededor,
  con la linea del ojo cerrado), para parpadear y para dormir.
* Las orejas salen en capas aparte, para que se muevan; debajo, la cabeza y el cuerpo se rellenan con su pelo.
* La lengua de Blitzen sale aparte, para jadear y relamerse.
* De noche: los dos acurrucados, recortados de `perretesDurmiendo.jpg` por su contorno (las z, las rayitas y el logotipo de
  la ilustracion quedan fuera: las z se animan en la app).
* Todas las capas de un perro comparten el mismo lienzo (mismo tamano y origen): se pintan una encima de otra sin recolocar.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "art" / "basePerretes.jpg"
SLEEPING = ROOT / "docs" / "art" / "perretesDurmiendo.jpg"
OUT = ROOT / "assets" / "dogs"
STORE = 0.35                # las capas se guardan al 35 % del original: de sobra para el tamano del cielo, incluso con pantallas HiDPI
MARGIN = 40                 # margen del lienzo (px del original) para que las orejas y la cabeza puedan moverse sin cortarse

# Coordenadas en pixeles de la ilustracion original (2400 x 1792).
EYES = {
    "blitzen": [(617, 438, 82, 72), (893, 438, 82, 72)],
    "black": [(1652, 870, 68, 60), (1945, 867, 68, 60)],
}
BLITZEN_AXIS = 762          # el eje de simetria de la cara de Blitzen
BLITZEN_FACE = (762, 500, 322, 365)          # elipse de la cara (centro y radios)
_BLITZEN_LEFT_EAR = [(575, 120), (420, 130), (300, 170), (200, 240), (140, 380), (100, 560), (60, 700), (70, 860), (100, 980),
                     (150, 1080), (250, 1150), (380, 1140), (520, 1085), (575, 990), (505, 900), (452, 800), (432, 660),
                     (442, 520), (470, 380), (575, 260)]
BLITZEN_EARS = {
    "izq": _BLITZEN_LEFT_EAR,
    "der": [(2 * BLITZEN_AXIS - x, y) for x, y in _BLITZEN_LEFT_EAR],
}
BLITZEN_SHOULDERS = [(470, 840), (1054, 840), (1130, 1000), (1200, 1180), (1250, 1420), (274, 1420), (324, 1180), (394, 1000)]   # el cuerpo bajo las orejas
BLITZEN_TONGUE = (700, 690, 825, 795)        # la caja de la lengua
BLACK_HEAD = (1798, 900, 262, 268)            # elipse de la cabeza de Black (centro y radios)
BLACK_EARS = {
    "izq": [(1318, 760), (1340, 690), (1400, 630), (1480, 570), (1560, 555), (1645, 580), (1665, 640), (1630, 690), (1590, 760),
            (1565, 860), (1545, 940), (1505, 990), (1440, 1000), (1385, 965), (1335, 880)],
    "der": [(2278, 760), (2256, 690), (2196, 630), (2116, 570), (2036, 555), (1951, 580), (1931, 640), (1966, 690), (2006, 760),
            (2031, 860), (2051, 940), (2091, 990), (2156, 1000), (2211, 965), (2261, 880)],
}


def grid(shape: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray]:
    return np.mgrid[0:shape[0], 0:shape[1]]


def ellipse(shape: tuple[int, ...], cx: float, cy: float, rx: float, ry: float) -> np.ndarray:
    yy, xx = grid(shape)
    return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0


def polygon(shape: tuple[int, ...], points: list[tuple[float, float]]) -> np.ndarray:
    mask = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return np.asarray(mask) > 0


def silhouettes(rgb: np.ndarray) -> list[np.ndarray]:
    """Las dos siluetas mayores encerradas por el contorno crema, de izquierda a derecha (Blitzen, Black)."""
    lum = rgb.mean(axis=2)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    cream = (lum > 150) & (r > g - 5) & (g > b - 5) & (r - b < 90)
    labels, n = ndi.label(ndi.binary_fill_holes(cream))
    sizes = ndi.sum(np.ones_like(lum), labels, range(1, n + 1))
    biggest = [int(i) + 1 for i in np.argsort(sizes)[::-1][:2]]
    masks = [labels == lab for lab in biggest]
    return sorted(masks, key=lambda m: np.nonzero(m)[1].mean())


def cream_of(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    lum = rgb.mean(axis=2)
    ring = mask & ~ndi.binary_erosion(mask, iterations=4)
    return np.median(rgb[ring & (lum > 170)], axis=0)


def cutout(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """RGBA con el borde suavizado: el aro exterior del contorno toma el crema puro y la opacidad de su mezcla con el fondo."""
    lum = rgb.mean(axis=2)
    ring = mask & ~ndi.binary_erosion(mask, iterations=4)
    cream = cream_of(rgb, mask)
    outer = ndi.binary_dilation(mask, iterations=2) & ~mask
    background = np.median(rgb[ndi.binary_dilation(mask, iterations=12) & ~ndi.binary_dilation(mask, iterations=6)], axis=0)
    alpha = np.zeros(lum.shape, np.float32)
    alpha[mask] = 1.0
    edge = (outer | (ring & ~ndi.binary_erosion(mask, iterations=2)))
    span = max(cream.mean() - background.mean(), 1.0)
    alpha[edge] = np.clip((lum[edge] - background.mean()) / span, 0.0, 1.0)
    out = np.zeros((*lum.shape, 4), np.float32)
    out[..., :3] = rgb
    out[edge, :3] = cream                                    # sin el halo oscuro del fondo
    out[..., 3] = alpha * 255
    return out


def ring_color(rgb: np.ndarray, x: float, y: float, rx: float, ry: float) -> tuple[int, int, int]:
    """El pelo que rodea un punto: la mediana de un anillo un poco mas ancho que el ovalo dado (sin lo mas claro)."""
    yy, xx = grid(rgb.shape)
    d = ((xx - x) / rx) ** 2 + ((yy - y) / ry) ** 2
    sample = rgb[(d > 1.35 ** 2) & (d < 1.6 ** 2)]
    lum = sample.mean(axis=1)
    sample = sample[lum < np.percentile(lum, 70)]            # sin las cejas de fuego ni el hocico
    return tuple(int(v) for v in np.median(sample, axis=0))


def close_eyes(layer: np.ndarray, rgb: np.ndarray, eyes: list[tuple[float, float, float, float]]) -> np.ndarray:
    """Los parpados: el ojo se cubre con el pelo de alrededor y queda la linea curva del ojo cerrado."""
    closed = Image.fromarray(layer, "RGBA")
    draw = ImageDraw.Draw(closed)
    for x, y, rx, ry in eyes:
        fur = ring_color(rgb, x, y, rx, ry)
        draw.ellipse((x - rx * 1.12, y - ry * 1.1, x + rx * 1.12, y + ry * 1.12), fill=(*fur, 255))
        line = (24, 17, 16, 255)
        width = max(6, round(rx * 0.13))
        points = [(x - rx * 0.92 + rx * 1.84 * i / 20, y + ry * 0.05 + ry * 0.42 * (1 - ((i - 10) / 10) ** 2)) for i in range(21)]
        draw.line(points, fill=line, width=width, joint="curve")
        for px, py in (points[0], points[-1]):
            draw.ellipse((px - width / 2, py - width / 2, px + width / 2, py + width / 2), fill=line)
    return np.asarray(closed).copy()


def split_ears(layer: np.ndarray, ears: dict[str, list[tuple[float, float]]], under: np.ndarray, fur: tuple[int, int, int]
               ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Separa las orejas: cada una a su capa; debajo, lo que es cabeza o cuerpo (`under`) se rellena con el pelo y el resto
    queda transparente (asi, al moverse, no asoma una segunda oreja)."""
    base = layer.copy()
    pieces = {}
    for side, poly in ears.items():
        area = polygon(layer.shape, poly)
        piece = layer.copy()
        piece[~area, 3] = 0
        pieces[side] = piece
        base[area & under, :3] = fur
        base[area & under, 3] = 255
        base[area & ~under, 3] = 0
    return base, pieces


def crop_box(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    return xs.min() - MARGIN, ys.min() - MARGIN, xs.max() + MARGIN + 1, ys.max() + 1


def save(layer: np.ndarray, box: tuple[int, int, int, int], name: str) -> None:
    piece = Image.fromarray(layer.astype(np.uint8), "RGBA").crop(box)
    size = (round(piece.width * STORE), round(piece.height * STORE))
    piece.resize(size, Image.Resampling.LANCZOS).save(OUT / name, optimize=True)


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    rgb = np.asarray(Image.open(source).convert("RGB")).astype(np.float32)
    shape = rgb.shape
    yy, xx = grid(shape)
    blitzen_mask, black_mask = silhouettes(rgb)

    # ---------------------------------------------------------------- Blitzen
    box = crop_box(blitzen_mask)
    full = cutout(rgb, blitzen_mask).astype(np.uint8)
    asleep_full = close_eyes(full, rgb, EYES["blitzen"])
    face = ellipse(shape, *BLITZEN_FACE)
    under = blitzen_mask & (face | polygon(shape, BLITZEN_SHOULDERS))
    fur = ring_color(rgb, 762, 980, 90, 60)
    tongue_box = np.zeros(shape[:2], bool)
    x0, y0, x1, y1 = BLITZEN_TONGUE
    tongue_box[y0:y1, x0:x1] = True
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    pink = tongue_box & (r > 180) & (r - g > 60) & (b > 100)
    tongue = ndi.binary_dilation(ndi.binary_fill_holes(pink), iterations=7) & tongue_box & (pink | (rgb.mean(axis=2) < 110))
    tongue = ndi.binary_fill_holes(tongue) & (yy > y0 + 12)
    tongue_layer = full.copy()
    tongue_layer[~tongue, 3] = 0
    save(tongue_layer, box, "blitzen-lengua.png")
    for suffix, layer in (("", full), ("-dormido", asleep_full)):
        base, ears = split_ears(layer, BLITZEN_EARS, under, fur)
        save(base, box, f"blitzen{suffix}.png")
        if not suffix:
            for side, piece in ears.items():
                save(piece, box, f"blitzen-oreja-{side}.png")
    print(f"blitzen: lienzo {tuple(int(v) for v in box)}")

    # ---------------------------------------------------------------- Black
    box = crop_box(black_mask)
    full = cutout(rgb, black_mask).astype(np.uint8)
    asleep_full = close_eyes(full, rgb, EYES["black"])
    head = ellipse(shape, *BLACK_HEAD)
    fur = ring_color(rgb, BLACK_HEAD[0], BLACK_HEAD[1] - 120, 120, 90)
    for suffix, layer in (("", full), ("-dormido", asleep_full)):
        base, ears = split_ears(layer, BLACK_EARS, head, fur)
        save(base, box, f"black{suffix}.png")
        if not suffix:
            for side, piece in ears.items():
                save(piece, box, f"black-oreja-{side}.png")
    print(f"black: lienzo {tuple(int(v) for v in box)}")

    # ---------------------------------------------------------------- los dos durmiendo
    rgb = np.asarray(Image.open(SLEEPING).convert("RGB")).astype(np.float32)
    pair = max(silhouettes(rgb), key=lambda m: m.sum())
    box = crop_box(pair)
    save(cutout(rgb, pair), box, "durmiendo.png")
    print(f"durmiendo: lienzo {tuple(int(v) for v in box)}")


if __name__ == "__main__":
    main()
