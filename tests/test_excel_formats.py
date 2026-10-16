"""Excel de varios tipos (ING y otros bancos): .xls antiguo de verdad, .xls que es HTML y .xlsx con la extension cambiada."""
from datetime import date, datetime
from decimal import Decimal as D

import pytest

from data.database import init_db, make_engine, make_session_factory
from etl.common import ParseError, load_rows
from etl.dispatcher import UnknownFormatError, parse_file
from services.import_service import ImportService

ING = [
    ["Movimientos de la Cuenta Nómina", None, None, None, None],
    ["Número de cuenta: ES00 0000 0000 0000", None, None, None, None],
    [None, None, None, None, None],
    ["F. VALOR", "CATEGORÍA", "DESCRIPCIÓN", "IMPORTE (€)", "SALDO (€)"],
    [datetime(2026, 4, 3), "Alimentación", "COMPRA MERCADONA", -23.4, 1976.6],
    [datetime(2026, 4, 2), "Nómina", "NOMINA EMPRESA", 1500.0, 2000.0],
    [datetime(2026, 4, 1), "Hogar", "RECIBO LUZ", -45.1, 500.0],
]


def write_xls(path):
    import xlwt

    book = xlwt.Workbook()
    sheet = book.add_sheet("Movimientos")
    style = xlwt.easyxf(num_format_str="DD/MM/YYYY")
    for r, row in enumerate(ING):
        for c, value in enumerate(row):
            if value is not None:
                sheet.write(r, c, value, style if isinstance(value, datetime) else xlwt.Style.default_style)
    book.save(str(path))


def write_html(path):
    def text(v):
        if v is None:
            return ""
        if isinstance(v, datetime):
            return v.strftime("%d/%m/%Y")
        return str(v).replace(".", ",") if isinstance(v, float) else str(v)

    body = "".join("<tr>" + "".join(f"<td>{text(v)}</td>" for v in row) + "</tr>" for row in ING)
    path.write_text(f"<html><body><table>{body}</table></body></html>", encoding="cp1252")


def write_xlsx(path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for row in ING:
        ws.append(row)
    wb.save(path)


@pytest.fixture()
def service():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return ImportService(make_session_factory(engine))


@pytest.mark.parametrize("name, writer", [("ing.xls", write_xls), ("ing-html.xls", write_html), ("ing-renamed.xls", write_xlsx), ("ing.xlsx", write_xlsx)])
def test_every_kind_of_excel_is_read_and_its_columns_can_be_assigned(tmp_path, service, name, writer):
    path = tmp_path / name
    writer(path)
    rows = load_rows(path)
    assert any("F. VALOR" in str(c) for row in rows for c in row) and len(rows) >= 7
    with pytest.raises(UnknownFormatError):                          # no es Imagin ni MyInvestor: se pregunta por las columnas
        parse_file(path)
    sample = service.sample(path)
    assert sample.header_index == 3
    mapping = service.suggest_mapping(sample, "ING")
    parsed = service.try_mapping(path, sample, mapping)
    assert [(t.description, t.amount, t.balance_after) for t in parsed.transactions] == [
        ("COMPRA MERCADONA", D("-23.4"), D("1976.6")), ("NOMINA EMPRESA", D("1500"), D("2000")), ("RECIBO LUZ", D("-45.1"), D("500"))]
    assert [t.booking_date for t in parsed.transactions] == [date(2026, 4, 3), date(2026, 4, 2), date(2026, 4, 1)]


def test_a_corrupt_excel_gives_a_clear_error(tmp_path):
    path = tmp_path / "roto.xlsx"
    path.write_bytes(b"PK\x03\x04 esto no es un excel")
    with pytest.raises(ParseError):
        load_rows(path)
