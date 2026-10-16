"""Preferencias de usuario persistidas en la tabla `settings`."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.metrics import FlowOptions
from data.database import session_scope
from data.models import Setting
from core.greeting import clean_name
from core.i18n import normalize_language

THEMES = ("dark", "light")
LOCK_MINUTES = (0, 1, 2, 5, 10, 15, 30)       # 0 = nunca se bloquea solo
DEFAULT_LOCK_MINUTES = 5
BACKUP_KEEP = (3, 5, 10, 20)                  # cuantas copias automaticas se conservan
DEFAULT_BACKUP_KEEP = 10


@dataclass(frozen=True, slots=True)
class AppSettings:
    theme: str = "dark"
    include_p2p: bool = True
    transfers_in_as_income: bool = True
    user_name: str = ""             # como se saluda al usuario; viaja con los datos al exportar e importar
    interest_accounts: bool = True       # le interesa gestionar sus cuentas bancarias
    interest_investments: bool = True    # le interesa gestionar sus inversiones (siempre al menos uno de los dos)
    language: str = "es"            # idioma de la interfaz: es, ca o en
    ambient: bool = True            # cielo animado en Inicio y luz que baja ligeramente segun la hora
    name_asked: bool = False        # ya se le pregunto el nombre (para no volver a pedirlo si dijo "ahora no")
    auto_lock_minutes: int = DEFAULT_LOCK_MINUTES   # minutos sin tocar el equipo antes de pedir de nuevo la contrasena (0 = nunca)
    lock_on_minimize: bool = True   # pedir la contrasena al minimizar la ventana
    backup_enabled: bool = True     # copias de seguridad automaticas cifradas
    backup_keep: int = DEFAULT_BACKUP_KEEP          # cuantas se conservan
    backup_folder: str = ""         # carpeta elegida ("" = la de por defecto, junto a los datos)

    @property
    def flow_options(self) -> FlowOptions:
        return FlowOptions(self.include_p2p, self.transfers_in_as_income)


class SettingsService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def load(self) -> AppSettings:
        with session_scope(self._factory) as s:
            stored = {row.key: row.value for row in s.scalars(select(Setting))}
        default = AppSettings()
        theme = stored.get("theme", default.theme)
        accounts = stored.get("interest_accounts", "1") == "1"
        investments = stored.get("interest_investments", "1") == "1"
        if not (accounts or investments):            # un valor corrupto: nunca se queda sin ningun interes
            accounts = investments = True
        try:
            lock_minutes = int(stored.get("auto_lock_minutes", DEFAULT_LOCK_MINUTES))
        except ValueError:
            lock_minutes = DEFAULT_LOCK_MINUTES
        try:
            backup_keep = int(stored.get("backup_keep", DEFAULT_BACKUP_KEEP))
        except ValueError:
            backup_keep = DEFAULT_BACKUP_KEEP
        return AppSettings(
            backup_enabled=stored.get("backup_enabled", "1") == "1",
            backup_keep=backup_keep if backup_keep in BACKUP_KEEP else DEFAULT_BACKUP_KEEP,
            backup_folder=stored.get("backup_folder", "").strip(),
            auto_lock_minutes=lock_minutes if lock_minutes in LOCK_MINUTES else DEFAULT_LOCK_MINUTES,
            lock_on_minimize=stored.get("lock_on_minimize", "1") == "1",
            theme=theme if theme in THEMES else default.theme,
            include_p2p=stored.get("include_p2p", "1") == "1",
            transfers_in_as_income=stored.get("transfers_in_as_income", "1") == "1",
            user_name=clean_name(stored.get("user_name", "")),
            name_asked=stored.get("name_asked", "0") == "1",
            ambient=stored.get("ambient", "1") == "1",
            interest_accounts=accounts,
            interest_investments=investments,
            language=normalize_language(stored.get("language")),
        )

    def load_state(self) -> dict[str, str]:
        """Estado de la interfaz (ultima pagina, tamano de la ventana): claves con prefijo `ui.`."""
        with session_scope(self._factory) as s:
            return {row.key[3:]: row.value for row in s.scalars(select(Setting)) if row.key.startswith("ui.")}

    def clear_state(self, *keys: str) -> None:
        with session_scope(self._factory) as s:
            for key in keys:
                row = s.get(Setting, f"ui.{key}")
                if row is not None:
                    s.delete(row)

    def save_state(self, **values: str | int) -> None:
        with session_scope(self._factory) as s:
            for key, value in values.items():
                s.merge(Setting(key=f"ui.{key}", value=str(value)))

    def save(self, settings: AppSettings) -> None:
        values = {
            "theme": settings.theme,
            "include_p2p": "1" if settings.include_p2p else "0",
            "transfers_in_as_income": "1" if settings.transfers_in_as_income else "0",
            "user_name": clean_name(settings.user_name),
            "name_asked": "1" if settings.name_asked else "0",
            "ambient": "1" if settings.ambient else "0",
            "auto_lock_minutes": str(settings.auto_lock_minutes if settings.auto_lock_minutes in LOCK_MINUTES else DEFAULT_LOCK_MINUTES),
            "lock_on_minimize": "1" if settings.lock_on_minimize else "0",
            "backup_enabled": "1" if settings.backup_enabled else "0",
            "backup_keep": str(settings.backup_keep if settings.backup_keep in BACKUP_KEEP else DEFAULT_BACKUP_KEEP),
            "backup_folder": settings.backup_folder.strip(),
            "language": normalize_language(settings.language),
            "interest_accounts": "1" if settings.interest_accounts or not settings.interest_investments else "0",
            "interest_investments": "1" if settings.interest_investments else "0",
        }
        with session_scope(self._factory) as s:
            for key, value in values.items():
                s.merge(Setting(key=key, value=value))
