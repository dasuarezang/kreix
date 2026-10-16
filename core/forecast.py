"""Previsión de fin de mes: cuanto dinero tendras en tus cuentas al acabar el mes si todo sigue como hasta ahora.

Logica pura. Se parte del dinero que hay en la ultima fecha con datos y se tiene en cuenta, hasta el ultimo dia del mes:
- los pagos recurrentes que aun no se han cobrado este mes (suscripciones, recibos...);
- los ingresos recurrentes que aun no han llegado (la nomina);
- el gasto del dia a dia (lo que no es un pago recurrente) al ritmo de los ultimos dias.
Es una estimacion honesta, no una promesa: no sabe de gastos extraordinarios ni de ingresos que no se repiten.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from core.entities import TransactionDraft
from core.metrics import FlowOptions, counts_as_flow, total_cash
from core.recurring import Recurring, detect_recurring, detect_recurring_income, merchant_key

LOOKBACK_DAYS = 60            # el gasto del dia a dia se mide con los ultimos dias
MIN_DAYS_OF_DATA = 14         # con menos datos no se estima el gasto del dia a dia (se dice, no se inventa)


@dataclass(frozen=True, slots=True)
class MonthForecast:
    as_of: date                       # ultimo dia con datos
    month_end: date
    days_left: int
    balance: Decimal                  # dinero en las cuentas ese dia
    fixed_due: Decimal                # pagos recurrentes que aun quedan por cobrar este mes
    income_due: Decimal               # ingresos recurrentes que aun quedan por llegar este mes
    daily_spend: Decimal              # gasto diario habitual (sin los pagos recurrentes)
    variable: Decimal                 # ese gasto durante los dias que quedan
    projected: Decimal                # lo que se espera tener a fin de mes
    reliable_variable: bool           # si hubo datos suficientes para estimar el gasto del dia a dia


def _occurrences(item: Recurring, after: date, until: date) -> int:
    """Cuantas veces se repite un pago/ingreso entre `after` (sin incluir) y `until` (incluido)."""
    count, when = 0, item.next_date
    step = timedelta(days=max(item.gap_days, 1))
    while when <= until:
        if when > after:
            count += 1
        when += step
    return count


def forecast_month_end(
    transactions: list[TransactionDraft], options: FlowOptions = FlowOptions(), recurring: list[Recurring] | None = None,
    marks: dict[str, bool] | None = None,
) -> MonthForecast | None:
    """None si no hay movimientos, no hay saldo o el ultimo dia con datos ya es el ultimo del mes."""
    if not transactions:
        return None
    balance = total_cash(transactions)
    if balance is None:
        return None
    last = max(t.booking_date for t in transactions)
    month_end = date(last.year, last.month, calendar.monthrange(last.year, last.month)[1])
    days_left = (month_end - last).days
    if days_left <= 0:
        return None

    payments = detect_recurring(transactions, marks=marks) if recurring is None else recurring
    incomes = detect_recurring_income(transactions)
    fixed = sum((p.amount * _occurrences(p, last, month_end) for p in payments), Decimal(0))
    income = sum((i.amount * _occurrences(i, last, month_end) for i in incomes), Decimal(0))

    regular = {merchant_key(p.name) for p in payments}
    start = last - timedelta(days=LOOKBACK_DAYS - 1)
    first = min(t.booking_date for t in transactions)
    window_start = max(start, first)
    span = (last - window_start).days + 1
    spent = sum((-t.amount for t in transactions
                 if t.amount < 0 and window_start <= t.booking_date <= last and merchant_key(t.description) not in regular
                 and counts_as_flow(t.category, t.amount, options, t.paired_with)), Decimal(0))
    reliable = span >= MIN_DAYS_OF_DATA
    daily = spent / span if reliable else Decimal(0)
    variable = daily * days_left
    return MonthForecast(
        as_of=last, month_end=month_end, days_left=days_left, balance=balance, fixed_due=fixed, income_due=income,
        daily_spend=daily, variable=variable, projected=balance - fixed + income - variable, reliable_variable=reliable,
    )
