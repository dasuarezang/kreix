"""Luz ambiente: baja muy ligeramente el brillo de la ventana segun la hora, sin cambiar el tema.

Una capa casi transparente sobre toda la ventana (no atrapa el raton). De manana y a mediodia no hace nada; por la
tarde empieza a atenuar con un toque calido al atardecer; de noche llega a un 7 % con un matiz azulado.
Es un cambio pequeno a proposito: se nota al compararlo con la manana, no molesta ni altera los colores de la marca.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget
from core.i18n import tr

# (hora, (r, g, b, alpha 0-255)). Entre dos puntos se interpola de forma lineal; 24 repite las 0.
KEYFRAMES: tuple[tuple[float, tuple[int, int, int, int]], ...] = (
    (0.0, (8, 14, 40, 18)),
    (5.0, (8, 14, 40, 15)),
    (7.5, (0, 0, 0, 0)),
    (13.0, (0, 0, 0, 0)),
    (16.0, (0, 0, 0, 4)),
    (19.0, (255, 120, 40, 9)),
    (21.0, (10, 16, 48, 14)),
    (24.0, (8, 14, 40, 18)),
)
MAX_ALPHA = 18


def hour_of(moment: datetime) -> float:
    return moment.hour + moment.minute / 60 + moment.second / 3600


def ambient_tint(hour: float) -> tuple[int, int, int, int]:
    """Color y opacidad de la capa para una hora en decimal. Opacidad 0 = sin cambios."""
    hour %= 24
    for (h0, c0), (h1, c1) in zip(KEYFRAMES, KEYFRAMES[1:]):
        if h0 <= hour <= h1:
            f = (hour - h0) / (h1 - h0) if h1 > h0 else 0.0
            if c0[3] == 0:                       # desde "sin capa": se conserva el color de destino y solo sube la opacidad
                rgb = c1[:3]
            elif c1[3] == 0:
                rgb = c0[:3]
            else:
                rgb = tuple(round(a + (b - a) * f) for a, b in zip(c0[:3], c1[:3]))
            alpha = round(c0[3] + (c1[3] - c0[3]) * f)
            return (*rgb, alpha)                 # type: ignore[return-value]
    return KEYFRAMES[0][1]


class AmbientLight(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._hour = 12.0
        self._enabled = True
        self.setAccessibleName(tr("Luz ambiente"))

    @property
    def tint(self) -> tuple[int, int, int, int]:
        return ambient_tint(self._hour) if self._enabled else (0, 0, 0, 0)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_hour(self, hour: float) -> None:
        if hour != self._hour:
            self._hour = hour
            self.update()

    def set_enabled(self, on: bool) -> None:
        if on != self._enabled:
            self._enabled = on
            self.update()

    def paintEvent(self, _event) -> None:
        r, g, b, a = self.tint
        if a <= 0:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(r, g, b, a))
