"""Saludo segun la hora del dia y limpieza del nombre de usuario. Sin Qt."""
from __future__ import annotations

from datetime import datetime

from core.categorizer import normalize
from core.i18n import N_, tr

MAX_NAME = 40
MORNING_FROM, AFTERNOON_FROM, NIGHT_FROM = 6, 14, 21     # horas: dias 6-13, tardes 14-20, noches 21-5


def clean_name(raw: str | None) -> str:
    """Espacios sobrantes fuera y un maximo de 40 caracteres. Vacio si no hay nada util."""
    return " ".join((raw or "").split())[:MAX_NAME].strip()


_SPECIAL = {"LAURA PADROS JARA": "Petitona♥"}     # un detalle para alguien especial: se muestra este nombre, el guardado no cambia


def shown_name(name: str) -> str:
    """El nombre tal como se muestra en el saludo (casi siempre el mismo)."""
    name = clean_name(name)
    return _SPECIAL.get(normalize(name), name)


def period_greeting(hour: int) -> str:
    """El saludo en castellano (clave de traduccion) que toca a esa hora."""
    if MORNING_FROM <= hour < AFTERNOON_FROM:
        return N_("Buenos días")
    if AFTERNOON_FROM <= hour < NIGHT_FROM:
        return N_("Buenas tardes")
    return N_("Buenas noches")


def greeting(now: datetime, name: str = "") -> str:
    """'Buenos días, Ana.' / 'Buenas tardes, Ana.' / 'Buenas noches, Ana.' (siempre con punto final), en el idioma activo.
    Sin nombre, solo el saludo: 'Buenos días.'"""
    base = tr(period_greeting(now.hour))
    name = shown_name(name)
    return f"{base}, {name}." if name else f"{base}."
