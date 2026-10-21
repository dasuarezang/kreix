"""Recorta a Blitzen y Black de la ilustracion `docs/art/basePerretes.jpg` y genera las capas que anima el cielo de Inicio.

Uso:  python tools/build_dogs.py            (necesita Pillow, numpy y scipy: solo para regenerar, la app no los usa)
Salida: assets/dogs/*.png

* La silueta de cada perro es lo que encierra su contorno crema de pegatina (el fondo de la ilustracion es casi negro).
* Cada perro sale dos veces: con los ojos abiertos y con los ojos cerrados (los parpados se pintan del color del pelo de
  alrededor, con la linea del ojo cerrado), para parpadear y para dormir.
* Las orejas de Black salen en capas aparte, para que se muevan; debajo, la cabeza se rellena con su pelo.
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
OUT = ROOT / "assets" / "dogs"
STORE = 0.35                # las capas se guardan al 35 % del original: de sobra para el tamano del cielo, incluso con pantallas HiDPI
MARGIN = 40                 # margen del lienzo (px del original) para que las orejas y la cabeza puedan moverse sin cortarse

# Coordenadas en pixeles de la ilustracion original (2400 x 1792).
EYES = {
    "blitzen": [(617, 438, 82, 72), (893, 438, 82, 72)],
    "black": [(1652, 870, 68, 60), (1945, 867, 68, 60)],
}
BLACK_HEAD = (1798, 900, 262, 268)            # elipse de la cabeza de Black (centro y radios), para rellenar bajo las orejas
BLACK_EARS = {
    "left": [(1318, 760), (1340, 690), (1400, 630), (1480, 570), (1560, 555), (1645, 580), (1665, 640), (1630, 690), (1590, 760),
             (1565, 860), (1545, 940), (1505, 990), (1440, 1000), (1385, 965), (1335, 880)],
    "right": [(2278, 760), (2256, 690), (2196, 630), (2116, 570), (2036, 555), (1951, 580), (1931, 640), (1966, 690), (2006, 760),
              (2031, 860), (2051, 940), (2091, 990), (2156, 1000), (2211, 965), (2261, 880)],
}


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


def cutout(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """RGBA con el borde suavizado: el aro exterior del contorno toma el crema puro y la opacidad de su mezcla con el fondo."""
    lum = rgb.mean(axis=2)
    inner = ndi.binary_erosion(mask, iterations=4)
    ring = mask & ~inner
    cream = np.median(rgb[ring & (lum > 170)], axis=0)
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
    """El pelo que rodea un ojo: la mediana de un anillo un poco mas ancho que el ojo."""
    yy, xx = np.mgrid[0:rgb.shape[0], 0:rgb.shape[1]]
    d = ((xx - x) / rx) ** 2 + ((yy - y) / ry) ** 2
    sample = rgb[(d > 1.35 ** 2) & (d < 1.6 ** 2)]
    lum = sample.mean(axis=1)
    sample = sample[lum < np.percentile(lum, 70)]            # sin las cejas de fuego ni el hocico
    return tuple(int(v) for v in np.median(sample, axis=0))


def close_eyes(layer: Image.Image, rgb: np.ndarray, eyes: list[tuple[float, float, float, float]]) -> Image.Image:
    """Los parpados: el ojo se cubre con el pelo de alrededor y queda la linea curva del ojo cerrado."""
    closed = layer.copy()
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
    return closed


def crop_box(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    return xs.min() - MARGIN, ys.min() - MARGIN, xs.max() + MARGIN + 1, ys.max() + 1


def save(layer: Image.Image, box: tuple[int, int, int, int], name: str) -> None:
    piece = layer.crop(box)
    size = (round(piece.width * STORE), round(piece.height * STORE))
    piece.resize(size, Image.Resampling.LANCZOS).save(OUT / name, optimize=True)


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE
    OUT.mkdir(parents=True, exist_ok=True)
    rgb = np.asarray(Image.open(source).convert("RGB")).astype(np.float32)
    blitzen_mask, black_mask = silhouettes(rgb)
    meta = {}
    for name, mask in (("blitzen", blitzen_mask), ("black", black_mask)):
        full = Image.fromarray(cutout(rgb, mask).astype(np.uint8), "RGBA")
        box = crop_box(mask)
        meta[name] = box
        if name == "black":
            yy, xx = np.mgrid[0:rgb.shape[0], 0:rgb.shape[1]]
            cx, cy, rx, ry = BLACK_HEAD
            head = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0
            base = full.copy()
            base_px = np.asarray(base).copy()
            for side, poly in BLACK_EARS.items():
                ear_mask = Image.new("L", full.size, 0)
                ImageDraw.Draw(ear_mask).polygon(poly, fill=255)
                ear_area = np.asarray(ear_mask) > 0
                ear = np.asarray(full).copy()
                ear[~ear_area, 3] = 0
                save(Image.fromarray(ear, "RGBA"), box, f"black-oreja-{'izq' if side == 'left' else 'der'}.png")
                fur = ring_color(rgb, cx, cy - 120, 120, 90)
                under = ear_area & head
                base_px[under, :3] = fur
                base_px[under, 3] = 255
                base_px[ear_area & ~head, 3] = 0
            base = Image.fromarray(base_px, "RGBA")
            save(base, box, "black.png")
            save(close_eyes(base, rgb, EYES[name]), box, "black-dormido.png")
        else:
            save(full, box, "blitzen.png")
            save(close_eyes(full, rgb, EYES[name]), box, "blitzen-dormido.png")
    for name, box in meta.items():
        print(f"{name}: lienzo {box} (original), {round((box[2] - box[0]) * STORE)} x {round((box[3] - box[1]) * STORE)} px guardado")


if __name__ == "__main__":
    main()
