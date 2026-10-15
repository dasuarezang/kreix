"""Lo que le interesa al usuario: cuentas, inversiones o ambas. Se pregunta la primera vez, se cambia en Ajustes y se
puede activar desde la propia pestana que falte. Viaja con los datos."""
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from services.settings_service import AppSettings
from tests.conftest import dispose_windows
from ui.dialogs import WelcomeDialog
from ui.widgets.interests import AT_LEAST_ONE, InterestPicker

FIX = Path(__file__).parent / "fixtures"
FILES = [FIX / "imagin_sample.csv", FIX / "myinvestor_operaciones.csv", FIX / "myinvestor_cartera.csv"]


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)


def answer(monkeypatch, name="Ana", accounts=True, investments=True, accept=True):
    """Simula lo que el usuario contesta en el dialogo de bienvenida."""
    def fake(self):
        self.name.setText(name)
        self.interests.set_values(accounts, investments)
        return WelcomeDialog.DialogCode.Accepted if accept else WelcomeDialog.DialogCode.Rejected

    monkeypatch.setattr(WelcomeDialog, "exec", fake)


# ---------------------------------------------------------------- ajustes persistidos
def test_interests_default_to_both_and_are_saved(window):
    s = window._svc.settings.load()
    assert (s.interest_accounts, s.interest_investments) == (True, True)
    window._apply_interests(True, False, "x")
    s = window._svc.settings.load()
    assert (s.interest_accounts, s.interest_investments) == (True, False)


def test_a_corrupt_value_with_both_off_never_leaves_the_user_with_nothing(window):
    from data.database import session_scope
    from data.models import Setting

    svc = window._svc.settings
    svc.save(AppSettings(interest_accounts=False, interest_investments=False))      # al guardar ya se protege
    s = svc.load()
    assert s.interest_accounts or s.interest_investments
    with session_scope(svc._factory) as session:                                    # y si la base trae un valor raro
        session.merge(Setting(key="interest_accounts", value="0"))
        session.merge(Setting(key="interest_investments", value="0"))
    s = svc.load()
    assert (s.interest_accounts, s.interest_investments) == (True, True)
    window._apply_interests(False, False, "x")                                      # tampoco se acepta por codigo
    assert window._settings.interest_accounts and window._settings.interest_investments


# ---------------------------------------------------------------- los dos interruptores
def test_the_picker_always_keeps_one_interest_on(qapp):
    picker = InterestPicker(True, True)
    got = []
    picker.changed.connect(lambda a, i: got.append((a, i)))
    picker.investments.switch.setChecked(False)
    assert got == [(True, False)] and picker.values() == (True, False) and picker.hint.isHidden()
    picker.accounts.switch.setChecked(False)                                # no se puede apagar la ultima
    assert picker.values() == (True, False) and got == [(True, False)]
    assert not picker.hint.isHidden() and picker.hint.text() == AT_LEAST_ONE
    picker.investments.switch.setChecked(True)                              # primero se activa la otra...
    picker.accounts.switch.setChecked(False)                                # ...y ya se puede apagar esta
    assert picker.values() == (False, True) and got[-1] == (False, True) and picker.hint.isHidden()
    picker.set_values(True, True)
    assert picker.values() == (True, True) and len(got) == 3                # set_values no emite
    picker.deleteLater()


# ---------------------------------------------------------------- primera vez
def test_first_run_asks_the_interests_in_the_same_dialog_as_the_name(window, monkeypatch):
    answer(monkeypatch, "Ana", accounts=False, investments=True)
    assert window.ask_name_if_needed() is True
    assert window._settings.user_name == "Ana"
    assert (window._settings.interest_accounts, window._settings.interest_investments) == (False, True)
    stored = window._svc.settings.load()
    assert (stored.user_name, stored.interest_accounts, stored.interest_investments) == ("Ana", False, True)
    assert window.settings_view.interests.values() == (False, True)
    assert window.accounts_view._stack.currentIndex() == 2                  # Cuentas: solo ofrece activarla
    assert window.dashboard._interests == (False, True)
    assert window.ask_name_if_needed() is False                              # solo se pregunta una vez


def test_not_now_keeps_both_interests_and_does_not_ask_again(window, monkeypatch):
    answer(monkeypatch, accounts=False, investments=False, accept=False)
    window.ask_name_if_needed()
    assert (window._settings.interest_accounts, window._settings.interest_investments) == (True, True)
    assert window._settings.name_asked and window.accounts_view._stack.currentIndex() != 2


def test_the_welcome_dialog_starts_from_the_current_values(window, monkeypatch):
    seen = []
    monkeypatch.setattr(WelcomeDialog, "exec", lambda self: seen.append(self.interests.values()) or WelcomeDialog.DialogCode.Rejected)
    window._settings = window._settings.__class__(**{**window._settings.__dict__, "interest_investments": False}) \
        if hasattr(window._settings, "__dict__") else window._settings
    window.ask_name_if_needed()
    assert seen and seen[0][0] is True


# ---------------------------------------------------------------- cambiarlo en Ajustes
def test_settings_switches_change_the_interests_and_confirm(window):
    sv = window.settings_view
    sv.interests.investments.switch.setChecked(False)
    assert not window._settings.interest_investments and window.toast.text == "Intereses guardados."
    assert window.investment_view._stack.currentIndex() == 2
    sv.interests.accounts.switch.setChecked(False)                            # la ultima no se apaga
    assert window._settings.interest_accounts and window.accounts_view._stack.currentIndex() != 2
    sv.interests.investments.switch.setChecked(True)
    assert window._settings.interest_investments and window.investment_view._stack.currentIndex() != 2


def test_other_settings_do_not_lose_the_interests(window):
    window._apply_interests(False, True, "x")
    window.settings_view.p2p.switch.setChecked(False)
    s = window._svc.settings.load()
    assert (s.interest_accounts, s.interest_investments, s.include_p2p) == (False, True, False)


def test_the_palette_offers_to_change_the_interests(window):
    cmd = next(c for c in window.palette_commands() if c.title == "Cambiar lo que me interesa")
    cmd.run()
    assert window.stack.currentIndex() == window.SETTINGS


# ---------------------------------------------------------------- activar desde la propia pestana
def test_entering_investments_when_not_interested_offers_to_activate_only_that(window):
    window._apply_interests(True, False, "x")
    window.navigate(window.INVESTMENT)
    v = window.investment_view
    assert v._stack.currentIndex() == 2 and not v.header.isVisibleTo(v) and not v.period.isVisibleTo(v)
    assert v.off_state.button.text() == "Activar inversiones" and "inversiones" in v.off_state.title_label.text().lower()
    v.off_state.button.click()
    assert window._settings.interest_investments and window._settings.interest_accounts
    assert window.toast.text == "Inversiones activadas." and v.header.isVisibleTo(v)
    assert v._stack.currentIndex() in (0, 1) and window.settings_view.interests.values() == (True, True)


def test_entering_accounts_when_not_interested_offers_to_activate_only_that(window):
    window._apply_interests(False, True, "x")
    window.navigate(window.ACCOUNTS)
    v = window.accounts_view
    assert v._stack.currentIndex() == 2 and v.off_state.button.text() == "Activar cuentas bancarias"
    v.off_state.button.click()
    assert window._settings.interest_accounts and window._settings.interest_investments
    assert window.toast.text == "Cuentas bancarias activadas."
    assert v._stack.currentIndex() in (0, 1)


def test_activating_one_does_not_turn_on_the_other(window):
    # solo se puede estar en "ninguna activada" por codigo; con una desactivada, activar la contraria deja ambas
    window._apply_interests(True, False, "x")
    window._activate_interest("accounts")                                     # ya estaba activa: no cambia nada mas
    assert (window._settings.interest_accounts, window._settings.interest_investments) == (True, False)


def test_activation_from_the_tab_can_be_undone(window):
    window._apply_interests(True, False, "x")
    window.navigate(window.INVESTMENT)
    window.investment_view.off_state.button.click()
    assert window.feedback.can_undo and window.toast.undo_button.isVisibleTo(window.toast)
    window.feedback.undo()
    assert not window._settings.interest_investments and window.investment_view._stack.currentIndex() == 2
    assert window.settings_view.interests.values() == (True, False)


def test_a_disabled_tab_does_not_load_its_data(window, monkeypatch):
    window.import_view.import_paths([str(p) for p in FILES])
    window._apply_interests(True, False, "x")
    calls = []
    monkeypatch.setattr(window._svc.investment, "view", lambda *a, **k: calls.append(1))
    window.investment_view.reload()
    window.refresh()
    assert calls == [] and window.investment_view._stack.currentIndex() == 2


# ---------------------------------------------------------------- Inicio se adapta
def test_home_hides_what_does_not_interest_the_user(window):
    window.import_view.import_paths([str(p) for p in FILES])
    d = window.dashboard
    window._apply_interests(True, False, "x")                                  # solo cuentas
    assert d.card_return.isHidden() and d.allocation_card.isHidden()
    assert not d.card_savings.isHidden() and not d.flow_card.isHidden() and not d.budgets.isHidden()
    assert [p[0] for p in d.card_net.split._parts] == ["Liquidez"] and d.card_net._chip_widgets == []
    assert d.card_net._sub.text() == "Lo que tienes en tus cuentas"
    assert d.setup.subtitle.text().endswith("de 2 hechos")                       # cuenta + presupuesto
    window._apply_interests(False, True, "x")                                  # solo inversiones
    assert d.card_savings.isHidden() and d.flow_card.isHidden() and d.upcoming.isHidden() and d.budgets.isHidden()
    assert not d.card_return.isHidden() and not d.allocation_card.isHidden()
    assert [p[0] for p in d.card_net.split._parts] == ["Inversión"] and d.card_net._sub.text() == "Lo que tienes invertido"
    assert d.setup.subtitle.text() == "2 de 2 hechos" or not d.setup.isVisibleTo(d)
    window._apply_interests(True, True, "x")
    assert not d.card_return.isHidden() and not d.card_savings.isHidden() and len(d.card_net.split._parts) == 2


def test_the_welcome_screen_adapts_its_steps(window):
    onboarding = window.dashboard.onboarding
    window._apply_interests(True, False, "x")
    assert "Imagin" in onboarding._step1.text() and "MyInvestor" not in onboarding._step1.text()
    assert onboarding._step3.text().startswith("Inicio y Cuentas")
    window._apply_interests(False, True, "x")
    assert "MyInvestor" in onboarding._step1.text() and "Imagin" not in onboarding._step1.text()
    assert onboarding._step3.text().startswith("Inicio e Inversiones")
    window._apply_interests(True, True, "x")
    assert "Imagin" in onboarding._step1.text() and "MyInvestor" in onboarding._step1.text()


# ---------------------------------------------------------------- exportar, importar y reiniciar
def test_the_interests_travel_with_the_exported_file(tmp_path, qapp):
    from main import build_window

    a, b = build_window(f"sqlite:///{tmp_path / 'a.db'}", "a"), build_window(f"sqlite:///{tmp_path / 'b.db'}", "b")
    try:
        a.eager = b.eager = True
        a.import_view.import_paths([str(FIX / "imagin_sample.csv")])
        a._apply_interests(True, False, "x")
        file = tmp_path / "datos.kreix"
        a.export_view.export_to(str(file))
        assert (b._settings.interest_accounts, b._settings.interest_investments) == (True, True)
        assert b.restore_from(str(file)) is True
        assert (b._settings.interest_accounts, b._settings.interest_investments) == (True, False)
        assert b.investment_view._stack.currentIndex() == 2 and b.settings_view.interests.values() == (True, False)
        assert b.dashboard._interests == (True, False)
    finally:
        dispose_windows(a, b)


def test_the_interests_survive_a_restart(tmp_path, qapp):
    from main import build_window

    url = f"sqlite:///{tmp_path / 'k.db'}"
    first = build_window(url, "k")
    first._apply_interests(False, True, "x")
    dispose_windows(first)
    second = build_window(url, "k")
    try:
        assert second.accounts_view._stack.currentIndex() == 2 and second.dashboard._interests == (False, True)
        assert second.settings_view.interests.values() == (False, True)
    finally:
        dispose_windows(second)
