"""Boton "Datos" de la barra lateral: agrupa Importar y Exportar en un submenu que se abre al pasar el raton.

El submenu es un panel flotante dentro de la propia ventana (no una ventana aparte), pegado al boton. Se abre al pasar el
cursor o al pulsar el boton (con teclado: Intro o Espacio), y se cierra al salir el cursor de ambos, al elegir una opcion o
con Escape. Las dos opciones son botones normales del grupo de navegacion, asi que las paginas y sus atajos no cambian.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from ui.widgets.nav_button import KeyboardRing

CLOSE_DELAY_MS = 220          # margen para cruzar del boton al panel sin que se cierre
GAP = 24                      # separacion entre la barra lateral y el panel


class DataFlyout(QFrame):
    """Panel con las opciones del grupo. Cuelga de la ventana para poder salirse de la barra lateral."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("DataFlyout")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(2)
        self._anchor: QWidget | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(CLOSE_DELAY_MS)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def add_item(self, button: QPushButton) -> None:
        self._layout.addWidget(button)

    def open_for(self, anchor: QWidget) -> None:
        """Se muestra a la derecha de `anchor`, con su borde inferior alineado con el del boton."""
        self._timer.stop()
        self._anchor = anchor
        parent = self.parentWidget()
        self.adjustSize()
        origin = anchor.mapTo(parent, QPoint(anchor.width() + GAP, 0))
        self.move(origin.x(), origin.y() + anchor.height() - self.height())
        self.show()
        self.raise_()

    def toggle_for(self, anchor: QWidget) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.open_for(anchor)

    def keep_open(self) -> None:
        self._timer.stop()

    def close_soon(self) -> None:
        if self.isVisible():
            self._timer.start()

    def enterEvent(self, event) -> None:
        self.keep_open()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.close_soon()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class DataMenuButton(KeyboardRing, QPushButton):
    """El boton "Datos": abre el panel al pasar el raton o al pulsarlo."""

    def __init__(self, text: str, flyout: DataFlyout) -> None:
        super().__init__(text)
        self.flyout = flyout
        self.setCheckable(True)                       # se marca cuando la pagina actual es Importar o Exportar
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.clicked.connect(self._on_click)

    def _on_click(self) -> None:
        self.setChecked(self._should_be_checked)      # pulsarlo no lo marca: solo lo marca estar en Importar o Exportar
        self.flyout.toggle_for(self)

    _should_be_checked = False

    def set_active(self, active: bool) -> None:
        self._should_be_checked = active
        self.setChecked(active)

    def enterEvent(self, event) -> None:
        self.flyout.open_for(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.flyout.close_soon()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Right):
            self.flyout.open_for(self)
        elif event.key() == Qt.Key.Key_Escape:
            self.flyout.hide()
        else:
            super().keyPressEvent(event)
