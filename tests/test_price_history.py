"""Historico de precios: lectura, importacion y efecto en las curvas (todo local, descargado por el usuario)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from core.entities import FileKind
from data.database import init_db, make_engine, make_session_factory
from etl.common import ParseError
from etl.dispatcher import parse_file
from etl.price_history_parser import isin_in, parse_price
from services.import_service import ImportService
from services.investment_service import InvestmentService

FIX = Path(__file__).parent / "fixtures"
AS_OF = date(2026, 10, 14)


@pytest.fixture()
def loaded():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    ImportService(factory).import_files(
        [FIX / "imagin_sample.csv", FIX / "myinvestor_operaciones.csv", FIX / "myinvestor_cartera.csv"], AS_OF)
    return factory


def _write(tmp_path: Path, name: str, text: str) -> Path:
    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    return f


def test_prices_in_spanish_and_english_formats():
    assert parse_price("1.234,56") == D("1234.56") and parse_price("1,234.56") == D("1234.56")
    assert parse_price("12,34") == D("12.34") and parse_price("12.345") == D("12.345")
    assert parse_price("1.234.567") == D(1234567) and parse_price(110) == D(110)
    assert isin_in("historico-ie00test0001.csv") == "IE00TEST0001"


def test_reads_a_yahoo_style_file_with_the_isin_in_the_name(tmp_path):
    f = _write(tmp_path, "IE00TEST0001.csv", "Date,Open,High,Low,Close,Adj Close,Volume\n2026-03-01,1,1,1,105.5,105.5,0\n2026-03-02,1,1,1,106.25,106.25,0\n")
    parsed = parse_file(f)
    assert parsed.kind is FileKind.PRICE_HISTORY
    assert [(p.isin, p.as_of, p.unit_price) for p in parsed.prices] == [
        ("IE00TEST0001", date(2026, 3, 1), D("105.5")), ("IE00TEST0001", date(2026, 3, 2), D("106.25"))]


def test_reads_a_spanish_file_and_needs_the_fund_when_there_is_no_isin(tmp_path):
    f = _write(tmp_path, "historico.csv", "Fecha;Valor liquidativo\n01/03/2026;105,50\n02/03/2026;106,25\n03/03/2026;-\n")
    with pytest.raises(ParseError, match="a qué fondo"):
        parse_file(f)
    parsed = parse_file(f, fund_isin="ie00test0001")
    assert len(parsed.prices) == 2 and parsed.prices[0].isin == "IE00TEST0001" and parsed.warnings    # la fila sin precio se avisa


def test_import_preview_and_idempotence(loaded, tmp_path):
    f = _write(tmp_path, "historico.csv", "Fecha;Cierre\n01/02/2026;104,00\n01/03/2026;105,50\n")
    svc = ImportService(loaded)
    preview = svc.preview([f], None, None, "IE00TEST0001")[0]
    assert preview.ok and preview.kind is FileKind.PRICE_HISTORY and (preview.rows, preview.new, preview.existing) == (2, 2, 0)
    assert svc.import_files([f], None, None, "IE00TEST0001").total_inserted == 2
    again = svc.preview([f], None, None, "IE00TEST0001")[0]
    assert (again.new, again.existing) == (0, 2) and not again.changes_data
    assert svc.import_files([f], None, None, "IE00TEST0001").total_inserted == 0               # no duplica
    bad = svc.preview([f])[0]
    assert not bad.ok and "Elige el fondo" in bad.explanation


def test_funds_listed_for_the_selector(loaded):
    assert {i for i, _ in ImportService(loaded).funds()} == {"IE00TEST0001", "IE00TEST0002"}


def test_price_history_gives_the_fund_chart_daily_points(loaded, tmp_path):
    before = InvestmentService(loaded).view()
    rows = "\n".join(f"{d:02d}/03/2026;{100 + d / 10:.2f}".replace(".", ",") for d in range(1, 20))
    f = _write(tmp_path, "historico.csv", "Fecha;Cierre\n" + rows + "\n")
    ImportService(loaded).import_files([f], None, None, "IE00TEST0001")
    after = InvestmentService(loaded).view()
    fund_before = next(x for x in before.funds if x.isin == "IE00TEST0001")
    fund_after = next(x for x in after.funds if x.isin == "IE00TEST0001")
    assert len(fund_after.points) > len(fund_before.points)                  # ahora hay puntos de dias sueltos
    assert after.summary.value == before.summary.value                      # el valor de hoy sigue siendo el del extracto
