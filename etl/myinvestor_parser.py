"""Parsers de MyInvestor: extracto de operaciones y extracto de cartera."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from core.categorizer import normalize
from core.entities import FileKind, OperationDraft, ParseResult, PositionSnapshot
from core.enums import Bank, OperationType
from etl.common import HashFactory, ParseError, Table, clean_text, to_date, to_decimal

OPS_REQUIRED = {"fecha operacion", "isin", "tipo operacion", "participaciones", "importe"}
PORTFOLIO_REQUIRED = {"producto", "isin", "participaciones totales", "valor liquidativo actual"}


def _operation_type(raw: str) -> OperationType | None:
    t = normalize(raw)
    if t.startswith("SUSCRIP") or "COMPRA" in t or "TRASPASO DE ENTRADA" in t or "ENTRADA" in t:
        return OperationType.BUY
    if t.startswith("REEMBOLSO") or "VENTA" in t or "TRASPASO DE SALIDA" in t or "SALIDA" in t:
        return OperationType.SELL
    return None


def parse_operations(table: Table, source_file: str) -> ParseResult:
    missing = OPS_REQUIRED - set(table.columns)
    if missing:
        raise ParseError(f"Faltan columnas de operaciones de MyInvestor: {sorted(missing)}")
    hashes = HashFactory(Bank.MYINVESTOR.value)
    result = ParseResult(FileKind.MYINVESTOR_OPERATIONS, source_file)

    for line, row in enumerate(table.rows, start=2):
        status = normalize(str(row.get("estado") or "EJECUTADA"))
        if status != "EJECUTADA":
            result.warnings.append(f"Fila {line} omitida: estado '{row.get('estado')}' (no ejecutada).")
            continue
        op_type = _operation_type(row["tipo operacion"])
        if op_type is None:
            result.warnings.append(f"Fila {line} omitida: tipo de operacion desconocido '{row['tipo operacion']}'.")
            continue
        try:
            trade = to_date(row["fecha operacion"])
            value = to_date(row["fecha valor"]) if str(row.get("fecha valor") or "").strip() else None
            units = to_decimal(row["participaciones"])
            nav = to_decimal(row["valor liquidativo"]) if str(row.get("valor liquidativo") or "").strip() else None
            amount = abs(to_decimal(row["importe"]))
        except ParseError as exc:
            result.warnings.append(f"Fila {line} ignorada: {exc}")
            continue
        isin = clean_text(row["isin"]).upper()
        cash = -amount if op_type is OperationType.BUY else amount
        if nav is not None and amount and abs(units * nav - amount) / amount > Decimal("0.005"):
            result.warnings.append(
                f"Fila {line}: participaciones x valor liquidativo ({units * nav:.2f}) "
                f"difiere del importe ({amount:.2f})."
            )
        result.operations.append(
            OperationDraft(
                bank=Bank.MYINVESTOR,
                isin=isin,
                product_name=clean_text(row.get("producto")),
                op_type=op_type,
                trade_date=trade,
                value_date=value,
                units=units,
                unit_price=nav,
                amount=cash,
                tx_hash=hashes.make(isin, trade, op_type.value, units, nav, amount),
                source_file=source_file,
            )
        )
    return result


def parse_portfolio(table: Table, source_file: str, as_of: date | None = None) -> ParseResult:
    """El extracto de cartera no incluye fecha: se usa `as_of` (por defecto, hoy)."""
    missing = PORTFOLIO_REQUIRED - set(table.columns)
    if missing:
        raise ParseError(f"Faltan columnas de cartera de MyInvestor: {sorted(missing)}")
    as_of = as_of or date.today()
    result = ParseResult(FileKind.MYINVESTOR_PORTFOLIO, source_file)

    for line, row in enumerate(table.rows, start=2):
        try:
            units = to_decimal(row["participaciones totales"])
            nav = to_decimal(row["valor liquidativo actual"])
            market = to_decimal(row["valor de mercado"])
            invested = to_decimal(row["capital invertido"])
            avg = to_decimal(row["precio medio compra"])
        except (ParseError, KeyError) as exc:
            result.warnings.append(f"Fila {line} ignorada: {exc}")
            continue
        if abs(units * nav - market) > Decimal("0.05"):
            result.warnings.append(
                f"Fila {line}: participaciones x valor liquidativo ({units * nav:.2f}) "
                f"difiere del valor de mercado ({market:.2f})."
            )
        result.positions.append(
            PositionSnapshot(
                isin=clean_text(row["isin"]).upper(),
                product_name=clean_text(row["producto"]),
                units=units,
                avg_cost=avg,
                unit_price=nav,
                invested=invested,
                market_value=market,
                as_of=as_of,
            )
        )
    return result
