"""Filas de la base de datos -> objetos de dominio de `core` (lo que consumen las metricas)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.entities import OperationDraft, PositionSnapshot, TransactionDraft
from data.models import Account, Investment, InvestmentOperation, Transaction, Valuation


def load_transactions(session: Session) -> list[TransactionDraft]:
    # Se leen solo las columnas (sin instanciar entidades ORM): con miles de movimientos es mucho mas rapido.
    t = Transaction
    rows = session.execute(
        select(
            Account.bank, t.booking_date, t.description, t.amount, t.balance_after, t.category,
            t.tx_hash, t.source_file, t.account_id, t.category_is_manual,
        )
        .join(Account, Account.id == t.account_id)
        .order_by(t.booking_date, t.id)
    )
    return [
        TransactionDraft(
            bank=bank, booking_date=day, description=desc, amount=amount, balance_after=balance,
            category=category, tx_hash=tx_hash, source_file=source or "", account_id=account_id,
            is_manual=bool(manual),
        )
        for bank, day, desc, amount, balance, category, tx_hash, source, account_id, manual in rows
    ]


def load_operations(session: Session) -> list[OperationDraft]:
    rows = session.execute(
        select(InvestmentOperation, Account.bank, Investment)
        .join(Account, Account.id == InvestmentOperation.account_id)
        .join(Investment, Investment.id == InvestmentOperation.investment_id)
        .order_by(InvestmentOperation.trade_date, InvestmentOperation.id)
    )
    return [
        OperationDraft(
            bank=bank, isin=inv.isin, product_name=inv.name, op_type=o.op_type, trade_date=o.trade_date,
            value_date=None, units=o.units, unit_price=o.unit_price, amount=o.amount,
            tx_hash=o.tx_hash, source_file=o.source_file or "", account_id=o.account_id,
        )
        for o, bank, inv in rows
    ]


def load_snapshots(session: Session) -> list[PositionSnapshot]:
    rows = session.execute(
        select(Valuation, Investment)
        .join(Investment, Investment.id == Valuation.investment_id)
        .order_by(Valuation.as_of)
    )
    return [
        PositionSnapshot(
            isin=inv.isin, product_name=inv.name, units=v.units,
            avg_cost=(v.invested / v.units) if v.units else v.unit_price,
            unit_price=v.unit_price, invested=v.invested, market_value=v.unit_price * v.units,
            as_of=v.as_of,
        )
        for v, inv in rows
    ]
