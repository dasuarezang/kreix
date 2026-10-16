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


def default_backup_folder() -> Path:
    """Donde van las copias de seguridad automaticas si el usuario no elige otra carpeta."""
    return default_db_path().parent / "Copias de seguridad"


def language_hint_path() -> Path:
    """Un archivo diminuto y sin cifrar con el idioma elegido (es, ca o en): la pantalla de contrasena sale antes de poder
    leer los datos cifrados, que es donde vive el idioma de verdad. No contiene nada personal. Tambien lo escribe el instalador."""
    return default_db_path().parent / "idioma.txt"


def read_language_hint() -> str | None:
    try:
        text = language_hint_path().read_text(encoding="utf-8").strip().lower()
    except OSError:
        return None
    return text if text in ("es", "ca", "en") else None


def write_language_hint(code: str) -> None:
    """Recuerda el idioma para la proxima pantalla de contrasena. Un fallo al escribir nunca debe estorbar."""
    try:
        path = language_hint_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if code in ("es", "ca", "en") and (not path.exists() or path.read_text(encoding="utf-8").strip() != code):
            path.write_text(code, encoding="utf-8")
    except OSError:
        pass


def legacy_db_path() -> Path:
    """La base sin cifrar de versiones anteriores (se migra la primera vez)."""
    return default_db_path()
