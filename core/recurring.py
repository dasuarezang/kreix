"""Pagos recurrentes (suscripciones, recibos...): gastos que se repiten cada mes por un importe parecido.

Logica pura. Un cargo es recurrente si se repite al menos 3 veces, en 3 meses distintos, con
unos 30 dias entre cargos y un importe estable (el supermercado no lo es: varia y es mas frecuente).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from datetime import date, timedelta
from decimal import Decimal
from statistics import median
from collections.abc import Mapping
from typing import Iterable

from core.categorizer import normalize
from core.entities import TransactionDraft
from core.enums import TxCategory

MIN_OCCURRENCES = 3
MONTHLY_GAP = (25, 35)          # dias entre cargos consecutivos
AMOUNT_TOLERANCE = Decimal("0.20")
ACTIVE_WITHIN_DAYS = 45         # un cargo que no se repite desde hace mas se da por cancelado
_IGNORED = {TxCategory.TRANSFER, TxCategory.INVESTMENT_TRANSFER, TxCategory.P2P, TxCategory.INCOME, TxCategory.SALARY}


@dataclass(frozen=True, slots=True)
class Recurring:
    name: str
    amount: Decimal             # importe habitual de cada cargo (positivo)
    occurrences: int
    last_date: date
    next_date: date             # fecha estimada del siguiente cargo
    category: TxCategory
    manual: bool = False        # lo marco el usuario (Kreix no lo habria detectado, o no del todo)
    gap_days: int = 30          # dias entre cargos


@lru_cache(maxsize=65536)
def merchant_key(description: str) -> str:
    """Clave del comercio: sin numeros ni referencias, que cambian de un cargo a otro."""
    words = [w for w in re.split(r"[^A-Z.]+", normalize(description)) if len(w) > 1]
    return " ".join(words[:3])


def detect_recurring(transactions: Iterable[TransactionDraft], today: date | None = None,
                     marks: Mapping[str, bool] | None = None) -> list[Recurring]:
    """Pagos recurrentes activos, de mayor a menor importe. `today` por defecto es el ultimo dia con datos.

    `marks` es lo que el usuario ha decidido por comercio (clave de `merchant_key`): `True` lo trata como recurrente aunque
    Kreix no lo detecte (con el ritmo y el importe que se vean en sus cargos; si solo hay uno, mensual) y `False` lo quita
    aunque Kreix lo detecte."""
    marks = marks or {}
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
        mark = marks.get(key)
        if mark is False:
            continue
        rows.sort(key=lambda t: t.booking_date)
        if mark:
            item = _manual(rows, reference)
            if item is not None:
                found.append(item)
            continue
        item = _regular(rows, reference)
        if item is not None:
            found.append(item)
    return sorted(found, key=lambda r: r.amount, reverse=True)


def _regular(rows: list[TransactionDraft], reference: date) -> Recurring | None:
    """Si estos movimientos (de un mismo comercio, por orden de fecha) se repiten como un pago mensual estable y activo."""
    months = {(t.booking_date.year, t.booking_date.month) for t in rows}
    if len(rows) < MIN_OCCURRENCES or len(months) < MIN_OCCURRENCES:
        return None
    gaps = [(b.booking_date - a.booking_date).days for a, b in zip(rows, rows[1:])]
    typical_gap = median(gaps)
    if not MONTHLY_GAP[0] <= typical_gap <= MONTHLY_GAP[1]:
        return None
    amounts = [abs(t.amount) for t in rows]
    typical = Decimal(median(amounts))
    if any(abs(a - typical) > typical * AMOUNT_TOLERANCE for a in amounts):
        return None
    last = rows[-1]
    if (reference - last.booking_date).days > ACTIVE_WITHIN_DAYS:
        return None
    return Recurring(
        name=last.description, amount=typical, occurrences=len(rows), last_date=last.booking_date,
        next_date=last.booking_date + timedelta(days=round(typical_gap)), category=last.category,
    )


def detect_recurring_income(transactions: Iterable[TransactionDraft], today: date | None = None) -> list[Recurring]:
    """Ingresos que llegan cada mes por un importe parecido (la nomina): el mismo criterio que los pagos, al reves. Un traspaso
    entre cuentas propias nunca cuenta como ingreso."""
    txs = list(transactions)
    if not txs:
        return []
    reference = today or max(t.booking_date for t in txs)
    groups: dict[str, list[TransactionDraft]] = defaultdict(list)
    for t in txs:
        if t.amount > 0 and t.category in (TxCategory.INCOME, TxCategory.SALARY) and t.paired_with is None and (key := merchant_key(t.description)):
            groups[key].append(t)
    found = []
    for rows in groups.values():
        rows.sort(key=lambda t: t.booking_date)
        item = _regular(rows, reference)
        if item is not None:
            found.append(item)
    return sorted(found, key=lambda r: r.amount, reverse=True)


MANUAL_GAP = (7, 400)           # ritmos que se aceptan en un pago marcado a mano (semanal ... anual)


def _manual(rows: list[TransactionDraft], reference: date) -> Recurring | None:
    """Un pago que el usuario ha marcado: su ritmo sale de sus cargos (mensual si solo hay uno)."""
    gaps = [(b.booking_date - a.booking_date).days for a, b in zip(rows, rows[1:])]
    gap = round(median(gaps)) if gaps else 30
    if not MANUAL_GAP[0] <= gap <= MANUAL_GAP[1]:
        gap = 30
    last = rows[-1]
    if (reference - last.booking_date).days > max(ACTIVE_WITHIN_DAYS, round(gap * 1.5)):
        return None                                     # lleva demasiado sin cobrarse: se da por cancelado
    return Recurring(
        name=last.description, amount=Decimal(median([-t.amount for t in rows])), occurrences=len(rows),
        last_date=last.booking_date, next_date=last.booking_date + timedelta(days=gap), category=last.category,
        manual=True, gap_days=gap,
    )


def monthly_cost(items: Iterable[Recurring]) -> Decimal:
    """Lo que suman los pagos al mes. Los de ritmo mensual cuentan su importe; los marcados a mano con otro ritmo se
    reparten (uno anual cuenta un doceavo)."""
    total = Decimal(0)
    for r in items:
        total += r.amount if MONTHLY_GAP[0] <= r.gap_days <= MONTHLY_GAP[1] else r.amount * 30 / r.gap_days
    return total
