"""Botones de navegacion: el aro de foco solo se dibuja cuando el foco llega por teclado (Tab), no al arrancar ni al hacer clic."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

KEYBOARD_REASONS = (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason)


class KeyboardRing:
    """Mezcla para botones: marca `kbd` cuando el foco viene del teclado; la hoja de estilos dibuja el aro solo entonces."""

    def _set_kbd(self, on: bool) -> None:
        if bool(self.property("kbd")) != on:
            self.setProperty("kbd", on)
            style = self.style()
            style.unpolish(self)
            style.polish(self)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._set_kbd(event.reason() in KEYBOARD_REASONS)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._set_kbd(False)


class NavButton(KeyboardRing, QPushButton):
    """Un elemento de la barra lateral (pagina, herramienta o entrada del submenu Datos)."""
