"""Hoja de pruebas de Blitzen y Black (de frente, estilo de linea gruesa): dia y noche, tema oscuro y claro, a gran tamano y
al tamano real del cielo de Inicio.

Uso:  python tools/dogs_preview.py salida.png
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui import fonts  # noqa: E402
from ui.widgets import dogs as df  # noqa: E402

BIG = 10.0              # aumento de la vista grande
CELL_W, CELL_H = 66, 62


def draw_cell(p: QPainter, dark: bool, kind: str, scale: float, t: float = 0.0, blink: float = 0.0, tilt: float = 0.0) -> None:
    lk = df.look(dark)
    p.save()
    p.scale(scale, scale)
    if kind == "day":
        p.save(); p.translate(21, 58); df.blitzen_sitting(p, lk, t, blink, tilt); p.restore()
        p.save(); p.translate(49, 58); df.black_sitting(p, lk, t, blink, -tilt); p.restore()
    else:
        p.save(); p.translate(40, 58); df.sleeping_pair(p, lk, t); p.restore()
    p.restore()


def main() -> None:
    """Una hoja de 2 x 2: arriba, de dia (oscuro y claro); abajo, de noche. Y otra al tamano real del cielo de Inicio."""
    out = Path(sys.argv[1])
    app = QApplication([])
    fonts.setup_application(app)
    cells = [(True, "day"), (False, "day"), (True, "night"), (False, "night")]
    image = QImage(int(CELL_W * BIG * 2), int(CELL_H * BIG * 2), QImage.Format.Format_ARGB32)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, (dark, kind) in enumerate(cells):
        p.save()
        p.translate((i % 2) * CELL_W * BIG, (i // 2) * CELL_H * BIG)
        p.fillRect(0, 0, int(CELL_W * BIG), int(CELL_H * BIG), QColor("#171C22" if dark else "#F6F2EA"))
        draw_cell(p, dark, kind, BIG, t=1.0)
        p.restore()
    p.end()
    image.save(str(out))
    # el tamano real: 2,6 aumentos de pantalla, como en el cielo de Inicio
    real = QImage(int(CELL_W * 2.6 * 2), int(CELL_H * 2.6 * 2), QImage.Format.Format_ARGB32)
    q = QPainter(real)
    q.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, (dark, kind) in enumerate(cells):
        q.save()
        q.translate((i % 2) * CELL_W * 2.6, (i // 2) * CELL_H * 2.6)
        q.fillRect(0, 0, int(CELL_W * 2.6), int(CELL_H * 2.6), QColor("#171C22" if dark else "#F6F2EA"))
        draw_cell(q, dark, kind, 2.6, t=1.0)
        q.restore()
    q.end()
    real.save(str(out.with_name(out.stem + "-real.png")))
    # las caras, muy ampliadas, con el tema oscuro y el claro
    faces = QImage(int(64 * 14), int(40 * 14 * 2), QImage.Format.Format_ARGB32)
    f = QPainter(faces)
    f.setRenderHint(QPainter.RenderHint.Antialiasing)
    for row, dark in enumerate((True, False)):
        lk = df.look(dark)
        f.save()
        f.translate(0, row * 40 * 14)
        f.fillRect(0, 0, faces.width(), 40 * 14, QColor("#171C22" if dark else "#F6F2EA"))
        f.scale(14, 14)
        pen = df.Pen(f, lk)
        f.save(); f.translate(18, 18); df.blitzen_head(pen, lk, 0.0, 1.0); f.restore()
        f.save(); f.translate(46, 18); df.black_head(pen, lk, 0.0); f.restore()
        f.restore()
    f.end()
    faces.save(str(out.with_name(out.stem + "-caras.png")))


if __name__ == "__main__":
    main()
