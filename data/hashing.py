"""Hash de movimientos acotado a una cuenta (el mismo extracto en dos cuentas no colisiona)."""
from __future__ import annotations

import hashlib


def scoped_hash(account_id: int, tx_hash: str) -> str:
    return hashlib.sha256(f"{account_id}\x1f{tx_hash}".encode("utf-8")).hexdigest()
