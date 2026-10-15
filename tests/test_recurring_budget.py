from datetime import date, timedelta
from decimal import Decimal as D

from core.account_metrics import CategoryAmount
from core.budget import BudgetLine, budget_lines
from core.entities import TransactionDraft
from core.enums import Bank, TxCategory
from core.recurring import detect_recurring, merchant_key, monthly_cost


def tx(day, desc, amount, cat=TxCategory.SUBSCRIPTIONS):
    return TransactionDraft(Bank.IMAGIN, day, desc, D(amount), None, cat, f"{day}{desc}{amount}", "t")


def monthly(desc, amount, months=5, start=date(2026, 5, 3), cat=TxCategory.SUBSCRIPTIONS):
    return [tx(date(start.year, start.month + i, start.day), desc, amount, cat) for i in range(months)]


def test_merchant_key_ignores_numbers_and_references():
    assert merchant_key("NETFLIX.COM 1234 ES") == merchant_key("Netflix.com 99 ES")
    assert merchant_key("SPOTIFY AB  *REF 77") == "SPOTIFY AB REF"


def test_detects_monthly_fixed_charges_and_estimates_the_next_one():
    rows = monthly("NETFLIX.COM", "-12.99") + monthly("SPOTIFY AB", "-10.99", start=date(2026, 5, 9))
    found = detect_recurring(rows)
    assert [(r.name, r.amount, r.occurrences) for r in found] == [
        ("NETFLIX.COM", D("12.99"), 5), ("SPOTIFY AB", D("10.99"), 5)]
    assert found[0].last_date == date(2026, 9, 3)
    assert found[0].next_date == date(2026, 9, 3) + timedelta(days=31)
    assert monthly_cost(found) == D("23.98")


def test_ignores_frequent_variable_spending_like_groceries():
    rows = [tx(date(2026, 9, d), "MERCADONA CL", -v, TxCategory.GROCERIES) for d, v in
            ((2, 20), (5, 41), (9, 12), (14, 33), (20, 28))]
    rows += [tx(date(2026, 8, d), "MERCADONA CL", -v, TxCategory.GROCERIES) for d, v in ((3, 25), (10, 19), (17, 60))]
    assert detect_recurring(rows) == []


def test_requires_three_months_and_a_stable_amount():
    assert detect_recurring(monthly("GYM CLUB", "-30", months=2)) == []
    unstable = [tx(date(2026, 7 + i, 5), "GYM CLUB", a) for i, a in enumerate(("-30", "-55", "-31"))]
    assert detect_recurring(unstable) == []
    slight = [tx(date(2026, 7 + i, 5), "GYM CLUB", a) for i, a in enumerate(("-30", "-32", "-31"))]
    assert [r.amount for r in detect_recurring(slight)] == [D("31")]


def test_a_cancelled_subscription_is_not_listed_and_transfers_or_income_never_are():
    old = monthly("HBO MAX", "-9.99", months=3, start=date(2026, 1, 4))
    live = monthly("NETFLIX.COM", "-12.99")
    p2p = monthly("BIZUM PAGO ALQUILER", "-300", cat=TxCategory.P2P)
    assert [r.name for r in detect_recurring(old + live + p2p)] == ["NETFLIX.COM"]
    assert detect_recurring([]) == []


def test_budget_lines_sorted_by_use_with_states():
    spending = [CategoryAmount(TxCategory.GROCERIES, D(270), D("0.6")), CategoryAmount(TxCategory.DINING, D(120), D("0.3")),
                CategoryAmount(TxCategory.LEISURE, D(10), D("0.1"))]
    lines = budget_lines({TxCategory.GROCERIES: D(300), TxCategory.DINING: D(100), TxCategory.LEISURE: D(100),
                          TxCategory.HEALTH: D(50), TxCategory.OTHER: D(0)}, spending)
    assert [(l.category, l.state) for l in lines] == [
        (TxCategory.DINING, "over"), (TxCategory.GROCERIES, "warn"), (TxCategory.LEISURE, "ok"), (TxCategory.HEALTH, "ok")]
    assert lines[0].remaining == D(-20)
    # un periodo de 3 meses se compara con el tope mensual por mes
    avg = budget_lines({TxCategory.GROCERIES: D(100)}, spending, months=3)[0]
    assert avg.spent == D(90) and avg.state == "warn"
    assert isinstance(avg, BudgetLine)
