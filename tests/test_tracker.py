"""Detector de cambios reales y cache de resultados: leer no es cambiar; escribir (o restaurar) si."""
from __future__ import annotations

from decimal import Decimal as D
from pathlib import Path

import pytest

from data.secure_store import SecureStore
from data.tracker import tracker_for
from data.vault import Vault
from services.accounts_service import AccountsService
from services.dashboard_service import DashboardService
from services.import_service import ImportService
from services.transfer_service import TransferService
from data.database import make_session_factory

FIX = Path(__file__).parent / "fixtures"
FAST = 1_000


@pytest.fixture()
def store(tmp_path, monkeypatch):
    original = Vault.__init__
    monkeypatch.setattr(Vault, "__init__", lambda self, pw, salt=None, iterations=FAST: original(self, pw, salt, iterations))
    return SecureStore.create(tmp_path / "k.krx", "clave-larga-1")


def test_reading_does_not_mark_the_store_as_changed(store):
    factory = make_session_factory(store.engine)
    store.dirty = False
    DashboardService(factory).load()
    AccountsService(factory).view()
    AccountsService(factory).accounts()
    assert store.dirty is False and store.flush() is False               # varias lecturas: nada que guardar


def test_writing_marks_the_store_as_changed_and_invalidates_the_cache(store):
    factory = make_session_factory(store.engine)
    tracker = tracker_for(store.engine)
    svc = AccountsService(factory)
    store.dirty = False
    before = tracker.version
    ImportService(factory).import_files([FIX / "imagin_sample.csv"])
    assert store.dirty and tracker.version > before
    first = svc.view()
    assert svc.view() is first                                           # sin cambios: el mismo resultado, sin recalcular
    svc.add("Otra")
    assert svc.view() is not first and len(svc.view().accounts) == 2     # un cambio lo invalida


def test_cached_view_is_keyed_by_its_arguments(store):
    factory = make_session_factory(store.engine)
    ImportService(factory).import_files([FIX / "imagin_sample.csv"])
    svc = AccountsService(factory)
    assert svc.view() is svc.view()
    assert svc.view([1]) is svc.view([1]) and svc.view([1]) is not svc.view()


def test_restoring_a_copy_counts_as_a_change(store, tmp_path):
    factory = make_session_factory(store.engine)
    transfer = TransferService(store.engine, factory)
    ImportService(factory).import_files([FIX / "imagin_sample.csv"])
    snap = transfer.snapshot()
    try:
        svc = AccountsService(factory)
        full = svc.view()
        with store.engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM transactions")
        assert len(svc.view().movements) == 0
        store.dirty = False
        transfer.restore_snapshot(snap)                                   # entra por `backup`, no por SQL
        assert store.dirty and len(svc.view().movements) == len(full.movements)
    finally:
        snap.unlink(missing_ok=True)
