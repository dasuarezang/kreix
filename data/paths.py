"""Rutas de los datos del usuario. Modulo ligero (sin SQLAlchemy): la pantalla de bloqueo lo usa antes de cargar el resto."""
from __future__ import annotations

import os
import sys
from pathlib import Path

VAULT_EXTENSION = ".krx"


def default_db_path() -> Path:
    """Carpeta de datos por usuario, fuera del codigo (los datos son privados)."""
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "Kreix" / "kreix.db"


def default_vault_path() -> Path:
    return default_db_path().with_suffix(VAULT_EXTENSION)


def legacy_db_path() -> Path:
    """La base sin cifrar de versiones anteriores (se migra la primera vez)."""
    return default_db_path()
