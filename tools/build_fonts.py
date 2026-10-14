"""Genera las fuentes estaticas de Kreix a partir de las fuentes variables libres de Google Fonts.

Uso:  python tools/build_fonts.py CARPETA_CON_Montserrat.ttf_y_DMSans.ttf
Requiere `fonttools` (solo para este paso, no para ejecutar la aplicacion).

Cada peso se guarda con un nombre de familia propio ("Montserrat ExtraBold", "DM Sans Medium"...) para que
Qt lo elija sin depender de la correspondencia de pesos de cada sistema operativo.
Fuentes con licencia SIL Open Font License (ver assets/fonts/LICENCIAS.txt).
"""
from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

OUT = Path(__file__).resolve().parent.parent / "assets" / "fonts"
SPECS = [  # (archivo fuente, ejes, familia, peso)
    ("Montserrat.ttf", {"wght": 800}, "Montserrat ExtraBold", 800),
    ("Montserrat.ttf", {"wght": 700}, "Montserrat Bold", 700),
    ("Montserrat.ttf", {"wght": 600}, "Montserrat SemiBold", 600),
    ("DMSans.ttf", {"wght": 400, "opsz": 14}, "DM Sans", 400),
    ("DMSans.ttf", {"wght": 500, "opsz": 14}, "DM Sans Medium", 500),
    ("DMSans.ttf", {"wght": 700, "opsz": 14}, "DM Sans Bold", 700),
]


def build(source: Path, axes: dict, family: str, weight: int) -> Path:
    font = instantiateVariableFont(TTFont(source), axes, inplace=False)
    names = font["name"]
    for record in list(names.names):
        if record.nameID in (16, 17, 21, 22, 25):
            names.removeNames(nameID=record.nameID)
    for name_id, value in ((1, family), (2, "Regular"), (3, family), (4, family), (6, family.replace(" ", ""))):
        names.setName(value, name_id, 3, 1, 0x409)
        names.setName(value, name_id, 1, 0, 0)
    font["OS/2"].usWeightClass = weight
    font["OS/2"].fsSelection = (font["OS/2"].fsSelection & ~0b1100001) | 0b1000000
    font["head"].macStyle = 0
    target = OUT / f"{family.replace(' ', '')}.ttf"
    font.save(target)
    return target


if __name__ == "__main__":
    src = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    for file, axes, family, weight in SPECS:
        print(build(src / file, axes, family, weight))
