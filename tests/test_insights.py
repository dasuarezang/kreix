"""Traspasos entre cuentas propias, reglas sugeridas, prevision de fin de mes y el panel «Por clasificar» de Inicio."""
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from core.entities import TransactionDraft
from core.enums import Bank, TxCategory
from core.forecast import MIN_DAYS_OF_DATA, forecast_month_end
from core.metrics import FlowOptions, counts_as_flow, monthly_cashflow
from core.recurring import detect_recurring_income
from core.suggestions import keyword_of, suggest_rules
from core.transfers import MAX_DAYS_APART, pair_transfers


def tx(day, desc, amount, cat=TxCategory.OTHER, account=1, balance=None, manual=False):
    return TransactionDraft(Bank.IMAGIN, day, desc, D(amount), None if balance is None else D(balance), cat,
                            f"{day}{desc}{amount}{account}", "t", account_id=account, is_manual=manual)


# ---------------------------------------------------------------- traspasos entre cuentas propias
def test_an_outgoing_and_an_incoming_transfer_of_the_same_amount_are_paired():
    rows = [tx(date(2026, 9, 5), "TRASPASO A AHORRO", "-300", TxCategory.TRANSFER, account=1),
            tx(date(2026, 9, 5), "TRASPASO RECIBIDO", "300", TxCategory.TRANSFER, account=2),
            tx(date(2026, 9, 6), "NOMINA", "1500", TxCategory.INCOME, account=1)]
    paired = pair_transfers(rows)
    assert [t.paired_with for t in paired] == [2, 1, None]
    assert paired[0].description == rows[0].description and paired[2] is rows[2]       # lo demas no se toca


def test_pairing_needs_different_accounts_a_close_date_and_at_least_one_transfer():
    base = date(2026, 9, 5)
    assert pair_transfers([tx(base, "A", "-50", TxCategory.TRANSFER, 1), tx(base, "B", "50", TxCategory.TRANSFER, 1)])[0].paired_with is None
    far = base + timedelta(days=MAX_DAYS_APART + 1)
    assert pair_transfers([tx(base, "A", "-50", TxCategory.TRANSFER, 1), tx(far, "B", "50", TxCategory.TRANSFER, 2)])[0].paired_with is None
    near = base + timedelta(days=MAX_DAYS_APART)
    assert pair_transfers([tx(base, "A", "-50", TxCategory.TRANSFER, 1), tx(near, "B", "50", TxCategory.TRANSFER, 2)])[0].paired_with == 2
    # una compra y un ingreso del mismo importe que no son traspasos no se unen
    assert pair_transfers([tx(base, "TIENDA", "-50", TxCategory.LEISURE, 1), tx(base, "PAGO AMIGO", "50", TxCategory.INCOME, 2)])[0].paired_with is None
    # con una mitad categorizada como ingreso, si
    assert pair_transfers([tx(base, "TRASPASO", "-50", TxCategory.TRANSFER, 1), tx(base, "ENTRADA", "50", TxCategory.INCOME, 2)])[1].paired_with == 1


def test_each_movement_pairs_once_and_the_closest_dates_win():
    rows = [tx(date(2026, 9, 5), "SALE 1", "-100", TxCategory.TRANSFER, 1),
            tx(date(2026, 9, 9), "SALE 2", "-100", TxCategory.TRANSFER, 1),
            tx(date(2026, 9, 8), "ENTRA", "100", TxCategory.TRANSFER, 2)]
    paired = pair_transfers(rows)
    assert paired[1].paired_with == 2 and paired[2].paired_with == 1 and paired[0].paired_with is None


def test_paired_transfers_are_neither_income_nor_expense_even_with_the_option_on():
    rows = [tx(date(2026, 9, 5), "TRASPASO", "-300", TxCategory.TRANSFER, 1),
            tx(date(2026, 9, 5), "TRASPASO", "300", TxCategory.TRANSFER, 2),
            tx(date(2026, 9, 7), "TRASPASO DE FUERA", "200", TxCategory.TRANSFER, 2)]        # este no tiene pareja
    flows = monthly_cashflow(pair_transfers(rows), options=FlowOptions(transfers_in_as_income=True))
    assert flows[0].income == D("200") and flows[0].expenses == 0


def test_counts_as_flow_only_ignores_a_pair_when_both_accounts_are_in_view():
    both, one = FlowOptions(scope=frozenset({1, 2})), FlowOptions(scope=frozenset({2}))
    assert counts_as_flow(TxCategory.TRANSFER, D(300), FlowOptions(), paired_with=1) is False        # todas las cuentas
    assert counts_as_flow(TxCategory.TRANSFER, D(300), both, paired_with=1) is False
    assert counts_as_flow(TxCategory.TRANSFER, D(300), one, paired_with=1) is True                   # mirando solo la cuenta 2: entra dinero de fuera
    assert counts_as_flow(TxCategory.TRANSFER, D(300), replace(one, transfers_in_as_income=False), paired_with=1) is False
    assert counts_as_flow(TxCategory.INCOME, D(300), FlowOptions(), paired_with=None) is True


def test_the_accounts_tab_pairs_transfers_and_shows_them_as_such(tmp_path):
    from data.database import init_db, make_engine, make_session_factory, session_scope
    from data.repositories import add_account, insert_transactions
    from services.accounts_service import AccountsService
    from ui.format import movement_category

    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    with session_scope(factory) as s:
        a = add_account(s, "Corriente").id
        b = add_account(s, "Ahorro").id
        insert_transactions(s, a, [tx(date(2026, 9, 1), "NOMINA", "1000", TxCategory.INCOME, a, "1000"),
                                   tx(date(2026, 9, 5), "TRASPASO A AHORRO", "-300", TxCategory.TRANSFER, a, "700")])
        insert_transactions(s, b, [tx(date(2026, 9, 5), "TRASPASO RECIBIDO", "300", TxCategory.TRANSFER, b, "300")])
    service = AccountsService(factory)
    every = service.view()
    assert every.summary.income == D("1000") and every.summary.expenses == 0
    assert any(movement_category(t) == "Traspaso entre tus cuentas" for t in every.movements)
    only_savings = service.view([b])
    assert only_savings.summary.income == D("300")                       # mirando solo Ahorro, el dinero llega de fuera
    only_current = service.view([a])
    assert only_current.summary.income == D("1000")


# ---------------------------------------------------------------- reglas sugeridas
@pytest.mark.parametrize("description, word", [
    ("COMPRA TARJETA MERCADONA VALENCIA", "MERCADONA"), ("Pago en Cafetería Sol", "CAFETERIA"), ("BIZUM A JUAN", "JUAN"),
    ("COMPRA 12345 ", ""), ("TPV", ""), ("AB 99", ""),
])
def test_the_keyword_is_the_first_word_that_names_the_merchant(description, word):
    assert keyword_of(description) == word


def test_repeated_merchants_without_category_are_suggested_most_frequent_first():
    rows = [tx(date(2026, 9, d), "COMPRA TARJETA PANADERIA LUZ", f"-{d}", TxCategory.UNCATEGORIZED) for d in (1, 5, 9, 13)]
    rows += [tx(date(2026, 9, d), f"PAGO ZAPATERIA {d}", "-40", TxCategory.UNCATEGORIZED) for d in (2, 6, 10)]
    rows += [tx(date(2026, 9, 3), "UNICO COMERCIO", "-9", TxCategory.UNCATEGORIZED)]                 # solo una vez: no se sugiere
    rows += [tx(date(2026, 9, d), "MERCADONA", "-9", TxCategory.GROCERIES) for d in (1, 2, 3)]        # ya tiene categoria
    rows += [tx(date(2026, 9, d), "GIMNASIO", "-9", TxCategory.UNCATEGORIZED, manual=True) for d in (1, 2, 3)]   # elegida a mano
    found = suggest_rules(rows)
    assert [(s.keyword, s.count) for s in found] == [("PANADERIA", 4), ("ZAPATERIA", 3)]
    assert found[0].total == D("28") and found[0].example.startswith("COMPRA")
    assert suggest_rules(rows, limit=1)[0].keyword == "PANADERIA" and len(suggest_rules(rows, limit=1)) == 1


# ---------------------------------------------------------------- prevision de fin de mes
def monthly_payment(desc, amount, months=4, day=10, end=date(2026, 9, 10)):
    out, d = [], end
    for _ in range(months):
        out.append(tx(d, desc, f"-{amount}", TxCategory.SUBSCRIPTIONS))
        d = (d.replace(day=1) - timedelta(days=1)).replace(day=day)
    return out


def daily_spending(start, end, amount="10"):
    days = (end - start).days + 1
    return [tx(start + timedelta(days=i), f"BAR NUMERO {i % 7}X", f"-{amount}", TxCategory.DINING) for i in range(days)]


def test_forecast_subtracts_fixed_payments_and_daily_spending_still_to_come():
    last = date(2026, 9, 20)
    rows = [tx(date(2026, 8, 1), "SALDO", "1", TxCategory.OTHER, balance="3000")]
    rows += monthly_payment("NETFLIX", "12.99", months=5, day=25, end=date(2026, 8, 25))     # aun falta el del 25
    rows += daily_spending(date(2026, 7, 1), last, "10")
    rows.append(tx(last, "ULTIMO DIA", "-1", TxCategory.OTHER, balance="2500"))
    forecast = forecast_month_end(rows)
    assert forecast.as_of == last and forecast.month_end == date(2026, 9, 30) and forecast.days_left == 10
    assert forecast.balance == D("2500") and forecast.fixed_due == D("12.99")
    assert forecast.reliable_variable and D("9") < forecast.daily_spend < D("11")
    assert forecast.projected == forecast.balance - forecast.fixed_due - forecast.variable
    assert forecast.projected < D("2500") - D("12.99") - D("90")


def test_forecast_adds_the_salary_that_is_still_to_arrive():
    last = date(2026, 9, 20)
    rows = [tx(date(2026, 5, 28) + timedelta(days=31 * i), "NOMINA EMPRESA SL", "1500", TxCategory.INCOME) for i in range(4)]
    assert detect_recurring_income(rows)[0].amount == D("1500")
    rows.append(tx(last, "ULTIMO DIA", "-5", TxCategory.OTHER, balance="1000"))
    forecast = forecast_month_end(rows)
    assert forecast.income_due == D("1500") and forecast.projected >= D("2000")        # (aun sin gasto diario fiable)


def test_forecast_is_honest_when_there_is_little_data_or_the_month_is_over():
    few = [tx(date(2026, 9, 12), "COMPRA", "-30", TxCategory.OTHER, balance="500"), tx(date(2026, 9, 14), "OTRA", "-20", TxCategory.OTHER, balance="480")]
    forecast = forecast_month_end(few)
    assert not forecast.reliable_variable and forecast.variable == 0 and forecast.projected == forecast.balance
    assert (few[-1].booking_date - few[0].booking_date).days < MIN_DAYS_OF_DATA
    assert forecast_month_end([tx(date(2026, 9, 30), "FIN", "-1", TxCategory.OTHER, balance="10")]) is None
    assert forecast_month_end([]) is None


def test_internal_transfers_do_not_count_as_daily_spending_in_the_forecast():
    rows = [tx(date(2026, 8, 1), "INICIO", "-1", TxCategory.OTHER, 1, "1000")]
    rows += [tx(date(2026, 9, 2), "TRASPASO A AHORRO", "-500", TxCategory.TRANSFER, 1, "500"),
             tx(date(2026, 9, 2), "TRASPASO RECIBIDO", "500", TxCategory.TRANSFER, 2, "500"),
             tx(date(2026, 9, 20), "FIN", "-1", TxCategory.OTHER, 1, "498")]
    forecast = forecast_month_end(pair_transfers(rows))
    assert forecast.daily_spend < D("2")


# ---------------------------------------------------------------- Inicio: prevision y «Por clasificar»
@pytest.fixture()
def home(window):

    window.show()
    return window


def import_sample(window, name="imagin_sample.csv"):
    from pathlib import Path

    window.import_view.import_paths([str(Path(__file__).parent / "fixtures" / name)])


def test_home_shows_the_forecast_card_and_hides_it_when_accounts_do_not_interest(home):
    import_sample(home)
    home.navigate(home.SUMMARY)
    forecast = home._svc.dashboard.load(home._settings.flow_options).forecast
    assert forecast is not None
    assert not home.dashboard.card_forecast.isHidden()
    home._apply_interests(False, True, "x")
    assert home.dashboard.card_forecast.isHidden()


def test_the_review_panel_lists_suggestions_and_opens_the_rule_dialog_with_the_word(home, monkeypatch):
    from ui.dialogs import RuleDialog

    day = date(2026, 9, 1)
    rows = [tx(day + timedelta(days=i), f"PAGO TIENDA RARA {i}", "-12", TxCategory.UNCATEGORIZED) for i in range(4)]
    from data.database import session_scope
    from data.repositories import add_account, insert_transactions

    with session_scope(home._svc.importer._factory) as s:
        account = add_account(s, "Cuenta").id
        insert_transactions(s, account, rows)
    home.refresh()
    home.navigate(home.SUMMARY)
    panel = home.dashboard.review
    assert not panel.isHidden() and [r.suggestion.keyword for r in panel.rows] == ["TIENDA"]
    assert "4 movimientos sin categoría" in panel.subtitle.text()
    seen = {}

    def fake_exec(self):
        seen["keyword"] = self.keyword.text()
        self.category.setCurrentIndex(self.category.findData(TxCategory.LEISURE))
        return RuleDialog.DialogCode.Accepted

    monkeypatch.setattr(RuleDialog, "exec", fake_exec)
    panel.rows[0].button.click()
    assert seen["keyword"] == "TIENDA"
    assert [r.keyword for r in home._svc.categories.rules()] == ["TIENDA"]
    assert home.dashboard.review.isHidden()                                     # ya no queda nada por clasificar


def test_the_review_panel_button_opens_accounts_filtered_by_uncategorized(home):
    day = date(2026, 9, 1)
    from data.database import session_scope
    from data.repositories import add_account, insert_transactions

    with session_scope(home._svc.importer._factory) as s:
        account = add_account(s, "Cuenta").id
        insert_transactions(s, account, [tx(day, "ALGO RARO UNO", "-5", TxCategory.UNCATEGORIZED), tx(day, "NOMINA", "100", TxCategory.INCOME)])
    home.refresh()
    home.dashboard.review.review_button.click()
    assert home.stack.currentIndex() == home.ACCOUNTS
