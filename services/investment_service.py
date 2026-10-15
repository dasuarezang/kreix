"""Caso de uso de la pestana Inversion: metricas, posiciones y operaciones por periodo."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from core import metrics
from core.entities import OperationDraft, PositionSnapshot, PricePointDraft
from core.enums import OperationType
from core.investment_metrics import InvestmentSummary, available_months, summarize_investment
from core.metrics import AllocationSlice, WealthPoint
from core.periods import GLOBAL, Period
from data.database import session_scope
from etl.reconcile import reconcile_portfolio
from services.mappers import load_operations, load_prices, load_snapshots


@dataclass(frozen=True, slots=True)
class FundHistory:
    isin: str
    name: str
    points: list[WealthPoint]            # valor (invested_value) y aportado (contributions) al cierre de cada mes


@dataclass(slots=True)
class InvestmentViewData:
    months: list[date] = field(default_factory=list)             # el mas reciente primero
    period: Period = GLOBAL
    summary: InvestmentSummary | None = None
    positions: list[PositionSnapshot] = field(default_factory=list)   # ultima foto de cada fondo
    allocation: list[AllocationSlice] = field(default_factory=list)
    operations: list[OperationDraft] = field(default_factory=list)    # del periodo, la mas reciente primero
    evolution: list[WealthPoint] = field(default_factory=list)        # aportado frente a valor, por mes
    funds: list[FundHistory] = field(default_factory=list)            # valor de cada fondo mes a mes (solo con tus extractos)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return self.summary is not None


class InvestmentService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def view(self, month: date | None = None) -> InvestmentViewData:
        with session_scope(self._factory) as s:
            ops, snaps, prices = load_operations(s), load_snapshots(s), load_prices(s)
        trades = [o for o in ops if o.op_type in (OperationType.BUY, OperationType.SELL)]
        if not trades and not snaps:
            return InvestmentViewData()

        period = Period.month(month) if month else GLOBAL
        latest = metrics.latest_positions(snaps)
        inside = [o for o in trades if period.contains(o.trade_date)]
        # mas reciente primero; a igualdad de fecha, la ultima importada arriba
        operations = [o for _, o in sorted(enumerate(inside), key=lambda p: (p[1].trade_date, p[0]), reverse=True)]

        dates = [o.trade_date for o in trades] + [p.as_of for p in snaps]
        evolution = metrics.wealth_evolution([], ops, snaps, metrics.month_ends(min(dates), max(dates)), prices)
        return InvestmentViewData(
            months=available_months(ops, snaps),
            period=period,
            summary=summarize_investment(ops, snaps, period, prices),
            positions=sorted(latest, key=lambda p: p.market_value, reverse=True),
            allocation=metrics.allocation_by_fund(latest),
            operations=operations,
            evolution=evolution,
            funds=_fund_histories(ops, snaps, _chart_dates(dates, prices), prices),
            warnings=reconcile_portfolio(latest, ops) if latest else [],
        )


MAX_CHART_POINTS = 400


def _chart_dates(dates: list[date], prices: list[PricePointDraft]) -> list[date]:
    """Los cierres de mes y, si el usuario importo un historico de precios, tambien sus dias (aligerados si son muchos)."""
    first, last = min(dates), max(dates)
    days = {d for d in metrics.month_ends(first, last)}
    days.update(p.as_of for p in prices if first <= p.as_of <= last)
    ordered = sorted(days)
    if len(ordered) > MAX_CHART_POINTS:
        step = -(-len(ordered) // MAX_CHART_POINTS)
        ordered = ordered[::step] + ([ordered[-1]] if (len(ordered) - 1) % step else [])
    return ordered


def _fund_histories(ops: list[OperationDraft], snaps: list[PositionSnapshot], dates: list[date],
                    prices: list[PricePointDraft] = ()) -> list[FundHistory]:
    """Valor de cada fondo en cada cierre de mes, a partir de los extractos ya importados (nada sale del equipo).
    Entre dos extractos el valor es una estimacion, igual que en el grafico de la cartera."""
    names: dict[str, str] = {}
    for item in [*ops, *snaps]:
        names[item.isin] = item.product_name
    latest = {p.isin: p.market_value for p in metrics.latest_positions(snaps)}
    out = []
    for isin, name in names.items():
        fund_ops = [o for o in ops if o.isin == isin]
        fund_snaps = [p for p in snaps if p.isin == isin]
        fund_prices = [p for p in prices if p.isin == isin]
        out.append(FundHistory(isin, name, metrics.wealth_evolution([], fund_ops, fund_snaps, dates, fund_prices)))
    out.sort(key=lambda f: latest.get(f.isin, 0), reverse=True)        # primero los fondos que mas pesan hoy
    return out
