"""Detector de cambios reales en la base de datos y cache de resultados que se invalida con el.

Leer una pagina no cambia nada, pero SQLAlchemy emite un "commit" tambien al cerrar una sesion de solo lectura. Contar esos
commits haria que el guardado cifrado se repitiera tras cada lectura y que nada se pudiera reutilizar. Con una base en
memoria (un unico DBAPI connection) se mira `sqlite3.Connection.total_changes`, que solo sube cuando se escribe una fila.
Lo que modifica la base sin pasar por SQL (restaurar una copia con `backup`) avisa con `bump()`.
"""
from __future__ import annotations

import weakref
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy.pool import StaticPool

MAX_CACHED = 12              # resultados guardados (cada uno puede ser una lista de miles de movimientos)


class ChangeTracker:
    def __init__(self, engine: Engine) -> None:
        self.version = 0
        self._exact = isinstance(engine.pool, StaticPool)          # un solo DBAPI connection: total_changes es fiable
        self._seen = 0
        self._listeners: list[Callable[[], None]] = []
        self._cache: OrderedDict[Any, Any] = OrderedDict()
        self._cache_version = 0
        event.listen(engine, "commit", self._on_commit)

    def on_change(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _on_commit(self, conn) -> None:
        if self._exact:
            total = conn.connection.driver_connection.total_changes
            if total == self._seen:
                return                                              # commit de una sesion de solo lectura
            self._seen = total
        self.bump()

    def bump(self) -> None:
        """Hubo un cambio (tambien el que no pasa por SQL, como restaurar una copia)."""
        self.version += 1
        for callback in self._listeners:
            callback()

    # ------------------------------------------------------------------ cache
    def cached(self, key: Any, compute: Callable[[], Any]) -> Any:
        """El resultado de `compute()` mientras la base no cambie; se recalcula en cuanto hay un cambio."""
        if self._cache_version != self.version:
            self._cache.clear()
            self._cache_version = self.version
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        value = compute()
        if self._cache_version == self.version:                    # por si el calculo mismo escribio algo
            self._cache[key] = value
            while len(self._cache) > MAX_CACHED:
                self._cache.popitem(last=False)
        return value


_TRACKERS: "weakref.WeakKeyDictionary[Engine, ChangeTracker]" = weakref.WeakKeyDictionary()


def tracker_for(engine: Engine) -> ChangeTracker:
    """El detector de cambios de este motor (uno por motor)."""
    tracker = _TRACKERS.get(engine)
    if tracker is None:
        tracker = _TRACKERS[engine] = ChangeTracker(engine)
    return tracker
