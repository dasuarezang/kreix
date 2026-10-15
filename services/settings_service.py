"""Preferencias de usuario persistidas en la tabla `settings`."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.metrics import FlowOptions
from data.database import session_scope
from data.models import Setting

THEMES = ("dark", "light")


@dataclass(frozen=True, slots=True)
class AppSettings:
    theme: str = "dark"
    include_p2p: bool = True
    transfers_in_as_income: bool = True

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
        return AppSettings(
            theme=theme if theme in THEMES else default.theme,
            include_p2p=stored.get("include_p2p", "1") == "1",
            transfers_in_as_income=stored.get("transfers_in_as_income", "1") == "1",
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
        }
        with session_scope(self._factory) as s:
            for key, value in values.items():
                s.merge(Setting(key=key, value=value))
