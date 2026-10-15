from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from core.categorizer import Categorizer
from core.entities import FileKind
from core.enums import AccountKind, Bank, OperationType, TxCategory
from data.database import init_db, make_engine, make_session_factory, session_scope
from data.repositories import (
    get_or_create_account,
    insert_operations,
    insert_transactions,
    upsert_valuations,
)
from etl.common import HashFactory, ParseError, to_date, to_decimal
from etl.dispatcher import parse_file
from etl.reconcile import reconcile_portfolio

FIX = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------- conversiones
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("-2,99EUR", "-2.99"),
        ("1.234,56 €", "1234.56"),
        ("4000,00", "4000.00"),
        ("−5,00EUR", "-5.00"),
        (12.5, "12.5"),
    ],
)
def test_to_decimal(raw, expected):
    assert to_decimal(raw) == Decimal(expected)


def test_to_decimal_invalid():
    with pytest.raises(ParseError):
        to_decimal("abc")


def test_to_date_formats():
    assert to_date("13/10/2026") == date(2026, 10, 13)
    assert to_date("2026-10-13 00:00:00") == date(2026, 10, 13)


# ---------------------------------------------------------------- categorizacion
@pytest.mark.parametrize(
    "text, amount, expected",
    [
        ("MERCADONA CL DE T", "-3.30", TxCategory.GROCERIES),
        ("PROXIM SUPERMERCA", "-1.95", TxCategory.GROCERIES),
        ("ANTHROPIC* CLAUDE", "-21.78", TxCategory.SUBSCRIPTIONS),
        ("Glovo 11OCT B4GFD", "-35.29", TxCategory.DINING),
        ("URBAN CLIMBING BC", "-12.00", TxCategory.LEISURE),
        ("BIZUM RECIBIDO", "40.00", TxCategory.P2P),
        ("TRASPASO", "50.00", TxCategory.TRANSFER),
        ("MEDIAMARKT", "-50.00", TxCategory.UNCATEGORIZED),  # "DIA" no debe casar
        ("COSA RARA", "10.00", TxCategory.INCOME),
    ],
)
def test_categorizer(text, amount, expected):
    assert Categorizer().categorize(text, Decimal(amount)) is expected


# ---------------------------------------------------------------- hashes
def test_identical_rows_get_distinct_but_stable_hashes():
    a, b = HashFactory("x"), HashFactory("x")
    first = [a.make("d", "BIZUM", 1, 2), a.make("d", "BIZUM", 1, 2)]
    second = [b.make("d", "BIZUM", 1, 2), b.make("d", "BIZUM", 1, 2)]
    assert first[0] != first[1]
    assert first == second


# ---------------------------------------------------------------- Imagin
def test_imagin_parse_and_autodetect():
    res = parse_file(FIX / "imagin_sample.csv")
    assert res.kind is FileKind.IMAGIN_STATEMENT
    assert len(res.transactions) == 6
    assert res.warnings == []  # los saldos cuadran
    first = res.transactions[0]
    assert (first.booking_date, first.amount, first.balance_after) == (
        date(2026, 9, 10), Decimal("-12.99"), Decimal("117.51"),
    )
    assert first.category is TxCategory.SUBSCRIPTIONS
    assert len({t.tx_hash for t in res.transactions}) == 6  # los dos Bizum iguales no colisionan


def test_imagin_balance_gap_is_reported(tmp_path):
    f = tmp_path / "gap.csv"
    f.write_text(
        "Concepto;Fecha;Importe;Saldo\nA;10/09/2026;-10,00EUR;90,00EUR\nB;08/09/2026;-5,00EUR;50,00EUR\n",
        encoding="utf-8",
    )
    assert any("no cuadra" in w for w in parse_file(f).warnings)


def test_unknown_format_is_rejected(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a;b\n1;2\n", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_file(f)


def test_pdf_is_rejected_pointing_to_csv_or_excel(tmp_path):
    f = tmp_path / "movimientos.pdf"
    f.write_bytes(b"%PDF-1.7 fake")
    with pytest.raises(ParseError, match="CSV o Excel"):
        parse_file(f)


def test_excel_with_preamble(tmp_path):
    f = tmp_path / "imagin.xlsx"
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for row in (["Extracto de cuenta", None, None, None], ["Concepto", "Fecha", "Importe", "Saldo"],
                ["MERCADONA", "13/10/2026", -3.3, 36.7]):
        ws.append(row)
    wb.save(f)
    res = parse_file(f)
    assert res.transactions[0].amount == Decimal("-3.3")
    assert res.transactions[0].category is TxCategory.GROCERIES


# ---------------------------------------------------------------- MyInvestor
def test_myinvestor_operations():
    res = parse_file(FIX / "myinvestor_operaciones.csv")
    assert res.kind is FileKind.MYINVESTOR_OPERATIONS
    assert [o.op_type for o in res.operations] == [OperationType.BUY, OperationType.BUY, OperationType.SELL]
    assert res.operations[0].amount == Decimal("-1000.00")   # compra: sale efectivo
    assert res.operations[2].amount == Decimal("220.00")     # venta: entra efectivo
    assert len(res.warnings) == 2                            # pendiente + tipo desconocido


def test_myinvestor_portfolio_and_reconcile():
    ops = parse_file(FIX / "myinvestor_operaciones.csv")
    pf = parse_file(FIX / "myinvestor_cartera.csv", portfolio_as_of=date(2026, 10, 14))
    assert pf.kind is FileKind.MYINVESTOR_PORTFOLIO
    assert pf.positions[0].units == Decimal("13.0000")
    assert pf.positions[0].as_of == date(2026, 10, 14)
    warnings = reconcile_portfolio(pf.positions, ops.operations)
    assert len(warnings) == 1 and "IE00TEST0002" in warnings[0]  # Uno cuadra (10+5-2=13); Dos no


# ---------------------------------------------------------------- persistencia idempotente
@pytest.fixture()
def factory():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return make_session_factory(engine)


def _import_imagin(factory, name):
    res = parse_file(FIX / name)
    with session_scope(factory) as s:
        acc = get_or_create_account(s, Bank.IMAGIN, AccountKind.CHECKING, "Imagin")
        return insert_transactions(s, acc.id, res.transactions)


def test_reimport_does_not_duplicate(factory):
    assert _import_imagin(factory, "imagin_sample.csv").inserted == 6
    again = _import_imagin(factory, "imagin_sample.csv")
    assert (again.inserted, again.skipped) == (0, 6)


def test_overlapping_statements_only_add_new_rows(factory):
    _import_imagin(factory, "imagin_sample.csv")
    stats = _import_imagin(factory, "imagin_overlap.csv")
    assert (stats.inserted, stats.skipped) == (1, 3)  # solo SPOTIFY es nuevo


def test_operations_and_valuations_idempotent(factory):
    ops = parse_file(FIX / "myinvestor_operaciones.csv")
    pf = parse_file(FIX / "myinvestor_cartera.csv", portfolio_as_of=date(2026, 10, 14))
    for _ in range(2):
        with session_scope(factory) as s:
            acc = get_or_create_account(s, Bank.MYINVESTOR, AccountKind.INVESTMENT, "MyInvestor")
            stats = insert_operations(s, acc.id, ops.operations)
            upsert_valuations(s, pf.positions)
    assert (stats.inserted, stats.skipped) == (0, 3)


def test_reimport_portfolio_counts_updates_not_new(factory):
    pf = parse_file(FIX / "myinvestor_cartera.csv", portfolio_as_of=date(2026, 10, 14))
    n = len(pf.positions)
    with session_scope(factory) as s:
        first = upsert_valuations(s, pf.positions)
    with session_scope(factory) as s:
        same = upsert_valuations(s, pf.positions)
    changed = [replace(p, units=p.units + 1) for p in pf.positions]
    with session_scope(factory) as s:
        third = upsert_valuations(s, changed)
    assert (first.inserted, first.updated) == (n, 0)
    assert (same.inserted, same.updated, same.skipped) == (0, 0, n)
    assert (third.inserted, third.updated) == (0, n)
