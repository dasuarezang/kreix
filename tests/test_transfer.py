import json
import sqlite3
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import services.transfer_service as ts
from data.database import SCHEMA_VERSION, init_db, make_engine, make_session_factory
from services.accounts_service import AccountsService
from services.dashboard_service import DashboardService
from services.import_service import ImportService
from services.investment_service import InvestmentService
from services.settings_service import AppSettings, SettingsService
from services.transfer_service import TransferError, TransferService

FIX = Path(__file__).parent / "fixtures"
FILES = [FIX / "imagin_sample.csv", FIX / "myinvestor_operaciones.csv", FIX / "myinvestor_cartera.csv"]
AS_OF = date(2026, 10, 14)


def make_instance(tmp_path, name):
    engine = make_engine(f"sqlite:///{tmp_path / (name + '.db')}")
    init_db(engine)
    factory = make_session_factory(engine)
    return engine, factory, TransferService(engine, factory)


@pytest.fixture()
def source(tmp_path):
    engine, factory, svc = make_instance(tmp_path, "origen")
    AccountsService(factory).add("Personal")
    ImportService(factory).import_files(FILES, AS_OF)
    SettingsService(factory).save(AppSettings("light", False, True))
    return engine, factory, svc


def write_zip(path, entries):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


def good_manifest(**changes):
    return json.dumps({"format": ts.FORMAT, "format_version": 1, "schema_version": SCHEMA_VERSION,
                       "app_version": "0.1.0", "exported_at": "2026-10-14T12:00:00+00:00", **changes})


def db_bytes(tmp_path, sql=(), user_version=SCHEMA_VERSION, name="x.db"):
    """Una base de datos con la estructura de Kreix (mas lo que se quiera anadir) como bytes."""
    engine = make_engine(f"sqlite:///{tmp_path / name}")
    init_db(engine)
    engine.dispose()
    conn = sqlite3.connect(tmp_path / name)
    for statement in sql:
        conn.execute(statement)
    conn.execute(f"PRAGMA user_version = {user_version}")
    conn.commit()
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.close()
    return (tmp_path / name).read_bytes()


# ---------------------------------------------------------------- ida y vuelta
def test_export_and_restore_moves_everything_as_is(tmp_path, source):
    _, src_factory, src_svc = source
    file = tmp_path / "datos.kreix"
    summary = src_svc.export_to(file)
    assert file.is_file() and summary.transactions == 6 and summary.operations == 3 and summary.valuations == 2
    assert not list(tmp_path.glob("*.part"))                                   # sin restos

    dest_engine, dest_factory, dest_svc = make_instance(tmp_path, "destino")
    assert dest_svc.summary().is_empty
    assert dest_svc.restore(file) == summary

    a, b = DashboardService(src_factory).load(), DashboardService(dest_factory).load()
    assert (a.net_worth, a.cash, a.portfolio_value, a.simple_return) == (b.net_worth, b.cash, b.portfolio_value, b.simple_return)
    assert b.net_worth == Decimal("1747.51")
    assert [x.name for x in AccountsService(dest_factory).accounts()] == ["Personal"]      # la cuenta viaja con su nombre
    assert len(AccountsService(dest_factory).view().movements) == 6
    assert len(InvestmentService(dest_factory).view().operations) == 3
    assert SettingsService(dest_factory).load() == AppSettings("light", False, True)    # los ajustes viajan tambien

    # la proteccion anti-duplicados viaja: reimportar los extractos en el destino no duplica nada
    again = ImportService(dest_factory).import_files(FILES[:2], AS_OF)
    assert [f.inserted for f in again.files] == [0, 0]


def test_restore_replaces_existing_data(tmp_path, source):
    _, _, src_svc = source
    file = tmp_path / "datos.kreix"
    src_svc.export_to(file)
    _, dest_factory, dest_svc = make_instance(tmp_path, "destino")
    ImportService(dest_factory).import_files([FIX / "imagin_overlap.csv"])
    assert dest_svc.summary().transactions == 4
    dest_svc.restore(file)
    assert dest_svc.summary().transactions == 6 and dest_svc.summary().operations == 3   # solo lo del archivo


def test_export_adds_extension_and_inspect_does_not_modify(tmp_path, source):
    _, _, src_svc = source
    src_svc.export_to(tmp_path / "copia")
    file = tmp_path / ("copia" + ts.EXTENSION)
    assert file.is_file()
    _, dest_factory, dest_svc = make_instance(tmp_path, "destino")
    info = dest_svc.inspect(file)
    assert info.summary.transactions == 6 and info.app_version and info.exported_at
    assert dest_svc.summary().is_empty


def test_export_works_while_the_database_is_in_use_and_is_a_single_file(tmp_path, source):
    _, factory, src_svc = source
    src_svc.export_to(tmp_path / "a.kreix")
    with zipfile.ZipFile(tmp_path / "a.kreix") as zf:
        assert sorted(zf.namelist()) == ["kreix.db", "manifest.json"]
        assert json.loads(zf.read("manifest.json"))["counts"]["transactions"] == 6


# ---------------------------------------------------------------- archivos no validos o hostiles
def restore_fails(tmp_path, file, message):
    _, dest_factory, dest_svc = make_instance(tmp_path, "dest_" + file.stem)
    ImportService(dest_factory).import_files([FIX / "imagin_sample.csv"])      # datos que NO deben tocarse
    with pytest.raises(TransferError, match=message):
        dest_svc.restore(file)
    assert dest_svc.summary().transactions == 6                                # el destino quedo intacto


def test_rejects_files_that_are_not_exports(tmp_path):
    notzip = tmp_path / "a.kreix"
    notzip.write_text("hola", encoding="utf-8")
    restore_fails(tmp_path, notzip, "no es una exportación")
    restore_fails(tmp_path, write_zip(tmp_path / "b.kreix", {"otra.txt": "x"}), "no es una exportación")
    restore_fails(tmp_path, write_zip(tmp_path / "c.kreix", {"manifest.json": good_manifest()}), "no es una exportación")
    wrong = write_zip(tmp_path / "d.kreix", {"manifest.json": good_manifest(format="otra-cosa"), "kreix.db": db_bytes(tmp_path)})
    restore_fails(tmp_path, wrong, "no es una exportación")
    broken = write_zip(tmp_path / "e.kreix", {"manifest.json": "{no es json", "kreix.db": db_bytes(tmp_path)})
    restore_fails(tmp_path, broken, "ficha")


def test_rejects_extra_entries_such_as_path_traversal(tmp_path):
    evil = write_zip(tmp_path / "f.kreix", {"manifest.json": good_manifest(), "kreix.db": db_bytes(tmp_path),
                                            "../../evil.py": "print('x')"})
    restore_fails(tmp_path, evil, "no es una exportación")


def test_rejects_databases_with_triggers_or_views(tmp_path):
    trigger = db_bytes(tmp_path, ["CREATE TRIGGER t AFTER INSERT ON settings BEGIN DELETE FROM settings; END"], name="t.db")
    restore_fails(tmp_path, write_zip(tmp_path / "g.kreix", {"manifest.json": good_manifest(), "kreix.db": trigger}), "no permitidos")
    view = db_bytes(tmp_path, ["CREATE VIEW v AS SELECT 1"], name="v.db")
    restore_fails(tmp_path, write_zip(tmp_path / "h.kreix", {"manifest.json": good_manifest(), "kreix.db": view}), "no permitidos")


def test_rejects_garbage_or_foreign_databases(tmp_path):
    garbage = write_zip(tmp_path / "i.kreix", {"manifest.json": good_manifest(), "kreix.db": b"esto no es sqlite" * 200})
    restore_fails(tmp_path, garbage, "base de datos válida")
    foreign = tmp_path / "foreign.db"
    conn = sqlite3.connect(foreign)
    conn.execute("CREATE TABLE otra (x)")
    conn.commit()
    conn.close()
    restore_fails(tmp_path, write_zip(tmp_path / "j.kreix", {"manifest.json": good_manifest(), "kreix.db": foreign.read_bytes()}),
                  "estructura")


def test_rejects_files_from_newer_versions(tmp_path):
    newer_db = db_bytes(tmp_path, user_version=SCHEMA_VERSION + 1, name="n.db")
    restore_fails(tmp_path, write_zip(tmp_path / "k.kreix", {"manifest.json": good_manifest(), "kreix.db": newer_db}), "versión más reciente")
    newer_format = write_zip(tmp_path / "l.kreix", {"manifest.json": good_manifest(format_version=99), "kreix.db": db_bytes(tmp_path)})
    restore_fails(tmp_path, newer_format, "versión más reciente")


def test_rejects_oversized_databases(tmp_path, monkeypatch):
    big = write_zip(tmp_path / "m.kreix", {"manifest.json": good_manifest(), "kreix.db": db_bytes(tmp_path)})
    monkeypatch.setattr(ts, "MAX_DB_BYTES", 1000)
    restore_fails(tmp_path, big, "demasiado grande")


def test_restoring_an_older_schema_migrates_it(tmp_path, source):
    """Un export hecho con la base v1 (hashes sin cuenta) se migra al restaurarlo."""
    _, _, src_svc = source
    file = tmp_path / "datos.kreix"
    src_svc.export_to(file)
    with zipfile.ZipFile(file) as zf:
        db = tmp_path / "old.db"
        db.write_bytes(zf.read("kreix.db"))
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()
    old = write_zip(tmp_path / "old.kreix", {"manifest.json": good_manifest(schema_version=1), "kreix.db": db.read_bytes()})
    engine, _, dest_svc = make_instance(tmp_path, "destino")
    dest_svc.restore(old)
    with engine.connect() as c:
        from sqlalchemy import text
        assert c.execute(text("PRAGMA user_version")).scalar() == SCHEMA_VERSION
