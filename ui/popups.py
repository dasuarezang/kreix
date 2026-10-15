"""Paneles emergentes (desplegables y menus) con esquinas redondeadas de verdad.

Qt dibuja los paneles emergentes sobre una ventana rectangular: con `border-radius` en la hoja de estilos se ven las
esquinas cuadradas por detras. Se resuelve haciendo transparente el fondo de esas ventanas antes de que se muestren.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget

POPUP_CLASSES = {"QComboBoxPrivateContainer", "QMenu"}


class PopupStyler(QObject):
    """Filtro de eventos de la aplicacion: prepara cada panel emergente la primera vez que se pule."""

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Polish and isinstance(obj, QWidget) and obj.isWindow() \
                and obj.metaObject().className() in POPUP_CLASSES and not obj.property("kreixPopup"):
            obj.setProperty("kreixPopup", True)
            obj.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            obj.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
            obj.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        return False
