"""Recorta a Blitzen y Black de sus ilustraciones (`docs/art/`) y genera las capas que anima el cielo de Inicio.

Uso:  python tools/build_dogs.py            (necesita Pillow, numpy y scipy: solo para regenerar, la app no los usa)
Salida: assets/dogs/*.png

* La silueta de cada perro es lo que encierra su contorno crema de pegatina (el fondo de la ilustracion es casi negro).
* Cada perro sale con los ojos abiertos y con los ojos cerrados (los parpados se pintan del color del pelo de alrededor,
  con la linea del ojo cerrado), para parpadear y para dormir.
* Cada perro es la ilustracion entera, sin cortes: las orejas no se separan (al moverlas se veian los cortes y el pelo de
  relleno de debajo). Solo salen aparte los parpados (para la web) y la lengua de Blitzen, para jadear y relamerse.
* De noche: los dos acurrucados, recortados de `perretesDurmiendo.jpg` por su contorno (las z, las rayitas y el logotipo de
  la ilustracion quedan fuera: las z se animan en la app).
* Para la web, los dos senalando con la pata (`perretesSenalando.jpg`), con sus rayitas de emocion: en `docs/art/recortes/`.
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
POINTING = ROOT / "docs" / "art" / "perretesSenalando.jpg"
OUT = ROOT / "assets" / "dogs"
OUT_WEB = ROOT / "docs" / "art" / "recortes"    # recortes que solo usa la web (no van en el programa)
STORE = 0.35                # las capas se guardan al 35 % del original: de sobra para el tamano del cielo, incluso con pantallas HiDPI
MARGIN = 40                 # margen del lienzo (px del original) alrededor de cada perro

# Coordenadas en pixeles de la ilustracion original (2400 x 1792).
EYES = {
    "blitzen": [(617, 438, 82, 72), (893, 438, 82, 72)],
    "black": [(1652, 870, 68, 60), (1945, 867, 68, 60)],
}
BLITZEN_TONGUE = (700, 690, 825, 795)        # la caja de la lengua


def grid(shape: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray]:
    return np.mgrid[0:shape[0], 0:shape[1]]


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
    yy, _ = grid(shape)
    blitzen_mask, black_mask = silhouettes(rgb)

    # ---------------------------------------------------------------- Blitzen y Black, enteros
    for name, mask in (("blitzen", blitzen_mask), ("black", black_mask)):
        box = crop_box(mask)
        full = cutout(rgb, mask).astype(np.uint8)
        asleep = close_eyes(full, rgb, EYES[name])
        lids = asleep.copy()                                  # solo los parpados: lo que cambia al cerrar los ojos
        lids[(asleep == full).all(axis=2), 3] = 0
        save(full, box, f"{name}.png")
        save(asleep, box, f"{name}-dormido.png")
        save(lids, box, f"{name}-parpados.png")
        if name == "blitzen":
            tongue_box = np.zeros(shape[:2], bool)
            x0, y0, x1, y1 = BLITZEN_TONGUE
            tongue_box[y0:y1, x0:x1] = True
            r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
            pink = tongue_box & (r > 180) & (r - g > 60) & (b > 100)
            tongue = ndi.binary_dilation(ndi.binary_fill_holes(pink), iterations=7) & tongue_box & (pink | (rgb.mean(axis=2) < 110))
            tongue = ndi.binary_fill_holes(tongue) & (yy > y0 + 12)
            layer = full.copy()
            layer[~tongue, 3] = 0
            save(layer, box, "blitzen-lengua.png")
        print(f"{name}: lienzo {tuple(int(v) for v in box)}")

    # ---------------------------------------------------------------- los dos durmiendo
    rgb = np.asarray(Image.open(SLEEPING).convert("RGB")).astype(np.float32)
    pair = max(silhouettes(rgb), key=lambda m: m.sum())
    box = crop_box(pair)
    save(cutout(rgb, pair), box, "durmiendo.png")
    print(f"durmiendo: lienzo {tuple(int(v) for v in box)}")

    # ---------------------------------------------------------------- los dos senalando (solo la web)
    rgb = np.asarray(Image.open(POINTING).convert("RGB")).astype(np.float32)
    lum = rgb.mean(axis=2)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    cream = (lum > 130) & (r > g - 5) & (g > b - 5) & (r - b < 90) & (r - b > 8)    # su contorno es algo mas oscuro en la pata
    labels, n = ndi.label(ndi.binary_fill_holes(cream))
    sizes = ndi.sum(np.ones_like(lum), labels, range(1, n + 1))
    order = np.argsort(sizes)[::-1]
    keep = [int(i) + 1 for i in order[:2]] + [int(i) + 1 for i in order[2:40] if sizes[i] > 1500]   # los dos y sus rayitas
    pair = np.isin(labels, keep)
    box = crop_box(pair)
    OUT_WEB.mkdir(parents=True, exist_ok=True)
    piece = Image.fromarray(cutout(rgb, pair).astype(np.uint8), "RGBA").crop(box)
    piece.resize((round(piece.width * 0.4), round(piece.height * 0.4)), Image.Resampling.LANCZOS).save(OUT_WEB / "senalando.png", optimize=True)
    print(f"senalando: lienzo {tuple(int(v) for v in box)} (al 40 %)")


if __name__ == "__main__":
    main()
