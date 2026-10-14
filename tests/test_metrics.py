from datetime import date
from decimal import Decimal as D

import pytest

from core import metrics as m
from core.entities import OperationDraft, PositionSnapshot, TransactionDraft
from core.enums import Bank, OperationType, TxCategory


def tx(d, amount, cat, balance=None, desc="x"):
    return TransactionDraft(Bank.IMAGIN, d, desc, D(amount), None if balance is None else D(balance), cat, f"{d}{amount}{desc}", "f")


def op(d, typ, units, price, isin="IE00AAAA0001"):
    amount = D(units) * D(price)
    return OperationDraft(
        Bank.MYINVESTOR, isin, "Fondo", typ, d, None, D(units), D(price),
        -amount if typ is OperationType.BUY else amount, f"{d}{typ}{units}{isin}", "f",
    )


def pos(units, price, invested, as_of=date(2026, 10, 14), isin="IE00AAAA0001", name="Fondo"):
    return PositionSnapshot(isin, name, D(units), D(invested) / D(units), D(price), D(invested), D(units) * D(price), as_of)


C = TxCategory


# ---------------------------------------------------------------- flujo de caja y ahorro
def sample_txs():
    return [
        tx(date(2026, 9, 1), "1000", C.INCOME),
        tx(date(2026, 9, 5), "-300", C.GROCERIES),
        tx(date(2026, 9, 6), "50", C.P2P),
        tx(date(2026, 9, 7), "-20", C.P2P),
        tx(date(2026, 9, 8), "500", C.TRANSFER),                # entrante: cuenta como ingreso
        tx(date(2026, 9, 8), "-60", C.TRANSFER),                # saliente: neutro
        tx(date(2026, 9, 9), "-100", C.INVESTMENT_TRANSFER),    # neutro
        tx(date(2026, 11, 2), "-40", C.LEISURE),                # octubre queda vacio
    ]


def test_cashflow_defaults_count_p2p_and_incoming_transfers():
    sep = m.monthly_cashflow(sample_txs())[0]
    assert (sep.income, sep.expenses) == (D(1550), D(320))  # 1000 + 50 Bizum + 500 traspaso
    assert sep.savings_rate == (D(1550) - D(320)) / D(1550)


def test_cashflow_options_can_exclude_each_source():
    no_p2p = m.monthly_cashflow(sample_txs(), options=m.FlowOptions(include_p2p=False))[0]
    assert (no_p2p.income, no_p2p.expenses) == (D(1500), D(300))
    no_transfers = m.monthly_cashflow(sample_txs(), options=m.FlowOptions(transfers_in_as_income=False))[0]
    assert (no_transfers.income, no_transfers.expenses) == (D(1050), D(320))
    neither = m.monthly_cashflow(sample_txs(), options=m.FlowOptions(False, False))[0]
    assert (neither.income, neither.expenses) == (D(1000), D(300))


def test_cashflow_fills_empty_months():
    flows = m.monthly_cashflow(sample_txs())
    assert [f.month for f in flows] == [date(2026, 9, 1), date(2026, 10, 1), date(2026, 11, 1)]
    assert flows[1].income == 0 and flows[1].savings_rate is None


def test_contributions_come_from_investment_operations():
    ops = [op(date(2026, 9, 3), OperationType.BUY, 10, 100), op(date(2026, 9, 20), OperationType.SELL, 2, 100)]
    assert m.monthly_cashflow([], ops)[0].contributions == D(800)  # 1000 comprados - 200 vendidos


def test_savings_rate_edge_cases():
    assert m.savings_rate(D(0), D(10)) is None
    assert m.savings_rate(D(100), D(150)) == D("-0.5")  # gastar mas de lo ingresado
    opts = m.FlowOptions(include_p2p=False, transfers_in_as_income=False)
    assert m.month_savings_rate(sample_txs(), date(2026, 9, 15), opts) == D("0.7")


# ---------------------------------------------------------------- saldo y patrimonio
def test_latest_balance_resolves_same_day_chain_regardless_of_order():
    # dos Bizum de 5 el mismo dia: 120,50 -> 125,50 -> 130,50
    a = tx(date(2026, 9, 9), "5", C.P2P, "130.50")
    b = tx(date(2026, 9, 9), "5", C.P2P, "125.50")
    older = tx(date(2026, 9, 8), "-20.50", C.GROCERIES, "120.50")
    for order in ([a, b, older], [b, a, older], [older, b, a]):
        assert m.latest_balance(order) == D("130.50")
    assert m.latest_balance([a, b, older], as_of=date(2026, 9, 8)) == D("120.50")
    assert m.latest_balance([]) is None


def test_net_worth_and_simple_return():
    positions = [pos(10, 110, 1000), pos(4, 50, 180, isin="IE00BBBB0002")]
    assert m.net_worth(D("300"), positions) == D(300) + D(1100) + D(200)
    assert m.simple_return(positions) == (D(1300) - D(1180)) / D(1180)
    assert m.simple_return([]) is None


def test_latest_positions_keeps_newest_per_fund():
    old, new = pos(10, 100, 1000, as_of=date(2026, 6, 1)), pos(10, 110, 1000, as_of=date(2026, 10, 1))
    assert m.latest_positions([old, new]) == [new]
    assert m.latest_positions([old, new], as_of=date(2026, 7, 1)) == [old]


def test_asset_allocation_sums_to_one():
    slices = m.asset_allocation(D(300), [pos(10, 110, 1000)])
    assert [s.label for s in slices] == ["Liquidez", "Inversión"]
    assert slices[0].weight == D(300) / D(1400)
    assert sum(s.weight for s in slices) == 1
    assert [s.weight for s in m.asset_allocation(None, [])] == [0, 0]  # sin datos, sin division por cero


# ---------------------------------------------------------------- TIR
def test_xirr_simple_year():
    flows = [(date(2025, 1, 1), D(-1000)), (date(2026, 1, 1), D(1100))]
    assert m.xirr(flows) == pytest.approx(0.10, abs=1e-6)


def test_xirr_multiple_flows():
    # 1000 al inicio y otros 1000 a mitad de camino; sale 2200 al final
    flows = [(date(2025, 1, 1), D(-1000)), (date(2025, 7, 2), D(-1000)), (date(2026, 1, 1), D(2200))]
    r = m.xirr(flows)
    assert r is not None
    assert sum(float(a) / (1 + r) ** ((d - flows[0][0]).days / 365) for d, a in flows) == pytest.approx(0, abs=1e-6)


def test_xirr_no_solution():
    assert m.xirr([(date(2026, 1, 1), D(-100))]) is None
    assert m.xirr([(date(2026, 1, 1), D(100)), (date(2026, 2, 1), D(100))]) is None


def test_portfolio_xirr_uses_operations_and_latest_value():
    ops = [op(date(2025, 1, 1), OperationType.BUY, 10, 100)]
    snap = [pos(10, 110, 1000, as_of=date(2026, 1, 1))]
    assert m.portfolio_xirr(ops, snap) == pytest.approx(0.10, abs=1e-6)


# ---------------------------------------------------------------- TWR
OPS = [
    op(date(2026, 1, 2), OperationType.BUY, 10, 100),
    op(date(2026, 2, 1), OperationType.BUY, 5, 102),
    op(date(2026, 3, 1), OperationType.SELL, 2, 110),
]


def test_twr_is_independent_of_contribution_timing():
    snap = [pos(13, 110, 1300, as_of=date(2026, 10, 14))]
    # el precio pasa de 100 a 110: 10 % haga las aportaciones que haga
    assert m.twr(OPS, snap) == pytest.approx(0.10, abs=1e-9)


def test_twr_vs_xirr_differ_when_money_is_added_late():
    ops = [op(date(2026, 1, 1), OperationType.BUY, 1, 100), op(date(2026, 7, 1), OperationType.BUY, 100, 150)]
    snap = [pos(101, 120, 15100, as_of=date(2026, 12, 31))]
    # el fondo sube 50 % y luego baja 20 %: 1.5 * 0.8 - 1 = 20 %
    assert m.twr(ops, snap) == pytest.approx(0.20, abs=1e-9)
    assert m.portfolio_xirr(ops, snap) < 0  # el dinero grande entro caro: el inversor ha perdido


def test_twr_without_operations():
    assert m.twr([]) is None


# ---------------------------------------------------------------- series y proyeccion
def test_month_ends():
    assert m.month_ends(date(2026, 1, 15), date(2026, 3, 10)) == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 10)]


def test_wealth_evolution_tracks_growth():
    snap = [pos(13, 110, 1300, as_of=date(2026, 10, 14))]
    txs = [tx(date(2026, 2, 1), "-5", C.OTHER, "400")]
    pts = m.wealth_evolution(txs, OPS, snap, [date(2026, 1, 31), date(2026, 10, 14)])
    assert pts[0].contributions == D(1000) and pts[0].cash == 0
    last = pts[-1]
    assert last.contributions == D(1000) + D(510) - D(220)
    assert last.invested_value == D(13) * D(110)
    assert last.net_worth == D(400) + D(1430)
    assert last.growth == D(1430) - D(1290)


def test_project_compound():
    one_year = m.project_compound(D(1000), D(0), 0.12, 1)
    assert one_year[-1].value == D("1120.00")
    with_savings = m.project_compound(D(0), D(100), 0.0, 2)
    assert with_savings[-1].value == D("2400.00") and with_savings[-1].contributed == D("2400.00")
