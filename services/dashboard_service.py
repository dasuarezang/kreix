"""Caso de uso: calcular todo lo que muestra el dashboard a partir de la base de datos."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from core import metrics
from core.metrics import AllocationSlice, FlowOptions, MonthlyFlow, WealthPoint
from data.database import session_scope
from etl.reconcile import reconcile_portfolio
from services.mappers import load_operations, load_snapshots, load_transactions

FLOW_MONTHS = 12


@dataclass(slots=True)
class DashboardData:
    has_data: bool = False
    cash: Decimal | None = None
    portfolio_value: Decimal = Decimal(0)
    net_worth: Decimal = Decimal(0)
    simple_return: Decimal | None = None
    xirr: float | None = None
    twr: float | None = None
    report_month: date | None = None
    month_income: Decimal = Decimal(0)
    month_expenses: Decimal = Decimal(0)
    month_savings_rate: Decimal | None = None
    allocation: list[AllocationSlice] = field(default_factory=list)
    flows: list[MonthlyFlow] = field(default_factory=list)
    wealth: list[WealthPoint] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class DashboardService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def load(self, options: FlowOptions = FlowOptions()) -> DashboardData:
        with session_scope(self._factory) as s:
            txs, ops, snaps = load_transactions(s), load_operations(s), load_snapshots(s)
        if not (txs or ops or snaps):
            return DashboardData()

        latest = metrics.latest_positions(snaps)
        cash = metrics.total_cash(txs)
        data = DashboardData(
            has_data=True,
            cash=cash,
            portfolio_value=metrics.portfolio_value(latest),
            net_worth=metrics.net_worth(cash, latest),
            simple_return=metrics.simple_return(latest),
            xirr=metrics.portfolio_xirr(ops, snaps) if ops else None,
            twr=metrics.twr(ops, snaps) if ops else None,
            allocation=metrics.asset_allocation(cash, latest),
            warnings=reconcile_portfolio(latest, ops) if latest else [],
        )

        flows = metrics.monthly_cashflow(txs, ops, options)
        data.flows = flows[-FLOW_MONTHS:]
        if txs:
            data.report_month = metrics.month_start(max(t.booking_date for t in txs))
            current = next((f for f in flows if f.month == data.report_month), None)
            if current:
                data.month_income, data.month_expenses = current.income, current.expenses
                data.month_savings_rate = current.savings_rate

        points = [t.booking_date for t in txs] + [o.trade_date for o in ops] + [p.as_of for p in snaps]
        data.wealth = metrics.wealth_evolution(txs, ops, snaps, metrics.month_ends(min(points), max(points)))
        return data
