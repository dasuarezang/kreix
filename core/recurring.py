"""Pagos recurrentes (suscripciones, recibos...): gastos que se repiten cada mes por un importe parecido.

Logica pura. Un cargo es recurrente si se repite al menos 3 veces, en 3 meses distintos, con
unos 30 dias entre cargos y un importe estable (el supermercado no lo es: varia y es mas frecuente).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median
from typing import Iterable

from core.categorizer import normalize
from core.entities import TransactionDraft
from core.enums import TxCategory

MIN_OCCURRENCES = 3
MONTHLY_GAP = (25, 35)          # dias entre cargos consecutivos
AMOUNT_TOLERANCE = Decimal("0.20")
ACTIVE_WITHIN_DAYS = 45         # un cargo que no se repite desde hace mas se da por cancelado
_IGNORED = {TxCategory.TRANSFER, TxCategory.INVESTMENT_TRANSFER, TxCategory.P2P, TxCategory.INCOME}


@dataclass(frozen=True, slots=True)
class Recurring:
    name: str
    amount: Decimal             # importe habitual de cada cargo (positivo)
    occurrences: int
    last_date: date
    next_date: date             # fecha estimada del siguiente cargo
    category: TxCategory


def merchant_key(description: str) -> str:
    """Clave del comercio: sin numeros ni referencias, que cambian de un cargo a otro."""
    words = [w for w in re.split(r"[^A-Z.]+", normalize(description)) if len(w) > 1]
    return " ".join(words[:3])


def detect_recurring(transactions: Iterable[TransactionDraft], today: date | None = None) -> list[Recurring]:
    """Pagos recurrentes activos, de mayor a menor importe. `today` por defecto es el ultimo dia con datos."""
    txs = list(transactions)
    if not txs:
        return []
    reference = today or max(t.booking_date for t in txs)
    groups: dict[str, list[TransactionDraft]] = defaultdict(list)
    for t in txs:
        if t.amount < 0 and t.category not in _IGNORED and (key := merchant_key(t.description)):
            groups[key].append(t)

    found: list[Recurring] = []
    for key, rows in groups.items():
        rows.sort(key=lambda t: t.booking_date)
        months = {(t.booking_date.year, t.booking_date.month) for t in rows}
        if len(rows) < MIN_OCCURRENCES or len(months) < MIN_OCCURRENCES:
            continue
        gaps = [(b.booking_date - a.booking_date).days for a, b in zip(rows, rows[1:])]
        typical_gap = median(gaps)
        if not MONTHLY_GAP[0] <= typical_gap <= MONTHLY_GAP[1]:
            continue
        amounts = [-t.amount for t in rows]
        typical = Decimal(median(amounts))
        if any(abs(a - typical) > typical * AMOUNT_TOLERANCE for a in amounts):
            continue
        last = rows[-1]
        if (reference - last.booking_date).days > ACTIVE_WITHIN_DAYS:
            continue
        found.append(Recurring(
            name=last.description, amount=typical, occurrences=len(rows), last_date=last.booking_date,
            next_date=last.booking_date + timedelta(days=round(typical_gap)), category=last.category,
        ))
    return sorted(found, key=lambda r: r.amount, reverse=True)


def monthly_cost(items: Iterable[Recurring]) -> Decimal:
    return sum((r.amount for r in items), Decimal(0))
