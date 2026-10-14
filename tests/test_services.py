from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from core.metrics import FlowOptions
from data.database import init_db, make_engine, make_session_factory
from services.dashboard_service import DashboardService
from services.data_service import DataService
from services.import_service import ImportService
from services.settings_service import AppSettings, SettingsService

FIX = Path(__file__).parent / "fixtures"
ALL = [FIX / "imagin_sample.csv", FIX / "myinvestor_operaciones.csv", FIX / "myinvestor_cartera.csv"]


@pytest.fixture()
def factory():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return make_session_factory(engine)


def test_empty_database_gives_empty_dashboard(factory):
    assert DashboardService(factory).load().has_data is False


def test_import_all_then_dashboard(factory):
    report = ImportService(factory).import_files(ALL, portfolio_as_of=date(2026, 10, 14))
    assert [f.ok for f in report.files] == [True, True, True]
    assert [f.inserted for f in report.files] == [6, 3, 2]
    assert len(report.reconciliation_warnings) == 1  # Fondo Test Dos no tiene operaciones

    data = DashboardService(factory).load()
    assert data.cash == Decimal("117.51")
    assert data.portfolio_value == Decimal("1630.00")            # 13 x 110 + 4 x 50
    assert data.net_worth == Decimal("1747.51")
    assert data.simple_return == (Decimal(1630) - Decimal(1480)) / Decimal(1480)
    assert data.report_month == date(2026, 9, 1)
    assert [s.label for s in data.allocation] == ["Liquidez", "Inversión"]
    assert data.wealth and data.wealth[-1].date == date(2026, 10, 14)
    assert data.warnings == report.reconciliation_warnings


def test_reimport_is_idempotent(factory):
    svc = ImportService(factory)
    svc.import_files(ALL, portfolio_as_of=date(2026, 10, 14))
    again = svc.import_files(ALL, portfolio_as_of=date(2026, 10, 14))
    assert [(f.inserted, f.skipped) for f in again.files[:2]] == [(0, 6), (0, 3)]
    assert DashboardService(factory).load().net_worth == Decimal("1747.51")


def test_bad_file_is_reported_without_breaking_the_rest(factory, tmp_path):
    bad = tmp_path / "raro.csv"
    bad.write_text("a;b\n1;2\n", encoding="utf-8")
    missing = tmp_path / "no_existe.csv"
    report = ImportService(factory).import_files([bad, FIX / "imagin_sample.csv", missing])
    assert [f.ok for f in report.files] == [False, True, False]
    assert report.files[0].kind_label == "Formato no reconocido"
    assert DashboardService(factory).load().cash == Decimal("117.51")


def test_flow_options_change_the_savings_rate(factory):
    ImportService(factory).import_files([FIX / "imagin_sample.csv"])
    svc = DashboardService(factory)
    with_all = svc.load(FlowOptions())
    without = svc.load(FlowOptions(include_p2p=False, transfers_in_as_income=False))
    assert with_all.month_income == Decimal(110)     # 2 Bizum de 5 + traspaso de 100
    assert without.month_income == Decimal(0)
    assert without.month_savings_rate is None


def test_settings_roundtrip_and_defaults(factory):
    svc = SettingsService(factory)
    assert svc.load() == AppSettings()
    svc.save(AppSettings(theme="light", include_p2p=False, transfers_in_as_income=True))
    assert svc.load() == AppSettings("light", False, True)
    svc.save(AppSettings("dark", True, False))
    assert svc.load() == AppSettings("dark", True, False)


def test_reset_all_clears_data_but_keeps_settings(factory):
    ImportService(factory).import_files(ALL, portfolio_as_of=date(2026, 10, 14))
    SettingsService(factory).save(AppSettings("light", False, True))
    DataService(factory).reset_all()
    assert DashboardService(factory).load().has_data is False
    assert SettingsService(factory).load() == AppSettings("light", False, True)
    # y se puede volver a importar desde cero
    assert ImportService(factory).import_files([FIX / "imagin_sample.csv"]).files[0].inserted == 6


def test_files_without_extension_are_accepted(factory, tmp_path):
    """Algunos exports (p. ej. 'extractImagin') no llevan extension."""
    plain = tmp_path / "extractImagin"
    plain.write_text((FIX / "imagin_sample.csv").read_text(encoding="utf-8"), encoding="utf-8")
    report = ImportService(factory).import_files([plain])
    assert report.files[0].ok and report.files[0].inserted == 6
