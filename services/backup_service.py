"""Copias de seguridad automaticas: una exportacion `.kreix` cifrada con la contrasena maestra, con fecha en el nombre.

Cuando se hace una copia:
- al abrir Kreix, si todavia no hay ninguna;
- despues de guardar cambios, como mucho una por hora;
- al cerrar, si hubo cambios desde la ultima.
Nunca se copian datos vacios ni se repite una copia sin cambios. Se conservan las ultimas N y se borran las mas viejas.

Una copia es un `.kreix` normal: se restaura con "Importar" (o desde Ajustes) escribiendo la contrasena maestra. Si se
cambia la contrasena, las copias se vuelven a cifrar con la nueva (si no, seguirian abriendose con la vieja).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from core.i18n import tr
from data.vault import CorruptVaultError, Vault, WrongPasswordError

PREFIX = "Kreix-copia-"
EXTENSION = ".kreix"
NAME = re.compile(r"^Kreix-copia-(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})(?:-(\d{2}))?\.kreix$")
KEEP_OPTIONS = (3, 5, 10, 20)
DEFAULT_KEEP = 10
INTERVAL = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class BackupConfig:
    enabled: bool
    folder: Path | None       # None = la carpeta por defecto
    keep: int


@dataclass(frozen=True, slots=True)
class BackupFile:
    path: Path
    moment: datetime
    size: int


def config_from(settings) -> BackupConfig:
    """Los ajustes de la aplicacion (`AppSettings`) vistos como configuracion de copias."""
    return BackupConfig(settings.backup_enabled, Path(settings.backup_folder) if settings.backup_folder else None,
                        settings.backup_keep)


def backup_name(moment: datetime, with_seconds: bool = False) -> str:
    stamp = moment.strftime("%Y-%m-%d_%H-%M" + ("-%S" if with_seconds else ""))
    return f"{PREFIX}{stamp}{EXTENSION}"


def parse_name(name: str) -> datetime | None:
    found = NAME.match(name)
    if not found:
        return None
    year, month, day, hour, minute, second = (int(g) if g else 0 for g in found.groups())
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


class BackupService:
    """`export(ruta)` escribe una copia cifrada en esa ruta; `config()` da los ajustes vigentes; `is_empty()` evita copiar nada."""

    def __init__(self, export: Callable[[Path], object], config: Callable[[], BackupConfig], default_folder: Path,
                 is_empty: Callable[[], bool] = lambda: False, clock: Callable[[], datetime] = datetime.now) -> None:
        self._export = export
        self._config = config
        self._default_folder = default_folder
        self._is_empty = is_empty
        self._clock = clock
        self.pending = False          # hay cambios guardados que aun no estan en ninguna copia
        self._check_first = True      # falta comprobar si la carpeta ya tiene alguna copia (se repite si cambia la carpeta)
        self.last_error = ""          # por que fallo la ultima copia (vacio si fue bien)
        self.last_note = ""           # aviso no grave (p. ej. se uso la carpeta por defecto)

    # ------------------------------------------------------------------ carpeta y lista
    def folder(self) -> Path:
        configured = self._config().folder
        return configured if configured else self._default_folder

    def files(self) -> list[BackupFile]:
        """Las copias de la carpeta, de la mas nueva a la mas vieja."""
        found: list[BackupFile] = []
        try:
            entries = list(self.folder().iterdir())
        except OSError:
            return []
        for entry in entries:
            moment = parse_name(entry.name)
            if moment is not None and entry.is_file():
                found.append(BackupFile(entry, moment, entry.stat().st_size))
        return sorted(found, key=lambda b: (b.moment, b.path.name), reverse=True)

    # ------------------------------------------------------------------ cuando copiar
    def note_saved(self) -> None:
        """Se guardaron cambios: la proxima copia ya tiene algo nuevo que recoger."""
        self.pending = True

    def folder_changed(self) -> None:
        """Se eligio otra carpeta: hay que ver si ya tiene copias (si no, se hace una enseguida)."""
        self._check_first = True

    def due(self) -> bool:
        if not self._config().enabled or not (self.pending or self._check_first):
            return False
        existing = self.files()
        if existing and not (self.pending and self._clock() - existing[0].moment >= INTERVAL):
            return False
        return not self._is_empty()

    def run_if_due(self) -> Path | None:
        if self.due():
            return self.create()
        if self._check_first and self._config().enabled and self.files():
            self._check_first = False                  # la carpeta ya tiene copias: no hace falta volver a mirar hasta que haya cambios
        return None

    def on_quit(self) -> Path | None:
        """Al cerrar: copia si hubo cambios desde la ultima (sin esperar la hora)."""
        if self.pending and self._config().enabled and not self._is_empty():
            return self.create()
        return None

    # ------------------------------------------------------------------ copiar
    def _writable_folder(self) -> Path:
        folder = self.folder()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            self.last_note = ""
            return folder
        except OSError:
            if folder == self._default_folder:
                raise
            self._default_folder.mkdir(parents=True, exist_ok=True)       # la elegida no existe aqui (p. ej. otro equipo)
            self.last_note = tr("No se pudo usar la carpeta elegida; las copias van a la carpeta por defecto.")
            return self._default_folder

    def create(self) -> Path | None:
        """Hace una copia ahora. Devuelve su ruta, o None si falla (el motivo queda en `last_error`)."""
        try:
            folder = self._writable_folder()
            now = self._clock()
            target = folder / backup_name(now)
            if target.exists():
                target = folder / backup_name(now, with_seconds=True)
            self._export(target)
        except Exception as exc:                  # noqa: BLE001 - una copia fallida nunca debe tumbar la aplicacion
            self.last_error = str(exc) or exc.__class__.__name__
            return None
        self.last_error = ""
        self.pending = False
        self._check_first = False
        self.prune(folder)
        return target

    def prune(self, folder: Path | None = None) -> int:
        """Borra las copias mas viejas por encima de las que hay que conservar. Devuelve cuantas borro."""
        keep = max(1, self._config().keep)
        removed = 0
        for old in self.files()[keep:]:
            try:
                old.path.unlink()
                removed += 1
            except OSError:
                pass
        return removed

    # ------------------------------------------------------------------ cambio de contrasena
    def rekey(self, old_password: str, seal: Callable[[bytes], bytes]) -> int:
        """Vuelve a cifrar las copias con la contrasena nueva (`seal`). Devuelve cuantas se cambiaron; las que no se abren
        con la contrasena vieja se dejan tal cual."""
        done = 0
        for backup in self.files():
            try:
                _vault, plain = Vault.unseal(backup.path.read_bytes(), old_password)
                partial = backup.path.with_name(backup.path.name + ".part")
                partial.write_bytes(seal(plain))
                partial.replace(backup.path)
                done += 1
            except (WrongPasswordError, CorruptVaultError, OSError):
                continue
        return done
