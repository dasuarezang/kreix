"""Avisos, preguntas y cuadros de texto con la cara de Kreix.

Los cuadros estandar de Qt (QMessageBox y QInputDialog) salen con el triangulo amarillo de Windows, los botones en el
idioma del sistema y sin nada de la marca. `install()` los sustituye, al arrancar, por estos: mismo fondo con resplandor,
titulo grande, el filo de marca y los botones de siempre. Las funciones tienen la misma firma que las de Qt, asi que el
resto del codigo (y las pruebas) siguen llamando a `QMessageBox.warning(...)`, `QInputDialog.getText(...)`, etc.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDoubleSpinBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QWidget,
)

from core.i18n import N_, tr
from ui.widgets.brand_dialog import BrandDialog

Button = QMessageBox.StandardButton
LABELS = {
    Button.Yes: N_("Sí"), Button.No: N_("No"), Button.Ok: N_("Aceptar"), Button.Cancel: N_("Cancelar"),
    Button.Close: N_("Cerrar"), Button.Save: N_("Guardar"), Button.Discard: N_("Descartar"),
}
ORDER = (Button.Cancel, Button.No, Button.Discard, Button.Close, Button.Save, Button.Ok, Button.Yes)   # el principal, a la derecha
POSITIVE = (Button.Yes, Button.Ok, Button.Save)
DISMISS = (Button.Cancel, Button.No, Button.Close, Button.Discard, Button.Ok)                         # que devuelve Esc


class BrandMessage(BrandDialog):
    """Un titulo, una explicacion y botones. `result_button` es el que se pulso (o el de cancelar si se cierra con Esc)."""

    def __init__(self, parent: QWidget | None, title: str, text: str, buttons: Button, default: Button, danger: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        self.setModal(True)
        self.result_button = Button.NoButton
        self.buttons: dict[Button, QPushButton] = {}
        row = QHBoxLayout()
        row.addStretch(1)
        for kind in ORDER:
            if not buttons & kind:
                continue
            button = QPushButton(tr(LABELS[kind]))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if kind in POSITIVE:
                button.setObjectName("Danger" if danger and kind is Button.Yes else "Primary")
            button.clicked.connect(lambda _=False, chosen=kind: self._choose(chosen))
            row.addWidget(button)
            self.buttons[kind] = button
        col = self.frame(title, text)
        col.addSpacing(4)
        col.addLayout(row)
        focus = self.buttons.get(default) or next((self.buttons[k] for k in POSITIVE if k in self.buttons), None)
        if focus is not None:
            focus.setDefault(True)
            focus.setFocus()
        self._dismiss = next((k for k in DISMISS if k in self.buttons), None)

    def _choose(self, kind: Button) -> None:
        self.result_button = kind
        self.accept() if kind in POSITIVE else self.reject()

    def reject(self) -> None:
        if self.result_button is Button.NoButton and self._dismiss is not None:
            self.result_button = self._dismiss
        super().reject()


def _ask(parent, title, text, buttons, default, danger=False) -> Button:
    dialog = BrandMessage(parent, title, text, buttons, default, danger)
    dialog.exec()
    answer = dialog.result_button
    dialog.deleteLater()
    return answer


def warning(parent, title, text, buttons=Button.Ok, defaultButton=Button.NoButton) -> Button:
    """Aviso. Si se ofrece Si, es una accion que no se puede deshacer: el boton va en rojo."""
    return _ask(parent, title, text, buttons, defaultButton, danger=bool(buttons & Button.Yes))


def question(parent, title, text, buttons=Button.Yes | Button.No, defaultButton=Button.NoButton) -> Button:
    return _ask(parent, title, text, buttons, defaultButton)


def information(parent, title, text, buttons=Button.Ok, defaultButton=Button.NoButton) -> Button:
    return _ask(parent, title, text, buttons, defaultButton)


class BrandInput(BrandDialog):
    """Pide un dato (texto, contrasena o numero) con la cara de Kreix."""

    def __init__(self, parent: QWidget | None, title: str, label: str, editor: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setModal(True)
        self.editor = editor
        editor.setAccessibleName(label)
        ok = QPushButton(tr("Aceptar"))
        ok.setObjectName("Primary")
        ok.setDefault(True)
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.clicked.connect(self.accept)
        cancel = QPushButton(tr("Cancelar"))
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(ok)
        col = self.frame(title, label)
        col.addWidget(editor)
        col.addSpacing(4)
        col.addLayout(row)
        editor.setFocus()
        if isinstance(editor, QLineEdit):
            editor.returnPressed.connect(self.accept)


def get_text(parent, title, label, echo=QLineEdit.EchoMode.Normal, text="", *args, **kwargs) -> tuple[str, bool]:
    editor = QLineEdit(text)
    editor.setEchoMode(echo)
    dialog = BrandInput(parent, title, label, editor)
    ok = dialog.exec() == QDialog.DialogCode.Accepted
    value = editor.text()
    dialog.deleteLater()
    return value, ok


def get_double(parent, title, label, value=0.0, minValue=-2147483647.0, maxValue=2147483647.0, decimals=1, *args, **kwargs) -> tuple[float, bool]:
    editor = QDoubleSpinBox()
    editor.setDecimals(decimals)
    editor.setRange(minValue, maxValue)
    editor.setValue(value)
    editor.setAlignment(Qt.AlignmentFlag.AlignRight)
    editor.setGroupSeparatorShown(True)
    dialog = BrandInput(parent, title, label, editor)
    ok = dialog.exec() == QDialog.DialogCode.Accepted
    number = editor.value()
    dialog.deleteLater()
    return number, ok


def install() -> None:
    """Cambia los cuadros estandar de Qt por los de la marca para toda la aplicacion."""
    QMessageBox.warning = staticmethod(warning)
    QMessageBox.question = staticmethod(question)
    QMessageBox.information = staticmethod(information)
    QInputDialog.getText = staticmethod(get_text)
    QInputDialog.getDouble = staticmethod(get_double)
