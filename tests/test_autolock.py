"""Bloqueo automatico: retardo tras fallos, comprobacion de contrasena, ajustes y comportamiento al estar inactivo o minimizar."""
from dataclasses import replace

import pytest
from PySide6.QtWidgets import QDialog, QMainWindow, QWidget

from core import i18n
from core.throttle import FIRST_DELAY, MAX_DELAY, AttemptThrottle, delay_after
from data.secure_store import SecureStore
from data.vault import Vault
from services.settings_service import DEFAULT_LOCK_MINUTES, LOCK_MINUTES, AppSettings
from tests.conftest import dispose_windows
from ui import autolock
from ui.autolock import AutoLock
from ui.lock_screen import LockDialog, LockMode


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


# ---------------------------------------------------------------- retardo tras fallos
def test_the_wait_grows_after_the_free_attempts_and_is_capped():
    assert [delay_after(n) for n in range(0, 8)] == [0, 0, 0, FIRST_DELAY, FIRST_DELAY * 2, FIRST_DELAY * 4, MAX_DELAY, MAX_DELAY]


def test_throttle_counts_waits_and_resets():
    clock = Clock()
    throttle = AttemptThrottle(clock)
    assert throttle.failed() == 0 and throttle.failed() == 0 and throttle.wait_left() == 0
    assert throttle.failed() == FIRST_DELAY and throttle.wait_left() == FIRST_DELAY
    clock.now += 2
    assert throttle.wait_left() == FIRST_DELAY - 2
    clock.now += 10
    assert throttle.wait_left() == 0
    throttle.succeeded()
    assert throttle.failures == 0 and throttle.failed() == 0


# ---------------------------------------------------------------- contrasena
def test_vault_and_store_verify_the_password_without_touching_the_disk(tmp_path):
    vault = Vault("una contraseña larga", iterations=1000)
    assert vault.check("una contraseña larga") and not vault.check("otra") and not vault.check("")
    store = SecureStore.create(tmp_path / "datos.krx", "clave-de-prueba", iterations=1000)
    assert store.verify_password("clave-de-prueba") and not store.verify_password("clave-de-pruebA")
    (tmp_path / "datos.krx").unlink()                         # no lee el archivo
    assert store.verify_password("clave-de-prueba")
    store._vault = Vault("nueva-contraseña", iterations=1000)  # tras cambiarla, vale la nueva
    assert store.verify_password("nueva-contraseña") and not store.verify_password("clave-de-prueba")


# ---------------------------------------------------------------- ajustes
def test_lock_settings_default_persist_and_ignore_invalid_values(window):
    service = window._svc.settings
    loaded = service.load()
    assert loaded.auto_lock_minutes == DEFAULT_LOCK_MINUTES and loaded.lock_on_minimize is True
    service.save(replace(loaded, auto_lock_minutes=15, lock_on_minimize=False))
    again = service.load()
    assert again.auto_lock_minutes == 15 and again.lock_on_minimize is False
    service.save(replace(loaded, auto_lock_minutes=0))
    assert service.load().auto_lock_minutes == 0
    service.save(replace(loaded, auto_lock_minutes=7))          # un valor que no esta en la lista
    assert service.load().auto_lock_minutes == DEFAULT_LOCK_MINUTES
    from data.models import Setting
    from data.database import session_scope

    with session_scope(window._svc.settings._factory) as s:
        s.merge(Setting(key="auto_lock_minutes", value="muchos"))
    assert service.load().auto_lock_minutes == DEFAULT_LOCK_MINUTES


def test_settings_view_offers_the_lock_controls_only_with_an_encrypted_store(window):
    view = window.settings_view
    assert view.lock_card.isHidden() and view.lock_minimize_card.isHidden() and view.security_card.isHidden()
    view.set_security(True)
    assert not view.lock_card.isHidden() and not view.lock_minimize_card.isHidden()
    assert [view.lock_after.itemData(i) for i in range(view.lock_after.count())] == list(LOCK_MINUTES)
    assert view.lock_after.currentData() == DEFAULT_LOCK_MINUTES


def test_changing_the_lock_controls_saves_them(window):
    view = window.settings_view
    view.lock_after.setCurrentIndex(LOCK_MINUTES.index(10))
    view._on_lock_after(LOCK_MINUTES.index(10))
    view.lock_minimize.switch.setChecked(False)
    saved = window._svc.settings.load()
    assert saved.auto_lock_minutes == 10 and saved.lock_on_minimize is False
    view.set_settings(replace(saved, auto_lock_minutes=2, lock_on_minimize=True))
    assert view.lock_after.currentData() == 2 and view.lock_minimize.switch.isChecked()


def test_lock_labels_are_plain_and_translated(qapp):
    from ui.views.settings_view import SettingsView

    assert SettingsView.lock_minutes_label(0) == "Nunca" and SettingsView.lock_minutes_label(1) == "1 minuto"
    assert SettingsView.lock_minutes_label(5) == "5 minutos"
    i18n.set_language("en")
    assert SettingsView.lock_minutes_label(0) == "Never" and SettingsView.lock_minutes_label(5) == "5 minutes"


# ---------------------------------------------------------------- pantalla de bloqueo con espera
def test_lock_dialog_makes_you_wait_after_repeated_failures(qapp):
    clock = Clock()
    throttle = AttemptThrottle(clock)
    dialog = LockDialog(LockMode.UNLOCK, lambda p: None if p == "bien" else "mal", throttle=throttle)
    for _ in range(2):
        dialog.password.setText("mal")
        dialog._submit()
    assert dialog.ok.isEnabled() and dialog.error.text() == "mal"
    dialog.password.setText("mal")
    dialog._submit()                                            # tercer fallo: espera
    assert not dialog.ok.isEnabled() and not dialog.password.isEnabled()
    assert "5 segundos" in dialog.status.text()
    dialog.password.setText("bien")
    dialog._submit()                                            # durante la espera no se acepta nada
    assert dialog.result() != QDialog.DialogCode.Accepted
    clock.now += 6
    dialog._tick()
    assert dialog.ok.isEnabled() and dialog.password.isEnabled() and dialog.status.isHidden()
    dialog._submit()
    assert dialog.result() == QDialog.DialogCode.Accepted and throttle.failures == 0
    dialog.deleteLater()


def test_a_pending_wait_survives_a_new_lock_screen(qapp):
    clock = Clock()
    throttle = AttemptThrottle(clock)
    for _ in range(3):
        throttle.failed()
    dialog = LockDialog(LockMode.UNLOCK, lambda p: None, throttle=throttle)
    assert not dialog.ok.isEnabled() and not dialog.status.isHidden()
    dialog.deleteLater()


def test_creating_a_password_never_makes_you_wait(qapp):
    dialog = LockDialog(LockMode.CREATE, lambda p: "mal")
    for _ in range(5):
        dialog.password.setText("una-clave-larga")
        dialog.confirm.setText("una-clave-larga")
        dialog._submit()
    assert dialog.ok.isEnabled()
    dialog.deleteLater()


def test_lock_dialog_can_hide_the_forgot_button_and_show_a_note(qapp):
    dialog = LockDialog(LockMode.UNLOCK, lambda p: None, note="Aviso previo.", allow_reset=False)
    assert dialog.forgot.isHidden() and dialog._intro_text().startswith("Aviso previo.")
    plain = LockDialog(LockMode.UNLOCK, lambda p: None)
    assert not plain.forgot.isHidden()
    dialog.deleteLater()
    plain.deleteLater()


# ---------------------------------------------------------------- AutoLock
class FakeStore:
    def __init__(self) -> None:
        self.flushed = 0

    def flush(self) -> bool:
        self.flushed += 1
        return True

    def verify_password(self, password: str) -> bool:
        return password == "clave"

    def seal_export(self, plain: bytes) -> bytes:
        return plain


class StubDialog:
    """Sustituye a LockDialog: registra como se creo y devuelve lo que diga `outcome`."""

    outcome = QDialog.DialogCode.Accepted
    created: list = []

    def __init__(self, mode, attempt, parent=None, finish=None, note="", allow_reset=True, throttle=None):
        self.mode, self.attempt, self.note, self.allow_reset, self.throttle = mode, attempt, note, allow_reset, throttle
        self.parent_widget = QWidget()
        StubDialog.created.append(self)

    def show(self): ...
    def raise_(self): ...
    def activateWindow(self): ...
    def exec(self): return StubDialog.outcome
    def deleteLater(self): ...


@pytest.fixture()
def rig(qapp, monkeypatch):
    StubDialog.created = []
    StubDialog.outcome = QDialog.DialogCode.Accepted
    monkeypatch.setattr(autolock, "LockDialog", StubDialog)
    quits = []
    monkeypatch.setattr(autolock.QApplication.instance(), "quit", lambda: quits.append(True))
    state = {"idle": 0.0, "settings": AppSettings(auto_lock_minutes=5, lock_on_minimize=True)}
    window = QMainWindow()
    window.show()
    store = FakeStore()
    lock = AutoLock(store, lambda: state["settings"], lambda: window, idle_seconds=lambda: state["idle"])
    yield lock, store, window, state, quits
    lock.stop()
    lock.deleteLater()
    dispose_windows(window)


def test_it_locks_after_the_chosen_minutes_without_activity(rig):
    lock, store, window, state, _ = rig
    state["idle"] = 5 * 60 - 1
    lock.check()
    assert lock.lock_count == 0 and window.isVisible()
    state["idle"] = 5 * 60
    lock.check()
    assert lock.lock_count == 1 and lock.last_reason == "idle" and store.flushed == 1
    assert "sin usarlo" in StubDialog.created[0].note and StubDialog.created[0].allow_reset is False
    assert StubDialog.created[0].attempt("clave") is None and StubDialog.created[0].attempt("x")
    assert window.isVisible()                                   # al desbloquear, la ventana vuelve


def test_nothing_happens_when_the_automatic_lock_is_off(rig):
    lock, _, _, state, _ = rig
    state["settings"] = replace(state["settings"], auto_lock_minutes=0)
    state["idle"] = 99999
    lock.check()
    assert lock.lock_count == 0


def test_it_locks_when_the_window_is_minimized_and_only_once(rig):
    lock, _, window, state, _ = rig
    window.showMinimized()
    lock.check()
    assert lock.lock_count == 1 and lock.last_reason == "minimize"
    assert not window.isMinimized()                              # se restaura al desbloquear
    lock.check()
    assert lock.lock_count == 1


def test_minimize_lock_can_be_turned_off(rig):
    lock, _, window, state, _ = rig
    state["settings"] = replace(state["settings"], lock_on_minimize=False)
    window.showMinimized()
    lock.check()
    assert lock.lock_count == 0


def test_windows_are_hidden_while_locked_and_back_after_unlocking(rig, monkeypatch):
    lock, _, window, state, _ = rig
    other = QWidget()
    other.show()
    seen = {}

    def during(self):
        seen["main"], seen["other"] = window.isVisible(), other.isVisible()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(StubDialog, "exec", during)
    lock.lock("manual")
    assert seen == {"main": False, "other": False}
    assert window.isVisible() and other.isVisible()
    other.close()


def test_open_dialogs_are_cancelled_when_locking(rig):
    lock, _, window, _, _ = rig
    dialog = QDialog(window)
    dialog.show()
    lock.lock("manual")
    assert not dialog.isVisible() and dialog.result() == QDialog.DialogCode.Rejected


def test_quit_from_the_lock_screen_closes_the_app(rig):
    lock, _, window, _, quits = rig
    StubDialog.outcome = QDialog.DialogCode.Rejected
    assert lock.lock("idle") is False and quits == [True] and not window.isVisible()


def test_the_wait_after_failures_is_shared_between_locks(rig):
    lock, *_ = rig
    lock.lock("manual")
    lock.lock("manual")
    assert StubDialog.created[0].throttle is StubDialog.created[1].throttle


def test_it_cannot_lock_twice_at_once(rig, monkeypatch):
    lock, *_ = rig
    inner = []
    monkeypatch.setattr(StubDialog, "exec", lambda self: inner.append(lock.lock("idle")) or QDialog.DialogCode.Accepted)
    lock.lock("manual")
    assert inner == [False] and lock.lock_count == 1


def test_without_system_idle_the_cursor_is_used(rig, monkeypatch):
    from PySide6.QtCore import QPoint

    lock, *_ = rig
    where = {"at": QPoint(1, 1)}

    class FakeCursor:
        @staticmethod
        def pos():
            return where["at"]

    monkeypatch.setattr(autolock, "QCursor", FakeCursor)
    lock._idle_seconds = lambda: None
    clock = Clock()
    lock._clock = clock
    lock._last_cursor, lock._last_activity = QPoint(1, 1), clock()
    clock.now += 400
    assert lock.idle_for() == 400
    where["at"] = QPoint(5, 7)
    assert lock.idle_for() == 0


def test_main_window_lock_now_uses_the_app_lock(window, qapp):
    calls = []
    qapp.kreix_autolock = type("L", (), {"lock": lambda self, reason: calls.append(reason)})()
    window.lock_now()
    assert calls == []                                          # sin almacen cifrado no se bloquea
    window.attach_store(FakeStore())
    window.lock_now()
    assert calls == ["manual"]
    names = [c.title for c in window.palette_commands()]
    assert "Bloquear Kreix ahora" in names
    del qapp.kreix_autolock


def test_idle_helper_returns_a_number_or_none():
    from ui.idle import system_idle_seconds

    value = system_idle_seconds()
    assert value is None or value >= 0
