"""Filas de la base de datos -> objetos de dominio de `core` (lo que consumen las metricas)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.entities import OperationDraft, PositionSnapshot, TransactionDraft
from data.models import Account, Investment, InvestmentOperation, Transaction, Valuation


def load_transactions(session: Session) -> list[TransactionDraft]:
    rows = session.execute(
        select(Transaction, Account.bank)
        .join(Account, Account.id == Transaction.account_id)
        .order_by(Transaction.booking_date, Transaction.id)
    )
    return [
        TransactionDraft(
            bank=bank, booking_date=t.booking_date, description=t.description, amount=t.amount,
            balance_after=t.balance_after, category=t.category, tx_hash=t.tx_hash,
            source_file=t.source_file or "", account_id=t.account_id,
        )
        for t, bank in rows
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
