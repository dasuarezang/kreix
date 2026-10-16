"""De punta a punta, con el almacen cifrado de verdad: guardado automatico, copia de seguridad, restauracion, cambio de
contrasena y bloqueo, tal como los conecta main.wire_store."""
from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog

import data.paths
import main
from data.secure_store import SecureStore
from data.vault import Vault, WrongPasswordError
from tests.conftest import dispose_windows
from ui import autolock

FIX = Path(__file__).parent / "fixtures"
PASSWORD = "clave de prueba larga"


@pytest.fixture()
def rig(qapp, tmp_path, monkeypatch):
    from ui import fonts
    from ui.widgets import charts

    charts.ANIMATIONS = False
    fonts.setup_application(qapp)
    monkeypatch.setattr(data.paths, "default_backup_folder", lambda: tmp_path / "copias")
    store = SecureStore.create(tmp_path / "datos.krx", PASSWORD, iterations=1000)
    window = main.build_window(engine=store.engine, db_label=str(store.path))
    backups, lock = main.wire_store(qapp, window, store, save_on_quit=False)
    yield store, window, backups, lock, tmp_path
    lock.stop()
    qapp.kreix_autosave.stop()
    qapp.kreix_autosave.deleteLater()
    lock.deleteLater()
    for survivor in {window, qapp.kreix_window}:
        try:
            dispose_windows(survivor)
        except RuntimeError:                                     # la ventana ya se cerro (se rehizo en otro idioma)
            pass
    del qapp.kreix_autolock, qapp.kreix_persist, qapp.kreix_autosave


def test_importing_saves_encrypted_and_makes_the_first_backup(rig, qapp):
    store, window, backups, _lock, tmp_path = rig
    assert backups.files() == []                                 # sin datos no hay nada que copiar
    window._svc.importer.import_files([FIX / "imagin_sample.csv"])
    assert store.dirty
    qapp.kreix_persist()                                         # el reloj de guardado
    assert not store.dirty and Vault.unseal((tmp_path / "datos.krx").read_bytes(), PASSWORD)
    [backup] = backups.files()
    assert backup.path.parent == tmp_path / "copias" and backup.path.read_bytes().startswith(b"KRX1")
    qapp.kreix_persist()
    assert len(backups.files()) == 1                             # una por hora, no una por guardado
    shown = window.settings_view
    assert len(shown.backup_list.buttons) == 1 and shown.backup_path.text() == str(tmp_path / "copias")


def test_a_backup_restores_the_data_after_a_loss(rig, qapp):
    store, window, backups, _lock, tmp_path = rig
    window._svc.importer.import_files([FIX / "imagin_sample.csv"])
    qapp.kreix_persist()
    before = window._svc.transfer.summary()
    [backup] = backups.files()
    window._svc.transfer.snapshot()                              # (el "Deshacer" no interviene)
    window.reset_data()
    assert window._svc.transfer.summary().transactions == 0
    window._svc.transfer.restore(backup.path, PASSWORD)
    assert window._svc.transfer.summary() == before


def test_changing_the_password_keeps_backups_openable_only_with_the_new_one(rig, qapp, monkeypatch):
    store, window, backups, _lock, tmp_path = rig
    window._svc.importer.import_files([FIX / "imagin_sample.csv"])
    qapp.kreix_persist()
    [backup] = backups.files()

    class Stub:
        def __init__(self, apply, parent=None):
            self.apply = apply

        def exec(self):
            assert self.apply(PASSWORD, "otra clave distinta") is None
            return QDialog.DialogCode.Accepted

    import ui.main_window as mw

    monkeypatch.setattr(mw, "ChangePasswordDialog", Stub)
    window.change_password()
    assert Vault.unseal(backup.path.read_bytes(), "otra clave distinta")[1]
    with pytest.raises(WrongPasswordError):
        Vault.unseal(backup.path.read_bytes(), PASSWORD)
    with pytest.raises(WrongPasswordError):
        Vault.unseal((tmp_path / "datos.krx").read_bytes(), PASSWORD)
    window._svc.transfer.restore(backup.path, "otra clave distinta")


def test_locking_asks_for_the_current_password_and_wrong_ones_are_refused(rig, qapp, monkeypatch):
    store, window, _backups, lock, _tmp = rig
    seen = []

    class Stub:
        def __init__(self, mode, attempt, parent=None, finish=None, note="", allow_reset=True, throttle=None):
            seen.append(attempt)

        def show(self): ...
        def raise_(self): ...
        def activateWindow(self): ...
        def deleteLater(self): ...
        def exec(self): return QDialog.DialogCode.Accepted

    monkeypatch.setattr(autolock, "LockDialog", Stub)
    window.lock_now()
    assert lock.lock_count == 1
    attempt = seen[0]
    assert attempt(PASSWORD) is None and attempt("mal") and attempt("")
    store._vault = Vault("nueva", iterations=1000)               # tras cambiarla, la vieja ya no desbloquea
    assert attempt("nueva") is None and attempt(PASSWORD)


def test_the_autosave_and_lock_survive_rebuilding_the_window_for_another_language(rig, qapp):
    store, window, backups, lock, _tmp = rig
    new = window.rebuild()
    assert qapp.kreix_window is new and new.backups is backups and new.secure_store is store
    assert lock._main_window() is new
    new.settings_view.set_security(True)
    assert not new.settings_view.backup_group.isHidden()
