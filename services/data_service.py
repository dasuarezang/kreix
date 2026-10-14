"""Caso de uso: gestion de los datos guardados (borrado total)."""
from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from data.database import session_scope
from data.models import Account, Investment


class DataService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def reset_all(self) -> None:
        """Borra cuentas, movimientos, operaciones, fondos y valoraciones.
        Los ajustes (tema, opciones de calculo) se conservan."""
        with session_scope(self._factory) as s:
            # los movimientos, operaciones y valoraciones caen en cascada con su cuenta/fondo
            s.execute(delete(Account))
            s.execute(delete(Investment))
