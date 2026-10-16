"""Traspasos entre las cuentas del propio usuario: lo que sale de una cuenta y entra en otra no es ni un gasto ni un ingreso.

Logica pura. Una salida y una entrada forman pareja si tienen el mismo importe, estan en cuentas distintas, caen con pocos dias
de diferencia y al menos una de las dos es un traspaso. Cada movimiento entra en una sola pareja (si hay varios posibles, se
unen primero los mas cercanos en fecha).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from decimal import Decimal

from core.entities import TransactionDraft
from core.enums import TxCategory

MAX_DAYS_APART = 3
# La otra mitad de un traspaso puede estar categorizada como cualquiera de estas (cada banco lo llama de una forma).
_OTHER_HALF = {TxCategory.TRANSFER, TxCategory.INCOME, TxCategory.SALARY, TxCategory.OTHER, TxCategory.UNCATEGORIZED}


def _eligible(t: TransactionDraft) -> bool:
    return t.account_id is not None and t.amount != 0 and t.category in _OTHER_HALF


def pair_transfers(transactions: list[TransactionDraft]) -> list[TransactionDraft]:
    """Los mismos movimientos, con `paired_with` (la cuenta de la otra mitad) en los que son traspasos entre cuentas propias."""
    outgoing: dict[Decimal, list[int]] = defaultdict(list)
    incoming: dict[Decimal, list[int]] = defaultdict(list)
    for index, t in enumerate(transactions):
        if _eligible(t):
            (outgoing if t.amount < 0 else incoming)[abs(t.amount)].append(index)

    partner: dict[int, int] = {}
    for amount, outs in outgoing.items():
        ins = incoming.get(amount)
        if not ins:
            continue
        candidates = []
        for o in outs:
            for i in ins:
                a, b = transactions[o], transactions[i]
                days = abs((a.booking_date - b.booking_date).days)
                if (days <= MAX_DAYS_APART and a.account_id != b.account_id
                        and (a.category is TxCategory.TRANSFER or b.category is TxCategory.TRANSFER)):
                    candidates.append((days, o, i))
        for _days, o, i in sorted(candidates):
            if o not in partner and i not in partner:
                partner[o], partner[i] = i, o
    if not partner:
        return transactions
    result = list(transactions)
    for index, other in partner.items():
        result[index] = replace(transactions[index], paired_with=transactions[other].account_id)
    return result
