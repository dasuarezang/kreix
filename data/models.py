"""Esquema de base de datos de Kreix (SQLAlchemy 2.0, tipado).

Decisiones de diseno:
- Dinero y unidades se guardan como enteros escalados (1e-6) mediante `Decimal6`.
  Es exacto (sin errores de coma flotante), y SUM()/ORDER BY siguen funcionando en SQL.
- Cada movimiento lleva un `tx_hash` UNIQUE. Con ON CONFLICT DO NOTHING en el
  repositorio, reimportar el mismo extracto no duplica nada.
- Los modelos no contienen logica de negocio: solo estructura y restricciones.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from core.enums import AccountKind, Bank, OperationType, TxCategory

SCALE = 1_000_000  # 6 decimales: cubre centimos y participaciones de fondos


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Decimal6(TypeDecorator[Decimal]):
    """Decimal exacto almacenado como INTEGER escalado por 10^6."""

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value: Decimal | int | str | None, dialect: Dialect) -> int | None:
        if value is None:
            return None
        return int((Decimal(value) * SCALE).to_integral_value())

    def process_result_value(self, value: int | None, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        return Decimal(value) / SCALE


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- tablas
class Account(Base):
    """Una cuenta/contrato en un banco. Permite varias cuentas por banco."""

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("bank", "name", name="uq_account_bank_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bank: Mapped[Bank] = mapped_column(Enum(Bank, native_enum=False, length=20))
    kind: Mapped[AccountKind] = mapped_column(Enum(AccountKind, native_enum=False, length=20))
    name: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    operations: Mapped[list[InvestmentOperation]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Transaction(Base):
    """Movimiento de efectivo (extractos de Imagin; ingresos/retiradas de MyInvestor)."""

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_tx_account_date", "account_id", "booking_date"),
        Index("ix_tx_category", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    booking_date: Mapped[date] = mapped_column(Date)
    value_date: Mapped[date | None] = mapped_column(Date, default=None)
    description: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Decimal6)  # >0 ingreso, <0 gasto
    balance_after: Mapped[Decimal | None] = mapped_column(Decimal6, default=None)
    category: Mapped[TxCategory] = mapped_column(
        Enum(TxCategory, native_enum=False, length=30), default=TxCategory.UNCATEGORIZED
    )
    category_is_manual: Mapped[bool] = mapped_column(default=False)  # no se pisa al recategorizar
    tx_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 hex
    source_file: Mapped[str | None] = mapped_column(String(255), default=None)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    account: Mapped[Account] = relationship(back_populates="transactions")


class Investment(Base):
    """Maestro de productos (un fondo/ETF por ISIN)."""

    __tablename__ = "investments"

    id: Mapped[int] = mapped_column(primary_key=True)
    isin: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    asset_class: Mapped[str | None] = mapped_column(String(40), default=None)  # RV, RF, monetario...
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    operations: Mapped[list[InvestmentOperation]] = relationship(back_populates="investment")
    valuations: Mapped[list[Valuation]] = relationship(
        back_populates="investment", cascade="all, delete-orphan"
    )


class InvestmentOperation(Base):
    """Compras, ventas y demas movimientos de cartera. Base para TIR y TWR."""

    __tablename__ = "investment_operations"
    __table_args__ = (
        CheckConstraint("units >= 0", name="ck_op_units_nonneg"),
        Index("ix_op_investment_date", "investment_id", "trade_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    investment_id: Mapped[int | None] = mapped_column(ForeignKey("investments.id"), default=None)
    op_type: Mapped[OperationType] = mapped_column(Enum(OperationType, native_enum=False, length=20))
    trade_date: Mapped[date] = mapped_column(Date)
    units: Mapped[Decimal] = mapped_column(Decimal6, default=Decimal(0))
    unit_price: Mapped[Decimal | None] = mapped_column(Decimal6, default=None)  # valor liquidativo
    amount: Mapped[Decimal] = mapped_column(Decimal6)  # efectivo: <0 sale de la cuenta (compra)
    fees: Mapped[Decimal] = mapped_column(Decimal6, default=Decimal(0))
    tx_hash: Mapped[str] = mapped_column(String(64), unique=True)
    source_file: Mapped[str | None] = mapped_column(String(255), default=None)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    account: Mapped[Account] = relationship(back_populates="operations")
    investment: Mapped[Investment | None] = relationship(back_populates="operations")


class Valuation(Base):
    """Valor liquidativo y posicion en una fecha. Sirve para Net Worth y TWR."""

    __tablename__ = "valuations"
    __table_args__ = (UniqueConstraint("investment_id", "as_of", name="uq_valuation_inv_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    investment_id: Mapped[int] = mapped_column(ForeignKey("investments.id", ondelete="CASCADE"))
    as_of: Mapped[date] = mapped_column(Date)
    unit_price: Mapped[Decimal] = mapped_column(Decimal6)
    units: Mapped[Decimal] = mapped_column(Decimal6)
    invested: Mapped[Decimal] = mapped_column(Decimal6, default=Decimal(0))  # capital aportado (extracto de cartera)

    investment: Mapped[Investment] = relationship(back_populates="valuations")

    @property
    def market_value(self) -> Decimal:
        return self.unit_price * self.units


class CategoryRule(Base):
    """Regla del usuario: los conceptos que contienen `keyword` van a `category`. Gana a las de serie."""

    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(80), unique=True)  # normalizada: mayusculas y sin acentos
    category: Mapped[TxCategory] = mapped_column(Enum(TxCategory, native_enum=False, length=30))


class Budget(Base):
    """Presupuesto mensual de una categoria de gasto."""

    __tablename__ = "budgets"

    category: Mapped[TxCategory] = mapped_column(Enum(TxCategory, native_enum=False, length=30), primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Decimal6)


class Goal(Base):
    """Meta de ahorro: un objetivo con nombre, lo ahorrado hasta ahora (lo apunta el usuario) y una fecha opcional."""

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    target: Mapped[Decimal] = mapped_column(Decimal6)
    saved: Mapped[Decimal] = mapped_column(Decimal6, default=Decimal(0))
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RecurringMark(Base):
    """Lo que el usuario ha dicho de un comercio: es un pago recurrente (`include`) o no lo es (excluido), por encima de la deteccion."""

    __tablename__ = "recurring_marks"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)      # clave del comercio (core.recurring.merchant_key)
    include: Mapped[bool] = mapped_column()


class PricePoint(Base):
    """Valor liquidativo de un fondo en un dia, importado de un historico de precios (CSV)."""

    __tablename__ = "price_points"

    isin: Mapped[str] = mapped_column(String(12), primary_key=True)
    as_of: Mapped[date] = mapped_column(Date, primary_key=True)
    unit_price: Mapped[Decimal] = mapped_column(Decimal6)


class Setting(Base):
    """Preferencias de la app (tema, ultima carpeta de importacion...)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))
