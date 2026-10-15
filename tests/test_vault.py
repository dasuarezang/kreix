"""Almacen cifrado: la base de datos solo llega a disco cifrada y solo se abre con la contrasena maestra."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

import main
from data.secure_store import SecureStore, erase_legacy_db, read_legacy_db
from data.vault import CorruptVaultError, Vault, WrongPasswordError
from data.database import make_session_factory
from ui.lock_screen import LockDialog, LockMode

FAST = 1_000          # vueltas de PBKDF2 solo para que las pruebas vayan rapido


def test_vault_roundtrip_and_wrong_password():
    blob = Vault("clave-larga-1", iterations=FAST).seal(b"hola datos")
    assert b"hola datos" not in blob
    _vault, plain = Vault.unseal(blob, "clave-larga-1")
    assert plain == b"hola datos"
    with pytest.raises(WrongPasswordError):
        Vault.unseal(blob, "otra-clave-xx")


def test_vault_rejects_files_that_are_not_vaults_or_were_tampered():
    with pytest.raises(CorruptVaultError):
        Vault.unseal(b"SQLite format 3\x00" + b"0" * 200, "x" * 10)
    blob = bytearray(Vault("clave-larga-1", iterations=FAST).seal(b"datos"))
    blob[-5] ^= 0xFF
    with pytest.raises(WrongPasswordError):
        Vault.unseal(bytes(blob), "clave-larga-1")


def _store(tmp_path: Path) -> SecureStore:
    path = tmp_path / "kreix.krx"
    return SecureStore.create(path, "clave-larga-1", iterations=FAST)


def test_store_saves_encrypted_and_reopens_with_the_same_data(tmp_path):
    store = _store(tmp_path)
    with store.engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO settings(key, value) VALUES ('probe', 'UsuarioSecretoZ')")
    assert store.dirty and store.flush() and not store.dirty
    raw = store.path.read_bytes()
    assert raw.startswith(b"KRX1") and b"UsuarioSecretoZ" not in raw and b"SQLite format" not in raw
    reopened = SecureStore.open(store.path, "clave-larga-1")
    with reopened.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT value FROM settings WHERE key='probe'").scalar() == "UsuarioSecretoZ"
    with pytest.raises(WrongPasswordError):
        SecureStore.open(store.path, "clave-incorrecta")


def test_flush_does_nothing_without_changes(tmp_path):
    store = _store(tmp_path)
    assert store.flush() is False


def test_no_plaintext_files_are_left_next_to_the_store(tmp_path):
    store = _store(tmp_path)
    with store.engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO settings(key, value) VALUES ('probe', 'x')")
    store.flush()
    for f in tmp_path.iterdir():
        assert not f.read_bytes().startswith(b"SQLite format"), f.name


def test_undo_snapshots_are_encrypted_on_disk(tmp_path):
    from services.transfer_service import TransferService
    store = _store(tmp_path)
    transfer = TransferService(store.engine, make_session_factory(store.engine))
    with store.engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO settings(key, value) VALUES ('probe', 'ValorMuySecreto')")
    snap = transfer.snapshot()
    try:
        assert b"ValorMuySecreto" not in snap.read_bytes() and not snap.read_bytes().startswith(b"SQLite")
        with store.engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM settings WHERE key='probe'")
        transfer.restore_snapshot(snap)
        with store.engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT value FROM settings WHERE key='probe'").scalar() == "ValorMuySecreto"
    finally:
        snap.unlink(missing_ok=True)


def test_legacy_plain_database_is_migrated_and_erased(tmp_path, monkeypatch, qapp):
    legacy = tmp_path / "kreix.db"
    conn = sqlite3.connect(legacy)
    conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO settings VALUES ('probe', 'DatoAntiguo')")
    conn.commit(); conn.close()
    original = Vault.__init__
    monkeypatch.setattr(Vault, "__init__", lambda self, pw, salt=None, iterations=FAST: original(self, pw, salt, iterations))
    path = tmp_path / "kreix.krx"

    def fake_exec(self):
        assert self._mode is LockMode.MIGRATE
        assert self._attempt("clave-larga-1") is None
        return 1
    monkeypatch.setattr(LockDialog, "exec", fake_exec)
    store = main.unlock_store(path, legacy)
    assert store is not None and not legacy.exists()
    assert b"DatoAntiguo" not in path.read_bytes()
    with store.engine.connect() as c:
        assert c.exec_driver_sql("SELECT value FROM settings WHERE key='probe'").scalar() == "DatoAntiguo"


def test_lock_dialog_rejects_wrong_password_and_short_or_mismatched_new_ones(qapp):
    calls = []
    dlg = LockDialog(LockMode.UNLOCK, lambda p: calls.append(p) or "Contraseña incorrecta. Inténtalo de nuevo.")
    dlg.password.setText("mala")
    dlg._submit()
    assert dlg.result() == 0 and not dlg.error.isHidden() and "incorrecta" in dlg.error.text() and calls == ["mala"]
    new = LockDialog(LockMode.CREATE, lambda p: None)
    new.password.setText("corta"); new.confirm.setText("corta"); new._submit()
    assert not new.error.isHidden() and new.result() == 0
    new.password.setText("clave-larga-1"); new.confirm.setText("otra-distinta"); new._submit()
    assert new.result() == 0
    new.confirm.setText("clave-larga-1"); new._submit()
    assert new.result() == 1


def test_erase_legacy_db_removes_the_files(tmp_path):
    db = tmp_path / "kreix.db"
    db.write_bytes(b"x" * 100)
    (tmp_path / "kreix.db-wal").write_bytes(b"y" * 10)
    erase_legacy_db(db)
    assert not list(tmp_path.iterdir())


def test_forgot_password_erases_the_vault_and_lets_the_user_start_over(tmp_path, monkeypatch, qapp):
    from PySide6.QtWidgets import QMessageBox
    original = Vault.__init__
    monkeypatch.setattr(Vault, "__init__", lambda self, pw, salt=None, iterations=FAST: original(self, pw, salt, iterations))
    path = tmp_path / "kreix.krx"
    old = SecureStore.create(path, "clave-vieja-1")
    with old.engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO settings(key, value) VALUES ('probe', 'DatosViejos')")
    old.save(); old.save()                                    # crea tambien el .bak
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dialogs = []

    def fake_exec(self):
        dialogs.append(self._mode)
        if self._mode is LockMode.UNLOCK:
            self._forgot()                                   # pulsa "He olvidado la contrasena" y confirma
        else:
            assert not path.exists() and not path.with_name(path.name + ".bak").exists()
            assert self._attempt("clave-nueva-1") is None
        return 0
    monkeypatch.setattr(LockDialog, "exec", fake_exec)
    store = main.unlock_store(path, tmp_path / "kreix.db")
    assert dialogs == [LockMode.UNLOCK, LockMode.CREATE] and store is not None
    with store.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM settings WHERE key='probe'").scalar() == 0
    SecureStore.open(path, "clave-nueva-1")
    with pytest.raises(WrongPasswordError):
        SecureStore.open(path, "clave-vieja-1")


def test_forgot_password_does_nothing_if_the_user_cancels(monkeypatch, qapp):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    dlg = LockDialog(LockMode.UNLOCK, lambda p: None)
    dlg._forgot()
    assert not dlg.reset_requested
    assert LockDialog(LockMode.CREATE, lambda p: None).forgot.isHidden()


def test_legacy_database_in_wal_mode_as_the_real_app_leaves_it_is_migrated(tmp_path, monkeypatch, qapp):
    from data.database import init_db, make_engine
    legacy = tmp_path / "kreix.db"
    engine = make_engine(f"sqlite:///{legacy}")               # igual que la version anterior: modo WAL, con -wal y -shm
    init_db(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO settings(key, value) VALUES ('probe', 'DatoWal')")
    engine.dispose()                                          # la app anterior ya esta cerrada
    original = Vault.__init__
    monkeypatch.setattr(Vault, "__init__", lambda self, pw, salt=None, iterations=FAST: original(self, pw, salt, iterations))
    monkeypatch.setattr(LockDialog, "exec", lambda self: self._attempt("123klk123") is None and 1)
    store = main.unlock_store(tmp_path / "kreix.krx", legacy)
    assert store is not None and not legacy.exists()
    with store.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT value FROM settings WHERE key='probe'").scalar() == "DatoWal"
