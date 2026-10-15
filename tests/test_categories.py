"""Categorias editables: reglas del usuario, cambio manual y presupuestos."""
from datetime import date
from decimal import Decimal as D

import pytest

from core.categorizer import Categorizer
from core.entities import TransactionDraft
from core.enums import AccountKind, Bank, TxCategory
from data.database import init_db, make_engine, make_session_factory, session_scope
from data.repositories import RuleError, get_or_create_account, insert_transactions
from services.category_service import CategoryService
from services.mappers import load_transactions


@pytest.fixture()
def factory():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return make_session_factory(engine)


def draft(desc, amount, n):
    return TransactionDraft(Bank.IMAGIN, date(2026, 9, n), desc, D(amount), None, TxCategory.UNCATEGORIZED, f"h{n}", "t")


def load(factory):
    with session_scope(factory) as s:
        return {t.description: t for t in load_transactions(s)}


def seed(factory):
    with session_scope(factory) as s:
        acc = get_or_create_account(s, Bank.IMAGIN, AccountKind.CHECKING, "Imagin")
        insert_transactions(s, acc.id, [draft("PANADERIA JUAN", "-3.50", 1), draft("PANADERIA JUAN 2", "-4", 2),
                                        draft("MERCADONA", "-20", 3)])


def test_user_rules_win_over_the_default_ones():
    c = Categorizer(user_rules=[("MERCADONA", TxCategory.LEISURE)])
    assert c.categorize("MERCADONA CL", D(-5)) == TxCategory.LEISURE
    assert c.categorize("LIDL", D(-5)) == TxCategory.GROCERIES


def test_adding_a_rule_recategorizes_existing_movements_and_deleting_it_undoes_it(factory):
    seed(factory)
    svc = CategoryService(factory)
    assert svc.add_rule("panadería", TxCategory.DINING) == 3        # las 2 panaderias y MERCADONA (que estaba sin clasificar)
    txs = load(factory)
    assert txs["PANADERIA JUAN"].category == txs["PANADERIA JUAN 2"].category == TxCategory.DINING
    assert txs["MERCADONA"].category == TxCategory.GROCERIES
    rule = svc.rules()[0]
    assert rule.keyword == "PANADERIA"
    assert svc.delete_rule(rule.id) == 2
    assert load(factory)["PANADERIA JUAN"].category == TxCategory.UNCATEGORIZED


def test_a_manual_category_is_never_overridden_by_rules_and_can_be_reset(factory):
    seed(factory)
    svc = CategoryService(factory)
    h = load(factory)["PANADERIA JUAN"].tx_hash
    svc.set_category(h, TxCategory.HEALTH)
    t = load(factory)["PANADERIA JUAN"]
    assert (t.category, t.is_manual) == (TxCategory.HEALTH, True)
    svc.add_rule("PANADERIA", TxCategory.DINING)
    assert load(factory)["PANADERIA JUAN"].category == TxCategory.HEALTH      # la regla no pisa lo manual
    assert load(factory)["PANADERIA JUAN 2"].category == TxCategory.DINING
    svc.set_category(h, None)
    t = load(factory)["PANADERIA JUAN"]
    assert (t.category, t.is_manual) == (TxCategory.DINING, False)


def test_rules_apply_to_later_imports(factory):
    from services.import_service import ImportService
    from pathlib import Path

    svc = CategoryService(factory)
    svc.add_rule("MERCADONA", TxCategory.LEISURE)
    fix = Path(__file__).parent / "fixtures" / "imagin_sample.csv"
    ImportService(factory).import_files([fix])
    cats = {t.description: t.category for t in load(factory).values()}
    assert cats["MERCADONA CL TEST"] == TxCategory.LEISURE
    assert cats["NETFLIX.COM"] == TxCategory.SUBSCRIPTIONS


def test_rejects_tiny_keywords_and_replaces_an_existing_rule(factory):
    svc = CategoryService(factory)
    with pytest.raises(RuleError):
        svc.add_rule(" a ", TxCategory.OTHER)
    svc.add_rule("zara", TxCategory.OTHER)
    svc.add_rule("ZARA", TxCategory.LEISURE)
    assert [(r.keyword, r.category) for r in svc.rules()] == [("ZARA", TxCategory.LEISURE)]


def test_budgets_roundtrip_and_zero_removes(factory):
    svc = CategoryService(factory)
    svc.save_budgets({TxCategory.GROCERIES: D("300"), TxCategory.DINING: D("80.50"), TxCategory.LEISURE: D(0)})
    assert svc.budgets() == {TxCategory.GROCERIES: D("300"), TxCategory.DINING: D("80.50")}
    svc.save_budgets({TxCategory.DINING: D("90")})
    assert svc.budgets() == {TxCategory.DINING: D("90")}
