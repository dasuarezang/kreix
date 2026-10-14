"""Periodos de analisis: un mes concreto o todo el historial (global)."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta


def month_start(d: date) -> date:
    return d.replace(day=1)


def month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def next_month(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def previous_month_end(d: date) -> date:
    return month_start(d) - timedelta(days=1)


@dataclass(frozen=True, slots=True)
class Period:
    """Intervalo cerrado [start, end]. Sin limites == global."""

    start: date | None = None
    end: date | None = None

    @classmethod
    def month(cls, any_day: date) -> Period:
        return cls(month_start(any_day), month_end(any_day))

    @property
    def is_global(self) -> bool:
        return self.start is None and self.end is None

    def contains(self, d: date) -> bool:
        return (self.start is None or d >= self.start) and (self.end is None or d <= self.end)


GLOBAL = Period()
