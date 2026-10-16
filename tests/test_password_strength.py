"""Medidor de fuerza de la contrasena: la estimacion pura y su aparicion en la pantalla de bloqueo y al cambiarla."""
import pytest

from core import i18n
from core.password_strength import LABELS, assess
from ui.lock_screen import LockDialog, LockMode
from ui.password_dialog import ChangePasswordDialog
from ui.widgets.strength_meter import StrengthMeter


@pytest.fixture(autouse=True)
def spanish():
    i18n.set_language("es")
    yield
    i18n.set_language("es")


@pytest.mark.parametrize("password", ["", "a", "abcdefgh", "password1", "12345678", "aaaaaaaaaa", "qwertyuiop", "987654321"])
def test_typical_or_tiny_passwords_are_very_weak(password):
    assert assess(password).level == 0


def test_strength_grows_with_length_and_variety():
    levels = [assess(p).level for p in ("kjhdsaq", "kjhdsaqxz", "Kj7dsaQxz1", "xK9#mQ2vL!4t", "correcto caballo bateria grapa")]
    assert levels == sorted(levels) and levels[-1] == 4 and levels[0] == 0


def test_only_digits_never_rate_above_weak_even_when_long():
    assert assess("48201739560184").level <= 1


def test_a_hint_is_given_until_the_password_is_very_strong():
    assert assess("kjhdsaqxz").hint and assess("correcto caballo bateria grapa").hint == ""
    assert assess("password1").hint                                         # tambien explica por que es debil


def test_very_long_input_is_handled_quickly():
    assert assess("ab" * 5000).level == 0 and assess("x9Q#" * 4000).level == 0       # un bloque repetido vale lo que el bloque
    assert assess("".join(chr(33 + (i * 37) % 90) for i in range(5000))).level >= 1


def test_every_level_has_a_label():
    assert len(LABELS) == 5 and assess("").label == LABELS[0]


def test_meter_shows_bars_word_and_hint(qapp):
    meter = StrengthMeter()
    assert meter.word.text() == "Seguridad de la contraseña" and meter._bars.filled == 0 and meter.hint.isHidden()
    meter.set_password("kjhdsaqxz")
    assert meter.word.text().startswith("Seguridad: ") and meter._bars.filled == max(1, meter.level)
    assert not meter.hint.isHidden() and meter.hint.text()
    meter.set_password("correcto caballo bateria grapa")
    assert meter.level == 4 and meter._bars.filled == 4 and meter.word.text() == "Seguridad: Muy fuerte"
    meter.set_password("")
    assert meter._bars.filled == 0
    i18n.set_language("en")
    meter.set_password("correcto caballo bateria grapa")
    assert meter.word.text() == "Strength: Very strong"
    meter.deleteLater()


def test_meter_follows_what_is_typed_when_creating_the_master_password(qapp):
    dialog = LockDialog(LockMode.CREATE, lambda _p: None)
    assert not dialog.meter.isHidden()
    dialog.password.setText("correcto caballo bateria grapa")
    assert dialog.meter.level == 4
    dialog.deleteLater()


def test_meter_is_not_shown_when_unlocking(qapp):
    dialog = LockDialog(LockMode.UNLOCK, lambda _p: None)
    assert dialog.meter.isHidden()
    dialog.deleteLater()


def test_meter_follows_the_new_password_in_the_change_dialog(qapp):
    dialog = ChangePasswordDialog(lambda _o, _n: None)
    dialog.new.setText("password1")
    assert dialog.meter.level == 0
    dialog.new.setText("correcto caballo bateria grapa")
    assert dialog.meter.level == 4
    dialog.deleteLater()


def test_dialogs_grow_so_the_meter_and_its_advice_are_never_cut(qapp):
    dialog = LockDialog(LockMode.CREATE, lambda _p: None)
    dialog.show()
    for text in ("", "password1", "kjhdsaqxz", "correcto caballo bateria grapa"):
        dialog.password.setText(text)
        qapp.processEvents()
        assert dialog.height() >= dialog.layout().totalHeightForWidth(dialog.width()), text
    dialog.close()
    dialog.deleteLater()
