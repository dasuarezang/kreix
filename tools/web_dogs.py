"""Exporta a la web (repositorio kreix-web) las capas de Blitzen y Black despiertos, para animarlos con CSS en el tema claro.

Uso:  python tools/web_dogs.py RUTA/kreix-web/assets/perretes
Salida: una imagen WebP por capa, todas del mismo tamano y sobre el mismo lienzo (la ilustracion basePerretes, de x=130 a 2330
y de y=60 a 1790, al 35 %): se apilan en la web sin recolocarlas (la lengua y la cola se mueven desde el punto que se imprime).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.widgets import dogs  # noqa: E402

CANVAS = (130, 60, 2330, 1790)          # x0, y0, x1, y1 en la ilustracion
SCALE = dogs.STORE
# (archivo de la web, capa de la app, perro)
LAYERS = (
    ("blitzen", "blitzen", dogs.BLITZEN),
    ("blitzen-ojos", "blitzen-parpados", dogs.BLITZEN),     # solo los parpados: encima del perro, sin duplicar sus bordes
    ("blitzen-lengua", "blitzen-lengua", dogs.BLITZEN),
    ("black", "black", dogs.BLACK),
    ("black-ojos", "black-parpados", dogs.BLACK),
)


def blank() -> QImage:
    w, h = round((CANVAS[2] - CANVAS[0]) * SCALE), round((CANVAS[3] - CANVAS[1]) * SCALE)
    image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    return image


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])  # noqa: F841
    for name, layer, dog in LAYERS:
        image = blank()
        p = QPainter(image)
        p.drawImage(round((dog.origin[0] - CANVAS[0]) * SCALE), round((dog.origin[1] - CANVAS[1]) * SCALE), dogs._layer(layer, SCALE))
        p.end()
        image.save(str(out / f"{name}.webp"), "webp", 90)
    tail = blank()                                           # la cola de Black, en reposo (la web la menea desde su nacimiento)
    p = QPainter(tail)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(SCALE, SCALE)
    p.translate(-CANVAS[0], -CANVAS[1])
    dogs._paint_tail(p, dogs.BLACK.tail, 0.0)
    p.end()
    tail.save(str(out / "black-cola.webp"), "webp", 90)
    # los dos senalando con la pata (la llamada a descargar): lo recorta tools/build_dogs.py
    QImage(str(ROOT / "docs" / "art" / "recortes" / "senalando.png")).save(str(out / "senalando.webp"), "webp", 90)

    w, h = CANVAS[2] - CANVAS[0], CANVAS[3] - CANVAS[1]
    print(f"lienzo {tail.width()} x {tail.height()}")
    for label, (x, y) in (("blitzen lengua", dogs.BLITZEN.tongue), ("black cola", dogs.BLACK.tail.anchor)):
        print(f"{label}: transform-origin {100 * (x - CANVAS[0]) / w:.2f}% {100 * (y - CANVAS[1]) / h:.2f}%")


if __name__ == "__main__":
    main()
