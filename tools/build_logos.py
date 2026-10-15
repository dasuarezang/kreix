"""Regenera los PNG y el .ico del logotipo a partir de los SVG de `logo-mejorado/` (los SVG son la fuente).

Uso:  python tools/build_logos.py
Lleva las cuatro barras de la senera (la K del logotipo tiene cuatro franjas rojas sobre el oro).
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
LOGOS = ROOT / "logo-mejorado"

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

# nombre del SVG -> (tamano del PNG, ¿con fondo opaco?)
PNGS = {
    "kreix-icono-claro": ((1024, 1024), False),
    "kreix-icono-oscuro": ((1024, 1024), False),
    "kreix-icono-transparente": ((1024, 1024), False),
    "kreix-icono-transparente-claro": ((1024, 1024), False),
    "kreix-monocromo-blanco": ((1024, 1024), False),
    "kreix-monocromo-negro": ((1024, 1024), False),
    "kreix-logotipo-transparente": ((1400, 480), False),
    "kreix-logotipo-claro": ((1400, 480), True),      # estos dos llevan su propio fondo: PNG sin transparencia
    "kreix-logotipo-oscuro": ((1400, 480), True),
}
FAVICON_SOURCE = "kreix-icono-oscuro"
FAVICON_SIZES = (16, 32, 48, 180, 256, 512)
ICO_SIZES = (16, 32, 48, 256)


def render(svg: str, size: tuple[int, int]) -> QImage:
    image = QImage(size[0], size[1], QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    QSvgRenderer(QByteArray((LOGOS / f"{svg}.svg").read_bytes())).render(painter)
    painter.end()
    return image


def png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(path: Path, images: list[QImage]) -> None:
    """ICO con entradas PNG (valido desde Windows Vista)."""
    blobs = [png_bytes(i) for i in images]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    for image, blob in zip(images, blobs):
        w = image.width() if image.width() < 256 else 0
        h = image.height() if image.height() < 256 else 0
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    path.write_bytes(header + entries + b"".join(blobs))


def main() -> None:
    QGuiApplication(sys.argv[:1])
    for name, (size, opaque) in PNGS.items():
        image = render(name, size)
        if opaque:
            image = image.convertToFormat(QImage.Format.Format_RGB888)
        image.save(str(LOGOS / f"{name}.png"), "PNG")
    for size in FAVICON_SIZES:
        render(FAVICON_SOURCE, (size, size)).save(str(LOGOS / f"favicon-{size}.png"), "PNG")
    write_ico(LOGOS / "favicon.ico", [render(FAVICON_SOURCE, (s, s)) for s in ICO_SIZES])
    print(f"Logotipos regenerados en {LOGOS}")


if __name__ == "__main__":
    main()
