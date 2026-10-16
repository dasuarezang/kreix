"""Lee un extracto de cualquier banco con el formato (columnas asignadas) que definio el usuario."""
from __future__ import annotations

from decimal import Decimal

from core.categorizer import Categorizer, normalize
from core.entities import FileKind, ParseResult, TransactionDraft
from core.enums import Bank
from core.i18n import tr
from etl.common import HashFactory, ParseError, Table, clean_text
from etl.imagin_parser import _check_balance_continuity
from etl.mapping import ColumnMapping, parse_amount, parse_date

NAMESPACE = "extracto-generico"
MAX_WARNINGS = 10          # de las filas ignoradas se detallan las primeras; el resto se cuenta


def _blank(value) -> bool:
    return value is None or not str(value).strip()


def _amount(row: dict, mapping: ColumnMapping) -> Decimal:
    comma = mapping.decimal_comma
    if mapping.amount:
        value = parse_amount(row[mapping.amount], comma)
    else:
        money = Decimal(0)
        seen = False
        if mapping.income and not _blank(row.get(mapping.income)):
            money += abs(parse_amount(row[mapping.income], comma))
            seen = True
        if mapping.expense and not _blank(row.get(mapping.expense)):
            money -= abs(parse_amount(row[mapping.expense], comma))
            seen = True
        if not seen:
            raise ParseError(tr("Importe no valido: {value}").format(value="''"))
        value = money
    return -value if mapping.invert_sign else value


def parse(table: Table, source_file: str, mapping: ColumnMapping, categorizer: Categorizer | None = None) -> ParseResult:
    problem = mapping.problem()
    if problem:
        raise ParseError(problem)
    missing = mapping.required - set(table.columns)
    if missing:
        raise ParseError(tr("Faltan columnas del formato «{name}»: {missing}").format(name=mapping.name, missing=sorted(missing)))
    categorizer = categorizer or Categorizer()
    hashes = HashFactory(NAMESPACE)
    result = ParseResult(FileKind.BANK_STATEMENT, source_file, format_name=mapping.name)
    ignored = 0
    for line, row in enumerate(table.rows, start=2):
        try:
            booking = parse_date(row[mapping.date], mapping.day_first)
            description = clean_text(row[mapping.description])
            amount = _amount(row, mapping)
            balance = parse_amount(row[mapping.balance], mapping.decimal_comma) if mapping.balance and not _blank(row[mapping.balance]) else None
        except ParseError as exc:
            ignored += 1
            if ignored <= MAX_WARNINGS:
                result.warnings.append(tr("Fila {line} ignorada: {exc}").format(line=line, exc=exc))
            continue
        result.transactions.append(TransactionDraft(
            bank=Bank.IMAGIN,                            # la columna `bank` solo distingue "cuenta corriente"; el nombre lo da la cuenta
            booking_date=booking,
            description=description,
            amount=amount,
            balance_after=balance,
            category=categorizer.categorize(description, amount),
            tx_hash=hashes.make(booking, normalize(description), amount, balance),
            source_file=source_file,
        ))
    result.ignored_rows = ignored
    if ignored > MAX_WARNINGS:
        result.warnings.append(tr("Y {n} filas más ignoradas por el mismo motivo.").format(n=ignored - MAX_WARNINGS))
    if not result.transactions:
        raise ParseError(tr("Con este formato no se ha podido leer ningún movimiento."))
    if mapping.balance:
        result.warnings.extend(_check_balance_continuity(result.transactions))
    return result
