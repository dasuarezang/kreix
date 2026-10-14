"""Tipografia de Kreix.

Montserrat (la del logotipo) para titulos y cifras grandes; DM Sans para el texto. Los archivos van
dentro del programa (assets/fonts), asi se ve igual en cualquier ordenador. Cada peso tiene su propia
familia ("Montserrat ExtraBold", "DM Sans Medium"...), de modo que Qt lo elige sin depender de la
correspondencia de pesos del sistema. Si no se pudieran cargar, se usa la fuente del sistema.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
FONT_DIR = BASE / "assets" / "fonts"

DISPLAY = "Montserrat ExtraBold"        # titulos de pagina y cifras grandes
DISPLAY_BOLD = "Montserrat Bold"        # cifras medianas
LABEL = "Montserrat SemiBold"           # etiquetas en mayusculas con tracking
BODY = "DM Sans"
BODY_MEDIUM = "DM Sans Medium"
BODY_BOLD = "DM Sans Bold"
FALLBACK = "Segoe UI"

_FILES = ("MontserratExtraBold", "MontserratBold", "MontserratSemiBold", "DMSans", "DMSansMedium", "DMSansBold")
_loaded: bool | None = None


def load_fonts() -> bool:
    """Registra las fuentes incluidas. Seguro de llamar varias veces."""
    global _loaded
    if _loaded is None:
        ok = True
        for name in _FILES:
            ok = QFontDatabase.addApplicationFont(str(FONT_DIR / f"{name}.ttf")) >= 0 and ok
        _loaded = ok
    return bool(_loaded)


def family(preferred: str) -> str:
    """La familia pedida si esta disponible; si no, la del sistema."""
    return preferred if preferred in QFontDatabase.families() else FALLBACK


def qfont(name: str, px: int, spacing: float = 0.0, tabular: bool = False) -> QFont:
    """Una fuente lista para pintar. `spacing` es el tracking en pixeles; `tabular` activa cifras de ancho fijo."""
    font = QFont(family(name))
    font.setPixelSize(px)
    if spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    if tabular:
        font.setFeature(QFont.Tag("tnum"), 1)
    return font


def stack(preferred: str) -> str:
    """Valor para `font-family` en QSS, con la del sistema como reserva."""
    return f'"{preferred}", "{FALLBACK}", sans-serif'


def setup_application(app) -> None:
    """Carga las fuentes y fija DM Sans como tipografia por defecto de la aplicacion."""
    load_fonts()
    app.setFont(qfont(BODY, 14))
