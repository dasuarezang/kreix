"""Formato de numeros, porcentajes y fechas en espanol (sin dependencias de Qt)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

NBSP = " "
MINUS = "−"
EMPTY = "—"
MONTHS_SHORT = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MONTHS_LONG = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _es_number(value: Decimal | float, decimals: int) -> str:
    text = f"{abs(value):,.{decimals}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fmt_eur(value: Decimal | float | None, decimals: int = 2) -> str:
    """5781.2 -> '5.781,20 €'. Los negativos usan el signo menos tipografico."""
    if value is None:
        return EMPTY
    sign = MINUS if value < 0 and round(abs(value), decimals) != 0 else ""
    return f"{sign}{_es_number(value, decimals)}{NBSP}€"


def fmt_pct(fraction: Decimal | float | None, decimals: int = 1, signed: bool = False) -> str:
    """0.0441 -> '4,4 %'. Recibe una fraccion, no un porcentaje."""
    if fraction is None:
        return EMPTY
    pct = float(fraction) * 100
    if round(abs(pct), decimals) == 0:
        sign = ""
    else:
        sign = MINUS if pct < 0 else ("+" if signed else "")
    return f"{sign}{_es_number(pct, decimals)}{NBSP}%"


def month_short(d: date) -> str:
    return f"{MONTHS_SHORT[d.month - 1]} {d.year % 100:02d}"


def month_long(d: date) -> str:
    return f"{MONTHS_LONG[d.month - 1]} {d.year}"
