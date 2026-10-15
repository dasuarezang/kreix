"""Botones de navegacion: el aro de foco solo se dibuja cuando el foco llega por teclado (Tab), no al arrancar ni al hacer clic."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
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


class _RingFilter(QObject):
    """Filtro de aplicacion: cualquier QPushButton recibe `kbd` solo cuando el foco llega por teclado."""

    def eventFilter(self, obj, event) -> bool:
        kind = event.type()
        if kind == QEvent.Type.FocusIn and isinstance(obj, QPushButton) and not isinstance(obj, KeyboardRing):
            _mark(obj, event.reason() in KEYBOARD_REASONS)
        elif kind == QEvent.Type.FocusOut and isinstance(obj, QPushButton) and not isinstance(obj, KeyboardRing):
            _mark(obj, False)
        return False


def _mark(button: QPushButton, on: bool) -> None:
    if bool(button.property("kbd")) != on:
        button.setProperty("kbd", on)
        style = button.style()
        style.unpolish(button)
        style.polish(button)


_ring_filter: _RingFilter | None = None


def install_keyboard_rings(app) -> None:
    """Una sola vez por aplicacion: el aro de foco de todos los botones solo sale con Tab, no al hacer clic."""
    global _ring_filter
    if _ring_filter is None or _ring_filter.parent() is not app:
        _ring_filter = _RingFilter(app)
        app.installEventFilter(_ring_filter)
