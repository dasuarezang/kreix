"""Presupuestos mensuales por categoria de gasto. Logica pura."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping

from core.account_metrics import CategoryAmount
from core.enums import TxCategory

# Categorias en las que tiene sentido fijar un tope de gasto (no ingresos ni movimientos entre cuentas).
BUDGETABLE = (
    TxCategory.GROCERIES, TxCategory.DINING, TxCategory.SUBSCRIPTIONS, TxCategory.LEISURE, TxCategory.TRANSPORT,
    TxCategory.HOUSING, TxCategory.HEALTH, TxCategory.P2P, TxCategory.OTHER, TxCategory.UNCATEGORIZED,
)
WARN_AT = Decimal("0.85")


@dataclass(frozen=True, slots=True)
class BudgetLine:
    category: TxCategory
    budget: Decimal
    spent: Decimal              # gasto del periodo (por mes si el periodo abarca varios)

    @property
    def remaining(self) -> Decimal:
        return self.budget - self.spent

    @property
    def ratio(self) -> Decimal:
        return self.spent / self.budget

    @property
    def state(self) -> str:
        """'ok', 'warn' (cerca del tope) o 'over' (superado)."""
        if self.spent > self.budget:
            return "over"
        return "warn" if self.ratio >= WARN_AT else "ok"


def budget_lines(
    budgets: Mapping[TxCategory, Decimal], spending: Iterable[CategoryAmount], months: int = 1
) -> list[BudgetLine]:
    """Una linea por categoria con presupuesto, de la mas consumida a la menos.
    `months` reparte el gasto de un periodo largo para compararlo con el tope mensual."""
    spent = {c.category: c.amount / max(months, 1) for c in spending}
    lines = [BudgetLine(cat, amount, spent.get(cat, Decimal(0))) for cat, amount in budgets.items() if amount > 0]
    return sorted(lines, key=lambda line: line.ratio, reverse=True)
