"""Base de datos de Kreix en memoria, respaldada por un archivo `.krx` cifrado.

La base de datos SQLite vive solo en RAM. Al abrir se descifra el `.krx` directamente a memoria (sin archivos temporales
en claro); al guardar se serializa y se cifra en bloque. Los servicios y las vistas siguen usando el mismo Engine de
SQLAlchemy de siempre: no saben que debajo hay un almacen cifrado.
"""
from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import StaticPool

from data.database import init_db
from data.paths import default_vault_path, legacy_db_path  # noqa: F401  (se reexportan)
from data.tracker import tracker_for
from data.vault import EXTENSION, Vault


def _memory_engine() -> Engine:
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def serialize(engine: Engine) -> bytes:
    with closing(engine.raw_connection()) as raw:
        return raw.driver_connection.serialize()


def rollback_journal(image: bytes) -> bytes:
    """Una base en modo WAL (la de versiones anteriores) no se puede abrir en memoria: se marca como diario normal."""
    data = bytearray(image)
    if len(data) > 19 and data[18] == 2 and data[19] == 2:
        data[18] = data[19] = 1
    return bytes(data)


def load_bytes(engine: Engine, data: bytes) -> None:
    data = rollback_journal(data)
    with closing(engine.raw_connection()) as raw:
        raw.driver_connection.deserialize(data)


class SecureStore:
    """Engine en memoria + archivo cifrado. `flush()` guarda solo si hubo cambios."""

    def __init__(self, path: Path, vault: Vault, engine: Engine) -> None:
        self.path = path
        self.engine = engine
        self._vault = vault
        self.dirty = False
        self._saved: list[Callable[[], None]] = []
        tracker_for(engine).on_change(self._mark_dirty)          # solo cambios reales: leer una pagina no obliga a guardar

    def _mark_dirty(self) -> None:
        self.dirty = True

    # ------------------------------------------------------------------ crear / abrir
    @classmethod
    def create(cls, path: Path, password: str, plain_db: bytes | None = None, iterations: int | None = None) -> "SecureStore":
        """Almacen nuevo. Si hay datos de una base anterior (`plain_db`), se cargan y quedan cifrados."""
        vault = Vault(password) if iterations is None else Vault(password, iterations=iterations)
        engine = _memory_engine()
        if plain_db:
            load_bytes(engine, plain_db)
        init_db(engine)
        store = cls(path, vault, engine)
        store.save()
        return store

    @classmethod
    def open(cls, path: Path, password: str) -> "SecureStore":
        """Descifra a memoria. Lanza `WrongPasswordError` si la contrasena no es la correcta."""
        vault, plain = Vault.unseal(path.read_bytes(), password)
        engine = _memory_engine()
        load_bytes(engine, plain)
        init_db(engine)                          # migra el esquema si el archivo es de una version anterior
        return cls(path, vault, engine)

    # ------------------------------------------------------------------ contrasena
    def change_password(self, old: str, new: str) -> None:
        """Cambia la contrasena maestra. Comprueba la actual (lanza `WrongPasswordError`), vuelve a cifrar con una
        clave y una sal nuevas y borra la copia `.bak`, que seguiria abriendose con la contrasena vieja."""
        Vault.unseal(self.path.read_bytes(), old)
        self._vault = Vault(new, iterations=self._vault.iterations)
        self.save()
        _erase(self.path, (".bak",))

    def verify_password(self, password: str) -> bool:
        """Comprueba la contrasena maestra sin tocar el disco (desbloqueo tras un bloqueo automatico)."""
        return self._vault.check(password)

    def unseal_export(self, blob: bytes) -> bytes:
        """Lo contrario de `seal_export`: abre una exportacion o copia de seguridad hecha con esta contrasena."""
        return self._vault.open_blob(blob)

    def seal_export(self, plain: bytes) -> bytes:
        """Cifra el contenido de una exportacion con la contrasena maestra (se abre con ella en cualquier equipo)."""
        return self._vault.seal(plain)

    # ------------------------------------------------------------------ guardar
    def on_saved(self, callback: Callable[[], None]) -> None:
        """Avisa cada vez que se guardan cambios en disco (para las copias de seguridad)."""
        self._saved.append(callback)

    def save(self) -> None:
        self._vault.write(self.path, serialize(self.engine))
        self.dirty = False
        for callback in self._saved:
            callback()

    def flush(self) -> bool:
        if not self.dirty:
            return False
        self.save()
        return True


def read_legacy_db(path: Path) -> bytes:
    """Contenido de la base sin cifrar (incluye lo que aun estuviera en el -wal)."""
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as conn:
        return rollback_journal(conn.serialize())


def erase_legacy_db(path: Path) -> None:
    """Borra la base sin cifrar y sus archivos auxiliares, sobrescribiendolos antes con ceros."""
    _erase(path, ("", "-wal", "-shm"))


def erase_vault(path: Path) -> None:
    """Restablecer: borra el almacen cifrado y su copia `.bak` (los datos se pierden para siempre)."""
    _erase(path, ("", ".bak", ".part"))


def _erase(path: Path, suffixes: tuple[str, ...]) -> None:
    for suffix in suffixes:
        target = path.with_name(path.name + suffix)
        if not target.exists():
            continue
        try:
            size = target.stat().st_size
            with open(target, "r+b") as f:
                f.write(b"\x00" * size)
                f.flush()
                os.fsync(f.fileno())
        except OSError:                                          # pragma: no cover - sin permiso de escritura
            pass
        try:
            target.unlink(missing_ok=True)
        except OSError:                                          # pragma: no cover - archivo en uso: no debe romper el arranque
            pass
