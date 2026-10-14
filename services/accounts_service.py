"""Caso de uso de la pestana Cuentas: varias cuentas, metricas y movimientos por periodo."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from core import metrics
from core.account_metrics import AccountSummary, CategoryAmount, available_months, expense_breakdown, summarize_account
from core.entities import TransactionDraft
from core.enums import AccountKind, Bank
from core.metrics import FlowOptions, MonthlyFlow
from core.periods import GLOBAL, Period
from data.database import session_scope
from data.repositories import add_account, delete_account, list_accounts, rename_account
from services.mappers import load_transactions


@dataclass(frozen=True, slots=True)
class AccountInfo:
    id: int
    name: str
    bank: Bank
    kind: AccountKind


@dataclass(slots=True)
class AccountsViewData:
    accounts: list[AccountInfo] = field(default_factory=list)
    selected: list[int] = field(default_factory=list)
    months: list[date] = field(default_factory=list)             # meses con movimientos, el mas reciente primero
    period: Period = GLOBAL
    summary: AccountSummary | None = None
    categories: list[CategoryAmount] = field(default_factory=list)
    balance_series: list[tuple[date, Decimal]] = field(default_factory=list)
    monthly: list[MonthlyFlow] = field(default_factory=list)
    movements: list[TransactionDraft] = field(default_factory=list)   # del periodo, el mas reciente primero

    @property
    def has_movements(self) -> bool:
        return bool(self.months)


class AccountsService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    # -- gestion de cuentas ------------------------------------------------
    def accounts(self) -> list[AccountInfo]:
        with session_scope(self._factory) as s:
            return [AccountInfo(a.id, a.name, a.bank, a.kind) for a in list_accounts(s, AccountKind.CHECKING)]

    def add(self, name: str) -> AccountInfo:
        with session_scope(self._factory) as s:
            a = add_account(s, name)
            return AccountInfo(a.id, a.name, a.bank, a.kind)

    def rename(self, account_id: int, name: str) -> None:
        with session_scope(self._factory) as s:
            rename_account(s, account_id, name)

    def delete(self, account_id: int) -> None:
        with session_scope(self._factory) as s:
            delete_account(s, account_id)

    # -- datos de la pestana ----------------------------------------------
    def view(
        self,
        account_ids: list[int] | None = None,
        month: date | None = None,
        options: FlowOptions = FlowOptions(),
    ) -> AccountsViewData:
        """`account_ids=None` son todas las cuentas; `month=None` es el periodo global."""
        accounts = self.accounts()
        valid = {a.id for a in accounts}
        selected = [i for i in (account_ids if account_ids is not None else sorted(valid)) if i in valid]
        with session_scope(self._factory) as s:
            txs = [t for t in load_transactions(s) if t.account_id in selected]

        period = Period.month(month) if month else GLOBAL
        inside = [t for t in txs if period.contains(t.booking_date)]
        return AccountsViewData(
            accounts=accounts,
            selected=selected,
            months=available_months(txs),
            period=period,
            summary=summarize_account(txs, period, options) if txs else None,
            categories=expense_breakdown(inside, options),
            balance_series=metrics.balance_series(txs, period.start, period.end),
            monthly=metrics.monthly_cashflow(txs, options=options),
            movements=metrics.order_movements(inside, newest_first=True),
        )
