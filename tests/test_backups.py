"""Copias de seguridad automaticas: cuando se hacen, cuantas se guardan, que se restaure lo copiado y que sigan el cambio de contrasena."""
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from data.secure_store import SecureStore
from data.vault import Vault, WrongPasswordError
from services.backup_service import (
    DEFAULT_KEEP, INTERVAL, BackupConfig, BackupService, backup_name, config_from, parse_name,
)
from services.settings_service import BACKUP_KEEP, DEFAULT_BACKUP_KEEP, AppSettings
from tests.test_autolock import FakeStore


class Rig:
    """Un BackupService con reloj propio, una carpeta de pruebas y una exportacion de mentira (escribe el instante)."""

    def __init__(self, tmp_path: Path) -> None:
        self.now = datetime(2026, 10, 16, 9, 0)
        self.config = BackupConfig(True, tmp_path / "copias", 3)
        self.empty = False
        self.fail = None
        self.service = BackupService(self._export, lambda: self.config, tmp_path / "por-defecto",
                                     is_empty=lambda: self.empty, clock=lambda: self.now)

    def _export(self, target: Path) -> None:
        if self.fail:
            raise self.fail
        target.write_bytes(self.now.isoformat().encode())

    def advance(self, **delta) -> None:
        self.now += timedelta(**delta)


@pytest.fixture()
def rig(tmp_path):
    return Rig(tmp_path)


# ---------------------------------------------------------------- nombres
def test_backup_names_carry_the_date_and_parse_back():
    moment = datetime(2026, 3, 7, 14, 5, 9)
    assert backup_name(moment) == "Kreix-copia-2026-03-07_14-05.kreix"
    assert backup_name(moment, with_seconds=True) == "Kreix-copia-2026-03-07_14-05-09.kreix"
    assert parse_name(backup_name(moment)) == datetime(2026, 3, 7, 14, 5)
    assert parse_name(backup_name(moment, True)) == moment
    for other in ("notas.kreix", "Kreix-copia-2026-13-40_99-99.kreix", "Kreix-copia-2026-03-07_14-05.kreix.part", "export.kreix"):
        assert parse_name(other) is None


# ---------------------------------------------------------------- cuando copiar
def test_first_backup_is_made_when_the_folder_has_none(rig):
    assert rig.service.due() and rig.service.run_if_due() is not None
    assert len(rig.service.files()) == 1
    assert not rig.service.due()                               # sin cambios nuevos no se repite


def test_a_change_makes_a_new_backup_only_after_the_interval(rig):
    rig.service.run_if_due()
    rig.service.note_saved()
    rig.advance(minutes=59)
    assert not rig.service.due()
    rig.advance(minutes=1)
    assert rig.service.due()
    rig.service.run_if_due()
    assert len(rig.service.files()) == 2 and rig.service.pending is False


def test_nothing_is_copied_when_there_is_no_data_or_it_is_turned_off(rig):
    rig.empty = True
    assert not rig.service.due() and rig.service.run_if_due() is None
    rig.empty = False
    rig.config = replace(rig.config, enabled=False)
    assert not rig.service.due() and rig.service.on_quit() is None and rig.service.files() == []


def test_closing_copies_pending_changes_without_waiting_for_the_hour(rig):
    rig.service.run_if_due()
    assert rig.service.on_quit() is None                       # nada que recoger
    rig.service.note_saved()
    rig.advance(minutes=5)
    assert rig.service.on_quit() is not None and len(rig.service.files()) == 2


def test_two_backups_in_the_same_minute_do_not_overwrite_each_other(rig):
    first = rig.service.create()
    second = rig.service.create()
    assert first != second and len(rig.service.files()) == 2


def test_choosing_another_folder_makes_a_backup_there_right_away(rig, tmp_path):
    rig.service.run_if_due()
    rig.config = replace(rig.config, folder=tmp_path / "otra")
    assert not rig.service.due()
    rig.service.folder_changed()
    assert rig.service.due() and rig.service.run_if_due().parent == tmp_path / "otra"


# ---------------------------------------------------------------- conservar las ultimas
def test_only_the_latest_backups_are_kept(rig):
    for _ in range(5):
        rig.service.create()
        rig.advance(hours=2)
    files = rig.service.files()
    assert len(files) == 3 and files[0].moment > files[-1].moment
    assert files[0].moment == datetime(2026, 10, 16, 17, 0)      # la mas nueva primero


def test_lowering_the_number_to_keep_prunes_on_demand_and_ignores_foreign_files(rig):
    for _ in range(3):
        rig.service.create()
        rig.advance(hours=2)
    folder = rig.service.folder()
    (folder / "mis-notas.txt").write_text("hola")
    (folder / "export-a-mano.kreix").write_bytes(b"x")
    rig.config = replace(rig.config, keep=1)
    assert rig.service.prune() == 2 and len(rig.service.files()) == 1
    assert (folder / "mis-notas.txt").exists() and (folder / "export-a-mano.kreix").exists()


# ---------------------------------------------------------------- fallos
def test_a_failed_backup_reports_why_and_does_not_raise(rig):
    rig.fail = OSError("disco lleno")
    assert rig.service.create() is None and rig.service.last_error == "disco lleno"
    rig.fail = None
    assert rig.service.create() is not None and rig.service.last_error == ""


def test_an_unusable_chosen_folder_falls_back_to_the_default_one(rig, tmp_path):
    blocker = tmp_path / "es-un-archivo"
    blocker.write_text("no soy una carpeta")
    rig.config = replace(rig.config, folder=blocker / "dentro")
    path = rig.service.create()
    assert path is not None and path.parent == tmp_path / "por-defecto" and rig.service.last_note


def test_listing_a_missing_folder_is_empty_not_an_error(rig, tmp_path):
    rig.config = replace(rig.config, folder=tmp_path / "no-existe")
    assert rig.service.files() == []


# ---------------------------------------------------------------- ajustes
def test_backup_settings_default_persist_and_ignore_invalid_values(window):
    service = window._svc.settings
    loaded = service.load()
    assert (loaded.backup_enabled, loaded.backup_keep, loaded.backup_folder) == (True, DEFAULT_BACKUP_KEEP, "") and DEFAULT_KEEP == DEFAULT_BACKUP_KEEP
    service.save(replace(loaded, backup_enabled=False, backup_keep=5, backup_folder="  D:\\Copias  "))
    again = service.load()
    assert (again.backup_enabled, again.backup_keep, again.backup_folder) == (False, 5, "D:\\Copias")
    service.save(replace(loaded, backup_keep=4))
    assert service.load().backup_keep == DEFAULT_BACKUP_KEEP and 4 not in BACKUP_KEEP
    config = config_from(again)
    assert config == BackupConfig(False, Path("D:\\Copias"), 5) and config_from(loaded).folder is None


# ---------------------------------------------------------------- copias reales
def test_a_real_backup_is_encrypted_and_restores_with_the_master_password(window, tmp_path):
    from core.enums import AccountKind, Bank
    from data.database import session_scope
    from data.models import Account

    transfer = window._svc.transfer
    with session_scope(window._svc.importer._factory) as s:
        s.add(Account(bank=Bank.IMAGIN, kind=AccountKind.CHECKING, name="Cuenta de prueba"))
    assert not transfer.summary().is_empty
    vault = Vault("clave maestra", iterations=1000)
    service = BackupService(lambda target: transfer.export_to(target, vault.seal), lambda: BackupConfig(True, tmp_path / "c", 3),
                            tmp_path / "d", is_empty=lambda: transfer.summary().is_empty)
    path = service.run_if_due()
    assert path is not None and path.read_bytes().startswith(b"KRX1")
    with session_scope(window._svc.importer._factory) as s:
        s.query(Account).delete()
    assert transfer.summary().accounts == 0
    transfer.restore(path, "clave maestra")
    assert transfer.summary().accounts == 1


def test_changing_the_password_re_encrypts_the_backups(rig, tmp_path):
    old, new = Vault("clave vieja", iterations=1000), Vault("clave nueva!", iterations=1000)
    rig.service._export = lambda target: target.write_bytes(old.seal(b"datos"))
    rig.service.create()
    rig.advance(hours=2)
    rig.service.create()
    stranger = rig.service.folder() / "Kreix-copia-2020-01-01_00-00.kreix"
    stranger.write_bytes(Vault("otra distinta", iterations=1000).seal(b"ajeno"))
    assert rig.service.rekey("clave vieja", new.seal) == 2
    for backup in rig.service.files():
        if backup.path == stranger:
            continue
        assert Vault.unseal(backup.path.read_bytes(), "clave nueva!")[1] == b"datos"
        with pytest.raises(WrongPasswordError):
            Vault.unseal(backup.path.read_bytes(), "clave vieja")
    assert Vault.unseal(stranger.read_bytes(), "otra distinta")[1] == b"ajeno"      # la que no se abria, intacta


# ---------------------------------------------------------------- almacen cifrado
def test_the_store_tells_when_it_saves(tmp_path):
    store = SecureStore.create(tmp_path / "datos.krx", "clave-de-prueba", iterations=1000)
    saved = []
    store.on_saved(lambda: saved.append(1))
    store.save()
    store.dirty = True
    assert store.flush() is True and len(saved) == 2
    assert store.flush() is False and len(saved) == 2           # sin cambios no hay aviso


# ---------------------------------------------------------------- pantalla de Ajustes y ventana
def test_settings_card_lists_backups_and_is_only_shown_with_an_encrypted_store(window, rig):
    view = window.settings_view
    assert view.backup_group.isHidden() and view.backup_heading.isHidden()
    rig.service.create()
    rig.advance(hours=2)
    rig.service.create()
    window.attach_store(FakeStore(), rig.service)
    assert not view.backup_group.isHidden() and view.backup_path.text() == str(rig.service.folder())
    assert len(view.backup_list.buttons) == 2
    window.attach_store(None)
    assert view.backup_group.isHidden() and window.backups is None


def test_backup_now_button_and_restore_signal_reach_the_window(window, rig, monkeypatch):
    window.attach_store(FakeStore(), rig.service)
    window.settings_view.backup_now.click()
    assert len(rig.service.files()) == 1 and len(window.settings_view.backup_list.buttons) == 1
    asked = []
    monkeypatch.setattr(type(window), "restore_from", lambda self, path: asked.append(path) or True)
    window.settings_view.backup_list.buttons[0].click()
    assert asked == [str(rig.service.files()[0].path)]
    rig.fail = OSError("sin espacio")
    window.settings_view.backup_now.click()
    assert rig.service.last_error == "sin espacio" and "sin espacio" in window.settings_view.backup_status.text()


def test_changing_backup_settings_updates_the_service(window, rig):
    window.attach_store(FakeStore(), rig.service)
    rig.service._config = lambda: config_from(window._settings)
    view = window.settings_view
    view.backup_keep.setCurrentIndex(BACKUP_KEEP.index(3))
    view._on_backup_keep(BACKUP_KEEP.index(3))
    assert window._settings.backup_keep == 3
    view._update(backup_folder=str(rig.service._default_folder.parent / "nueva"))
    assert (rig.service._default_folder.parent / "nueva").is_dir()          # recibio una copia enseguida
