"""Parser del extracto de Imagin: Concepto;Fecha;Importe;Saldo (CSV con ';')."""
from __future__ import annotations

from core.categorizer import Categorizer, normalize
from core.entities import FileKind, ParseResult, TransactionDraft
from core.enums import Bank
from etl.common import HashFactory, ParseError, Table, clean_text, to_date, to_decimal

REQUIRED = {"concepto", "fecha", "importe", "saldo"}


def parse(table: Table, source_file: str, categorizer: Categorizer | None = None) -> ParseResult:
    missing = REQUIRED - set(table.columns)
    if missing:
        raise ParseError(f"Faltan columnas de Imagin: {sorted(missing)}")
    categorizer = categorizer or Categorizer()
    hashes = HashFactory(Bank.IMAGIN.value)
    result = ParseResult(FileKind.IMAGIN_STATEMENT, source_file)

    for line, row in enumerate(table.rows, start=2):
        try:
            description = clean_text(row["concepto"])
            booking = to_date(row["fecha"])
            amount = to_decimal(row["importe"])
            balance = to_decimal(row["saldo"]) if str(row["saldo"] or "").strip() else None
        except ParseError as exc:
            result.warnings.append(f"Fila {line} ignorada: {exc}")
            continue
        # El saldo posterior forma parte del hash: separa pagos iguales el mismo dia
        # sin depender del orden del fichero ni de la ventana de fechas exportada.
        tx_hash = hashes.make(booking, normalize(description), amount, balance)
        result.transactions.append(
            TransactionDraft(
                bank=Bank.IMAGIN,
                booking_date=booking,
                description=description,
                amount=amount,
                balance_after=balance,
                category=categorizer.categorize(description, amount),
                tx_hash=tx_hash,
                source_file=source_file,
            )
        )
    result.warnings.extend(_check_balance_continuity(result.transactions))
    return result


def _check_balance_continuity(txs: list[TransactionDraft]) -> list[str]:
    """Verifica saldo_anterior + importe = saldo. Detecta huecos o filas perdidas.

    El extracto viene normalmente del mas reciente al mas antiguo, pero se acepta
    cualquiera de los dos ordenes eligiendo el que mas filas cuadra."""
    pairs = [(a, b) for a, b in zip(txs, txs[1:]) if a.balance_after is not None and b.balance_after is not None]
    if not pairs:
        return []

    def newest_first(a: TransactionDraft, b: TransactionDraft) -> bool:
        return a.balance_after - a.amount == b.balance_after  # type: ignore[operator]

    def oldest_first(a: TransactionDraft, b: TransactionDraft) -> bool:
        return b.balance_after - b.amount == a.balance_after  # type: ignore[operator]

    ok_desc = sum(newest_first(a, b) for a, b in pairs)
    ok_asc = sum(oldest_first(a, b) for a, b in pairs)
    check = newest_first if ok_desc >= ok_asc else oldest_first
    bad = [(a, b) for a, b in pairs if not check(a, b)]
    return [
        f"El saldo no cuadra entre '{a.description}' ({a.booking_date}) y "
        f"'{b.description}' ({b.booking_date}): posible movimiento faltante."
        for a, b in bad
    ]

