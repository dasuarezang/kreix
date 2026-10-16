"""Modo privacidad, tamano del texto, estado y comprobacion de las copias, y bloqueo al suspender o bloquear Windows."""
import ctypes
from ctypes import wintypes
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow

from core import i18n
from data.secure_store import SecureStore
from data.vault import CorruptVaultError, Vault, WrongPasswordError
from services.backup_service import BackupConfig, BackupService, NoBackupError
from services.settings_service import TEXT_SCALES, AppSettings
from services.transfer_service import TransferError
from tests.conftest import dispose_windows
from tests.test_autolock import FakeStore, StubDialog
from ui import autolock, fonts
from ui import format as formatting
from ui import theme
from ui.autolock import AutoLock
from ui.session_watch import (
    PBT_APMSUSPEND, WM_POWERBROADCAST, WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK, SessionWatcher, should_lock,
)
from ui import blur
from ui.widgets import charts

FIX = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------- modo privacidad
def test_private_mode_masks_every_euro_amount_in_each_language():
    formatting.set_private(True)
    shown = formatting.fmt_eur(1234.5)
    assert blur.has_mark(shown) and blur.clean_text(shown) == "8.888,88 €" == blur.clean_text(formatting.fmt_eur(-3))   # relleno: nunca la cifra real
    assert "1.234" not in shown and "1234" not in shown
    assert formatting.fmt_eur(None) == "—"                                          # lo que no hay no se tapa
    assert formatting.fmt_pct(0.1) != "••" and "%" in formatting.fmt_pct(0.1)       # los porcentajes siguen a la vista
    i18n.set_language("en")
    assert blur.clean_text(formatting.fmt_eur(1234.5)) == "€8,888.88"
    formatting.set_private(False)
    assert formatting.fmt_eur(1234.5) == "€1,234.50"


def test_axis_labels_are_hidden_too_in_private_mode():
    assert charts.axis_label(1500) == "1,5k"
    formatting.set_private(True)
    assert blur.has_mark(charts.axis_label(1500)) and "1" not in blur.clean_text(charts.axis_label(1500))


def test_toggling_privacy_rewrites_the_visible_figures_and_is_remembered(window):
    from decimal import Decimal

    import_view = window.import_view
    import_view.import_paths([str(FIX / "imagin_sample.csv")])
    window.navigate(window.ACCOUNTS)
    assert not blur.has_mark(window.accounts_view.card_balance._value.text())
    window.privacy_button.click()
    assert formatting.is_private() and window.privacy_button.isChecked()
    assert blur.has_mark(window.accounts_view.card_balance._value.text())
    assert window._svc.settings.load().privacy_mode is True
    assert "Mostrar" in window.privacy_button.toolTip()
    window.privacy_button.click()
    assert not formatting.is_private() and not blur.has_mark(window.accounts_view.card_balance._value.text())
    assert window._svc.settings.load().privacy_mode is False and "Ocultar" in window.privacy_button.toolTip()
    del Decimal


def test_privacy_has_a_shortcut_a_palette_command_and_survives_a_rebuild(window, monkeypatch):
    monkeypatch.setattr(window, "deleteLater", lambda: None)               # la ventana de la prueba la cierra el fixture
    assert any(c.title == "Ocultar o mostrar las cantidades" for c in window.palette_commands())
    window.set_privacy(True, announce=True)
    assert "ocultas" in window.toast.text
    new = window.rebuild()
    try:
        assert formatting.is_private() and new.privacy_button.isChecked()
    finally:
        dispose_windows(new)


def test_the_privacy_setting_roundtrips_and_defaults_to_visible(window):
    service = window._svc.settings
    assert service.load().privacy_mode is False
    service.save(replace(service.load(), privacy_mode=True))
    assert service.load().privacy_mode is True


# ---------------------------------------------------------------- tamano del texto
def test_scaled_sizes_and_fonts_follow_the_chosen_text_size():
    assert fonts.scaled(14) == 14 and fonts.qfont(fonts.BODY, 14).pixelSize() == 14
    fonts.set_scale(125)
    assert fonts.scaled(14) == 18 and fonts.qfont(fonts.BODY, 14).pixelSize() == 18
    fonts.set_scale(999)                                                              # un valor raro vuelve al normal
    assert fonts.scaled(14) == 14


def test_the_stylesheet_scales_text_and_big_boxes_but_not_thin_lines():
    normal = theme.stylesheet(theme.DARK)
    fonts.set_scale(125)
    big = theme.stylesheet(theme.DARK)
    assert "font-size: 15px" in normal and "font-size: 19px" in big
    assert "min-height: 52px" in big and "min-height: 1px" in big                    # la caja de 42 px crece; el filo de 1 px no
    assert big.count("{") == normal.count("{")


def test_text_scale_setting_roundtrips_and_ignores_garbage(window):
    from data.database import session_scope
    from data.models import Setting

    service = window._svc.settings
    assert service.load().text_scale == 100 and TEXT_SCALES == (100, 110, 125)
    service.save(replace(service.load(), text_scale=125))
    assert service.load().text_scale == 125
    service.save(replace(service.load(), text_scale=77))
    assert service.load().text_scale == 100
    with session_scope(service._factory) as s:
        s.merge(Setting(key="text_scale", value="enorme"))
    assert service.load().text_scale == 100


def test_picking_a_text_size_saves_it_and_rebuilds_the_window(window, monkeypatch, qapp):
    rebuilt = []
    monkeypatch.setattr(type(window), "rebuild", lambda self: rebuilt.append(fonts.SCALE))
    view = window.settings_view
    assert [view.text_size.itemData(i) for i in range(view.text_size.count())] == [100, 110, 125]
    view.text_size.setCurrentIndex(2)
    view._on_text_size(2)
    qapp.processEvents()
    from PySide6.QtTest import QTest

    QTest.qWait(30)
    assert window._settings.text_scale == 125 and window._svc.settings.load().text_scale == 125
    assert rebuilt == [1.25]
    view._on_text_size(2)                                                               # el mismo: no hace nada
    QTest.qWait(30)
    assert rebuilt == [1.25]


def test_a_rebuilt_window_uses_the_saved_text_size(window, monkeypatch):
    monkeypatch.setattr(window, "deleteLater", lambda: None)
    window._svc.settings.save(replace(window._settings, text_scale=125))
    new = window.rebuild()
    try:
        assert fonts.SCALE == 1.25 and "font-size: 19px" in new.styleSheet()
        assert new.settings_view.text_size.currentData() == 125
    finally:
        dispose_windows(new)


def test_tables_and_panels_make_room_for_bigger_text(window):
    from ui.widgets.tables import ROW_HEIGHT, DataTable

    fonts.set_scale(125)
    from ui.widgets.tables import Column

    table = DataTable([Column("A", lambda r: r, stretch=True)], min_height=0)
    assert table.verticalHeader().defaultSectionSize() == round(ROW_HEIGHT * 1.25)


def test_the_scale_hint_file_is_read_for_the_password_screen(tmp_path):
    import data.paths as paths

    assert paths.read_scale_hint() == 100
    paths.write_scale_hint(125)
    assert paths.read_scale_hint() == 125
    paths.write_scale_hint(333)
    assert paths.read_scale_hint() == 125
    paths.scale_hint_path().write_text("basura", encoding="utf-8")
    assert paths.read_scale_hint() == 100


# ---------------------------------------------------------------- tema mas rapido
def test_the_window_carries_the_stylesheet_and_the_app_only_a_fixed_base(window):
    base = theme.base_stylesheet()
    app_sheet = QApplication.instance().styleSheet()
    window.apply_theme("light")
    assert theme.LIGHT.bg in window.styleSheet() and QApplication.instance().styleSheet() == app_sheet
    assert "QToolTip" in base and theme.LIGHT.bg not in base and theme.DARK.bg not in base


def test_a_loose_dialog_styles_itself(qapp):
    from ui.lock_screen import LockDialog, LockMode

    dialog = LockDialog(LockMode.UNLOCK, lambda p: None)
    assert theme.current().bg in dialog.styleSheet()
    dialog.deleteLater()


# ---------------------------------------------------------------- estado y comprobacion de las copias
@pytest.mark.parametrize("seconds, text", [
    (10, "ahora mismo"), (300, "hace 5 min"), (3 * 3600, "hace 3 h"), (30 * 3600, "ayer"), (5 * 86400, "hace 5 días"),
])
def test_relative_times_are_in_plain_words(seconds, text):
    now = datetime(2026, 10, 16, 12, 0)
    assert formatting.fmt_ago(now - timedelta(seconds=seconds), now) == text


def test_relative_times_follow_the_language():
    now = datetime(2026, 10, 16, 12, 0)
    i18n.set_language("en")
    assert formatting.fmt_ago(now - timedelta(hours=3), now) == "3 h ago"
    i18n.set_language("ca")
    assert formatting.fmt_ago(now - timedelta(minutes=5), now) == "fa 5 min"


def make_service(tmp_path, clock, enabled=True):
    vault = Vault("clave maestra de prueba", iterations=1000)
    state = {"enabled": enabled}
    service = BackupService(lambda p: p.write_bytes(vault.seal(b"datos")), lambda: BackupConfig(state["enabled"], tmp_path / "c", 3),
                            tmp_path / "d", clock=clock)
    return service, state


def test_the_sidebar_says_when_the_last_backup_was_and_warns_when_there_is_none_or_it_is_old(window, tmp_path):
    now = datetime(2026, 10, 16, 12, 0)
    window.clock = lambda: now
    service, state = make_service(tmp_path, lambda: now - timedelta(hours=2))
    assert window.backup_foot.isHidden()
    window.attach_store(FakeStore(), service)
    assert window.backup_foot.text() == "Aún sin copias de seguridad" and window.backup_foot.property("tone") == "warn"
    service.create()
    window.update_backup_foot()
    assert window.backup_foot.text() == "Última copia: hace 2 h" and window.backup_foot.property("tone") == "ok"
    window.clock = lambda: now + timedelta(days=4)
    window.tick_clock()
    assert "hace 4 días" in window.backup_foot.text() and window.backup_foot.property("tone") == "warn"
    state["enabled"] = False
    window._settings = replace(window._settings, backup_enabled=False)
    window.update_backup_foot()
    assert window.backup_foot.text() == "Copias de seguridad desactivadas" and not window.backup_foot.isHidden()
    window.attach_store(None)
    window.update_backup_foot()
    assert window.backup_foot.isHidden()


def test_a_vault_opens_its_own_exports_without_asking_for_the_password(tmp_path):
    vault = Vault("clave maestra de prueba", iterations=1000)
    blob = vault.seal(b"contenido")
    assert vault.open_blob(blob) == b"contenido"
    with pytest.raises(WrongPasswordError):
        Vault("otra clave distinta", iterations=1000).open_blob(blob)                 # otra sal: no es de este almacen
    altered = bytearray(blob)
    altered[-3] ^= 0xFF
    with pytest.raises(WrongPasswordError):
        vault.open_blob(bytes(altered))
    with pytest.raises(CorruptVaultError):
        vault.open_blob(b"no soy nada")


def test_checking_the_latest_backup_really_opens_it(window, tmp_path, monkeypatch):
    from main import wire_store  # noqa: F401  (el cableado real se prueba en test_security_flow)

    store = SecureStore.create(tmp_path / "datos.krx", "clave maestra de prueba", iterations=1000)
    transfer = window._svc.transfer
    window._svc.importer.import_files([FIX / "imagin_sample.csv"])
    service = BackupService(lambda p: transfer.export_to(p, store.seal_export), lambda: BackupConfig(True, tmp_path / "c", 3), tmp_path / "d",
                            inspect=lambda p: transfer.inspect(p, unseal=store.unseal_export))
    with pytest.raises(NoBackupError):
        service.check_latest()                                                            # sin copias, no hay nada que abrir
    service.create()
    backup, info = service.check_latest()
    assert info.summary.transactions == 6 and backup.path.exists()
    window.attach_store(FakeStore(), service)
    window.check_backup()
    assert "se abre bien" in window.toast.text and "6 movimientos" in window.toast.text
    other = SecureStore.create(tmp_path / "otro.krx", "una clave completamente distinta", iterations=1000)
    service._inspect = lambda p: transfer.inspect(p, unseal=other.unseal_export)       # con otra clave la copia no abre
    with pytest.raises(TransferError):
        service.check_latest()
    shown = []
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a[1]))
    window.check_backup()
    assert shown == ["La última copia no se abre"]


def test_the_check_button_is_in_settings_and_is_wired(window, tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(type(window), "check_backup", lambda self: asked.append(1))
    window.settings_view.backup_check.click()
    assert asked == [1]


# ---------------------------------------------------------------- bloqueo al suspender o bloquear Windows
def test_only_suspend_and_session_lock_messages_trigger_a_lock():
    assert should_lock(WM_POWERBROADCAST, PBT_APMSUSPEND) and should_lock(WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK)
    assert not should_lock(WM_POWERBROADCAST, 0x0007)                                  # reanudar no bloquea
    assert not should_lock(WM_WTSSESSION_CHANGE, 0x8)                                  # desbloquear tampoco
    assert not should_lock(0x0100, PBT_APMSUSPEND)


def test_the_native_filter_reads_windows_messages_and_calls_back(qapp):
    calls = []
    watcher = SessionWatcher(lambda: calls.append(1))
    msg = wintypes.MSG()
    msg.message, msg.wParam = WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK
    assert watcher.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg)) == (False, 0)
    assert calls == [1]
    msg.message, msg.wParam = 0x000F, 0                                                # WM_PAINT: nada
    watcher.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))
    watcher.nativeEventFilter(b"otra_cosa", 0)
    assert calls == [1]
    watcher.start()
    watcher.stop()


@pytest.fixture()
def rig(qapp, monkeypatch):
    StubDialog.created, StubDialog.outcome = [], QDialog.DialogCode.Accepted
    monkeypatch.setattr(autolock, "LockDialog", StubDialog)
    window = QMainWindow()
    window.show()
    state = {"settings": AppSettings(auto_lock_minutes=0, lock_on_minimize=False, lock_on_session=True)}
    lock = AutoLock(FakeStore(), lambda: state["settings"], lambda: window, idle_seconds=lambda: 0.0)
    yield lock, state
    lock.stop()
    lock.deleteLater()
    dispose_windows(window)


def test_a_session_event_locks_kreix_a_moment_later_with_its_own_note(rig, qapp):
    from PySide6.QtTest import QTest

    lock, state = rig
    lock.session_event()
    assert lock.lock_count == 0                                                        # no dentro del filtro de Windows
    QTest.qWait(50)
    assert lock.lock_count == 1 and lock.last_reason == "session" and "Windows" in StubDialog.created[0].note


def test_the_session_lock_can_be_turned_off_and_never_stacks(rig, qapp):
    from PySide6.QtTest import QTest

    lock, state = rig
    state["settings"] = replace(state["settings"], lock_on_session=False)
    lock.session_event()
    QTest.qWait(50)
    assert lock.lock_count == 0
    state["settings"] = replace(state["settings"], lock_on_session=True)
    lock.locked = True
    lock.session_event()
    QTest.qWait(50)
    assert lock.lock_count == 0


def test_the_session_lock_setting_is_in_settings_and_saved(window):
    view = window.settings_view
    view.set_security(True)
    assert not view.lock_session_card.isHidden() and view.lock_session.switch.isChecked()
    view.lock_session.switch.setChecked(False)
    assert window._svc.settings.load().lock_on_session is False
    view.set_settings(replace(window._settings, lock_on_session=True))
    assert view.lock_session.switch.isChecked()


def test_blurred_amounts_are_painted_without_showing_any_figure(qapp):
    """Un pintor que reconoce las marcas dibuja una mancha, no texto: la imagen es distinta de la del relleno sin difuminar."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter

    def render(text, draw):
        image = QImage(160, 30, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("white"))
        p = QPainter(image)
        p.setFont(QFont("Arial", 14))
        p.setPen(QColor("black"))
        draw(p, QRectF(0, 0, 160, 30), int(Qt.AlignmentFlag.AlignCenter), text)
        p.end()
        return image

    filler = "8.888,88 €"
    sharp = render(filler, lambda p, r, f, t: p.drawText(r, f, t))
    soft = render(blur.mark(filler), blur.draw_text)
    assert soft != sharp and any(soft.pixelColor(x, 15).value() < 250 for x in range(160))      # hay mancha, y no es el texto nitido
    again = render(blur.mark(filler), blur.draw_text)
    assert again == soft                                                                        # y sale igual la segunda vez (cache)
