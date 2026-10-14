"""Repositorios: persistencia idempotente de los objetos de dominio.

Las inserciones usan ON CONFLICT DO NOTHING sobre `tx_hash`, asi que importar
dos veces el mismo extracto (o extractos que se solapan) no duplica nada.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from core.entities import OperationDraft, PositionSnapshot, TransactionDraft
from core.enums import AccountKind, Bank
from data.models import Account, Investment, InvestmentOperation, Transaction, Valuation


@dataclass(frozen=True, slots=True)
class InsertStats:
    inserted: int = 0
    skipped: int = 0

    def __add__(self, other: InsertStats) -> InsertStats:
        return InsertStats(self.inserted + other.inserted, self.skipped + other.skipped)


def get_or_create_account(session: Session, bank: Bank, kind: AccountKind, name: str) -> Account:
    account = session.scalar(select(Account).where(Account.bank == bank, Account.name == name))
    if account is None:
        account = Account(bank=bank, kind=kind, name=name)
        session.add(account)
        session.flush()
    return account


def get_or_create_investment(session: Session, isin: str, name: str) -> Investment:
    inv = session.scalar(select(Investment).where(Investment.isin == isin))
    if inv is None:
        inv = Investment(isin=isin, name=name)
        session.add(inv)
        session.flush()
    return inv


def insert_transactions(session: Session, account_id: int, drafts: list[TransactionDraft]) -> InsertStats:
    stats = InsertStats()
    for d in drafts:
        stmt = (
            insert(Transaction)
            .values(
                account_id=account_id,
                booking_date=d.booking_date,
                description=d.description,
                amount=d.amount,
                balance_after=d.balance_after,
                category=d.category,
                tx_hash=d.tx_hash,
                source_file=d.source_file,
            )
            .on_conflict_do_nothing(index_elements=["tx_hash"])
        )
        added = session.execute(stmt).rowcount
        stats += InsertStats(inserted=added, skipped=1 - added)
    return stats


def insert_operations(session: Session, account_id: int, drafts: list[OperationDraft]) -> InsertStats:
    stats = InsertStats()
    for d in drafts:
        inv = get_or_create_investment(session, d.isin, d.product_name)
        stmt = (
            insert(InvestmentOperation)
            .values(
                account_id=account_id,
                investment_id=inv.id,
                op_type=d.op_type,
                trade_date=d.trade_date,
                units=d.units,
                unit_price=d.unit_price,
                amount=d.amount,
                fees=Decimal(0),
                tx_hash=d.tx_hash,
                source_file=d.source_file,
            )
            .on_conflict_do_nothing(index_elements=["tx_hash"])
        )
        added = session.execute(stmt).rowcount
        stats += InsertStats(inserted=added, skipped=1 - added)
    return stats


def upsert_valuations(session: Session, positions: list[PositionSnapshot]) -> int:
    """Una valoracion por fondo y fecha; reimportar la misma fecha la actualiza."""
    for p in positions:
        inv = get_or_create_investment(session, p.isin, p.product_name)
        stmt = insert(Valuation).values(
            investment_id=inv.id, as_of=p.as_of, unit_price=p.unit_price, units=p.units, invested=p.invested
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["investment_id", "as_of"],
            set_={
                "unit_price": stmt.excluded.unit_price,
                "units": stmt.excluded.units,
                "invested": stmt.excluded.invested,
            },
        )
        session.execute(stmt)
    return len(positions)
