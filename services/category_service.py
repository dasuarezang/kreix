"""Caso de uso: categorias editables (reglas del usuario, cambio manual) y presupuestos."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from core.enums import TxCategory
from data.database import session_scope
from data.repositories import (
    add_rule,
    delete_rule,
    get_budgets,
    list_rules,
    recategorize,
    set_budgets,
    set_transaction_category,
)


@dataclass(frozen=True, slots=True)
class RuleInfo:
    id: int
    keyword: str
    category: TxCategory


class CategoryService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def rules(self) -> list[RuleInfo]:
        with session_scope(self._factory) as s:
            return [RuleInfo(r.id, r.keyword, r.category) for r in list_rules(s)]

    def add_rule(self, keyword: str, category: TxCategory) -> int:
        """Guarda la regla y la aplica a lo ya importado. Devuelve cuantos movimientos han cambiado."""
        with session_scope(self._factory) as s:
            add_rule(s, keyword, category)
            return recategorize(s)

    def delete_rule(self, rule_id: int) -> int:
        with session_scope(self._factory) as s:
            delete_rule(s, rule_id)
            return recategorize(s)

    def set_category(self, tx_hash: str, category: TxCategory | None) -> None:
        """Cambia la categoria de un movimiento; `None` la devuelve a la automatica."""
        with session_scope(self._factory) as s:
            set_transaction_category(s, tx_hash, category)

    def budgets(self) -> dict[TxCategory, Decimal]:
        with session_scope(self._factory) as s:
            return get_budgets(s)

    def save_budgets(self, budgets: dict[TxCategory, Decimal]) -> None:
        with session_scope(self._factory) as s:
            set_budgets(s, budgets)
