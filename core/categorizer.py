"""Categorizacion por reglas (diccionario de palabras clave). Logica pura.

Las reglas se evaluan en orden: la primera que coincide gana. Una palabra clave
coincide si aparece al inicio de una palabra del concepto (sin acentos, en mayusculas),
asi "SUPERMERC" casa con "PROXIM SUPERMERCA" pero "DIA" no casa con "MEDIAMARKT".
"""
from __future__ import annotations

import re
from functools import lru_cache
import unicodedata
from collections.abc import Sequence
from decimal import Decimal

from core.enums import TxCategory

Rules = list[tuple[TxCategory, tuple[str, ...]]]

DEFAULT_RULES: Rules = [
    (TxCategory.INVESTMENT_TRANSFER, ("MYINVESTOR",)),
    (TxCategory.TRANSFER, ("TRASPASO",)),
    (TxCategory.P2P, ("BIZUM",)),
    (TxCategory.SUBSCRIPTIONS, (
        "APPLE.COM/BILL", "ANTHROPIC", "OPENAI", "SPOTIFY", "NETFLIX", "HBO", "DISNEY",
        "YOUTUBE", "AMAZON PRIME", "SPLIIIT", "ICLOUD", "GOOGLE ONE", "DROPBOX",
    )),
    (TxCategory.GROCERIES, (
        "MERCADONA", "ESSELUNGA", "SUPERMERC", "CARREFOUR", "LIDL", "ALDI", "BONPREU",
        "CONSUM", "ALCAMPO", "EROSKI", "CAPRABO", "CONAD", "COOP",
    )),
    (TxCategory.DINING, (
        "GLOVO", "UBER EATS", "JUST EAT", "DELIVEROO", "PIZZERIA", "RESTAURA", "MCDONALD",
        "BURGER", "CAFE", "CAFETERIA", "STARBUCKS", "TRATTORIA",
    )),
    (TxCategory.TRANSPORT, (
        "TRENORD", "RENFE", "CLESS TICKET", "AEROPUERTO", "AEROPORT", "UBER", "CABIFY",
        "BOLT", "TMB", "RYANAIR", "VUELING", "IBERIA", "GASOLINERA", "REPSOL", "CEPSA",
        "METRO", "FLIXBUS", "ALSA",
    )),
    (TxCategory.LEISURE, (
        "CLIMBING", "CINE", "STEAM", "PLAYSTATION", "TICKETMASTER", "GYM", "GIMNASIO",
        "DECATHLON", "ENTRADAS", "MUSEO", "TEATRO",
    )),
    (TxCategory.HOUSING, ("RENTALS", "ALQUILER", "ENDESA", "IBERDROLA", "NATURGY", "AGUAS")),
    (TxCategory.HEALTH, ("FARMACIA", "CLINICA", "DENTAL", "OPTICA", "HOSPITAL")),
    (TxCategory.INCOME, ("NOMINA", "SALARIO", "TRANSFERENCIA RECIBIDA", "PAYROLL")),
]


@lru_cache(maxsize=65536)          # funcion pura y los mismos conceptos se repiten mucho (comercios, suscripciones)
def normalize(text: str) -> str:
    """Mayusculas, sin acentos y espacios colapsados."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).strip().upper()


def _compile(rules: Rules) -> list[tuple[TxCategory, re.Pattern[str]]]:
    return [
        (cat, re.compile("|".join(r"(?<![A-Z0-9])" + re.escape(k.strip()) for k in kws)))
        for cat, kws in rules
    ]


class Categorizer:
    """`user_rules` (palabra clave -> categoria) se evaluan antes que las de serie."""

    def __init__(self, rules: Rules | None = None, user_rules: Sequence[tuple[str, TxCategory]] = ()) -> None:
        own: Rules = [(cat, (kw,)) for kw, cat in user_rules]
        self._compiled = _compile(own + (rules or DEFAULT_RULES))
        self._memo: dict[tuple[str, bool], TxCategory] = {}      # el resultado solo depende del concepto y del signo

    def categorize(self, description: str, amount: Decimal) -> TxCategory:
        key = (description, amount > 0)
        found = self._memo.get(key)
        if found is None:
            found = self._memo[key] = self._categorize(description, amount)
        return found

    def _categorize(self, description: str, amount: Decimal) -> TxCategory:
        text = normalize(description)
        for category, pattern in self._compiled:
            if pattern.search(text):
                return category
        # Sin regla: un ingreso desconocido es ingreso; un gasto queda para revision manual.
        return TxCategory.INCOME if amount > 0 else TxCategory.UNCATEGORIZED
