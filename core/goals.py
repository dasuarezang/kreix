"""Metas de ahorro: logica pura (sin interfaz ni base de datos)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class Goal:
    id: int
    name: str
    target: Decimal
    saved: Decimal
    deadline: date | None = None

    @property
    def fraction(self) -> float:
        """Avance de 0 a 1 (se queda en 1 aunque se supere la meta)."""
        if self.target <= 0:
            return 1.0
        return float(min(max(self.saved / self.target, ZERO), Decimal(1)))

    @property
    def remaining(self) -> Decimal:
        return max(self.target - self.saved, ZERO)

    @property
    def reached(self) -> bool:
        return self.saved >= self.target > 0


def months_left(deadline: date, today: date) -> int:
    """Meses naturales que quedan hasta la fecha (0 si es este mes o ya paso)."""
    return max((deadline.year - today.year) * 12 + deadline.month - today.month, 0)


def monthly_needed(goal: Goal, today: date) -> Decimal | None:
    """Cuanto habria que apartar cada mes para llegar a tiempo. None si no hay fecha, ya se alcanzo o ya vencio."""
    if goal.deadline is None or goal.reached or goal.deadline < today:
        return None
    months = max(months_left(goal.deadline, today), 1)
    return (goal.remaining / months).quantize(Decimal("0.01"))
