"""Idioma del sistema (modulo ligero: la pantalla de bloqueo lo necesita antes de cargar el resto de la interfaz)."""
from __future__ import annotations

from PySide6.QtCore import QLocale

from core import i18n


def system_language() -> str:
    """El idioma del sistema si Kreix lo tiene (castellano, catalan o ingles); si no, castellano."""
    return i18n.normalize_language(QLocale.system().name()[:2].lower())
