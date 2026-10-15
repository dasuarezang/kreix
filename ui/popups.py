"""Paneles emergentes (desplegables y menus) con esquinas redondeadas de verdad.

Qt dibuja los paneles emergentes sobre una ventana rectangular: con `border-radius` en la hoja de estilos se ven las
esquinas cuadradas por detras. Se resuelve haciendo transparente el fondo de esas ventanas antes de que se muestren.
Se hace en estos dos controles, no con un filtro de eventos de toda la aplicacion (eso obligaria a pasar por Python cada
evento de la interfaz: pintar, mover el raton, temporizadores...).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QMenu, QWidget


def round_popup(window: QWidget) -> None:
    """Ventana emergente sin marco ni sombra del sistema y con fondo transparente (se dibuja el de la hoja de estilos)."""
    if window.property("kreixPopup"):
        return
    window.setProperty("kreixPopup", True)
    window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    window.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)


class Menu(QMenu):
    """QMenu con esquinas redondeadas."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        round_popup(self)


class Combo(QComboBox):
    """QComboBox cuyo panel desplegable tiene esquinas redondeadas."""

    def showPopup(self) -> None:
        round_popup(self.view().window())
        super().showPopup()
