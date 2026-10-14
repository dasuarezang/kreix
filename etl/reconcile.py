"""Cuadre entre el extracto de cartera (verdad actual) y el historico de operaciones."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from core.entities import OperationDraft, PositionSnapshot
from core.enums import OperationType

TOLERANCE = Decimal("0.0001")


def reconcile_portfolio(positions: list[PositionSnapshot], operations: list[OperationDraft]) -> list[str]:
    net: dict[str, Decimal] = defaultdict(Decimal)
    for op in operations:
        if op.op_type is OperationType.BUY:
            net[op.isin] += op.units
        elif op.op_type is OperationType.SELL:
            net[op.isin] -= op.units

    warnings: list[str] = []
    held = {p.isin: p for p in positions}
    for isin, pos in held.items():
        diff = pos.units - net.get(isin, Decimal(0))
        if abs(diff) > TOLERANCE:
            warnings.append(
                f"{pos.product_name} ({isin}): la cartera tiene {pos.units} participaciones y las "
                f"operaciones importadas suman {net.get(isin, Decimal(0))}. Faltan operaciones por importar."
            )
    for isin, units in net.items():
        if units > TOLERANCE and isin not in held:
            warnings.append(
                f"{isin}: las operaciones dejan {units} participaciones pero no aparece en la cartera "
                "(vendido, traspasado o extracto de cartera incompleto)."
            )
    return warnings
