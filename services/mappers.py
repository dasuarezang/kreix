"""Filas de la base de datos -> objetos de dominio de `core` (lo que consumen las metricas)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.entities import OperationDraft, PositionSnapshot, PricePointDraft, TransactionDraft
from core.enums import Bank, TxCategory
from core.transfers import pair_transfers
from data.models import SCALE, Account, Investment, InvestmentOperation, PricePoint, Valuation


_TX_SQL = (
    "SELECT a.bank, t.booking_date, t.description, t.amount, t.balance_after, t.category, t.tx_hash, t.source_file, "
    "t.account_id, t.category_is_manual FROM transactions t JOIN accounts a ON a.id = t.account_id "
    "ORDER BY t.booking_date, t.id"
)
_BANKS = {b.name: b for b in Bank}
_CATEGORIES = {c.name: c for c in TxCategory}


def load_transactions(session: Session) -> list[TransactionDraft]:
    # Se leen las columnas en crudo y se convierten a mano (igual que haria el ORM con sus tipos): con decenas de miles de
    # movimientos, pasar por la capa de tipos de SQLAlchemy fila a fila era lo que mas tardaba.
    scale = Decimal(SCALE)
    from_iso = date.fromisoformat
    return pair_transfers([
        TransactionDraft(
            bank=_BANKS[bank], booking_date=from_iso(day), description=desc,
            amount=Decimal(amount) / scale, balance_after=None if balance is None else Decimal(balance) / scale,
            category=_CATEGORIES[category], tx_hash=tx_hash, source_file=source or "", account_id=account_id,
            is_manual=bool(manual),
        )
        for bank, day, desc, amount, balance, category, tx_hash, source, account_id, manual
        in session.connection().exec_driver_sql(_TX_SQL).fetchall()       # de golpe: iterar el cursor fila a fila cuesta mas
    ])                                                                    # y los traspasos entre cuentas propias, emparejados


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


def load_prices(session: Session) -> list[PricePointDraft]:
    rows = session.execute(select(PricePoint.isin, PricePoint.as_of, PricePoint.unit_price).order_by(PricePoint.isin, PricePoint.as_of))
    return [PricePointDraft(isin, day, price) for isin, day, price in rows]


def cached_transactions(factory) -> list[TransactionDraft]:
    """Los movimientos tal como estan ahora, leidos una sola vez mientras los datos no cambien (cambiar de mes, de cuenta o de
    pagina no los vuelve a leer). Quien los reciba no debe modificar la lista (son movimientos inmutables)."""
    from data.database import session_scope
    from data.tracker import tracker_for

    def read() -> list[TransactionDraft]:
        with session_scope(factory) as s:
            return load_transactions(s)

    return tracker_for(factory.kw["bind"]).cached(("transactions",), read)
