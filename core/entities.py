"""Objetos de dominio que producen los parsers (ETL) y consumen los repositorios.

Son inmutables y no conocen SQLAlchemy ni pandas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

from core.enums import Bank, OperationType, TxCategory


class FileKind(str, Enum):
    IMAGIN_STATEMENT = "imagin_extracto"
    MYINVESTOR_OPERATIONS = "myinvestor_operaciones"
    MYINVESTOR_PORTFOLIO = "myinvestor_cartera"


@dataclass(frozen=True, slots=True)
class TransactionDraft:
    bank: Bank
    booking_date: date
    description: str
    amount: Decimal                 # >0 ingreso, <0 gasto
    balance_after: Decimal | None
    category: TxCategory
    tx_hash: str
    source_file: str


@dataclass(frozen=True, slots=True)
class OperationDraft:
    bank: Bank
    isin: str
    product_name: str
    op_type: OperationType
    trade_date: date
    value_date: date | None
    units: Decimal
    unit_price: Decimal | None
    amount: Decimal                 # efectivo: <0 compra (sale de la cuenta), >0 venta
    tx_hash: str
    source_file: str


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    """Foto de una posicion en una fecha (extracto de cartera)."""

    isin: str
    product_name: str
    units: Decimal
    avg_cost: Decimal
    unit_price: Decimal             # valor liquidativo actual
    invested: Decimal
    market_value: Decimal
    as_of: date


@dataclass(slots=True)
class ParseResult:
    kind: FileKind
    source_file: str
    transactions: list[TransactionDraft] = field(default_factory=list)
    operations: list[OperationDraft] = field(default_factory=list)
    positions: list[PositionSnapshot] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # nada se descarta en silencio
