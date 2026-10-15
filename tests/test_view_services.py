from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from core.enums import TxCategory
from core.metrics import FlowOptions
from data.database import init_db, make_engine, make_session_factory
from data.repositories import AccountError
from services.accounts_service import AccountsService
from services.import_service import ImportService
from services.investment_service import InvestmentService

FIX = Path(__file__).parent / "fixtures"
AS_OF = date(2026, 10, 14)


@pytest.fixture()
def factory():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture()
def loaded(factory):
    ImportService(factory).import_files(
        [FIX / "imagin_sample.csv", FIX / "myinvestor_operaciones.csv", FIX / "myinvestor_cartera.csv"], AS_OF
    )
    return factory


# ---------------------------------------------------------------- cuentas
def test_accounts_view_empty(factory):
    v = AccountsService(factory).view()
    assert v.accounts == [] and not v.has_movements and v.summary is None and v.movements == []


def test_accounts_view_global_and_month(loaded):
    svc = AccountsService(loaded)
    g = svc.view()
    assert [a.name for a in g.accounts] == ["Imagin"] and g.has_movements
    assert g.months == [date(2026, 9, 1)]
    assert len(g.movements) == 6
    assert g.movements[0].description == "NETFLIX.COM"            # mas reciente arriba
    assert g.movements[1].description == "BIZUM RECIBIDO" and g.movements[1].amount == D(5)
    assert g.movements[1].balance_after == D("130.50")            # el Bizum de las 130,50 va antes que el de 125,50
    assert g.movements[2].balance_after == D("125.50")
    assert g.summary.balance == D("117.51")
    assert [d for d, _ in g.balance_series][-1] == date(2026, 9, 10)

    m = svc.view(month=date(2026, 9, 20))
    assert m.period.start == date(2026, 9, 1) and len(m.movements) == 6
    before = svc.view(month=date(2026, 5, 1))                      # antes del primer movimiento: saldo desconocido
    assert before.movements == [] and before.summary.income == 0 and before.summary.balance is None
    after = svc.view(month=date(2026, 10, 1))                      # despues del ultimo: el saldo se arrastra
    assert after.movements == [] and after.summary.balance == D("117.51")


def test_accounts_options_flow_through(loaded):
    svc = AccountsService(loaded)
    on = svc.view(options=FlowOptions())
    off = svc.view(options=FlowOptions(include_p2p=False, transfers_in_as_income=False))
    assert on.summary.income == D(110) and off.summary.income == D(0)
    assert {c.category for c in on.categories} == {TxCategory.GROCERIES, TxCategory.SUBSCRIPTIONS, TxCategory.UNCATEGORIZED}


def test_two_accounts_selection_and_import_target(factory):
    svc = AccountsService(factory)
    mine = svc.add("Personal")
    shared = svc.add("Compartida")
    imp = ImportService(factory)
    imp.import_files([FIX / "imagin_sample.csv"], account_id=mine.id)
    imp.import_files([FIX / "imagin_overlap.csv"], account_id=shared.id)

    only_mine = svc.view([mine.id])
    only_shared = svc.view([shared.id])
    both = svc.view()
    assert len(only_mine.movements) == 6 and len(only_shared.movements) == 4 and len(both.movements) == 10
    assert only_mine.summary.balance == D("117.51") and only_shared.summary.balance == D("107.52")
    assert both.summary.balance == D("225.03")                    # cada cuenta con su cadena de saldos
    assert svc.view([999]).selected == [] and svc.view([999]).summary is None


def test_import_without_target_uses_first_account_and_rejects_unknown(factory):
    svc = AccountsService(factory)
    first = svc.add("Primera")
    svc.add("Segunda")
    ImportService(factory).import_files([FIX / "imagin_sample.csv"])
    assert len(svc.view([first.id]).movements) == 6
    bad = ImportService(factory).import_files([FIX / "imagin_sample.csv"], account_id=12345)
    assert bad.files[0].error and not bad.files[0].ok


def test_account_crud_errors(factory):
    svc = AccountsService(factory)
    acc = svc.add("A")
    svc.rename(acc.id, "B")
    assert [a.name for a in svc.accounts()] == ["B"]
    with pytest.raises(AccountError):
        svc.add("B")
    svc.delete(acc.id)
    assert svc.accounts() == []


# ---------------------------------------------------------------- inversion
def test_investment_view_empty(factory):
    v = InvestmentService(factory).view()
    assert not v.has_data and v.operations == [] and v.months == []


def test_investment_view_global(loaded):
    v = InvestmentService(loaded).view()
    assert v.has_data and len(v.months) == 10
    assert v.summary.value == D(1630)                              # 13 x 110 + 4 x 50
    assert [p.product_name for p in v.positions] == ["Fondo Test Uno", "Fondo Test Dos"]   # mayor valor primero
    assert [o.trade_date for o in v.operations] == [date(2026, 3, 1), date(2026, 2, 1), date(2026, 1, 2)]
    assert v.allocation[0].label == "Fondo Test Uno"
    assert v.evolution[-1].date == AS_OF
    assert len(v.warnings) == 1                                    # Fondo Test Dos sin operaciones


def test_investment_view_month(loaded):
    feb = InvestmentService(loaded).view(month=date(2026, 2, 10))
    assert [o.trade_date for o in feb.operations] == [date(2026, 2, 1)]
    assert feb.summary.contributions_period == D(510) and feb.summary.operations == 1
    assert len(feb.positions) == 2                                 # las posiciones son siempre las actuales
    quiet = InvestmentService(loaded).view(month=date(2026, 6, 1))
    assert quiet.operations == [] and quiet.summary.contributions_period == 0


def test_investment_view_has_a_value_history_for_each_fund(loaded):
    v = InvestmentService(loaded).view()
    assert [f.name for f in v.funds] == ["Fondo Test Uno", "Fondo Test Dos"]          # el que mas pesa, primero
    dates = [w.date for w in v.evolution]
    assert all([w.date for w in f.points] == dates for f in v.funds)
    assert v.funds[0].points[-1].invested_value == D(110) * 13                       # su posicion al ultimo extracto
    assert sum(f.points[-1].invested_value for f in v.funds) == v.evolution[-1].invested_value
