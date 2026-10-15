"""Conexion, sesiones e inicializacion de la base de datos SQLite."""
from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from data.hashing import scoped_hash
from data.paths import default_db_path  # noqa: F401  (se reexporta: es la ruta de siempre)
from data.models import Base

SCHEMA_VERSION = 5  # v2: hashes con cuenta; v3: reglas y presupuestos; v4: metas e historico de precios; v5: marcas de pagos recurrentes
_HASHED_TABLES = ("transactions", "investment_operations")


def make_engine(url: str | None = None) -> Engine:
    """Crea el engine. `url` permite ":memory:" en tests o un driver cifrado
    (p. ej. sqlcipher) en el futuro sin tocar el resto del codigo."""
    if url is None:
        path = default_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{path}"
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return engine


def init_db(engine: Engine) -> None:
    """Crea las tablas si no existen y migra bases de datos antiguas.
    (Alembic llegara mas adelante; mientras tanto basta `PRAGMA user_version`.)"""
    Base.metadata.create_all(engine)
    _migrate(engine)


def _migrate(engine: Engine) -> None:
    with engine.begin() as conn:
        version = conn.exec_driver_sql("PRAGMA user_version").scalar() or 0
        if version < 2:
            for table in _HASHED_TABLES:
                rows = conn.exec_driver_sql(f"SELECT id, account_id, tx_hash FROM {table}").all()
                for row_id, account_id, tx_hash in rows:
                    conn.exec_driver_sql(
                        f"UPDATE {table} SET tx_hash = ? WHERE id = ?", (scoped_hash(account_id, tx_hash), row_id)
                    )
        if version < SCHEMA_VERSION:
            conn.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Sesion transaccional: commit si todo va bien, rollback si falla."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
