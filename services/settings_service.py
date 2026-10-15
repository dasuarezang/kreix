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
        return AppSettings(
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
            "language": normalize_language(settings.language),
            "interest_accounts": "1" if settings.interest_accounts or not settings.interest_investments else "0",
            "interest_investments": "1" if settings.interest_investments else "0",
        }
        with session_scope(self._factory) as s:
            for key, value in values.items():
                s.merge(Setting(key=key, value=value))
