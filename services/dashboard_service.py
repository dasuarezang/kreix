"""Caso de uso: calcular todo lo que muestra el dashboard a partir de la base de datos."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from core import metrics
from core.account_metrics import expense_breakdown
from core.budget import BudgetLine, budget_lines
from core.metrics import AllocationSlice, FlowOptions, MonthlyFlow, WealthPoint
from core.recurring import Recurring, detect_recurring
from data.database import session_scope
from data.repositories import get_budgets, last_import_date
from etl.reconcile import reconcile_portfolio
from services.mappers import load_operations, load_snapshots, load_transactions

FLOW_MONTHS = 12
UPCOMING_DAYS = 35       # pagos recurrentes que se esperan en este plazo desde el ultimo dia con datos


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
    upcoming: list[Recurring] = field(default_factory=list)       # proximos pagos recurrentes, el mas cercano primero
    budgets: list[BudgetLine] = field(default_factory=list)       # todos los presupuestos frente al gasto del ultimo mes, del mas gastado al menos
    has_budgets: bool = False
    last_update: date | None = None      # cuando se actualizaron los datos por ultima vez
    has_transactions: bool = False
    has_operations: bool = False
    has_portfolio: bool = False


class DashboardService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def load(self, options: FlowOptions = FlowOptions()) -> DashboardData:
        with session_scope(self._factory) as s:
            txs, ops, snaps = load_transactions(s), load_operations(s), load_snapshots(s)
            budgets = get_budgets(s)
            imported = last_import_date(s)
        if not (txs or ops or snaps):
            return DashboardData()

        latest = metrics.latest_positions(snaps)
        cash = metrics.total_cash(txs)
        data = DashboardData(
            has_data=True,
            has_transactions=bool(txs),
            has_operations=bool(ops),
            has_portfolio=bool(snaps),
            has_budgets=bool(budgets),
            cash=cash,
            portfolio_value=metrics.portfolio_value(latest),
            net_worth=metrics.net_worth(cash, latest),
            simple_return=metrics.simple_return(latest),
            xirr=metrics.portfolio_xirr(ops, snaps) if ops else None,
            twr=metrics.twr(ops, snaps) if ops else None,
            allocation=metrics.asset_allocation(cash, latest),
            warnings=reconcile_portfolio(latest, ops) if latest else [],
        )

        # Fecha de la ultima importacion; si no hay marcas (p. ej. solo cartera), el dia mas reciente que traen los datos.
        newest = [d for d in ([t.booking_date for t in txs] + [o.trade_date for o in ops] + [p.as_of for p in snaps])]
        data.last_update = imported or (max(newest) if newest else None)

        flows = metrics.monthly_cashflow(txs, ops, options)
        data.flows = flows[-FLOW_MONTHS:]
        if txs:
            data.report_month = metrics.month_start(max(t.booking_date for t in txs))
            current = next((f for f in flows if f.month == data.report_month), None)
            if current:
                data.month_income, data.month_expenses = current.income, current.expenses
                data.month_savings_rate = current.savings_rate
            last_day = max(t.booking_date for t in txs)
            data.upcoming = sorted(
                (r for r in detect_recurring(txs) if (r.next_date - last_day).days <= UPCOMING_DAYS),
                key=lambda r: r.next_date)
            data.has_budgets = bool(budgets)
            this_month = [t for t in txs if metrics.month_start(t.booking_date) == data.report_month]
            data.budgets = budget_lines(budgets, expense_breakdown(this_month, options))

        points = [t.booking_date for t in txs] + [o.trade_date for o in ops] + [p.as_of for p in snaps]
        data.wealth = metrics.wealth_evolution(txs, ops, snaps, metrics.month_ends(min(points), max(points)))
        return data
