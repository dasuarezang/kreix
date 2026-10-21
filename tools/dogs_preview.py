"""Hoja de pruebas de Blitzen y Black: varios momentos de la animacion de dia y de noche, en tema oscuro y claro.

Uso:  python tools/dogs_preview.py salida.png [aumento]
Cada fila es un tema; cada columna, un momento (en reposo, ladeando la cabeza, parpadeando, de noche...). El aumento por
defecto (5,2) es el del cielo de Inicio en una pantalla HiDPI al 200 %.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.widgets import dogs as df  # noqa: E402

CELL_W, CELL_H = 70, 52                     # unidades del cielo por momento
GROUND = 48.0
MOMENTS = (                                  # (rotulo, de dia o de noche, t)
    ("reposo", "day", 0.0),
    ("parpadeo", "day", 4.32),
    ("se relame", "day", 7.45),
    ("orejas y cola", "day", 9.6),
    ("noche", "night", 1.0),
    ("noche, z", "night", 3.0),
)


def main() -> None:
    out = Path(sys.argv[1])
    zoom = float(sys.argv[2]) if len(sys.argv) > 2 else 5.2
    app = QApplication([])  # noqa: F841
    image = QImage(int(CELL_W * zoom * len(MOMENTS)), int(CELL_H * zoom * 2), QImage.Format.Format_ARGB32)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for row, dark in enumerate((True, False)):
        for col, (_label, kind, t) in enumerate(MOMENTS):
            p.save()
            p.translate(col * CELL_W * zoom, row * CELL_H * zoom)
            p.fillRect(0, 0, int(CELL_W * zoom), int(CELL_H * zoom), QColor("#101418" if dark else "#F6F2EA"))
            p.scale(zoom, zoom)
            (df.paint_day if kind == "day" else df.paint_night)(p, dark, t, GROUND, CELL_W / 2)
            p.restore()
    p.end()
    image.save(str(out))


if __name__ == "__main__":
    main()
