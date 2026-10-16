"""Formato de numeros, porcentajes, fechas y etiquetas, segun el idioma activo (sin dependencias de Qt).

Castellano y catalan escriben los numeros como 1.234,56 €; el ingles como €1,234.56.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from core import i18n
from core.enums import OperationType, TxCategory
from core.i18n import N_, tr

NBSP = " "
MINUS = "−"
EMPTY = "—"
# Nombres en castellano, por compatibilidad: para mostrarlos usa month_short() / month_long() / i18n.months_*().
MONTHS_SHORT = list(i18n.MONTHS_SHORT["es"])
MONTHS_LONG = list(i18n.MONTHS_LONG["es"])


def _number(value: Decimal | float, decimals: int) -> str:
    text = f"{abs(value):,.{decimals}f}"
    if i18n.decimal_comma():
        return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text


_es_number = _number      # nombre antiguo


HIDDEN = "••••"
_private = False          # modo privacidad: ninguna cantidad en euros se muestra


def set_private(on: bool) -> None:
    """Activa o desactiva el modo privacidad (ocultar las cantidades). Las vistas se vuelven a pintar al recargarse."""
    global _private
    _private = bool(on)


def is_private() -> bool:
    return _private


def fmt_eur(value: Decimal | float | None, decimals: int = 2) -> str:
    """5781.2 -> '5.781,20 €' (castellano y catalan) o '€5,781.20' (ingles). Los negativos usan el signo menos.
    En modo privacidad, '•••• €' (o '€••••'): nada que ensenar a quien mire la pantalla."""
    if value is None:
        return EMPTY
    if _private:
        return f"{HIDDEN}{NBSP}€" if i18n.decimal_comma() else f"€{HIDDEN}"
    sign = MINUS if value < 0 and round(abs(value), decimals) != 0 else ""
    if i18n.decimal_comma():
        return f"{sign}{_number(value, decimals)}{NBSP}€"
    return f"{sign}€{_number(value, decimals)}"


def fmt_pct(fraction: Decimal | float | None, decimals: int = 1, signed: bool = False) -> str:
    """0.0441 -> '4,4 %' (castellano y catalan) o '4.4%' (ingles). Recibe una fraccion, no un porcentaje."""
    if fraction is None:
        return EMPTY
    pct = float(fraction) * 100
    if round(abs(pct), decimals) == 0:
        sign = ""
    else:
        sign = MINUS if pct < 0 else ("+" if signed else "")
    unit = f"{NBSP}%" if i18n.decimal_comma() else "%"
    return f"{sign}{_number(pct, decimals)}{unit}"


def month_short(d: date) -> str:
    return f"{i18n.months_short()[d.month - 1]} {d.year % 100:02d}"


def month_long(d: date) -> str:
    return f"{i18n.months_long()[d.month - 1]} {d.year}"


def fmt_datetime_long(moment: datetime) -> str:
    """'Lunes 7 de Enero del 2027 - 20:20h' (castellano), 'Dilluns 7 de Gener del 2027 - 20:20h' (catalan),
    'Monday 7 January 2027 - 20:20' (ingles)."""
    lang = i18n.language()
    weekday = i18n.weekdays()[moment.weekday()].capitalize()
    month = i18n.months_long()[moment.month - 1].capitalize()
    clock = f"{moment.hour:02d}:{moment.minute:02d}"
    if lang == "en":
        return f"{weekday} {moment.day} {month} {moment.year} - {clock}"
    particle = "d'" if lang == "ca" and month[0] in "AEIOU" else "de "
    return f"{weekday} {moment.day} {particle}{month} del {moment.year} - {clock}h"


def fmt_ago(moment: datetime, now: datetime) -> str:
    """Hace cuanto fue algo, en palabras sencillas: 'ahora mismo', 'hace 5 min', 'hace 3 h', 'ayer', 'hace 4 días'."""
    seconds = (now - moment).total_seconds()
    if seconds < 90:
        return tr("ahora mismo")
    minutes = round(seconds / 60)
    if minutes < 60:
        return tr("hace {n} min").format(n=minutes)
    hours = round(seconds / 3600)
    if hours < 24:
        return tr("hace {n} h").format(n=hours)
    days = (now.date() - moment.date()).days
    if days <= 1:
        return tr("ayer")
    return tr("hace {n} días").format(n=days)


CATEGORY_LABELS = {
    TxCategory.INCOME: N_("Ingresos"),
    TxCategory.GROCERIES: N_("Supermercado"),
    TxCategory.DINING: N_("Restaurantes"),
    TxCategory.SUBSCRIPTIONS: N_("Suscripciones"),
    TxCategory.LEISURE: N_("Ocio"),
    TxCategory.TRANSPORT: N_("Transporte"),
    TxCategory.HOUSING: N_("Vivienda"),
    TxCategory.HEALTH: N_("Salud"),
    TxCategory.P2P: N_("Bizum"),
    TxCategory.TRANSFER: N_("Traspaso"),
    TxCategory.INVESTMENT_TRANSFER: N_("Aportación a inversión"),
    TxCategory.OTHER: N_("Otros"),
    TxCategory.UNCATEGORIZED: N_("Sin categoría"),
}
OPERATION_LABELS = {
    OperationType.BUY: N_("Compra"),
    OperationType.SELL: N_("Venta"),
    OperationType.DIVIDEND: N_("Dividendo"),
    OperationType.FEE: N_("Comisión"),
    OperationType.DEPOSIT: N_("Ingreso"),
    OperationType.WITHDRAWAL: N_("Retirada"),
}


def category_label(category: TxCategory) -> str:
    return tr(CATEGORY_LABELS.get(category, category.value))


def movement_category(t) -> str:
    """La categoria de un movimiento tal como se ve: un traspaso entre dos cuentas propias lo dice."""
    if getattr(t, "paired_with", None) is not None:
        return tr("Traspaso entre tus cuentas")
    return category_label(t.category)


def operation_label(op_type: OperationType) -> str:
    return tr(OPERATION_LABELS.get(op_type, op_type.value))


def fmt_date(d: date) -> str:
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def fmt_units(value: Decimal | float | None, decimals: int = 4) -> str:
    if value is None:
        return EMPTY
    return _number(value, decimals)
