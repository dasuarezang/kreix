"""Idiomas de la aplicacion: castellano (el original), catalan e ingles. Sin Qt: lo usan tambien servicios y ETL.

El texto original esta en castellano y es la clave de busqueda: `tr("Cuentas")` devuelve "Comptes" en catalan y
"Accounts" en ingles. Si un texto no tiene traduccion, se ve en castellano (nunca falla ni deja huecos).

- `tr(texto)`: traduce en el momento de usarse. Para textos con datos, `tr("Quedan {n}").format(n=3)`.
- `trn(uno, varios, n)`: singular o plural segun `n`.
- `N_(texto)`: marca un texto para traducirlo luego, al mostrarlo (constantes de modulo, que se crean antes de elegir idioma).
"""
from __future__ import annotations

import importlib

LANGUAGES = ("es", "ca", "en")
DEFAULT = "es"
NAMES = {"es": "Castellano", "ca": "Català", "en": "English"}

_current = DEFAULT
_catalogs: dict[str, dict[str, str]] = {}


def normalize_language(code: str | None) -> str:
    return code if code in LANGUAGES else DEFAULT


def set_language(code: str) -> None:
    global _current
    _current = normalize_language(code)


def language() -> str:
    return _current


def catalog(code: str) -> dict[str, str]:
    """Traducciones de un idioma (vacio para el castellano, que es el original)."""
    if code == DEFAULT:
        return {}
    if code not in _catalogs:
        _catalogs[code] = dict(importlib.import_module(f"core.locales.{code}").TEXTS)
    return _catalogs[code]


def tr(text: str) -> str:
    if _current == DEFAULT:
        return text
    return catalog(_current).get(text, text)


def N_(text: str) -> str:  # noqa: N802 (convencion de gettext)
    """Marca un texto para traducirlo despues; en el momento de definirlo no cambia nada."""
    return text


def trn(one: str, many: str, n: int) -> str:
    """Singular si n == 1, plural en otro caso; cada forma se traduce por separado."""
    return tr(one if n == 1 else many)


# ----------------------------------------------------------------------------- calendario
MONTHS_LONG = {
    "es": ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
           "diciembre"),
    "ca": ("gener", "febrer", "març", "abril", "maig", "juny", "juliol", "agost", "setembre", "octubre", "novembre",
           "desembre"),
    "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
           "December"),
}
MONTHS_SHORT = {
    "es": ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
    "ca": ("gen", "feb", "mar", "abr", "mai", "jun", "jul", "ago", "set", "oct", "nov", "des"),
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
}
WEEKDAYS = {                       # de lunes a domingo
    "es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"),
    "ca": ("dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
}


def months_long() -> tuple[str, ...]:
    return MONTHS_LONG[_current]


def months_short() -> tuple[str, ...]:
    return MONTHS_SHORT[_current]


def weekdays() -> tuple[str, ...]:
    return WEEKDAYS[_current]


def decimal_comma() -> bool:
    """Castellano y catalan escriben 1.234,56; el ingles escribe 1,234.56."""
    return _current != "en"
