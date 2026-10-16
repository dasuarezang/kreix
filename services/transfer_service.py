"""Exportar todos los datos a un archivo .kreix y restaurarlos en otra instalacion.

El archivo es un ZIP con dos entradas: `manifest.json` (version, fecha y totales) y
`kreix.db` (una copia consistente de la base de datos). Restaurar reemplaza los datos
del equipo por los del archivo, tal cual: cuentas, movimientos, categorias, ajustes y
la proteccion anti-duplicados se conservan.

Un archivo recibido puede venir de cualquier sitio, asi que se trata como no fiable:
solo se aceptan esas dos entradas, con tamano acotado; la base de datos se abre en solo
lectura, se comprueba su integridad y se rechaza si trae disparadores o vistas.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from data.tracker import tracker_for
from data.vault import MAGIC, CorruptVaultError, SessionSeal, Vault, WrongPasswordError
from data.database import SCHEMA_VERSION, init_db, session_scope
from data.models import Account, Investment, InvestmentOperation, Transaction, Valuation
from core.i18n import tr

FORMAT = "kreix-export"
FORMAT_VERSION = 1
EXTENSION = ".kreix"
DB_ENTRY, MANIFEST_ENTRY = "kreix.db", "manifest.json"
MAX_DB_BYTES = 1 << 30            # 1 GB
MAX_MANIFEST_BYTES = 1 << 20      # 1 MB
REQUIRED_TABLES = {"accounts", "transactions", "investments", "investment_operations", "valuations", "settings"}
APP_VERSION = "0.5.0"


class TransferError(ValueError):
    """El archivo no es un export valido de Kreix (o no se puede usar)."""


class PasswordRequired(TransferError):
    """El archivo esta cifrado: hay que pedir la contrasena maestra con la que se exporto."""


class WrongImportPassword(TransferError):
    """La contrasena no abre el archivo."""


def is_encrypted(path: str | Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


@dataclass(frozen=True, slots=True)
class DataSummary:
    accounts: int = 0
    transactions: int = 0
    operations: int = 0
    investments: int = 0
    valuations: int = 0

    @property
    def is_empty(self) -> bool:
        return not (self.transactions or self.operations or self.valuations or self.accounts)


@dataclass(frozen=True, slots=True)
class BackupInfo:
    exported_at: str
    app_version: str
    summary: DataSummary


def _image(engine: Engine) -> bytes:
    """Imagen consistente de la base de datos en memoria (sin archivos), en modo diario normal: un solo bloque."""
    with closing(engine.raw_connection()) as raw:
        data = bytearray(raw.driver_connection.serialize())
    if len(data) > 19 and data[18] == 2 and data[19] == 2:            # base en modo WAL: se guarda sin WAL
        data[18] = data[19] = 1
    return bytes(data)


def _sqlite_summary(conn: sqlite3.Connection) -> DataSummary:
    def count(table: str) -> int:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    return DataSummary(count("accounts"), count("transactions"), count("investment_operations"),
                       count("investments"), count("valuations"))


def _validate_database(path: Path) -> DataSummary:
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error as exc:                                   # pragma: no cover - ruta invalida
        raise TransferError(tr("No se pudo abrir la base de datos del archivo.")) from exc
    try:
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise TransferError(tr("La base de datos del archivo está dañada."))
            objects = conn.execute("SELECT type, name FROM sqlite_master").fetchall()
        except sqlite3.DatabaseError as exc:
            raise TransferError(tr("El archivo no contiene una base de datos válida.")) from exc
        if any(kind in ("trigger", "view") for kind, _ in objects):
            raise TransferError(tr("El archivo contiene elementos no permitidos y no se importará."))
        if not REQUIRED_TABLES <= {name for kind, name in objects if kind == "table"}:
            raise TransferError(tr("El archivo no tiene la estructura de datos de Kreix."))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise TransferError(tr("El archivo se creó con una versión más reciente de Kreix. Actualiza la aplicación."))
        return _sqlite_summary(conn)
    finally:
        conn.close()


class TransferService:
    def __init__(self, engine: Engine, factory: sessionmaker[Session]) -> None:
        self._engine = engine
        self._factory = factory
        self._seal = SessionSeal()          # clave solo en memoria: las copias de "Deshacer" nunca quedan en claro en disco

    # ------------------------------------------------------------------ resumen
    def summary(self) -> DataSummary:
        with session_scope(self._factory) as s:
            def count(model) -> int:
                return s.scalar(select(func.count()).select_from(model)) or 0

            return DataSummary(count(Account), count(Transaction), count(InvestmentOperation),
                               count(Investment), count(Valuation))

    # ------------------------------------------------------------------ exportar
    def export_to(self, path: str | Path, seal=None) -> DataSummary:
        """`seal`: funcion que cifra los bytes (la del almacen cifrado). Sin ella el archivo queda en claro."""
        target = Path(path)
        if target.suffix.lower() != EXTENSION:
            target = target.with_name(target.name + EXTENSION)
        image = _image(self._engine)                            # copia consistente, sin archivo temporal
        probe = sqlite3.connect(":memory:")
        try:
            probe.deserialize(image)
            summary = _sqlite_summary(probe)
        finally:
            probe.close()
        manifest = {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "counts": asdict(summary),
        }
        partial = target.with_name(target.name + ".part")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST_ENTRY, json.dumps(manifest, indent=2))
            zf.writestr(DB_ENTRY, image)
        partial.write_bytes(seal(buffer.getvalue()) if seal is not None else buffer.getvalue())
        os.replace(partial, target)                              # el archivo final aparece completo o no aparece
        return summary

    # ------------------------------------------------------------------ instantaneas (para "Deshacer")
    def snapshot(self) -> Path:
        """Copia consistente de la base de datos en un archivo temporal CIFRADO; quien la pide debe borrarla."""
        image = _image(self._engine)
        fd, name = tempfile.mkstemp(prefix="kreix-undo-", suffix=".bin")
        with os.fdopen(fd, "wb") as f:
            f.write(self._seal.seal(image))
        return Path(name)

    def restore_snapshot(self, path: str | Path) -> None:
        """Vuelve a los datos de una instantanea propia (no pasa por la validacion de archivos recibidos)."""
        image = self._seal.unseal(Path(path).read_bytes())
        src = sqlite3.connect(":memory:")
        try:
            src.deserialize(image)
            with closing(self._engine.raw_connection()) as raw:
                src.backup(raw.driver_connection)
        finally:
            src.close()
        init_db(self._engine)
        tracker_for(self._engine).bump()            # la copia entra sin pasar por SQL: se avisa a los que miran cambios

    # ------------------------------------------------------------------ leer un archivo
    @contextmanager
    def _opened(self, path: str | Path, password: str | None = None,
                unseal=None) -> Iterator[tuple[dict, Path, DataSummary]]:
        source: Path | io.BytesIO = Path(path)
        if not source.is_file():
            raise TransferError(tr("Este archivo no es una exportación de Kreix."))
        if is_encrypted(source):
            if unseal is not None:                     # una copia propia: se abre con la clave del almacen, sin pedir contrasena
                try:
                    source = io.BytesIO(unseal(source.read_bytes()))
                except WrongPasswordError as exc:
                    raise WrongImportPassword(tr("La copia no se abre con tu contraseña actual.")) from exc
                except CorruptVaultError as exc:
                    raise TransferError(tr("El archivo está dañado.")) from exc
        if isinstance(source, Path) and is_encrypted(source):
            if not password:
                raise PasswordRequired(tr("El archivo está cifrado: hace falta la contraseña maestra con la que se exportó."))
            try:
                _vault, plain = Vault.unseal(source.read_bytes(), password)
            except WrongPasswordError as exc:
                raise WrongImportPassword(tr("La contraseña no es correcta.")) from exc
            except CorruptVaultError as exc:
                raise TransferError(tr("El archivo está dañado.")) from exc
            source = io.BytesIO(plain)
        if not zipfile.is_zipfile(source):
            raise TransferError(tr("Este archivo no es una exportación de Kreix."))
        workdir = Path(tempfile.mkdtemp(prefix="kreix-import-"))
        try:
            with zipfile.ZipFile(source) as zf:
                infos = {i.filename: i for i in zf.infolist()}
                if set(infos) != {MANIFEST_ENTRY, DB_ENTRY}:
                    raise TransferError(tr("Este archivo no es una exportación de Kreix."))
                if infos[MANIFEST_ENTRY].file_size > MAX_MANIFEST_BYTES or infos[DB_ENTRY].file_size > MAX_DB_BYTES:
                    raise TransferError(tr("El archivo es demasiado grande para ser una exportación de Kreix."))
                try:
                    manifest = json.loads(zf.read(MANIFEST_ENTRY))
                except (ValueError, UnicodeDecodeError) as exc:
                    raise TransferError(tr("La ficha del archivo está dañada.")) from exc
                if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
                    raise TransferError(tr("Este archivo no es una exportación de Kreix."))
                if int(manifest.get("format_version", 0)) > FORMAT_VERSION:
                    raise TransferError(tr("El archivo se creó con una versión más reciente de Kreix. Actualiza la aplicación."))
                db_path = workdir / DB_ENTRY
                written = 0
                with zf.open(DB_ENTRY) as src, open(db_path, "wb") as out:
                    while chunk := src.read(1 << 20):
                        written += len(chunk)
                        if written > MAX_DB_BYTES:
                            raise TransferError(tr("El archivo es demasiado grande para ser una exportación de Kreix."))
                        out.write(chunk)
            yield manifest, db_path, _validate_database(db_path)
        except zipfile.BadZipFile as exc:
            raise TransferError(tr("El archivo está dañado.")) from exc
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def inspect(self, path: str | Path, password: str | None = None, unseal=None) -> BackupInfo:
        """Lee una exportacion sin restaurarla. `unseal` (la funcion del almacen) la abre sin pedir contrasena: asi se comprueba
        una copia de seguridad propia."""
        with self._opened(path, password, unseal) as (manifest, _db, summary):
            return BackupInfo(str(manifest.get("exported_at", "")), str(manifest.get("app_version", "")), summary)

    # ------------------------------------------------------------------ restaurar
    def restore(self, path: str | Path, password: str | None = None) -> DataSummary:
        """Reemplaza TODOS los datos actuales por los del archivo."""
        with self._opened(path, password) as (_manifest, db_path, summary):
            src = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
            try:
                with closing(self._engine.raw_connection()) as raw:
                    src.backup(raw.driver_connection)
            finally:
                src.close()
        init_db(self._engine)           # si el archivo es de una version anterior, se migra
        tracker_for(self._engine).bump()
        return summary
