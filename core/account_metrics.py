"""Metricas de las cuentas bancarias (efectivo): resumen por periodo y desglose de gastos."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Sequence

from core.entities import TransactionDraft
from core.enums import TxCategory
from core.metrics import FlowOptions, counts_as_flow, savings_rate, total_cash
from core.periods import Period, month_start

ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class CategoryAmount:
    category: TxCategory
    amount: Decimal             # gasto en positivo
    share: Decimal              # fraccion del gasto total


@dataclass(frozen=True, slots=True)
class AccountSummary:
    balance: Decimal | None                 # saldo al cierre del periodo
    income: Decimal
    expenses: Decimal                       # en positivo
    movements: int
    avg_daily_expense: Decimal | None
    avg_monthly_expense: Decimal | None
    largest_expense: TransactionDraft | None
    top_category: CategoryAmount | None

    @property
    def net(self) -> Decimal:
        return self.income - self.expenses

    @property
    def savings_rate(self) -> Decimal | None:
        return savings_rate(self.income, self.expenses)


def available_months(transactions: Iterable[TransactionDraft]) -> list[date]:
    """Meses con movimientos, del mas reciente al mas antiguo."""
    return sorted({month_start(t.booking_date) for t in transactions}, reverse=True)


def expense_breakdown(
    transactions: Iterable[TransactionDraft], options: FlowOptions = FlowOptions()
) -> list[CategoryAmount]:
    """Gasto por categoria, de mayor a menor. Solo cuenta lo que cuenta como gasto."""
    totals: dict[TxCategory, Decimal] = defaultdict(Decimal)
    for t in transactions:
        if t.amount < 0 and counts_as_flow(t.category, t.amount, options, t.paired_with):
            totals[t.category] += -t.amount
    grand = sum(totals.values(), ZERO)
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [CategoryAmount(c, a, a / grand) for c, a in ranked] if grand else []


def _span_days(first: date, last: date) -> int:
    return (last - first).days + 1


def summarize_account(
    transactions: Sequence[TransactionDraft], period: Period, options: FlowOptions = FlowOptions()
) -> AccountSummary:
    """Resumen de las cuentas dadas en un periodo. El saldo es el del cierre del periodo,
    aunque el periodo sea un mes (por eso recibe todos los movimientos, no solo los del mes)."""
    inside = [t for t in transactions if period.contains(t.booking_date)]
    income = sum((t.amount for t in inside if t.amount > 0 and counts_as_flow(t.category, t.amount, options, t.paired_with)), ZERO)
    expenses = sum((-t.amount for t in inside if t.amount < 0 and counts_as_flow(t.category, t.amount, options, t.paired_with)), ZERO)

    avg_daily = avg_monthly = None
    if inside:
        first = period.start or min(t.booking_date for t in inside)
        last = min(period.end, max(t.booking_date for t in transactions)) if period.end else max(t.booking_date for t in inside)
        days = max(_span_days(first, last), 1)
        months = (last.year - first.year) * 12 + last.month - first.month + 1
        avg_daily = expenses / days
        avg_monthly = expenses / max(months, 1)

    spending = [t for t in inside if t.amount < 0 and counts_as_flow(t.category, t.amount, options, t.paired_with)]
    breakdown = expense_breakdown(inside, options)
    return AccountSummary(
        balance=total_cash(transactions, as_of=period.end),
        income=income,
        expenses=expenses,
        movements=len(inside),
        avg_daily_expense=avg_daily,
        avg_monthly_expense=avg_monthly,
        largest_expense=min(spending, key=lambda t: t.amount) if spending else None,
        top_category=breakdown[0] if breakdown else None,
    )
