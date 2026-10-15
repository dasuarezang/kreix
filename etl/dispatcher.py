"""Deteccion automatica del tipo de fichero (por cabeceras) y despacho al parser."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from core.entities import FileKind, ParseResult
from etl import imagin_parser, myinvestor_parser, price_history_parser
from etl.common import ParseError, build_table, load_rows, normalize_header
from core.i18n import tr

SIGNATURES: dict[FileKind, set[str]] = {
    FileKind.IMAGIN_STATEMENT: imagin_parser.REQUIRED,
    FileKind.MYINVESTOR_OPERATIONS: myinvestor_parser.OPS_REQUIRED,
    FileKind.MYINVESTOR_PORTFOLIO: myinvestor_parser.PORTFOLIO_REQUIRED,
}
MAX_PREAMBLE_ROWS = 25  # algunos Excel traen titulos antes de la tabla


def detect(rows: list[list[Any]]) -> tuple[FileKind, int]:
    """Devuelve (tipo, indice de la fila de cabecera)."""
    for idx, row in enumerate(rows[:MAX_PREAMBLE_ROWS]):
        headers = {normalize_header(c) for c in row}
        for kind, required in SIGNATURES.items():
            if required <= headers:
                return kind, idx
        if price_history_parser.is_price_header(headers):
            return FileKind.PRICE_HISTORY, idx
    raise ParseError(tr("Formato no reconocido: no se encontraron las cabeceras de Imagin ni de MyInvestor."))


def parse_file(path: str | Path, portfolio_as_of: date | None = None, fund_isin: str | None = None) -> ParseResult:
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        raise ParseError(
            tr("Kreix solo importa extractos en CSV o Excel. Descárgalo en uno de esos formatos desde tu banco.")
        )
    rows = load_rows(path)
    kind, header_idx = detect(rows)
    table = build_table(rows, header_idx)
    if kind is FileKind.IMAGIN_STATEMENT:
        return imagin_parser.parse(table, path.name)
    if kind is FileKind.MYINVESTOR_OPERATIONS:
        return myinvestor_parser.parse_operations(table, path.name)
    if kind is FileKind.PRICE_HISTORY:
        result = price_history_parser.parse_prices(table, path.name, fund_isin)
        if any(not p.isin for p in result.prices):
            raise ParseError(tr("Este histórico no indica a qué fondo pertenece. Elige el fondo en «Fondo del histórico» antes de importarlo."))
        return result
    return myinvestor_parser.parse_portfolio(table, path.name, portfolio_as_of)
