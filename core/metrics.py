"""Metricas financieras de Kreix. Logica pura: no conoce UI, base de datos ni pandas.

Entradas: los objetos de dominio de `core.entities`.
  - TransactionDraft  -> movimientos de efectivo (Imagin)
  - OperationDraft    -> compras/ventas de fondos (MyInvestor)
  - PositionSnapshot  -> fotos de cartera (participaciones y valor liquidativo por fecha)

Convenciones:
  - Dinero en Decimal. Tasas (ahorro, rentabilidad) como fraccion: 0.25 == 25 %.
  - Traspasos: los entrantes cuentan como ingreso (opcion, activada por defecto); los
    salientes y las aportaciones a MyInvestor son neutros.
  - Las aportaciones a inversion se calculan desde las compras/ventas de MyInvestor.
  - TIR y TWR suponen que el historial de operaciones esta completo
    (ver etl.reconcile para detectar si falta alguna).
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Sequence

from core.entities import OperationDraft, PositionSnapshot, PricePointDraft, TransactionDraft
from core.enums import OperationType, TxCategory
from core.periods import month_end, month_start, next_month as _next_month  # noqa: F401 (reexportados)

ZERO = Decimal(0)
_TRADES = (OperationType.BUY, OperationType.SELL)


# =========================================================================== flujo de caja
@dataclass(frozen=True, slots=True)
class MonthlyFlow:
    month: date                 # primer dia del mes
    income: Decimal
    expenses: Decimal           # en positivo
    contributions: Decimal      # aportaciones netas a inversion (compras - ventas)

    @property
    def net(self) -> Decimal:
        return self.income - self.expenses

    @property
    def savings_rate(self) -> Decimal | None:
        return savings_rate(self.income, self.expenses)


@dataclass(frozen=True, slots=True)
class FlowOptions:
    """Que movimientos cuentan como ingreso/gasto (se configuran en Ajustes)."""

    include_p2p: bool = True                # Bizum
    transfers_in_as_income: bool = True     # traspasos que entran (p. ej. de otra cuenta propia)
    scope: frozenset[int] | None = None     # cuentas que se estan mirando (None: todas): un traspaso entre dos de ellas no cuenta


def counts_as_flow(category: TxCategory, amount: Decimal, options: FlowOptions = FlowOptions(),
                   paired_with: int | None = None) -> bool:
    """Si un movimiento entra en ingresos/gastos. `paired_with` es la cuenta de la otra mitad si es un traspaso entre cuentas
    propias: si esa cuenta tambien se esta mirando, el dinero solo ha cambiado de sitio y no es ni ingreso ni gasto."""
    if paired_with is not None and (options.scope is None or paired_with in options.scope):
        return False
    if category is TxCategory.INVESTMENT_TRANSFER:
        return False  # las aportaciones se calculan desde las operaciones de MyInvestor
    if category is TxCategory.TRANSFER:
        return options.transfers_in_as_income and amount > 0  # los que salen son neutros
    if category is TxCategory.P2P:
        return options.include_p2p
    return True


def savings_rate(income: Decimal, expenses: Decimal) -> Decimal | None:
    """(ingresos - gastos) / ingresos. None si no hay ingresos. Puede ser negativa."""
    if income <= 0:
        return None
    return (income - expenses) / income


def monthly_cashflow(
    transactions: Iterable[TransactionDraft],
    operations: Iterable[OperationDraft] = (),
    options: FlowOptions = FlowOptions(),
) -> list[MonthlyFlow]:
    """Ingresos, gastos y aportaciones por mes, sin huecos entre el primer y el ultimo mes."""
    income: dict[date, Decimal] = defaultdict(Decimal)
    expenses: dict[date, Decimal] = defaultdict(Decimal)
    contributions: dict[date, Decimal] = defaultdict(Decimal)

    for t in transactions:
        if not counts_as_flow(t.category, t.amount, options, t.paired_with):
            continue
        m = month_start(t.booking_date)
        if t.amount >= 0:
            income[m] += t.amount
        else:
            expenses[m] += -t.amount
    for op in operations:
        if op.op_type in _TRADES:
            contributions[month_start(op.trade_date)] += -op.amount  # compra: amount<0

    months = set(income) | set(expenses) | set(contributions)
    if not months:
        return []
    out: list[MonthlyFlow] = []
    m, last = min(months), max(months)
    while m <= last:
        out.append(MonthlyFlow(m, income[m], expenses[m], contributions[m]))
        m = _next_month(m)
    return out


def month_savings_rate(
    transactions: Iterable[TransactionDraft], month: date, options: FlowOptions = FlowOptions()
) -> Decimal | None:
    flows = {f.month: f for f in monthly_cashflow(transactions, options=options)}
    flow = flows.get(month_start(month))
    return flow.savings_rate if flow else None


# =========================================================================== saldos y patrimonio
def _chain_order(group: list[TransactionDraft]) -> list[TransactionDraft]:
    """Ordena los movimientos de UN dia y UNA cuenta de mas antiguo a mas reciente
    siguiendo la cadena de saldos (saldo previo + importe = saldo). Si la cadena no se
    puede resolver sin ambiguedad, conserva el orden de entrada."""
    if len(group) < 2 or any(t.balance_after is None for t in group):
        return list(group)
    previous = [t.balance_after - t.amount for t in group]  # type: ignore[operator]  # saldo anterior de cada uno, una sola vez
    balances = {t.balance_after for t in group}
    starts = [t for t, prev in zip(group, previous) if prev not in balances]
    if len(starts) != 1:
        return list(group)
    by_previous: dict[Decimal, list[TransactionDraft]] = defaultdict(list)
    for t, prev in zip(group, previous):
        by_previous[prev].append(t)
    ordered = [starts[0]]
    used = {id(starts[0])}
    while True:
        nxt = next((t for t in by_previous.get(ordered[-1].balance_after, []) if id(t) not in used), None)  # type: ignore[arg-type]
        if nxt is None:
            break
        ordered.append(nxt)
        used.add(id(nxt))
    return ordered if len(ordered) == len(group) else list(group)


_CHRONO_MEMO: list[tuple[tuple[int, ...], list[TransactionDraft], list[TransactionDraft]]] = []
_CHRONO_MEMO_SIZE = 4


def chronological(transactions: Iterable[TransactionDraft]) -> list[TransactionDraft]:
    """De mas antiguo a mas reciente. Entre dias, por fecha; dentro de un dia, por la
    cadena de saldos de cada cuenta (el orden en que se guardaron no importa).

    Una vista pide este orden varias veces sobre los mismos movimientos (saldo, serie de saldos, tabla): como los
    movimientos son inmutables, el resultado se recuerda por la identidad de los que entran."""
    txs = transactions if isinstance(transactions, list) else list(transactions)
    key = tuple(map(id, txs))
    for known, _source, result in _CHRONO_MEMO:
        if known == key:
            return list(result)
    ordered = _chronological(txs)
    _CHRONO_MEMO.append((key, txs, ordered))                 # se guarda tambien `txs`: mientras viva, sus ids no se reutilizan
    del _CHRONO_MEMO[:-_CHRONO_MEMO_SIZE]
    return list(ordered)


def _chronological(transactions: Iterable[TransactionDraft]) -> list[TransactionDraft]:
    by_day: dict[date, dict[int | None, list[TransactionDraft]]] = defaultdict(lambda: defaultdict(list))
    for t in transactions:
        by_day[t.booking_date][t.account_id].append(t)
    out: list[TransactionDraft] = []
    for day in sorted(by_day):
        for group in by_day[day].values():
            if len(group) == 1:
                out.append(group[0])
            else:
                out.extend(_chain_order(group))
    return out


def order_movements(transactions: Iterable[TransactionDraft], newest_first: bool = True) -> list[TransactionDraft]:
    ordered = chronological(transactions)
    return ordered[::-1] if newest_first else ordered


def latest_balance(transactions: Iterable[TransactionDraft], as_of: date | None = None) -> Decimal | None:
    """Saldo de UNA cuenta en `as_of` (o el mas reciente). Para varias cuentas, `total_cash`."""
    rows = [t for t in transactions if t.balance_after is not None and (as_of is None or t.booking_date <= as_of)]
    if not rows:
        return None
    return chronological(rows)[-1].balance_after


def total_cash(transactions: Iterable[TransactionDraft], as_of: date | None = None) -> Decimal | None:
    """Suma del saldo de cada cuenta (cada una con su propia cadena de saldos)."""
    by_account: dict[int | None, list[TransactionDraft]] = defaultdict(list)
    for t in transactions:
        by_account[t.account_id].append(t)
    balances = [b for rows in by_account.values() if (b := latest_balance(rows, as_of)) is not None]
    return sum(balances, ZERO) if balances else None


def _closing_balances(transactions: Iterable[TransactionDraft]) -> dict[int | None, dict[date, Decimal]]:
    """Por cuenta, el saldo al cierre de cada dia con movimientos (ordenado por fecha).
    Se ordena una sola vez: asi las series largas no repiten el trabajo por cada fecha."""
    by_account: dict[int | None, list[TransactionDraft]] = defaultdict(list)
    for t in transactions:
        if t.balance_after is not None:
            by_account[t.account_id].append(t)
    closing: dict[int | None, dict[date, Decimal]] = {}
    for acc, rows in by_account.items():
        days: dict[date, Decimal] = {}
        for t in chronological(rows):
            days[t.booking_date] = t.balance_after  # type: ignore[assignment]  # el ultimo del dia gana
        closing[acc] = days
    return closing


def balance_series(
    transactions: Iterable[TransactionDraft], start: date | None = None, end: date | None = None
) -> list[tuple[date, Decimal]]:
    """Saldo (sumando cuentas) al cierre de cada dia con movimientos dentro de [start, end]."""
    closing = _closing_balances(transactions)
    all_days = sorted({d for days in closing.values() for d in days})
    series: list[tuple[date, Decimal]] = []
    current: dict[int | None, Decimal] = {}
    for d in all_days:
        for acc, days in closing.items():
            if d in days:
                current[acc] = days[d]
        if (start is None or d >= start) and (end is None or d <= end):
            series.append((d, sum(current.values(), ZERO)))
    return series


def latest_positions(snapshots: Iterable[PositionSnapshot], as_of: date | None = None) -> list[PositionSnapshot]:
    """Ultima foto de cada fondo (hasta `as_of`)."""
    best: dict[str, PositionSnapshot] = {}
    for s in snapshots:
        if as_of is not None and s.as_of > as_of:
            continue
        if s.isin not in best or s.as_of > best[s.isin].as_of:
            best[s.isin] = s
    return list(best.values())


def portfolio_value(positions: Iterable[PositionSnapshot]) -> Decimal:
    return sum((p.market_value for p in positions), ZERO)


def net_worth(cash: Decimal | None, positions: Iterable[PositionSnapshot]) -> Decimal:
    return (cash or ZERO) + portfolio_value(positions)


def simple_return(positions: Iterable[PositionSnapshot]) -> Decimal | None:
    """Rentabilidad global: (valor de mercado - capital invertido) / capital invertido."""
    positions = list(positions)
    invested = sum((p.invested for p in positions), ZERO)
    if invested <= 0:
        return None
    return (portfolio_value(positions) - invested) / invested


# =========================================================================== asset allocation
@dataclass(frozen=True, slots=True)
class AllocationSlice:
    label: str
    value: Decimal
    weight: Decimal             # fraccion del total


def _slices(items: list[tuple[str, Decimal]]) -> list[AllocationSlice]:
    total = sum((v for _, v in items), ZERO)
    return [AllocationSlice(label, v, (v / total) if total else ZERO) for label, v in items]


def asset_allocation(cash: Decimal | None, positions: Iterable[PositionSnapshot]) -> list[AllocationSlice]:
    """Liquidez (Imagin) frente a inversion (MyInvestor)."""
    return _slices([("Liquidez", max(cash or ZERO, ZERO)), ("Inversión", portfolio_value(positions))])


def allocation_by_fund(positions: Iterable[PositionSnapshot]) -> list[AllocationSlice]:
    return _slices(sorted(((p.product_name, p.market_value) for p in positions), key=lambda x: -x[1]))


# =========================================================================== TIR (XIRR)
def xirr(flows: Iterable[tuple[date, Decimal]]) -> float | None:
    """Tasa interna de retorno anualizada con fechas irregulares (base 365 dias).

    Convencion del inversor: aportaciones negativas, valor final positivo.
    Devuelve None si no hay solucion (faltan cambios de signo)."""
    items = sorted(((d, float(a)) for d, a in flows), key=lambda x: x[0])
    if len(items) < 2 or not any(a > 0 for _, a in items) or not any(a < 0 for _, a in items):
        return None
    t0 = items[0][0]
    years = [((d - t0).days / 365.0, a) for d, a in items]

    def npv(rate: float) -> float:
        return sum(a / (1.0 + rate) ** t for t, a in years)

    lo, hi = -0.999999, 1.0
    f_lo, f_hi = npv(lo), npv(hi)
    while f_lo * f_hi > 0 and hi < 1e6:
        hi *= 2
        f_hi = npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(300):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
        if hi - lo < 1e-12:
            break
    return (lo + hi) / 2


def estimated_value(
    operations: Iterable[OperationDraft], snapshots: Iterable[PositionSnapshot], on: date,
    prices: Iterable[PricePointDraft] = (),
) -> Decimal:
    """Valor estimado de la cartera un dia concreto (participaciones segun las operaciones,
    precio interpolado entre los valores liquidativos conocidos, incluido un historico de precios si lo hay)."""
    return _Portfolio(operations, snapshots, prices).value(on, include_day=True)


def portfolio_cashflows(
    operations: Iterable[OperationDraft], end_value: Decimal, as_of: date
) -> list[tuple[date, Decimal]]:
    flows = [(o.trade_date, o.amount) for o in operations if o.op_type in _TRADES]
    flows.append((as_of, end_value))
    return flows


def portfolio_xirr(operations: Sequence[OperationDraft], snapshots: Iterable[PositionSnapshot]) -> float | None:
    latest = latest_positions(snapshots)
    if not latest:
        return None
    as_of = max(p.as_of for p in latest)
    return xirr(portfolio_cashflows(operations, portfolio_value(latest), as_of))


# =========================================================================== TWR
class _Portfolio:
    """Reconstruye participaciones y valor por fecha a partir de las operaciones, y
    estima el precio de cada fondo interpolando entre los valores liquidativos
    conocidos (los de las propias operaciones y los de las fotos de cartera)."""

    def __init__(self, operations: Iterable[OperationDraft], snapshots: Iterable[PositionSnapshot],
                 history: Iterable[PricePointDraft] = ()) -> None:
        self.ops = sorted((o for o in operations if o.op_type in _TRADES and o.units > 0), key=lambda o: o.trade_date)
        prices: dict[str, dict[date, Decimal]] = defaultdict(dict)
        for h in history:                                   # primero el historico: las operaciones y las fotos mandan sobre el
            prices[h.isin][h.as_of] = h.unit_price
        for o in self.ops:
            if o.unit_price is not None:
                prices[o.isin][o.trade_date] = o.unit_price
        for s in snapshots:
            prices[s.isin][s.as_of] = s.unit_price  # la foto manda sobre la operacion del mismo dia
        self.curves = {isin: sorted(p.items()) for isin, p in prices.items()}
        self.isins = {o.isin for o in self.ops}

    def price(self, isin: str, d: date) -> Decimal | None:
        pts = self.curves.get(isin)
        if not pts:
            return None
        if d <= pts[0][0]:
            return pts[0][1]
        if d >= pts[-1][0]:
            return pts[-1][1]
        for (d0, p0), (d1, p1) in zip(pts, pts[1:]):
            if d0 <= d <= d1:
                if d1 == d0:
                    return p1
                w = Decimal((d - d0).days) / Decimal((d1 - d0).days)
                return p0 + (p1 - p0) * w
        return pts[-1][1]  # pragma: no cover

    def units(self, isin: str, d: date, *, include_day: bool) -> Decimal:
        total = ZERO
        for o in self.ops:
            if o.isin != isin:
                continue
            if o.trade_date < d or (include_day and o.trade_date == d):
                total += o.units if o.op_type is OperationType.BUY else -o.units
        return total

    def value(self, d: date, *, include_day: bool) -> Decimal:
        total = ZERO
        for isin in self.isins:
            u = self.units(isin, d, include_day=include_day)
            p = self.price(isin, d)
            if u and p is not None:
                total += u * p
        return total


def twr(
    operations: Iterable[OperationDraft],
    snapshots: Iterable[PositionSnapshot] = (),
    end: date | None = None,
    start: date | None = None,
    prices: Iterable[PricePointDraft] = (),
) -> float | None:
    """Rentabilidad ponderada en el tiempo (time-weighted return).

    Encadena la rentabilidad de cada tramo entre aportaciones/reembolsos, de modo que
    el momento y tamano de las aportaciones no afecta al resultado.
    Sin `start` es la acumulada desde la primera compra; con `start`, la del periodo
    (start, end]. Devuelve None si en ese periodo no habia capital invertido."""
    snapshots = list(snapshots)
    pf = _Portfolio(operations, snapshots, prices)
    if not pf.ops:
        return None
    if end is None:
        end = max([s.as_of for s in snapshots] + [o.trade_date for o in pf.ops])
    flow_dates = sorted({o.trade_date for o in pf.ops if o.trade_date <= end and (start is None or o.trade_date > start)})

    growth = 1.0
    started = False
    prev_after: Decimal | None = pf.value(start, include_day=True) if start is not None else None
    if prev_after is not None and prev_after > 0:
        started = True
    for d in flow_dates:
        before = pf.value(d, include_day=False)
        if prev_after is not None and prev_after > 0:
            growth *= float(before / prev_after)
        prev_after = pf.value(d, include_day=True)
        started = started or prev_after > 0
    if prev_after is not None and prev_after > 0:
        growth *= float(pf.value(end, include_day=True) / prev_after)
    return growth - 1.0 if started else None


# =========================================================================== series temporales
@dataclass(frozen=True, slots=True)
class WealthPoint:
    date: date
    cash: Decimal
    invested_value: Decimal     # valor estimado de la cartera
    contributions: Decimal      # aportaciones netas acumuladas
    net_worth: Decimal

    @property
    def growth(self) -> Decimal:
        """Lo que ha aportado la rentabilidad (interes compuesto) sobre lo aportado."""
        return self.invested_value - self.contributions


def month_ends(start: date, end: date) -> list[date]:
    out: list[date] = []
    m = month_start(start)
    while m <= end:
        out.append(min(month_end(m), end))
        m = _next_month(m)
    return out


def wealth_evolution(
    transactions: Sequence[TransactionDraft],
    operations: Sequence[OperationDraft],
    snapshots: Sequence[PositionSnapshot],
    dates: Sequence[date],
    prices: Iterable[PricePointDraft] = (),
) -> list[WealthPoint]:
    pf = _Portfolio(operations, snapshots, prices)
    trades = [o for o in operations if o.op_type in _TRADES]
    series = [(sorted(days), days) for days in _closing_balances(transactions).values()]
    points: list[WealthPoint] = []
    for d in dates:
        cash = ZERO
        for ordered, days in series:
            i = bisect_right(ordered, d)
            if i:
                cash += days[ordered[i - 1]]
        invested = pf.value(d, include_day=True)
        contributed = sum((-o.amount for o in trades if o.trade_date <= d), ZERO)
        points.append(WealthPoint(d, cash, invested, contributed, cash + invested))
    return points


@dataclass(frozen=True, slots=True)
class ProjectionPoint:
    month: int
    contributed: Decimal
    value: Decimal


def project_compound(
    initial: Decimal, monthly_contribution: Decimal, annual_rate: float, years: int
) -> list[ProjectionPoint]:
    """Proyeccion de interes compuesto con aportacion mensual al final de cada mes.
    `annual_rate` es la rentabilidad efectiva anual (0.07 == 7 %)."""
    monthly = (1.0 + annual_rate) ** (1.0 / 12.0) - 1.0
    value, contributed = float(initial), float(initial)
    out = [ProjectionPoint(0, initial, initial)]
    for m in range(1, years * 12 + 1):
        value = value * (1.0 + monthly) + float(monthly_contribution)
        contributed += float(monthly_contribution)
        out.append(ProjectionPoint(m, Decimal(str(round(contributed, 2))), Decimal(str(round(value, 2)))))
    return out
