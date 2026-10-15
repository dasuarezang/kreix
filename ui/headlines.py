"""Frases que resumen lo que cuenta cada grafico ("Gastas mas en Supermercado: el 46 % del total").

Funciones puras sin Qt: devuelven una frase corta, o una cadena vacia si no hay datos suficientes para decir algo cierto.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from core.account_metrics import CategoryAmount
from core.metrics import AllocationSlice, MonthlyFlow, WealthPoint
from ui.format import category_label, fmt_eur, fmt_pct, month_long

ZERO = Decimal(0)


def category_headline(items: Sequence[CategoryAmount]) -> str:
    if not items:
        return ""
    top = items[0]
    return f"Gastas más en {category_label(top.category)}: {fmt_eur(top.amount)}, el {fmt_pct(top.share, 0)} del total."


def balance_headline(series: Sequence[tuple[date, Decimal]], is_month: bool) -> str:
    if len(series) < 2:
        return ""
    change = series[-1][1] - series[0][1]
    span = "este mes" if is_month else "en este periodo"
    if abs(change) < Decimal("0.5"):
        return f"Tu saldo se ha mantenido casi igual {span}."
    return f"Tu saldo ha {'subido' if change > 0 else 'bajado'} {fmt_eur(abs(change))} {span}."


def monthly_headline(flows: Sequence[MonthlyFlow]) -> str:
    months = [f for f in flows if f.income or f.expenses]
    if len(months) < 2:
        return ""
    good = sum(1 for f in months if f.income >= f.expenses)
    if good == len(months):
        return f"Has gastado menos de lo que ingresas en los {len(months)} meses."
    return f"Has gastado menos de lo que ingresas en {good} de {len(months)} meses."


def allocation_headline(cash: Decimal | None, portfolio: Decimal, net_worth: Decimal) -> str:
    if net_worth <= 0 or portfolio <= 0:
        return ""
    return f"El {fmt_pct(portfolio / net_worth, 0)} de tu patrimonio está invertido y el resto es liquidez."


def flow_headline(flows: Sequence[MonthlyFlow]) -> str:
    if not flows:
        return ""
    last = flows[-1]
    text = f"En {month_long(last.month)}: ingresaste {fmt_eur(last.income)} y gastaste {fmt_eur(last.expenses)}"
    if last.contributions > 0:
        text += f", y aportaste {fmt_eur(last.contributions)} a inversión"
    return text + "."


def wealth_headline(points: Sequence[WealthPoint]) -> str:
    if len(points) < 2:
        return ""
    change = points[-1].net_worth - points[0].net_worth
    if abs(change) < Decimal("0.5"):
        return ""
    verb = "ha crecido" if change > 0 else "ha bajado"
    return f"Tu patrimonio {verb} {fmt_eur(abs(change))} desde {month_long(points[0].date)}."


def fund_headline(allocation: Sequence[AllocationSlice]) -> str:
    if not allocation:
        return ""
    top = max(allocation, key=lambda s: s.weight)
    if len(allocation) == 1:
        return f"Toda tu cartera está en {top.label}."
    return f"Tu mayor posición es {top.label}: el {fmt_pct(top.weight, 0)} de la cartera."


def evolution_headline(points: Sequence[WealthPoint]) -> str:
    if not points:
        return ""
    last = points[-1]
    if last.contributions <= 0 or last.invested_value <= 0:
        return ""
    gain = last.invested_value - last.contributions
    if abs(gain) < Decimal("0.5"):
        return f"Has aportado {fmt_eur(last.contributions)} y tu cartera vale lo mismo."
    word = "sumado" if gain > 0 else "restado"
    return (f"Has aportado {fmt_eur(last.contributions)} y tu cartera vale {fmt_eur(last.invested_value)}: "
            f"la rentabilidad ha {word} {fmt_eur(abs(gain))}.")
