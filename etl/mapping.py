"""Formatos de extracto definidos por el usuario: que columna es la fecha, el concepto, el importe y el saldo.

Cuando Kreix no reconoce un CSV o Excel (no es de Imagin ni de MyInvestor), el usuario asigna las columnas una vez y el
formato queda guardado: la proxima vez que llegue un archivo con esas columnas se lee solo. Este modulo es puro (sin Qt ni
base de datos): el mapa, su guardado como JSON, la busqueda de la fila de titulos y las sugerencias automaticas.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from core.i18n import tr
from etl.common import ParseError, normalize_header, to_decimal

MAX_PREAMBLE_ROWS = 25
SAMPLE_ROWS = 8
MAX_FORMATS = 50

# Palabras que delatan cada columna (ya sin acentos y en minusculas). Primero las mas especificas.
_DATE_WORDS = ("fecha operacion", "fecha contable", "fecha", "data operacio", "data", "date", "booking", "posted")
_DATE_AVOID = ("valor", "value")                       # "fecha valor" es la segunda fecha: no la preferida
_TEXT_WORDS = ("concepto", "descripcion", "detalle", "movimiento", "concepte", "descripcio", "description", "details",
               "memo", "payee", "narrative", "reference", "referencia", "observaciones")
_AMOUNT_WORDS = ("importe", "cantidad", "import", "amount", "quantia")
_IN_WORDS = ("ingreso", "ingresos", "abono", "abonos", "credito", "haber", "credit", "deposit", "entrada", "ingres")
_OUT_WORDS = ("gasto", "gastos", "cargo", "cargos", "debito", "debe", "debit", "withdrawal", "salida", "despesa")
_BALANCE_WORDS = ("saldo", "balance", "saldo posterior", "saldo contable")


@dataclass(frozen=True, slots=True)
class ColumnMapping:
    """Un formato guardado. Los nombres de columna estan normalizados (como `normalize_header`)."""

    name: str
    date: str
    description: str
    amount: str = ""             # una columna con el importe con signo...
    income: str = ""             # ...o dos columnas: ingresos y gastos
    expense: str = ""
    balance: str = ""            # opcional
    day_first: bool = True       # 03/04/2026 es 3 de abril (False: 4 de marzo)
    decimal_comma: bool = True   # 1.234,56 (False: 1,234.56)
    invert_sign: bool = False    # los gastos vienen como numeros positivos

    @property
    def uses_two_columns(self) -> bool:
        return not self.amount

    @property
    def required(self) -> set[str]:
        return {c for c in (self.date, self.description, self.amount, self.income, self.expense, self.balance) if c}

    def problem(self) -> str | None:
        """Por que este mapa no sirve (None si esta completo)."""
        if not self.date:
            return tr("Elige la columna de la fecha.")
        if not self.description:
            return tr("Elige la columna del concepto.")
        if not self.amount and not (self.income or self.expense):
            return tr("Elige la columna del importe (o las de ingresos y gastos).")
        if self.amount and (self.income or self.expense):
            return tr("Usa una columna de importe o dos de ingresos y gastos, pero no las dos cosas.")
        used = [c for c in (self.date, self.description, self.amount, self.income, self.expense, self.balance) if c]
        if len(set(used)) != len(used):
            return tr("Cada columna solo puede servir para una cosa.")
        return None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ColumnMapping | None":
        """None si el dato guardado esta corrupto o incompleto (nunca rompe la carga)."""
        try:
            texts = {k: str(data.get(k, "")) for k in ("name", "date", "description", "amount", "income", "expense", "balance")}
            mapping = cls(**texts, day_first=bool(data.get("day_first", True)), decimal_comma=bool(data.get("decimal_comma", True)),
                          invert_sign=bool(data.get("invert_sign", False)))
        except (TypeError, ValueError, AttributeError):
            return None
        return mapping if mapping.name.strip() and mapping.problem() is None else None


def dump_formats(formats: list[ColumnMapping]) -> str:
    return json.dumps([f.to_json() for f in formats[:MAX_FORMATS]], ensure_ascii=False)


def load_formats(text: str) -> list[ColumnMapping]:
    try:
        raw = json.loads(text)
    except (ValueError, TypeError):
        return []
    if not isinstance(raw, list):
        return []
    found = (ColumnMapping.from_json(item) for item in raw[:MAX_FORMATS] if isinstance(item, dict))
    return [m for m in found if m is not None]


# ---------------------------------------------------------------- buscar la tabla dentro del archivo
def find_header(rows: list[list[Any]], mapping: ColumnMapping) -> int | None:
    """Fila de titulos que contiene todas las columnas del formato (None si el archivo no es de este formato)."""
    needed = mapping.required
    for index, row in enumerate(rows[:MAX_PREAMBLE_ROWS]):
        if needed <= {normalize_header(cell) for cell in row}:
            return index
    return None


def guess_header_row(rows: list[list[Any]]) -> int:
    """La fila de titulos mas probable: la primera con varias celdas de texto que no son numeros ni fechas y que tiene
    debajo una fila con datos."""
    best, best_width = 0, 0
    for index, row in enumerate(rows[:MAX_PREAMBLE_ROWS]):
        cells = [c for c in row if str(c if c is not None else "").strip()]
        if len(cells) < 3:
            continue
        texty = sum(1 for c in cells if not _looks_numeric(c) and _try_date(c, True) is None)
        if texty >= max(3, int(len(cells) * 0.7)) and len(cells) >= best_width:
            if index + 1 < len(rows) and any(str(c or "").strip() for c in rows[index + 1]):
                return index
            best, best_width = index, len(cells)
    return best


# ---------------------------------------------------------------- numeros y fechas
def _looks_numeric(value: Any) -> bool:
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return True
    return bool(re.fullmatch(r"[-+(]?\s*[\d.,\s]+\s*[A-Za-z€$£]{0,3}\)?-?", str(value or "").strip())) and any(ch.isdigit() for ch in str(value))


def parse_amount(value: Any, decimal_comma: bool = True) -> Decimal:
    """Importe de una celda: numero de Excel o texto ('-2,99 EUR', '1.234,56', '(12.50)', '12,50-', '1,234.56')."""
    if isinstance(value, bool) or value is None or str(value).strip() == "":
        raise ParseError(tr("Importe no valido: {value}").format(value=repr(value)))
    if isinstance(value, (int, float, Decimal)):
        return to_decimal(value)
    text = str(value).strip().replace("−", "-").replace("–", "-").replace(" ", " ")
    negative = text.startswith("(") and text.endswith(")") or text.endswith("-") or text.startswith("-")
    digits = re.sub(r"[^\d,.]", "", text)
    if not any(ch.isdigit() for ch in digits):
        raise ParseError(tr("Importe no valido: {value}").format(value=repr(value)))
    if decimal_comma:
        digits = digits.replace(".", "").replace(",", ".")
    else:
        digits = digits.replace(",", "")
    try:
        number = Decimal(digits)
    except InvalidOperation as exc:
        raise ParseError(tr("Importe no valido: {value}").format(value=repr(value))) from exc
    return -number if negative else number


def guess_decimal_comma(samples: list[Any]) -> bool:
    """True si los importes de ejemplo usan coma decimal (1.234,56); False si usan punto (1,234.56). Por defecto, coma."""
    comma = dot = 0
    for value in samples:
        if isinstance(value, (int, float, Decimal)) or value is None:
            continue
        text = str(value).strip()
        if re.search(r"\d,\d{1,2}(?!\d)\D*$", text):
            comma += 1
        elif re.search(r"\d\.\d{1,2}(?!\d)\D*$", text):
            dot += 1
    return not dot > comma


_DATE_RE = re.compile(r"^(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{1,4})(?:[ T,].*)?$")


def _try_date(value: Any, day_first: bool) -> date | None:
    try:
        return parse_date(value, day_first)
    except ParseError:
        return None


def parse_date(value: Any, day_first: bool = True) -> date:
    """Fecha de una celda: de Excel, o texto en dia/mes/ano (o mes/dia/ano), ano/mes/dia, con / - o .; ano de 2 o 4 cifras."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value if value is not None else "").strip()
    found = _DATE_RE.match(text)
    if not found:
        raise ParseError(tr("Fecha no valida: {value}").format(value=repr(value)))
    a, b, c = found.groups()
    try:
        if len(a) == 4:                                               # ano/mes/dia
            return date(int(a), int(b), int(c))
        year = int(c) + (2000 if len(c) <= 2 and int(c) < 70 else 1900 if len(c) <= 2 else 0)
        day, month = (int(a), int(b)) if day_first else (int(b), int(a))
        return date(year, month, day)
    except ValueError as exc:
        raise ParseError(tr("Fecha no valida: {value}").format(value=repr(value))) from exc


def guess_day_first(samples: list[Any]) -> bool:
    """False solo si hay pruebas de mes/dia (un primer numero que no puede ser dia, o un segundo mayor que 12)."""
    for value in samples:
        found = _DATE_RE.match(str(value or "").strip())
        if found and len(found.group(1)) != 4:
            first, second = int(found.group(1)), int(found.group(2))
            if second > 12 and first <= 12:
                return False
    return True


# ---------------------------------------------------------------- sugerencias
@dataclass(slots=True)
class FileSample:
    """Las primeras filas de un archivo desconocido, para ensenarselas al usuario."""

    rows: list[list[Any]]                  # todas las filas leidas (el asistente muestra solo las primeras)
    header_index: int
    headers: list[str] = field(default_factory=list)       # titulos tal como vienen
    keys: list[str] = field(default_factory=list)          # los mismos, normalizados

    @classmethod
    def of(cls, rows: list[list[Any]], header_index: int | None = None) -> "FileSample":
        index = guess_header_row(rows) if header_index is None else header_index
        index = max(0, min(index, max(0, len(rows) - 1)))
        header = rows[index] if rows else []
        headers = [str(c).strip() if c is not None and str(c).strip() else tr("Columna {n}").format(n=i + 1) for i, c in enumerate(header)]
        keys = [normalize_header(c) or f"columna {i + 1}" for i, c in enumerate(header)]
        return cls(rows, index, headers, keys)

    def body(self, limit: int | None = None) -> list[list[Any]]:
        data = [r for r in self.rows[self.header_index + 1:] if any(str(c).strip() for c in r if c is not None)]
        return data if limit is None else data[:limit]

    def column(self, key: str, limit: int = 30) -> list[Any]:
        if key not in self.keys:
            return []
        position = self.keys.index(key)
        return [row[position] if position < len(row) else None for row in self.body(limit)]


def _pick(keys: list[str], words: tuple[str, ...], taken: set[str], avoid: tuple[str, ...] = ()) -> str:
    for word in words:                                              # primero el titulo exacto, luego el que lo contiene
        for key in keys:
            if key not in taken and key == word:
                return key
    for word in words:
        for key in keys:
            if key in taken or any(a in key for a in avoid):
                continue
            if re.search(rf"\b{re.escape(word)}", key):
                return key
    return ""


def guess_mapping(sample: FileSample, name: str = "") -> ColumnMapping:
    """Un primer intento de asignar las columnas, por el nombre y, si no basta, por lo que contienen. El usuario lo revisa."""
    keys, taken = sample.keys, set()

    def take(words, avoid=()):
        found = _pick(keys, words, taken, avoid)
        if found:
            taken.add(found)
        return found

    date_key = take(_DATE_WORDS, _DATE_AVOID) or take(_DATE_WORDS)
    income, expense = take(_IN_WORDS), take(_OUT_WORDS)
    balance = take(_BALANCE_WORDS)
    amount = "" if (income and expense) else take(_AMOUNT_WORDS)
    if amount:
        income = expense = ""
    elif not (income and expense):
        income = expense = ""
    description = take(_TEXT_WORDS)
    free = [k for k in keys if k not in taken]
    if not date_key:                                                # por el contenido: la columna donde casi todo son fechas
        for key in free:
            values = [v for v in sample.column(key) if str(v or "").strip()]
            if values and sum(1 for v in values if _try_date(v, True)) >= max(1, int(len(values) * 0.8)):
                date_key = key
                taken.add(key)
                break
    free = [k for k in keys if k not in taken]
    if not amount and not income:
        for key in free:
            values = [v for v in sample.column(key) if str(v or "").strip()]
            if values and all(_looks_numeric(v) for v in values):
                amount = key
                taken.add(key)
                break
    free = [k for k in keys if k not in taken]
    if not description and free:                                    # la columna de texto mas larga
        def width(key: str) -> int:
            return sum(len(str(v or "")) for v in sample.column(key))
        description = max(free, key=width)
    amounts = sample.column(amount or income or expense)
    return ColumnMapping(
        name=name, date=date_key, description=description, amount=amount, income=income, expense=expense, balance=balance,
        day_first=guess_day_first(sample.column(date_key)), decimal_comma=guess_decimal_comma(amounts),
    )
