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
from core.i18n import N_, tr

ZERO = Decimal(0)


def category_headline(items: Sequence[CategoryAmount]) -> str:
    if not items:
        return ""
    top = items[0]
    return tr("Gastas más en {category}: {amount}, el {share} del total.").format(category=category_label(top.category), amount=fmt_eur(top.amount), share=fmt_pct(top.share, 0))


def balance_headline(series: Sequence[tuple[date, Decimal]], is_month: bool) -> str:
    if len(series) < 2:
        return ""
    change = series[-1][1] - series[0][1]
    span = tr("este mes") if is_month else tr("en este periodo")
    if abs(change) < Decimal("0.5"):
        return tr("Tu saldo se ha mantenido casi igual {span}.").format(span=span)
    key = N_("Tu saldo ha subido {amount} {span}.") if change > 0 else N_("Tu saldo ha bajado {amount} {span}.")
    return tr(key).format(amount=fmt_eur(abs(change)), span=span)


def monthly_headline(flows: Sequence[MonthlyFlow]) -> str:
    months = [f for f in flows if f.income or f.expenses]
    if len(months) < 2:
        return ""
    good = sum(1 for f in months if f.income >= f.expenses)
    if good == len(months):
        return tr("Has gastado menos de lo que ingresas en los {months} meses.").format(months=len(months))
    return tr("Has gastado menos de lo que ingresas en {good} de {months} meses.").format(good=good, months=len(months))


def allocation_headline(cash: Decimal | None, portfolio: Decimal, net_worth: Decimal) -> str:
    if net_worth <= 0 or portfolio <= 0:
        return ""
    return tr("El {net_worth} de tu patrimonio está invertido y el resto es liquidez.").format(net_worth=fmt_pct(portfolio / net_worth, 0))


def flow_headline(flows: Sequence[MonthlyFlow]) -> str:
    if not flows:
        return ""
    last = flows[-1]
    text = tr("En {month}: ingresaste {income} y gastaste {expenses}").format(month=month_long(last.month), income=fmt_eur(last.income), expenses=fmt_eur(last.expenses))
    if last.contributions > 0:
        text += tr(", y aportaste {contributions} a inversión").format(contributions=fmt_eur(last.contributions))
    return text + "."


def wealth_headline(points: Sequence[WealthPoint]) -> str:
    if len(points) < 2:
        return ""
    change = points[-1].net_worth - points[0].net_worth
    if abs(change) < Decimal("0.5"):
        return ""
    key = (N_("Tu patrimonio ha crecido {change} desde {date}.") if change > 0
           else N_("Tu patrimonio ha bajado {change} desde {date}."))
    return tr(key).format(change=fmt_eur(abs(change)), date=month_long(points[0].date))


def fund_headline(allocation: Sequence[AllocationSlice]) -> str:
    if not allocation:
        return ""
    top = max(allocation, key=lambda s: s.weight)
    if len(allocation) == 1:
        return tr("Toda tu cartera está en {label}.").format(label=top.label)
    return tr("Tu mayor posición es {label}: el {weight} de la cartera.").format(label=top.label, weight=fmt_pct(top.weight, 0))


def evolution_headline(points: Sequence[WealthPoint]) -> str:
    if not points:
        return ""
    last = points[-1]
    if last.contributions <= 0 or last.invested_value <= 0:
        return ""
    gain = last.invested_value - last.contributions
    if abs(gain) < Decimal("0.5"):
        return tr("Has aportado {contributions} y tu cartera vale lo mismo.").format(contributions=fmt_eur(last.contributions))
    key = (N_("Has aportado {contributions} y tu cartera vale {invested_value}: la rentabilidad ha sumado {gain}.") if gain > 0
           else N_("Has aportado {contributions} y tu cartera vale {invested_value}: la rentabilidad ha restado {gain}."))
    return tr(key).format(contributions=fmt_eur(last.contributions), invested_value=fmt_eur(last.invested_value),
                          gain=fmt_eur(abs(gain)))
