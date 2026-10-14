"""Carga de logos desde `logo-mejorado/` (funciona en desarrollo y empaquetado)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ui.theme import Palette

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
LOGO_DIR = BASE / "logo-mejorado"

# El logotipo transparente lleva el texto en gris (#7F7F7F): se sustituye por el color del tema.
_PLACEHOLDER_TEXT = "#7F7F7F"
_WORDMARK_CROP = "110 70 1050 340"  # recorta los margenes del lienzo 1400x480


def _render(svg: bytes, width: int, height: int) -> QPixmap:
    dpr = max(QGuiApplication.primaryScreen().devicePixelRatio(), 1.0) if QGuiApplication.primaryScreen() else 1.0
    pix = QPixmap(int(width * dpr), int(height * dpr))
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg)).render(painter)
    painter.end()
    pix.setDevicePixelRatio(dpr)
    return pix


def wordmark(palette: Palette, height: int = 44) -> QPixmap:
    """Icono + 'KREIX' con el texto en el color del tema activo."""
    svg = (LOGO_DIR / "kreix-logotipo-transparente.svg").read_text(encoding="utf-8")
    svg = svg.replace(_PLACEHOLDER_TEXT, palette.text)
    svg = re.sub(r'viewBox="[^"]*"', f'viewBox="{_WORDMARK_CROP}"', svg, count=1)
    crop_w, crop_h = (float(v) for v in _WORDMARK_CROP.split()[2:])
    width = round(height * crop_w / crop_h)
    svg = re.sub(r'width="\d+" height="\d+"', f'width="{width}" height="{height}"', svg, count=1)
    return _render(svg.encode("utf-8"), width, height)


def mark(size: int = 64) -> QPixmap:
    """Solo el icono (K sobre recuadro oscuro)."""
    svg = (LOGO_DIR / "kreix-icono-oscuro.svg").read_bytes()
    return _render(svg, size, size)


def app_icon() -> QIcon:
    icon = QIcon(str(LOGO_DIR / "favicon.ico"))
    if icon.isNull():
        icon = QIcon(mark(256))
    return icon
