"""Cuadros de aviso y de texto con la marca, el buscador y las novedades."""
import pytest
from PySide6.QtWidgets import QDialog, QDoubleSpinBox, QInputDialog, QLineEdit, QMessageBox

from core import i18n
from ui.command_palette import Command, CommandPalette
from ui.widgets import brand_message
from ui.widgets.brand_dialog import BrandDialog
from ui.whats_new import WhatsNewDialog

B = QMessageBox.StandardButton


def test_warning_with_yes_is_a_red_button_and_questions_are_primary(qapp):
    danger = brand_message.BrandMessage(None, "Borrar", "¿Seguro?", B.Yes | B.No, B.No, danger=True)
    assert danger.buttons[B.Yes].objectName() == "Danger" and danger.buttons[B.No].objectName() == ""
    assert danger.buttons[B.No].isDefault()
    ask = brand_message.BrandMessage(None, "Eliminar", "¿Seguro?", B.Yes | B.Cancel, B.Cancel)
    assert ask.buttons[B.Yes].objectName() == "Primary" and [b.text() for b in ask.buttons.values()] == ["Cancelar", "Sí"]
    info = brand_message.BrandMessage(None, "Aviso", "Hecho", B.Ok, B.NoButton)
    assert info.buttons[B.Ok].isDefault() and info.buttons[B.Ok].objectName() == "Primary"
    for dialog in (danger, ask, info):
        dialog.deleteLater()


def test_buttons_return_what_was_pressed_and_escape_cancels(qapp):
    dialog = brand_message.BrandMessage(None, "t", "x", B.Yes | B.Cancel, B.Cancel)
    dialog.buttons[B.Yes].click()
    assert dialog.result_button is B.Yes and dialog.result() == QDialog.DialogCode.Accepted
    other = brand_message.BrandMessage(None, "t", "x", B.Yes | B.Cancel, B.Cancel)
    other.reject()
    assert other.result_button is B.Cancel
    no_cancel = brand_message.BrandMessage(None, "t", "x", B.Yes | B.No, B.No)
    no_cancel.reject()
    assert no_cancel.result_button is B.No
    for d in (dialog, other, no_cancel):
        d.deleteLater()


def test_buttons_follow_the_language(qapp):
    i18n.set_language("en")
    dialog = brand_message.BrandMessage(None, "t", "x", B.Yes | B.No | B.Ok, B.No)
    assert {b.text() for b in dialog.buttons.values()} == {"Yes", "No", "OK"}
    dialog.deleteLater()


def test_message_and_input_functions_keep_qts_signatures(qapp, monkeypatch):
    monkeypatch.setattr(brand_message.BrandMessage, "exec", lambda self: self.buttons[B.Yes].click() or 1)
    assert brand_message.question(None, "t", "x") is B.Yes
    assert brand_message.warning(None, "t", "x", B.Yes | B.No, B.No) is B.Yes
    monkeypatch.setattr(brand_message.BrandMessage, "exec", lambda self: self.buttons[B.Ok].click() or 1)
    assert brand_message.information(None, "t", "x") is B.Ok
    monkeypatch.setattr(brand_message.BrandMessage, "exec", lambda self: self.reject() or 0)
    assert brand_message.question(None, "t", "x", B.Yes | B.Cancel, B.Cancel) is B.Cancel


def test_text_and_number_dialogs(qapp, monkeypatch):
    def fill(self):
        if isinstance(self.editor, QLineEdit):
            self.editor.setText("Mi cuenta")
        else:
            self.editor.setValue(12.5)
        self.accept()
        return 1

    monkeypatch.setattr(brand_message.BrandInput, "exec", fill)
    assert brand_message.get_text(None, "Añadir cuenta", "Nombre:") == ("Mi cuenta", True)
    assert brand_message.get_double(None, "Apuntar", "Importe:", 0.0, -100.0, 100.0, 2) == (12.5, True)
    monkeypatch.setattr(brand_message.BrandInput, "exec", lambda self: self.reject() or 0)
    assert brand_message.get_text(None, "t", "x", QLineEdit.EchoMode.Password)[1] is False
    password = brand_message.BrandInput(None, "t", "x", QLineEdit())
    assert isinstance(password, BrandDialog)
    password.deleteLater()


def test_install_replaces_the_standard_boxes_and_can_be_undone(qapp, monkeypatch):
    originals = {name: getattr(QMessageBox, name) for name in ("warning", "question", "information")}
    original_input = (QInputDialog.getText, QInputDialog.getDouble)
    try:
        brand_message.install()
        assert QMessageBox.warning is brand_message.warning and QInputDialog.getText is brand_message.get_text
        assert QInputDialog.getDouble is brand_message.get_double
    finally:
        for name, value in originals.items():
            setattr(QMessageBox, name, value)
        QInputDialog.getText, QInputDialog.getDouble = original_input


def test_every_app_dialog_uses_the_brand_background_and_rule(qapp, window):
    assert issubclass(WhatsNewDialog, BrandDialog) and issubclass(brand_message.BrandMessage, BrandDialog)
    dialog = WhatsNewDialog("0.3.0")
    assert dialog.heading.text() == "Novedades de Kreix 0.3.0"
    dialog.deleteLater()


def test_palette_rows_are_readable_and_only_the_chosen_one_is_dark_on_yellow(qapp, window):
    commands = [Command(f"Ir a {n}", "Ctrl+1", lambda: None) for n in ("Inicio", "Cuentas", "Ajustes")]
    palette = CommandPalette(commands, None, window)
    labels = [palette.list.itemWidget(palette.list.item(i)) for i in range(3)]
    assert [bool(l.property("selected")) for l in labels] == [True, False, False]
    palette.list.setCurrentRow(2)
    assert [bool(l.property("selected")) for l in labels] == [False, False, True]
    from ui import theme

    assert theme.current().on_accent in labels[2].text() and theme.current().muted in labels[0].text()
    assert "opacity" not in labels[0].text()                      # Qt no entiende opacity: el gris va con el color del tema
    palette.deleteLater()
