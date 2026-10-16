"""La primera vez: la bienvenida va antes de ensenar la ventana, que sale ya con el nombre, los intereses y el idioma."""
import pytest
from PySide6.QtWidgets import QApplication

import main
from core import i18n
from tests.conftest import dispose_windows
from ui.dialogs import WelcomeDialog


@pytest.fixture()
def fresh(qapp):
    from ui import fonts
    from ui.widgets import charts

    charts.ANIMATIONS = False
    fonts.setup_application(qapp)
    window = main.build_window("sqlite:///:memory:", "memoria")
    window.eager = True
    yield window
    for w in {window, getattr(qapp, "kreix_window", window)}:
        try:
            dispose_windows(w)
        except RuntimeError:
            pass


def answer(monkeypatch, name="Ana", language=None, accounts=True, investments=True):
    def fake(self):
        self.name.setText(name)
        if language:
            self.languages.buttons[language].click()
        return WelcomeDialog.DialogCode.Accepted

    monkeypatch.setattr(WelcomeDialog, "exec", fake)
    monkeypatch.setattr(WelcomeDialog, "result_interests", lambda self: (accounts, investments))


def test_a_new_install_needs_the_welcome_and_an_old_one_does_not(fresh):
    assert fresh.needs_welcome()
    fresh._apply_user_name("Ana", announce=False)
    assert not fresh.needs_welcome()


def test_the_welcome_before_showing_leaves_home_ready_with_name_and_interests(fresh, monkeypatch):
    answer(monkeypatch, "Ana", accounts=True, investments=False)
    shown = fresh.welcome_before_show()
    assert shown is fresh and not fresh.isVisible()                          # la ventana no se ha mostrado aun
    assert fresh.dashboard.header.title.text().endswith("Ana.")
    assert not fresh._settings.interest_investments and fresh._settings.name_asked
    assert fresh._svc.settings.load().user_name == "Ana"


def test_the_dialog_has_no_window_behind_it_so_it_centres_on_the_screen(fresh, monkeypatch):
    seen = []
    monkeypatch.setattr(WelcomeDialog, "exec", lambda self: seen.append(self.parent()) or WelcomeDialog.DialogCode.Rejected)
    fresh.welcome_before_show()
    assert seen == [None]
    other = main.build_window("sqlite:///:memory:", "otra")
    seen.clear()
    other.ask_name_if_needed()                                              # despues de mostrar (el camino de siempre) si cuelga de la ventana
    assert seen == [other]
    dispose_windows(other)


def test_changing_language_in_the_welcome_builds_the_final_window_without_showing_the_old_one(fresh, monkeypatch, qapp):
    answer(monkeypatch, "Ana", language="en")
    shown = fresh.welcome_before_show()
    assert shown is not fresh and qapp.kreix_window is shown
    assert i18n.language() == "en" and shown._settings.language == "en"
    assert shown.toast.text != "Language changed to English."              # sin aviso de cambio de idioma: aun no ha visto nada
    assert not fresh.isVisible() and not shown.isVisible()                  # quien llama decide cuando mostrarla


def test_saying_not_now_still_remembers_the_chosen_language_and_never_asks_again(fresh, monkeypatch, qapp):
    monkeypatch.setattr(WelcomeDialog, "exec", lambda self: self.languages.buttons["ca"].click() or WelcomeDialog.DialogCode.Rejected)
    shown = fresh.welcome_before_show()
    assert shown._settings.language == "ca" and not shown.needs_welcome()


def test_reveal_fades_the_window_in_and_ends_fully_opaque(fresh, qapp):
    from PySide6.QtTest import QTest

    main.reveal(fresh, duration_ms=60)
    assert fresh.isVisible() and fresh.windowOpacity() < 1.0
    QTest.qWait(200)
    assert fresh.windowOpacity() == 1.0


def test_the_lock_screen_hands_over_before_the_welcome(qapp):
    from ui.lock_screen import LockDialog, LockMode

    dialog = LockDialog(LockMode.CREATE, lambda p: None)
    dialog.show()
    dialog.release()
    assert not dialog.isVisible()
    dialog.deleteLater()
