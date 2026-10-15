"""Vista previa de importacion: que se ha leido y que es nuevo, sin guardar nada. Errores con solucion."""
from datetime import date
from pathlib import Path

import pytest

from data.database import init_db, make_engine, make_session_factory, session_scope
from data.repositories import list_accounts
from services.import_errors import describe, friendly_error
from services.import_service import ImportService

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture()
def service():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    return ImportService(factory), factory


def test_preview_counts_rows_dates_and_saves_nothing(service):
    svc, factory = service
    [p] = svc.preview([FIX / "imagin_sample.csv"])
    assert (p.ok, p.rows, p.new, p.existing, p.updated) == (True, 6, 6, 0, 0)
    assert (p.first, p.last) == (date(2026, 9, 6), date(2026, 9, 10))
    assert p.kind_label == "Extracto de Imagin" and p.changes_data
    with session_scope(factory) as s:
        assert list_accounts(s) == []                                  # ni siquiera crea la cuenta


def test_preview_after_import_says_everything_already_exists(service):
    svc, _ = service
    svc.import_files([FIX / "imagin_sample.csv"])
    [again] = svc.preview([FIX / "imagin_sample.csv"])
    assert (again.new, again.existing) == (0, 6) and not again.changes_data
    [overlap] = svc.preview([FIX / "imagin_overlap.csv"])
    assert overlap.new + overlap.existing == overlap.rows and overlap.existing > 0


def test_preview_of_operations_and_portfolio_distinguishes_new_updated_and_same(service):
    svc, _ = service
    as_of = date(2026, 10, 14)
    ops, folio = FIX / "myinvestor_operaciones.csv", FIX / "myinvestor_cartera.csv"
    first = svc.preview([ops, folio], portfolio_as_of=as_of)
    assert [(p.rows, p.new) for p in first] == [(3, 3), (2, 2)]
    svc.import_files([ops, folio], portfolio_as_of=as_of)
    again = svc.preview([ops, folio], portfolio_as_of=as_of)
    assert [(p.new, p.existing, p.updated) for p in again] == [(0, 3, 0), (0, 2, 0)]
    other_day = svc.preview([folio], portfolio_as_of=date(2026, 10, 15))[0]
    assert (other_day.new, other_day.existing) == (2, 0)               # otra fecha: valoraciones nuevas


def test_preview_reports_unreadable_files_with_a_solution(service, tmp_path):
    svc, _ = service
    bad = tmp_path / "raro.csv"
    bad.write_text("a;b\n1;2\n", encoding="utf-8")
    pdf = tmp_path / "extracto.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    missing = tmp_path / "no-existe.csv"
    results = svc.preview([bad, pdf, missing])
    assert [r.ok for r in results] == [False, False, False]
    assert "no reconozco" in results[0].explanation.lower() and "csv" in results[0].explanation.lower()
    assert "pdf" in results[1].explanation.lower()
    assert results[2].explanation                                       # tambien un archivo inexistente explica algo


def test_friendly_errors_keep_the_technical_detail_and_fall_back_to_a_generic_hint():
    assert friendly_error("Fecha no valida: '32/13/2026'")[0].startswith("Hay una fecha")
    assert "32/13/2026" in describe("Fecha no valida: '32/13/2026'")
    assert friendly_error("algo inesperado")[0].startswith("No he podido leer")
    assert describe("")                                                  # nunca devuelve vacio


def test_import_report_exposes_the_same_explanation(service, tmp_path):
    svc, _ = service
    bad = tmp_path / "x.csv"
    bad.write_text("a;b\n", encoding="utf-8")
    report = svc.import_files([bad])
    assert not report.files[0].ok and "no reconozco" in report.files[0].explanation.lower()
