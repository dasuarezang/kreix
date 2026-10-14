"""Caso de uso de la pestana Inversion: metricas, posiciones y operaciones por periodo."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from core import metrics
from core.entities import OperationDraft, PositionSnapshot
from core.enums import OperationType
from core.investment_metrics import InvestmentSummary, available_months, summarize_investment
from core.metrics import AllocationSlice, WealthPoint
from core.periods import GLOBAL, Period
from data.database import session_scope
from etl.reconcile import reconcile_portfolio
from services.mappers import load_operations, load_snapshots


@dataclass(slots=True)
class InvestmentViewData:
    months: list[date] = field(default_factory=list)             # el mas reciente primero
    period: Period = GLOBAL
    summary: InvestmentSummary | None = None
    positions: list[PositionSnapshot] = field(default_factory=list)   # ultima foto de cada fondo
    allocation: list[AllocationSlice] = field(default_factory=list)
    operations: list[OperationDraft] = field(default_factory=list)    # del periodo, la mas reciente primero
    evolution: list[WealthPoint] = field(default_factory=list)        # aportado frente a valor, por mes
    warnings: list[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return self.summary is not None


class InvestmentService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def view(self, month: date | None = None) -> InvestmentViewData:
        with session_scope(self._factory) as s:
            ops, snaps = load_operations(s), load_snapshots(s)
        trades = [o for o in ops if o.op_type in (OperationType.BUY, OperationType.SELL)]
        if not trades and not snaps:
            return InvestmentViewData()

        period = Period.month(month) if month else GLOBAL
        latest = metrics.latest_positions(snaps)
        inside = [o for o in trades if period.contains(o.trade_date)]
        # mas reciente primero; a igualdad de fecha, la ultima importada arriba
        operations = [o for _, o in sorted(enumerate(inside), key=lambda p: (p[1].trade_date, p[0]), reverse=True)]

        dates = [o.trade_date for o in trades] + [p.as_of for p in snaps]
        evolution = metrics.wealth_evolution([], ops, snaps, metrics.month_ends(min(dates), max(dates)))
        return InvestmentViewData(
            months=available_months(ops, snaps),
            period=period,
            summary=summarize_investment(ops, snaps, period),
            positions=sorted(latest, key=lambda p: p.market_value, reverse=True),
            allocation=metrics.allocation_by_fund(latest),
            operations=operations,
            evolution=evolution,
            warnings=reconcile_portfolio(latest, ops) if latest else [],
        )
