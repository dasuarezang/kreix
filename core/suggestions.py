"""Reglas sugeridas: comercios que se repiten entre los movimientos sin categoria, para crear una regla de un solo clic.

Logica pura. Una regla de Kreix es "si el concepto contiene PALABRA, va a la categoria X". La palabra que se sugiere es la primera
que identifica al comercio (se saltan las genericas: COMPRA, TARJETA, PAGO...), asi que siempre aparece tal cual en los conceptos.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from core.categorizer import normalize
from core.entities import TransactionDraft
from core.enums import TxCategory

MIN_REPEATS = 3                 # un comercio se sugiere si aparece al menos tres veces sin categoria
MIN_WORD_LENGTH = 4
MAX_SUGGESTIONS = 3
_GENERIC = frozenset("""
COMPRA COMPRAS PAGO PAGOS TARJETA TARJ RECIBO RECIBOS CARGO CARGOS ADEUDO TRANSFERENCIA TRANSF BIZUM DOMICILIACION DOMICILIADO
REFERENCIA OPERACION COMISION INGRESO INGRESOS ABONO RETIRADA CAJERO EFECTIVO PAGO. COMPRAS. TPV INTERNET ONLINE WEB COM
CON DEL LOS LAS UNA PARA POR SIN
""".split())


@dataclass(frozen=True, slots=True)
class RuleSuggestion:
    keyword: str                # la palabra para la regla (en mayusculas y sin acentos, como la compara Kreix)
    count: int                  # cuantos movimientos sin categoria la llevan
    total: Decimal              # lo que suman (en positivo)
    example: str                # el concepto COMPLETO del movimiento mas reciente, tal como sale en el extracto
    variants: int = 1           # cuantos conceptos distintos comparten la palabra


def keyword_of(description: str) -> str:
    """La palabra que identifica al comercio en un concepto ('' si no hay ninguna que sirva)."""
    for word in re.split(r"[^A-Z0-9]+", normalize(description)):
        if len(word) >= MIN_WORD_LENGTH and word not in _GENERIC and not word.isdigit() and not re.search(r"\d{3,}", word):
            return word
    return ""


def suggest_rules(transactions: list[TransactionDraft], limit: int = MAX_SUGGESTIONS) -> list[RuleSuggestion]:
    """Los comercios que mas se repiten entre los movimientos sin categoria, de mas a menos."""
    groups: dict[str, list[TransactionDraft]] = defaultdict(list)
    for t in transactions:
        if t.category is TxCategory.UNCATEGORIZED and not t.is_manual and (word := keyword_of(t.description)):
            groups[word].append(t)
    found = [
        RuleSuggestion(word, len(rows), sum((abs(t.amount) for t in rows), Decimal(0)), max(rows, key=lambda t: t.booking_date).description,
                       len({normalize(t.description) for t in rows}))
        for word, rows in groups.items() if len(rows) >= MIN_REPEATS
    ]
    found.sort(key=lambda s: (s.count, s.total), reverse=True)
    return found[:limit]


def uncategorized(transactions: list[TransactionDraft]) -> list[TransactionDraft]:
    return [t for t in transactions if t.category is TxCategory.UNCATEGORIZED]
