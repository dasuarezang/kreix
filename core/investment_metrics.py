"""Metricas de la cartera de inversion por periodo (mes o global)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Sequence

from core import metrics
from core.entities import OperationDraft, PositionSnapshot
from core.enums import OperationType
from core.metrics import AllocationSlice
from core.periods import Period, month_start, next_month, previous_month_end

ZERO = Decimal(0)
_TRADES = (OperationType.BUY, OperationType.SELL)


@dataclass(frozen=True, slots=True)
class InvestmentSummary:
    positions: int
    value: Decimal                          # global: valor de mercado actual; mes: estimado al cierre
    contributions_total: Decimal            # aportado neto (compras - ventas) hasta el fin del periodo
    contributions_period: Decimal           # aportado neto dentro del periodo
    gain: Decimal | None                    # plusvalia total segun la cartera (solo global)
    simple_return: Decimal | None           # rentabilidad sobre capital invertido (solo global)
    period_gain: Decimal | None             # variacion de valor del periodo, sin contar aportaciones
    twr: float | None                       # rentabilidad ponderada: acumulada (global) o del mes
    xirr: float | None                      # TIR anualizada (solo global)
    operations: int
    buys: int
    sells: int
    avg_monthly_contribution: Decimal | None
    largest_position: AllocationSlice | None


def available_months(operations: Iterable[OperationDraft], snapshots: Iterable[PositionSnapshot]) -> list[date]:
    """Meses desde la primera operacion hasta el ultimo dato, del mas reciente al mas antiguo."""
    ops = [o.trade_date for o in operations if o.op_type in _TRADES]
    if not ops:
        return []
    last = max(ops + [s.as_of for s in snapshots])
    months: list[date] = []
    m = month_start(min(ops))
    while m <= last:
        months.append(m)
        m = next_month(m)
    return months[::-1]


def estimated_value(operations: Sequence[OperationDraft], snapshots: Sequence[PositionSnapshot], on: date) -> Decimal:
    return metrics.estimated_value(operations, snapshots, on)


def _net_contributions(ops: Iterable[OperationDraft], period: Period) -> Decimal:
    return sum((-o.amount for o in ops if o.op_type in _TRADES and period.contains(o.trade_date)), ZERO)


def summarize_investment(
    operations: Sequence[OperationDraft], snapshots: Sequence[PositionSnapshot], period: Period
) -> InvestmentSummary:
    trades = [o for o in operations if o.op_type in _TRADES]
    latest = metrics.latest_positions(snapshots)
    in_period = [o for o in trades if period.contains(o.trade_date)]
    all_dates = [o.trade_date for o in trades] + [s.as_of for s in snapshots]
    last_data = max(all_dates) if all_dates else None

    until_end = Period(None, period.end)
    contributions_total = _net_contributions(trades, until_end)
    contributions_period = _net_contributions(trades, period)

    if trades:
        first_month = month_start(min(o.trade_date for o in trades))
        end = min(period.end, last_data) if (period.end and last_data) else (last_data or date.today())
        months = (end.year - first_month.year) * 12 + end.month - first_month.month + 1
        avg_monthly = contributions_total / max(months, 1)
    else:
        avg_monthly = None

    holdings = metrics.allocation_by_fund(latest)
    base = dict(
        positions=len(latest),
        contributions_total=contributions_total,
        contributions_period=contributions_period,
        operations=len(in_period),
        buys=sum(1 for o in in_period if o.op_type is OperationType.BUY),
        sells=sum(1 for o in in_period if o.op_type is OperationType.SELL),
        avg_monthly_contribution=avg_monthly,
        largest_position=holdings[0] if holdings else None,
    )

    if period.is_global:
        if latest:
            value = metrics.portfolio_value(latest)
        elif last_data:
            value = metrics.estimated_value(operations, snapshots, last_data)
        else:
            value = ZERO
        gain = value - sum((p.invested for p in latest), ZERO) if latest else None
        return InvestmentSummary(
            value=value, gain=gain, simple_return=metrics.simple_return(latest) if latest else None,
            period_gain=None, twr=metrics.twr(operations, snapshots) if trades else None,
            xirr=metrics.portfolio_xirr(operations, snapshots) if trades and latest else None, **base,
        )

    assert period.start is not None and period.end is not None
    end = min(period.end, last_data) if last_data else period.end
    start_day = previous_month_end(period.start)
    value_end = metrics.estimated_value(operations, snapshots, end)
    value_start = metrics.estimated_value(operations, snapshots, start_day)
    return InvestmentSummary(
        value=value_end, gain=None, simple_return=None,
        period_gain=value_end - value_start - contributions_period,
        twr=metrics.twr(operations, snapshots, end=end, start=start_day) if trades else None,
        xirr=None, **base,
    )
