"""Utilidades de lectura y limpieza compartidas por los parsers."""
from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

from core.categorizer import normalize

CSV_ENCODINGS = ("utf-8-sig", "cp1252")
_MINUS = str.maketrans({"−": "-", "–": "-", " ": " "})


class ParseError(ValueError):
    pass


# ---------------------------------------------------------------- lectura de ficheros
def load_rows(path: Path) -> list[list[Any]]:
    """Lee CSV/TSV/TXT o Excel como lista de filas crudas (sin asumir cabecera)."""
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        df = pd.read_excel(path, header=None, dtype=object)
        return [[None if pd.isna(v) else v for v in row] for row in df.itertuples(index=False)]
    raw = path.read_bytes()
    for enc in CSV_ENCODINGS:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - cp1252 casi nunca falla
        raise ParseError(f"No se pudo decodificar {path.name}")
    lines = text.splitlines()
    sample = "\n".join(lines[:20])
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=";,\t").delimiter
    except csv.Error:
        delimiter = ";"
    return [row for row in csv.reader(lines, delimiter=delimiter)]


def normalize_header(h: Any) -> str:
    """'Importe (EUR)' -> 'importe'; 'Fecha Operación' -> 'fecha operacion'."""
    text = re.sub(r"\(.*?\)", "", str(h or ""))
    return normalize(text).lower()


def build_frame(rows: list[list[Any]], header_index: int) -> pd.DataFrame:
    header = [normalize_header(h) for h in rows[header_index]]
    body = [r for r in rows[header_index + 1:] if any(str(c).strip() for c in r if c is not None)]
    width = len(header)
    body = [(list(r) + [None] * width)[:width] for r in body]
    return pd.DataFrame(body, columns=header)


# ---------------------------------------------------------------- conversiones
def to_decimal(value: Any) -> Decimal:
    """Acepta numeros de Excel o cadenas espanolas ('-2,99EUR', '1.234,56 €').

    En cadenas, '.' es separador de miles y ',' el decimal.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ParseError(f"Importe no valido: {value!r}")
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).translate(_MINUS)
    text = re.sub(r"[^\d,.\-+]", "", text)
    text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ParseError(f"Importe no valido: {value!r}") from exc


def to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt, size in (("%d/%m/%Y", 10), ("%Y-%m-%d", 10), ("%d-%m-%Y", 10)):
        try:
            return datetime.strptime(text[:size], fmt).date()
        except ValueError:
            continue
    raise ParseError(f"Fecha no valida: {value!r}")


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


# ---------------------------------------------------------------- hashes anti-duplicado
def make_hash(*parts: Any) -> str:
    payload = "\x1f".join(str(p) for p in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class HashFactory:
    """Genera hashes estables. Si dos filas son identicas (misma fecha, concepto,
    importe y saldo) las distingue por orden de aparicion, de modo que dos pagos
    legitimos iguales no se pierden, y reimportar el mismo extracto da los mismos
    hashes."""

    def __init__(self, namespace: str) -> None:
        self._ns = namespace
        self._seen: Counter[str] = Counter()

    def make(self, *parts: Any) -> str:
        base = make_hash(self._ns, *parts)
        occurrence = self._seen[base]
        self._seen[base] += 1
        return make_hash(base, occurrence)
