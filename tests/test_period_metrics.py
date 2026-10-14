from datetime import date
from decimal import Decimal as D

import pytest

from core import account_metrics as am
from core import investment_metrics as im
from core import metrics as m
from core.entities import OperationDraft, PositionSnapshot, TransactionDraft
from core.enums import Bank, OperationType, TxCategory
from core.periods import GLOBAL, Period, month_end, month_start, previous_month_end

C = TxCategory


def tx(d, amount, cat, balance=None, desc="x", acc=1):
    return TransactionDraft(Bank.IMAGIN, d, desc, D(amount), None if balance is None else D(balance), cat,
                            f"{acc}{d}{amount}{desc}{balance}", "f", acc)


def op(d, typ, units, price, isin="IE00AAAA0001"):
    amount = D(units) * D(price)
    return OperationDraft(Bank.MYINVESTOR, isin, "Fondo A", typ, d, None, D(units), D(price),
                          -amount if typ is OperationType.BUY else amount, f"{d}{typ}{units}{isin}", "f")


def snap(units, price, invested, as_of, isin="IE00AAAA0001", name="Fondo A"):
    return PositionSnapshot(isin, name, D(units), D(invested) / D(units), D(price), D(invested), D(units) * D(price), as_of)


# ---------------------------------------------------------------- periodos
def test_period_helpers():
    assert Period.month(date(2026, 2, 10)) == Period(date(2026, 2, 1), date(2026, 2, 28))
    assert GLOBAL.is_global and GLOBAL.contains(date(1999, 1, 1))
    p = Period.month(date(2026, 9, 5))
    assert p.contains(date(2026, 9, 30)) and not p.contains(date(2026, 10, 1))
    assert previous_month_end(date(2026, 3, 15)) == date(2026, 2, 28)
    assert previous_month_end(date(2026, 1, 1)) == date(2025, 12, 31)
    assert month_start(date(2026, 9, 17)) == date(2026, 9, 1) and month_end(date(2024, 2, 3)) == date(2024, 2, 29)


# ---------------------------------------------------------------- orden y saldos
def same_day_rows():
    # 09/09: 120,50 -> +5 -> 125,50 -> +5 -> 130,50 -> -12,99 -> 117,51
    return [
        tx(date(2026, 9, 9), "-12.99", C.SUBSCRIPTIONS, "117.51", "NETFLIX"),
        tx(date(2026, 9, 9), "5", C.P2P, "130.50", "B2"),
        tx(date(2026, 9, 9), "5", C.P2P, "125.50", "B1"),
        tx(date(2026, 9, 8), "-20.50", C.GROCERIES, "120.50", "MERC"),
    ]


def test_chronological_uses_balance_chain_whatever_the_input_order():
    expected = ["MERC", "B1", "B2", "NETFLIX"]
    import itertools
    for perm in itertools.permutations(same_day_rows()):
        assert [t.description for t in m.chronological(perm)] == expected
    assert [t.description for t in m.order_movements(same_day_rows())] == expected[::-1]


def test_chain_falls_back_to_input_order_when_ambiguous():
    rows = [tx(date(2026, 1, 1), "5", C.OTHER, None, "a"), tx(date(2026, 1, 1), "6", C.OTHER, None, "b")]
    assert [t.description for t in m.chronological(rows)] == ["a", "b"]


def test_total_cash_and_series_with_two_accounts():
    a = [tx(date(2026, 9, 1), "100", C.INCOME, "100", acc=1), tx(date(2026, 9, 5), "-30", C.OTHER, "70", acc=1)]
    b = [tx(date(2026, 9, 3), "50", C.INCOME, "50", acc=2)]
    assert m.total_cash(a + b) == D(120)
    assert m.total_cash(a + b, as_of=date(2026, 9, 4)) == D(150)
    assert m.total_cash([]) is None
    assert m.balance_series(a + b) == [(date(2026, 9, 1), D(100)), (date(2026, 9, 3), D(150)), (date(2026, 9, 5), D(120))]
    assert m.balance_series(a + b, start=date(2026, 9, 3), end=date(2026, 9, 4)) == [(date(2026, 9, 3), D(150))]


# ---------------------------------------------------------------- resumen de cuentas
def month_txs():
    return [
        tx(date(2026, 8, 30), "500", C.TRANSFER, "600"),
        tx(date(2026, 9, 1), "1000", C.INCOME, "1600"),
        tx(date(2026, 9, 2), "-300", C.GROCERIES, "1300"),
        tx(date(2026, 9, 10), "-100", C.LEISURE, "1200"),
        tx(date(2026, 9, 15), "20", C.P2P, "1220"),
        tx(date(2026, 9, 30), "-60", C.GROCERIES, "1160"),
        tx(date(2026, 10, 3), "-40", C.DINING, "1120"),
    ]


def test_summary_of_a_month():
    s = am.summarize_account(month_txs(), Period.month(date(2026, 9, 1)))
    assert s.balance == D(1160)                         # saldo al cierre de septiembre, no el actual
    assert (s.income, s.expenses, s.movements) == (D(1020), D(460), 5)
    assert s.net == D(560) and s.savings_rate == D(560) / D(1020)
    assert s.avg_daily_expense == D(460) / D(30)
    assert s.largest_expense.amount == D(-300)
    assert (s.top_category.category, s.top_category.amount) == (C.GROCERIES, D(360))


def test_summary_global_and_options():
    txs = month_txs()
    g = am.summarize_account(txs, GLOBAL)
    assert g.balance == D(1120) and g.movements == 7
    assert g.income == D(1520)                           # incluye el traspaso entrante de 500
    assert g.avg_monthly_expense == D(500) / D(3)        # agosto, septiembre y octubre
    only_real = am.summarize_account(txs, GLOBAL, m.FlowOptions(include_p2p=False, transfers_in_as_income=False))
    assert only_real.income == D(1000)


def test_summary_of_empty_period():
    s = am.summarize_account(month_txs(), Period.month(date(2026, 1, 1)))
    assert (s.income, s.expenses, s.movements) == (0, 0, 0)
    assert s.avg_daily_expense is None and s.largest_expense is None and s.top_category is None
    assert am.summarize_account([], GLOBAL).balance is None


def test_expense_breakdown_and_months():
    b = am.expense_breakdown(month_txs())
    assert [(x.category, x.amount) for x in b] == [(C.GROCERIES, D(360)), (C.LEISURE, D(100)), (C.DINING, D(40))]
    assert sum(x.share for x in b) == 1
    assert am.expense_breakdown([]) == []
    assert am.available_months(month_txs()) == [date(2026, 10, 1), date(2026, 9, 1), date(2026, 8, 1)]


# ---------------------------------------------------------------- TWR por periodo
OPS = [op(date(2026, 1, 2), OperationType.BUY, 10, 100), op(date(2026, 2, 1), OperationType.BUY, 5, 102),
       op(date(2026, 3, 1), OperationType.SELL, 2, 110)]
SNAP = [snap(13, 110, 1300, date(2026, 10, 14))]


def test_monthly_twr_matches_the_fund_price_change():
    feb = m.twr(OPS, SNAP, end=date(2026, 2, 28), start=date(2026, 1, 31))
    p_start = 100 + 2 * (29 / 30)             # precio interpolado el 31/01
    p_end = 102 + 8 * (27 / 28)               # precio interpolado el 28/02
    assert feb == pytest.approx(p_end / p_start - 1, abs=1e-9)
    assert m.twr(OPS, SNAP, end=date(2026, 4, 30), start=date(2026, 3, 31)) == pytest.approx(0.0, abs=1e-12)
    assert m.twr(OPS, SNAP, end=date(2025, 12, 31), start=date(2025, 11, 30)) is None   # aun sin capital


def test_estimated_value():
    assert m.estimated_value(OPS, SNAP, date(2026, 1, 2)) == D(1000)
    assert m.estimated_value(OPS, SNAP, date(2025, 12, 1)) == D(0)
    assert m.estimated_value(OPS, SNAP, date(2026, 10, 14)) == D(1430)


# ---------------------------------------------------------------- resumen de inversion
def test_investment_summary_global():
    s = im.summarize_investment(OPS, SNAP, GLOBAL)
    assert s.value == D(1430) and s.positions == 1
    assert s.contributions_total == D(1000) + D(510) - D(220)
    assert s.gain == D(1430) - D(1300) and s.simple_return == (D(1430) - D(1300)) / D(1300)
    assert s.twr == pytest.approx(0.10, abs=1e-9) and s.xirr is not None
    assert (s.operations, s.buys, s.sells) == (3, 2, 1)
    assert s.avg_monthly_contribution == D(1290) / D(10)        # enero..octubre
    assert s.largest_position.label == "Fondo A"


def test_investment_summary_for_a_month():
    s = im.summarize_investment(OPS, SNAP, Period.month(date(2026, 2, 1)))
    assert s.contributions_period == D(510) and s.contributions_total == D(1510)
    assert s.operations == 1 and s.buys == 1 and s.xirr is None and s.gain is None
    p_end = D(15) * (D(102) + D(8) * D(27) / D(28))
    p_start = D(10) * (D(100) + D(2) * D(29) / D(30))
    assert float(s.value) == pytest.approx(float(p_end), abs=1e-6)
    assert float(s.period_gain) == pytest.approx(float(p_end - p_start - 510), abs=1e-6)


def test_investment_summary_empty_and_months():
    s = im.summarize_investment([], [], GLOBAL)
    assert s.value == 0 and s.twr is None and s.avg_monthly_contribution is None and s.largest_position is None
    months = im.available_months(OPS, SNAP)
    assert months[0] == date(2026, 10, 1) and months[-1] == date(2026, 1, 1) and len(months) == 10
    assert im.available_months([], []) == []
