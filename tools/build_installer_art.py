"""Dibuja las imagenes del instalador con la marca (fondo carbon con resplandor rojo, el logotipo y las cuatro franjas).

Uso:  python tools/build_installer_art.py
Salida: packaging/art/panel-*.bmp (la columna de bienvenida y despedida) e icono-*.bmp (el cuadrito de las demas paginas),
en tres tamanos para que se vea nitido con la escala de pantalla de Windows al 100, 150 y 200 %.
Inno Setup solo acepta mapas de bits (.bmp).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QRadialGradient  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui import assets, fonts, theme  # noqa: E402

OUT = ROOT / "packaging" / "art"
PANEL = (164, 314)                    # tamano base de la columna lateral de Inno Setup (a 96 ppp)
ICON = (55, 55)                       # y el del cuadrito de la cabecera
SCALES = {"100": 1.0, "150": 1.5, "200": 2.0}


def _background(painter: QPainter, width: int, height: int, glow_at: tuple[float, float]) -> None:
    pal = theme.DARK
    painter.fillRect(0, 0, width, height, QColor(pal.bg))
    gradient = QRadialGradient(QPointF(width * glow_at[0], height * glow_at[1]), max(width, height) * 1.0)
    start = QColor(pal.glow)
    start.setAlpha(120)
    end = QColor(pal.glow)
    end.setAlpha(0)
    gradient.setColorAt(0.0, start)
    gradient.setColorAt(1.0, end)
    painter.fillRect(0, 0, width, height, gradient)


def _stripes(painter: QPainter, x: float, y: float, height: float) -> None:
    """Las cuatro franjas inclinadas de la K, del amarillo al rojo (la misma geometria que `StripeMark`)."""
    pal = theme.DARK
    slant, bar, gap = height * 0.50, height * 0.185, height * 0.165
    yellow, red = QColor(pal.accent), QColor(pal.red)
    painter.setPen(Qt.PenStyle.NoPen)
    for i, alpha in enumerate((255, 190, 120, 60)):
        t = i / 3
        color = QColor(round(yellow.red() + (red.red() - yellow.red()) * t), round(yellow.green() + (red.green() - yellow.green()) * t),
                       round(yellow.blue() + (red.blue() - yellow.blue()) * t))
        color.setAlpha(alpha)
        painter.setBrush(color)
        left = x + i * (bar + gap)
        path = QPainterPath()
        path.moveTo(left + slant, y)
        path.lineTo(left + slant + bar, y)
        path.lineTo(left + bar, y + height)
        path.lineTo(left, y + height)
        path.closeSubpath()
        painter.drawPath(path)


def panel(scale: float) -> QImage:
    width, height = round(PANEL[0] * scale), round(PANEL[1] * scale)
    image = QImage(width, height, QImage.Format.Format_RGB888)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    _background(painter, width, height, (0.95, 0.02))
    logo = assets.wordmark(theme.DARK, round(36 * scale))                # icono + KREIX
    logo.setDevicePixelRatio(1.0)
    pix = logo.scaledToHeight(round(36 * scale), Qt.TransformationMode.SmoothTransformation)
    painter.drawPixmap(round((width - pix.width()) / 2), round(34 * scale), pix)
    stripe_h = 62 * scale
    _stripes(painter, width / 2 - stripe_h * 1.05, height * 0.46, stripe_h)    # sin texto: sirve igual en los tres idiomas
    painter.end()
    return image


def icon(scale: float) -> QImage:
    width, height = round(ICON[0] * scale), round(ICON[1] * scale)
    image = QImage(width, height, QImage.Format.Format_RGB888)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _background(painter, width, height, (0.95, 0.0))
    mark = assets.mark(round(40 * scale))
    mark.setDevicePixelRatio(1.0)
    painter.drawPixmap(round((width - mark.width()) / 2), round((height - mark.height()) / 2), mark)
    painter.end()
    return image


def main() -> None:
    app = QApplication(sys.argv[:1])
    fonts.setup_application(app)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, scale in SCALES.items():
        panel(scale).save(str(OUT / f"panel-{name}.bmp"))
        icon(scale).save(str(OUT / f"icono-{name}.bmp"))
    print(f"Imagenes del instalador en {OUT}")


if __name__ == "__main__":
    main()
