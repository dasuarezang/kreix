"""Bancos que Kreix reconoce solos por las cabeceras de su extracto (ademas de Imagin y MyInvestor).

Cada banco se identifica por unas cabeceras que casi nadie mas usa; las columnas se eligen por su titulo, probando varios
nombres porque los bancos cambian la exportacion de vez en cuando y la tienen en varios idiomas. Si un archivo no encaja con
ninguno, no pasa nada: Kreix sigue ofreciendo el asistente para que el usuario diga que columna es cada cosa.
Modulo puro (sin Qt ni base de datos).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from etl.common import normalize_header
from etl.mapping import MAX_PREAMBLE_ROWS, ColumnMapping, FileSample, guess_day_first, guess_decimal_comma


@dataclass(frozen=True, slots=True)
class BankPreset:
    name: str
    signature: frozenset[str]                       # titulos (normalizados) que tiene que traer el archivo para ser de este banco
    date: tuple[str, ...]
    description: tuple[str, ...]                    # por orden de preferencia: se usa la primera con texto en cada fila
    amount: tuple[str, ...] = ()
    income: tuple[str, ...] = ()
    expense: tuple[str, ...] = ()
    balance: tuple[str, ...] = ()
    fee: tuple[str, ...] = ()
    currency: tuple[str, ...] = ()
    only_column: tuple[str, ...] = ()               # si se indica, solo se leen las filas cuyo valor en esa columna este en `only_values`
    only_values: tuple[str, ...] = ()


PRESETS: tuple[BankPreset, ...] = (
    BankPreset(
        "CaixaBank", frozenset({"f. operacion", "ingreso", "gasto", "saldo"}),
        date=("f. operacion",), description=("concepto complementario 1", "concepto propio", "concepto comun", "concepto"),
        income=("ingreso",), expense=("gasto",), balance=("saldo",), currency=("divisa",),
    ),
    BankPreset(
        "Santander", frozenset({"fecha operacion", "fecha valor", "concepto", "importe", "saldo"}),
        date=("fecha operacion",), description=("concepto",), amount=("importe",), balance=("saldo",), currency=("divisa",),
    ),
    BankPreset(
        "Revolut", frozenset({"started date", "completed date", "description", "amount"}),
        date=("completed date",), description=("description",), amount=("amount",), balance=("balance",), fee=("fee",),
        currency=("currency",),
    ),
    BankPreset(
        "Revolut", frozenset({"fecha de inicio", "fecha de finalizacion", "descripcion", "importe"}),
        date=("fecha de finalizacion",), description=("descripcion",), amount=("importe",), balance=("saldo",), fee=("comision",),
        currency=("divisa",),
    ),
    BankPreset(
        "Trade Republic", frozenset({"date", "category", "type", "amount", "transaction_id"}),
        date=("date",), description=("description", "counterparty_name", "name"), amount=("amount",), currency=("currency",),
        only_column=("category",), only_values=("CASH",),          # las compras y ventas de bolsa no son gastos de la cuenta
    ),
)


def _first(keys: set[str], options: tuple[str, ...]) -> str:
    return next((o for o in options if o in keys), "")


def recognize(rows: list[list[Any]]) -> tuple[ColumnMapping, int] | None:
    """(formato, fila de titulos) si el archivo es de un banco conocido; None si no."""
    for index, row in enumerate(rows[:MAX_PREAMBLE_ROWS]):
        keys = {normalize_header(c) for c in row}
        for preset in PRESETS:
            if not preset.signature <= keys:
                continue
            description = _first(keys, preset.description)
            fallbacks = tuple(k for k in preset.description if k in keys and k != description)
            sample = FileSample.of(rows, index)
            date = _first(keys, preset.date)
            amount = _first(keys, preset.amount)
            income, expense = ("", "") if amount else (_first(keys, preset.income), _first(keys, preset.expense))
            only = _first(keys, preset.only_column)
            mapping = ColumnMapping(
                name=preset.name, date=date, description=description, amount=amount, income=income, expense=expense,
                balance=_first(keys, preset.balance), day_first=guess_day_first(sample.column(date)),
                decimal_comma=guess_decimal_comma(sample.column(amount or income or expense)),
                description_fallbacks=fallbacks, fee=_first(keys, preset.fee), currency=_first(keys, preset.currency),
                only_column=only, only_values=preset.only_values if only else (),
            )
            if mapping.problem() is None:
                return mapping, index
    return None
