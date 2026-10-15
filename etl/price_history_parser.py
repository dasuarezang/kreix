"""Historico de precios de un fondo (CSV o Excel descargado por el usuario de su banco, Morningstar, Yahoo, Investing...).

Se reconoce por tener una columna de fecha y una de precio (valor liquidativo, cierre, precio...). El ISIN puede venir
en una columna `ISIN`, en el nombre del archivo, o elegirse al importar. Los numeros se leen en formato espanol
(1.234,56) o ingles (1,234.56); las fechas, como dd/mm/aaaa, aaaa-mm-dd o "Oct 14, 2026".
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from core.entities import FileKind, ParseResult, PricePointDraft
from core.i18n import tr
from etl.common import ParseError, Table, clean_text, to_date

DATE_COLUMNS = ("fecha", "date", "dia", "day")
# Por orden de preferencia (la primera que exista en el archivo)
PRICE_COLUMNS = ("valor liquidativo", "vl", "nav", "precio", "price", "cierre", "close", "ultimo", "ultimo precio", "last")
ISIN_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b")


def is_price_header(headers: set[str]) -> bool:
    return any(c in headers for c in DATE_COLUMNS) and any(c in headers for c in PRICE_COLUMNS)


def isin_in(text: str) -> str:
    match = ISIN_RE.search(text.upper())
    return match.group(1) if match else ""


def parse_price(value: Any) -> Decimal:
    """'1.234,56', '1,234.56', '12.345', '12,34' o un numero de Excel."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ParseError(tr("Importe no valido: {value}").format(value=repr(value)))
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = re.sub(r"[^\d,.\-]", "", str(value))
    if "," in text and "." in text:                       # el ultimo separador es el decimal
        decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
        thousands = "." if decimal_sep == "," else ","
        text = text.replace(thousands, "").replace(decimal_sep, ".")
    elif text.count(",") > 1:
        text = text.replace(",", "")                       # 1,234,567 -> miles
    elif text.count(".") > 1:
        text = text.replace(".", "")                       # 1.234.567 -> miles
    else:
        text = text.replace(",", ".")                      # una sola coma o un solo punto: es el decimal
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ParseError(tr("Importe no valido: {value}").format(value=repr(value))) from exc


_EXTRA_DATE_FORMATS = ("%d.%m.%Y", "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%m/%d/%Y", "%Y/%m/%d")


def parse_day(value: Any) -> date:
    try:
        return to_date(value)
    except ParseError:
        text = clean_text(value)
        for fmt in _EXTRA_DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        raise


def parse_prices(table: Table, source_file: str, fund_isin: str | None = None) -> ParseResult:
    date_col = next(c for c in DATE_COLUMNS if c in table.columns)
    price_col = next(c for c in PRICE_COLUMNS if c in table.columns)
    file_isin = (fund_isin or "").upper() or isin_in(source_file)
    result = ParseResult(FileKind.PRICE_HISTORY, source_file)
    skipped = 0
    for row in table.rows:
        raw_date, raw_price = row.get(date_col), row.get(price_col)
        if raw_date in (None, "") or raw_price in (None, ""):
            skipped += 1
            continue
        try:
            day, price = parse_day(raw_date), parse_price(raw_price)
        except ParseError:
            skipped += 1
            continue
        if price <= 0:
            skipped += 1
            continue
        isin = clean_text(row.get("isin")).upper() or file_isin
        result.prices.append(PricePointDraft(isin, day, price))
    if not result.prices:
        raise ParseError(tr("No se ha podido leer ningún precio del archivo."))
    if skipped:
        result.warnings.append(tr("{n} filas sin fecha o sin precio válidos se han ignorado.").format(n=skipped))
    return result
