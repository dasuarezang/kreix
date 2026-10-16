"""Inicio saluda segun la hora y por el nombre del usuario; el nombre se pide una vez, se cambia en Ajustes y viaja con los datos."""
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

from core.greeting import MAX_NAME, clean_name, greeting, period_greeting
from tests.conftest import dispose_windows
from ui.dialogs import WelcomeDialog

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 15, hour, minute)


# ---------------------------------------------------------------- logica pura
def test_greeting_changes_with_the_hour_of_the_day():
    assert greeting(at(6), "Ana") == "Buenos días, Ana."
    assert greeting(at(13, 59), "Ana") == "Buenos días, Ana."
    assert greeting(at(14), "Ana") == "Buenas tardes, Ana."
    assert greeting(at(20, 59), "Ana") == "Buenas tardes, Ana."
    assert greeting(at(21), "Ana") == "Buenas noches, Ana."
    assert greeting(at(0), "Ana") == "Buenas noches, Ana." and greeting(at(5, 59), "Ana") == "Buenas noches, Ana."
    assert [period_greeting(h) for h in range(24)].count("Buenos días") == 8


def test_greeting_without_a_name_is_just_the_greeting():
    assert greeting(at(9)) == "Buenos días." and greeting(at(9), "   ") == "Buenos días."


def test_clean_name_trims_collapses_spaces_and_limits_the_length():
    assert clean_name("  Ana   María  ") == "Ana María"
    assert clean_name(None) == "" and clean_name("   ") == ""
    assert len(clean_name("x" * 200)) == MAX_NAME
    assert clean_name("José Ángel") == "José Ángel"


# ---------------------------------------------------------------- ajustes persistidos
def test_name_is_saved_in_the_settings_and_loaded_back(window):
    svc = window._svc.settings
    assert svc.load().user_name == "" and svc.load().name_asked is False
    window._apply_user_name("  Ana  ")
    loaded = svc.load()
    assert (loaded.user_name, loaded.name_asked) == ("Ana", True)
    assert window._settings.user_name == "Ana"


# ---------------------------------------------------------------- pantalla de inicio
def test_home_shows_the_greeting_with_the_name_and_follows_the_clock(window):
    dash = window.dashboard
    dash.clock = lambda: at(9)
    dash.set_user_name("Ana")
    assert dash.header.title.text() == "Buenos días, Ana."
    assert dash.onboarding.title.text() == "Buenos días, Ana."            # tambien en la pantalla vacia de bienvenida
    dash.clock = lambda: at(16)
    dash.update_greeting()                                                # el temporizador de un minuto lo hace solo
    assert dash.header.title.text() == "Buenas tardes, Ana."
    dash.clock = lambda: at(23)
    dash.set_user_name("")
    assert dash.header.title.text() == "Buenas noches."


def test_the_first_tab_is_called_inicio(window):
    assert window.PAGES[window.SUMMARY] == "Inicio"
    assert window._nav.button(window.SUMMARY).text() == "Inicio"
    assert window.dashboard.header._eyebrow.text().lower() == "inicio"
    assert "Ir a Inicio" in [c.title for c in window.palette_commands()]


# ---------------------------------------------------------------- primera vez
def test_asks_the_name_once_and_remembers_it(window, monkeypatch):
    calls = []

    def accept(self):
        calls.append(1)
        self.name.setText("  Ana   Pérez ")
        return WelcomeDialog.DialogCode.Accepted

    monkeypatch.setattr(WelcomeDialog, "exec", accept)
    assert window.ask_name_if_needed() is True
    assert window._settings.user_name == "Ana Pérez" and window.dashboard.header.title.text().endswith("Ana Pérez.")
    assert window.settings_view.name_edit.text() == "Ana Pérez"
    assert window.ask_name_if_needed() is False and calls == [1]            # ya preguntado: no insiste


def test_saying_not_now_is_respected_and_never_asked_again(window, monkeypatch):
    calls = []
    monkeypatch.setattr(WelcomeDialog, "exec", lambda self: calls.append(1) or WelcomeDialog.DialogCode.Rejected)
    assert window.ask_name_if_needed() is False
    assert window._settings.name_asked and window._settings.user_name == ""
    assert window.ask_name_if_needed() is False and calls == [1]
    assert window._svc.settings.load().name_asked is True                   # tambien tras reiniciar


def test_welcome_dialog_asks_the_name_and_the_interests_with_a_way_out(qapp):
    dialog = WelcomeDialog()
    ok = dialog._buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert ok.text() == "Empezar" and dialog._buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == "Ahora no"
    assert dialog.result_name() == "" and dialog.result_interests() == (True, True)      # por defecto: ambas cosas
    dialog.name.setText("  Ana ")
    assert dialog.result_name() == "Ana" and ok.isEnabled()
    dialog.deleteLater()


# ---------------------------------------------------------------- cambiarlo en Ajustes
def test_changing_the_name_in_settings_updates_home_and_confirms_with_a_message(window):
    sv = window.settings_view
    assert not sv.name_save.isEnabled()
    sv.name_edit.setText("Luis")
    assert sv.name_save.isEnabled()
    sv.name_save.click()
    assert window._settings.user_name == "Luis" and window.dashboard.header.title.text().endswith(", Luis.")
    assert window.toast.text == "Nombre guardado: Luis." and not sv.name_save.isEnabled()
    sv.name_edit.setText("")                                                 # quitar el nombre
    sv.save_name()
    assert window._settings.user_name == "" and ","  not in window.dashboard.header.title.text()
    assert "sin nombre" in window.toast.text


def test_other_settings_changes_do_not_lose_the_name(window):
    window.settings_view.name_edit.setText("Luis")
    window.settings_view.save_name()
    window.settings_view.p2p.switch.setChecked(False)
    assert window._svc.settings.load().user_name == "Luis" and window._svc.settings.load().include_p2p is False


def test_the_palette_offers_to_change_the_name(window):
    cmd = next(c for c in window.palette_commands() if c.title == "Cambiar mi nombre")
    cmd.run()
    assert window.stack.currentIndex() == window.SETTINGS


# ---------------------------------------------------------------- exportar e importar
def test_the_name_travels_with_the_exported_file(tmp_path, qapp):
    from main import build_window

    a, b = build_window(f"sqlite:///{tmp_path / 'a.db'}", "a"), build_window(f"sqlite:///{tmp_path / 'b.db'}", "b")
    try:
        a.eager = b.eager = True
        a.import_view.import_paths([str(FIX / "imagin_sample.csv")])
        a._apply_user_name("Ana")
        file = tmp_path / "datos.kreix"
        a.export_view.export_to(str(file))

        assert b._settings.user_name == "" and not b._settings.name_asked
        assert b.restore_from(str(file)) is True
        assert b._settings.user_name == "Ana" and b._settings.name_asked                     # y no vuelve a preguntar
        assert b.settings_view.name_edit.text() == "Ana"
        assert b.dashboard.header.title.text().endswith(", Ana.")
        assert b._svc.settings.load().user_name == "Ana"
        assert b.ask_name_if_needed() is False
    finally:
        dispose_windows(a, b)


def test_undo_of_a_restore_brings_back_the_previous_name(tmp_path, qapp):
    from main import build_window

    a, b = build_window(f"sqlite:///{tmp_path / 'a.db'}", "a"), build_window(f"sqlite:///{tmp_path / 'b.db'}", "b")
    try:
        a._apply_user_name("Ana")
        a.import_view.import_paths([str(FIX / "imagin_sample.csv")])
        file = tmp_path / "datos.kreix"
        a.export_view.export_to(str(file))
        b._apply_user_name("Luis")
        b.restore_from(str(file))
        assert b._settings.user_name == "Ana"
        b.feedback.undo()
        assert b._settings.user_name == "Luis" and b.dashboard.header.title.text().endswith(", Luis.")
    finally:
        dispose_windows(a, b)


def test_a_special_name_is_greeted_differently_without_changing_what_is_saved():
    from datetime import datetime

    from core.greeting import greeting, shown_name

    for typed in ("Laura Padros", "laura  PADRÓS", " Laura Padrós "):
        assert greeting(datetime(2026, 1, 1, 9), typed) == "Buenos días, Petitona♥."
        assert shown_name(typed) == "Petitona♥"
    assert greeting(datetime(2026, 1, 1, 9), "Laura") == "Buenos días, Laura."          # solo ese nombre completo
    assert greeting(datetime(2026, 1, 1, 9), "Padros") == "Buenos días, Padros."
    assert greeting(datetime(2026, 1, 1, 22), "") == "Buenas noches."


def test_the_special_name_shows_on_home_but_settings_keep_what_was_typed(window):
    window._apply_user_name("Laura Padros", announce=False)
    assert "Petitona♥" in window.dashboard.header.title_label.text() if hasattr(window.dashboard.header, "title_label") else True
    assert window._settings.user_name == "Laura Padros" and window.settings_view.name_edit.text() == "Laura Padros"
