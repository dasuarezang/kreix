from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from data.database import init_db, make_engine, make_session_factory, session_scope
from data.models import Account, AccountKind, Bank, Transaction


@pytest.fixture()
def factory():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return make_session_factory(engine)


def _account(s):
    acc = Account(bank=Bank.IMAGIN, kind=AccountKind.CHECKING, name="Cuenta Imagin")
    s.add(acc)
    s.flush()
    return acc


def _tx(acc, h, amount="-12.34"):
    return Transaction(
        account_id=acc.id, booking_date=date(2026, 9, 1),
        description="MERCADONA", amount=Decimal(amount), tx_hash=h,
    )


def test_decimal_roundtrip_is_exact(factory):
    with session_scope(factory) as s:
        acc = _account(s)
        s.add(_tx(acc, "a", "-0.10"))
        s.add(_tx(acc, "b", "-0.20"))
    with session_scope(factory) as s:
        total = s.scalar(select(func.sum(Transaction.amount)))
        assert total == Decimal("-0.30")  # en float seria -0.30000000000000004


def test_duplicate_hash_is_rejected(factory):
    with pytest.raises(IntegrityError):
        with session_scope(factory) as s:
            acc = _account(s)
            s.add(_tx(acc, "same"))
            s.add(_tx(acc, "same"))


def test_cascade_delete_account(factory):
    with session_scope(factory) as s:
        acc = _account(s)
        s.add(_tx(acc, "x"))
    with session_scope(factory) as s:
        s.delete(s.scalars(select(Account)).one())
    with session_scope(factory) as s:
        assert s.scalar(select(func.count()).select_from(Transaction)) == 0
