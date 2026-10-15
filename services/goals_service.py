"""Caso de uso: metas de ahorro."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from core.goals import Goal
from data.database import session_scope
from data.repositories import add_to_goal, delete_goal, list_goals, save_goal

MAX_NAME = 60


class GoalError(ValueError):
    """Datos de meta no validos."""


def _to_goal(g) -> Goal:
    return Goal(g.id, g.name, g.target, g.saved, g.deadline)


class GoalsService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def goals(self) -> list[Goal]:
        with session_scope(self._factory) as s:
            return [_to_goal(g) for g in list_goals(s)]

    def save(self, name: str, target: Decimal, saved: Decimal = Decimal(0), deadline: date | None = None,
             goal_id: int | None = None) -> int:
        name = " ".join(name.split())[:MAX_NAME]
        if not name:
            raise GoalError("name")
        if target <= 0:
            raise GoalError("target")
        with session_scope(self._factory) as s:
            return save_goal(s, name, target, max(saved, Decimal(0)), deadline, goal_id)

    def contribute(self, goal_id: int, amount: Decimal) -> None:
        """Suma (o resta, si es negativo) lo ahorrado; nunca baja de cero."""
        with session_scope(self._factory) as s:
            add_to_goal(s, goal_id, amount)

    def delete(self, goal_id: int) -> None:
        with session_scope(self._factory) as s:
            delete_goal(s, goal_id)
