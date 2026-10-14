from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from core.enums import AccountKind, Bank
from data.database import SCHEMA_VERSION, init_db, make_engine, make_session_factory, session_scope
from data.models import Account, Transaction
from data.repositories import (
    AccountError,
    add_account,
    delete_account,
    get_or_create_account,
    insert_transactions,
    list_accounts,
    rename_account,
)
from etl.dispatcher import parse_file

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture()
def factory():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return make_session_factory(engine)


def count(s):
    return s.scalar(select(func.count()).select_from(Transaction))


def test_same_statement_in_two_accounts_is_not_a_duplicate(factory):
    drafts = parse_file(FIX / "imagin_sample.csv").transactions
    with session_scope(factory) as s:
        a = add_account(s, "Personal")
        b = add_account(s, "Compartida")
        assert insert_transactions(s, a.id, drafts).inserted == 6
        assert insert_transactions(s, b.id, drafts).inserted == 6      # otra cuenta: no es duplicado
        assert insert_transactions(s, a.id, drafts).inserted == 0      # la misma cuenta: si
        assert count(s) == 12


def test_account_management(factory):
    with session_scope(factory) as s:
        acc = add_account(s, "  Mi   cuenta ")
        assert acc.name == "Mi cuenta"                                  # espacios normalizados
        with pytest.raises(AccountError):
            add_account(s, "Mi cuenta")                                 # repetida
        with pytest.raises(AccountError):
            add_account(s, "   ")                                       # vacia
        other = add_account(s, "Otra")
        with pytest.raises(AccountError):
            rename_account(s, other.id, "Mi cuenta")                    # choca con otra
        assert rename_account(s, other.id, "Ahorro").name == "Ahorro"
        assert [a.name for a in list_accounts(s, AccountKind.CHECKING)] == ["Mi cuenta", "Ahorro"]
        assert list_accounts(s, AccountKind.INVESTMENT) == []


def test_delete_account_removes_its_movements_only(factory):
    drafts = parse_file(FIX / "imagin_sample.csv").transactions
    with session_scope(factory) as s:
        a, b = add_account(s, "A"), add_account(s, "B")
        insert_transactions(s, a.id, drafts)
        insert_transactions(s, b.id, drafts)
        delete_account(s, a.id)
    with session_scope(factory) as s:
        assert count(s) == 6
        assert [x.name for x in list_accounts(s)] == ["B"]
        with pytest.raises(AccountError):
            delete_account(s, 999)


def test_migration_rehashes_old_database_so_reimport_does_not_duplicate(tmp_path):
    """Simula una base de datos anterior a la v2 (hashes sin cuenta) y comprueba que migra."""
    url = f"sqlite:///{tmp_path / 'old.db'}"
    engine = make_engine(url)
    init_db(engine)
    factory = make_session_factory(engine)
    drafts = parse_file(FIX / "imagin_sample.csv").transactions
    with session_scope(factory) as s:
        acc = get_or_create_account(s, Bank.IMAGIN, AccountKind.CHECKING, "Imagin")
        insert_transactions(s, acc.id, drafts)
        # estado de una BD antigua: hash sin cuenta y user_version = 1
        for t, d in zip(s.scalars(select(Transaction).order_by(Transaction.id)), drafts):
            t.tx_hash = d.tx_hash
    with engine.begin() as conn:
        conn.execute(text("PRAGMA user_version = 1"))

    init_db(engine)   # al abrir la app de nuevo

    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA user_version")).scalar() == SCHEMA_VERSION
    with session_scope(factory) as s:
        acc = s.scalars(select(Account)).one()
        assert insert_transactions(s, acc.id, drafts).inserted == 0     # reimportar no duplica
        assert count(s) == 6
    init_db(engine)                                                     # y migrar dos veces es inocuo
    with session_scope(factory) as s:
        assert insert_transactions(s, acc.id, drafts).inserted == 0
