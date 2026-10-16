"""Deteccion automatica del tipo de fichero (por cabeceras) y despacho al parser."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from core.entities import FileKind, ParseResult
from etl import banks, generic_parser, imagin_parser, myinvestor_parser, price_history_parser
from etl.common import ParseError, build_table, load_rows, normalize_header
from etl.mapping import ColumnMapping, find_header
from core.i18n import tr

SIGNATURES: dict[FileKind, set[str]] = {
    FileKind.IMAGIN_STATEMENT: imagin_parser.REQUIRED,
    FileKind.MYINVESTOR_OPERATIONS: myinvestor_parser.OPS_REQUIRED,
    FileKind.MYINVESTOR_PORTFOLIO: myinvestor_parser.PORTFOLIO_REQUIRED,
}
MAX_PREAMBLE_ROWS = 25  # algunos Excel traen titulos antes de la tabla


class UnknownFormatError(ParseError):
    """El archivo no es de ningun banco conocido: el usuario puede asignar sus columnas."""


def detect(rows: list[list[Any]]) -> tuple[FileKind, int]:
    """Devuelve (tipo, indice de la fila de cabecera)."""
    for idx, row in enumerate(rows[:MAX_PREAMBLE_ROWS]):
        headers = {normalize_header(c) for c in row}
        for kind, required in SIGNATURES.items():
            if required <= headers:
                return kind, idx
        if price_history_parser.is_price_header(headers):
            return FileKind.PRICE_HISTORY, idx
    raise UnknownFormatError(tr("Formato no reconocido: no se encontraron las cabeceras de Imagin ni de MyInvestor."))


def parse_file(path: str | Path, portfolio_as_of: date | None = None, fund_isin: str | None = None,
               formats: tuple[ColumnMapping, ...] | list[ColumnMapping] = ()) -> ParseResult:
    """`formats`: los formatos de otros bancos que el usuario ya definio; se prueban si el archivo no es de Imagin ni de MyInvestor."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        raise ParseError(
            tr("Kreix solo importa extractos en CSV o Excel. Descárgalo en uno de esos formatos desde tu banco.")
        )
    rows = load_rows(path)
    try:
        kind, header_idx = detect(rows)
    except UnknownFormatError:
        for mapping in formats:
            header_idx = find_header(rows, mapping)
            if header_idx is not None:
                return generic_parser.parse(build_table(rows, header_idx), path.name, mapping)
        known = banks.recognize(rows)                         # CaixaBank, Santander, Revolut, Trade Republic...
        if known is not None:
            return generic_parser.parse(build_table(rows, known[1]), path.name, known[0])
        raise
    if kind is FileKind.PRICE_HISTORY and (known := banks.recognize(rows)) is not None:       # Trade Republic tambien trae fecha y precio
        return generic_parser.parse(build_table(rows, known[1]), path.name, known[0])
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
