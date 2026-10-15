"""Repositorios: persistencia idempotente de los objetos de dominio.

Las inserciones usan ON CONFLICT DO NOTHING sobre `tx_hash`, asi que importar
dos veces el mismo extracto (o extractos que se solapan) no duplica nada.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from core.categorizer import Categorizer, normalize
from core.entities import OperationDraft, PositionSnapshot, TransactionDraft
from core.enums import AccountKind, Bank, TxCategory
from data.hashing import scoped_hash
from data.models import (
    Account, Budget, CategoryRule, Goal, Investment, InvestmentOperation, PricePoint, RecurringMark, Transaction, Valuation,
)


@dataclass(frozen=True, slots=True)
class InsertStats:
    inserted: int = 0
    skipped: int = 0
    updated: int = 0

    def __add__(self, other: InsertStats) -> InsertStats:
        return InsertStats(
            self.inserted + other.inserted, self.skipped + other.skipped, self.updated + other.updated
        )


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
    """Inserta en bloque (un solo `executemany`): con decenas de miles de filas, una sentencia por fila tardaba segundos.
    Las que ya existen (mismo `tx_hash`) se ignoran, incluidas las repetidas dentro del propio archivo."""
    if not drafts:
        return InsertStats()
    rows = [
        {
            "account_id": account_id, "booking_date": d.booking_date, "description": d.description, "amount": d.amount,
            "balance_after": d.balance_after, "category": d.category, "tx_hash": scoped_hash(account_id, d.tx_hash),
            "source_file": d.source_file,
        }
        for d in drafts
    ]
    before = session.scalar(select(func.count()).select_from(Transaction)) or 0
    session.execute(insert(Transaction).on_conflict_do_nothing(index_elements=["tx_hash"]), rows)
    added = (session.scalar(select(func.count()).select_from(Transaction)) or 0) - before
    return InsertStats(inserted=added, skipped=len(rows) - added)


def insert_operations(session: Session, account_id: int, drafts: list[OperationDraft]) -> InsertStats:
    stats = InsertStats()
    funds: dict[str, Investment] = {}                  # un fondo se busca una sola vez por archivo
    for d in drafts:
        inv = funds.get(d.isin) or funds.setdefault(d.isin, get_or_create_investment(session, d.isin, d.product_name))
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
                tx_hash=scoped_hash(account_id, d.tx_hash),
                source_file=d.source_file,
            )
            .on_conflict_do_nothing(index_elements=["tx_hash"])
        )
        added = session.execute(stmt).rowcount
        stats += InsertStats(inserted=added, skipped=1 - added)
    return stats


def upsert_valuations(session: Session, positions: list[PositionSnapshot]) -> InsertStats:
    """Una valoracion por fondo y fecha; reimportar la misma fecha la actualiza.

    Cuenta como nueva la que no existia, como actualizada la que cambia algun dato y como
    omitida la que ya estaba igual."""
    stats = InsertStats()
    for p in positions:
        inv = get_or_create_investment(session, p.isin, p.product_name)
        current = session.scalar(
            select(Valuation).where(Valuation.investment_id == inv.id, Valuation.as_of == p.as_of)
        )
        if current is None:
            session.add(
                Valuation(investment_id=inv.id, as_of=p.as_of, unit_price=p.unit_price, units=p.units, invested=p.invested)
            )
            stats += InsertStats(inserted=1)
        elif (current.unit_price, current.units, current.invested) != (p.unit_price, p.units, p.invested):
            current.unit_price, current.units, current.invested = p.unit_price, p.units, p.invested
            stats += InsertStats(updated=1)
        else:
            stats += InsertStats(skipped=1)
    session.flush()
    return stats


# ----------------------------------------------------------------- cuentas
def list_accounts(session: Session, kind: AccountKind | None = None) -> list[Account]:
    stmt = select(Account).order_by(Account.id)
    if kind is not None:
        stmt = stmt.where(Account.kind == kind)
    return list(session.scalars(stmt))


class AccountError(ValueError):
    """Operacion de cuentas no valida (nombre vacio o repetido, cuenta inexistente...)."""


def add_account(session: Session, name: str, bank: Bank = Bank.IMAGIN, kind: AccountKind = AccountKind.CHECKING) -> Account:
    name = " ".join(name.split())
    if not name:
        raise AccountError("El nombre de la cuenta no puede estar vacio.")
    if session.scalar(select(Account).where(Account.bank == bank, Account.name == name)):
        raise AccountError(f"Ya existe una cuenta llamada '{name}'.")
    account = Account(bank=bank, kind=kind, name=name)
    session.add(account)
    session.flush()
    return account


def rename_account(session: Session, account_id: int, name: str) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise AccountError("La cuenta no existe.")
    name = " ".join(name.split())
    if not name:
        raise AccountError("El nombre de la cuenta no puede estar vacio.")
    clash = session.scalar(select(Account).where(Account.bank == account.bank, Account.name == name, Account.id != account_id))
    if clash:
        raise AccountError(f"Ya existe una cuenta llamada '{name}'.")
    account.name = name
    return account


def delete_account(session: Session, account_id: int) -> None:
    account = session.get(Account, account_id)
    if account is None:
        raise AccountError("La cuenta no existe.")
    session.delete(account)  # sus movimientos y operaciones caen en cascada


def last_import_date(session: Session) -> date | None:
    """El dia (hora local) en que se importaron datos por ultima vez; None si no hay marcas de importacion."""
    from sqlalchemy import func

    latest = [
        session.scalar(select(func.max(Transaction.imported_at))),
        session.scalar(select(func.max(InvestmentOperation.imported_at))),
    ]
    latest = [d for d in latest if d is not None]
    if not latest:
        return None
    moment = max(latest)
    if moment.tzinfo is None:                       # SQLite devuelve la fecha sin zona: se guardo en UTC
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone().date()


# ----------------------------------------------------------------- categorias y presupuestos
class RuleError(ValueError):
    """Regla de categoria no valida (palabra clave demasiado corta, inexistente...)."""


MIN_KEYWORD = 2


def list_rules(session: Session) -> list[CategoryRule]:
    return list(session.scalars(select(CategoryRule).order_by(CategoryRule.id)))


def user_categorizer(session: Session) -> Categorizer:
    return Categorizer(user_rules=[(r.keyword, r.category) for r in list_rules(session)])


def recategorize(session: Session) -> int:
    """Vuelve a aplicar las reglas a los movimientos que el usuario no ha categorizado a mano.
    Devuelve cuantos han cambiado de categoria."""
    categorizer = user_categorizer(session)
    rows = session.execute(
        select(Transaction.id, Transaction.description, Transaction.amount, Transaction.category)
        .where(Transaction.category_is_manual.is_(False))
    )
    changes = []
    for row_id, description, amount, current in rows:
        wanted = categorizer.categorize(description, amount)
        if wanted != current:
            changes.append({"id": row_id, "category": wanted})
    if changes:
        session.execute(update(Transaction), changes)
    return len(changes)


def add_rule(session: Session, keyword: str, category: TxCategory) -> CategoryRule:
    keyword = normalize(keyword)
    if len(keyword) < MIN_KEYWORD:
        raise RuleError(f"La palabra clave necesita al menos {MIN_KEYWORD} caracteres.")
    rule = session.scalar(select(CategoryRule).where(CategoryRule.keyword == keyword))
    if rule is None:
        rule = CategoryRule(keyword=keyword, category=category)
        session.add(rule)
    else:
        rule.category = category
    session.flush()
    return rule


def delete_rule(session: Session, rule_id: int) -> None:
    rule = session.get(CategoryRule, rule_id)
    if rule is None:
        raise RuleError("La regla no existe.")
    session.delete(rule)
    session.flush()


def set_transaction_category(session: Session, tx_hash: str, category: TxCategory | None) -> None:
    """Fija la categoria de un movimiento a mano; con `None` vuelve a la automatica."""
    tx = session.scalar(select(Transaction).where(Transaction.tx_hash == tx_hash))
    if tx is None:
        raise RuleError("El movimiento no existe.")
    if category is None:
        tx.category_is_manual = False
        tx.category = user_categorizer(session).categorize(tx.description, tx.amount)
    else:
        tx.category_is_manual = True
        tx.category = category


def get_budgets(session: Session) -> dict[TxCategory, Decimal]:
    return {b.category: b.amount for b in session.scalars(select(Budget))}


def set_budgets(session: Session, budgets: dict[TxCategory, Decimal]) -> None:
    """Sustituye los presupuestos; los importes a cero o negativos equivalen a no tener presupuesto."""
    session.execute(delete(Budget))
    for category, amount in budgets.items():
        if amount > 0:
            session.add(Budget(category=category, amount=amount))
    session.flush()


# ------------------------------------------------------------------ metas de ahorro
def list_goals(session: Session) -> list[Goal]:
    return list(session.scalars(select(Goal).order_by(Goal.created_at, Goal.id)))


def save_goal(session: Session, name: str, target: Decimal, saved: Decimal, deadline: date | None,
              goal_id: int | None = None) -> int:
    goal = session.get(Goal, goal_id) if goal_id is not None else None
    if goal is None:
        goal = Goal(name=name, target=target, saved=saved, deadline=deadline)
        session.add(goal)
    else:
        goal.name, goal.target, goal.saved, goal.deadline = name, target, saved, deadline
    session.flush()
    return goal.id


def add_to_goal(session: Session, goal_id: int, amount: Decimal) -> None:
    goal = session.get(Goal, goal_id)
    if goal is not None:
        goal.saved = max(Decimal(0), goal.saved + amount)
        session.flush()


def delete_goal(session: Session, goal_id: int) -> None:
    session.execute(delete(Goal).where(Goal.id == goal_id))


# ------------------------------------------------------------------ historico de precios
def save_price_points(session: Session, rows: list[tuple[str, date, Decimal]]) -> tuple[int, int]:
    """Guarda los precios; si ya habia uno ese dia para ese fondo lo actualiza. Devuelve (nuevos, actualizados)."""
    wanted = {(isin, as_of): price for isin, as_of, price in rows}          # si un dia viene repetido, manda el ultimo
    existing = {(p.isin, p.as_of): p for p in session.scalars(
        select(PricePoint).where(PricePoint.isin.in_({isin for isin, _ in wanted})))}
    new = updated = 0
    for (isin, as_of), price in wanted.items():
        point = existing.get((isin, as_of))
        if point is None:
            session.add(PricePoint(isin=isin, as_of=as_of, unit_price=price))
            new += 1
        elif point.unit_price != price:
            point.unit_price = price
            updated += 1
    session.flush()
    return new, updated


def list_price_points(session: Session) -> list[PricePoint]:
    return list(session.scalars(select(PricePoint).order_by(PricePoint.isin, PricePoint.as_of)))


# ------------------------------------------------------------------ pagos recurrentes marcados a mano
def get_recurring_marks(session: Session) -> dict[str, bool]:
    return {m.key: m.include for m in session.scalars(select(RecurringMark))}


def set_recurring_mark(session: Session, key: str, include: bool | None) -> None:
    """`True`: es recurrente aunque Kreix no lo detecte; `False`: no lo es aunque lo detecte; `None`: vuelve a la deteccion."""
    mark = session.get(RecurringMark, key)
    if include is None:
        if mark is not None:
            session.delete(mark)
    elif mark is None:
        session.add(RecurringMark(key=key, include=include))
    else:
        mark.include = include
    session.flush()
