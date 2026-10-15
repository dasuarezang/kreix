"""Cielo animado junto al saludo de Inicio: un sol que sube por la manana, baja por la tarde, y una luna con estrellas de noche.

El astro recorre un arco pequeno segun la hora: el sol de las 6 a las 21 (bajo y a la izquierda al amanecer, alto a
mediodia, bajo y a la derecha al atardecer, mas anaranjado cuanto mas cerca del horizonte) y la luna de las 21 a las 6.
Respira, gira sus rayos, deja pasar una nube y centellean las estrellas: poco movimiento, pero que se note vivo.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from ui import theme
from ui.widgets import charts
from core.i18n import tr

DAWN, DUSK = 6.0, 21.0            # el sol sale a las 6 y se pone a las 21
SUN_HIGH = QColor("#FFD23F")
SUN_LOW = QColor("#FF8A3D")
MOON = QColor("#F3EFE7")
SUN_HIGH_LIGHT = QColor("#F2A100")        # en el tema claro los astros se oscurecen un poco para que se vean sobre el papel
MOON_LIGHT = QColor("#7580C4")
RADIUS = 8.5                       # radio del sol y de la luna
FRAME_MS = 40                      # 25 imagenes por segundo: suficiente para un movimiento suave y barato


@dataclass(frozen=True, slots=True)
class SkyState:
    kind: str           # "sun" | "moon"
    progress: float     # 0 = sale, 1 = se pone: posicion a lo largo del arco


def sky_state(hour: float) -> SkyState:
    """Que astro se ve y en que punto de su recorrido, para una hora en decimal (14.5 = 14:30)."""
    hour %= 24
    if DAWN <= hour < DUSK:
        return SkyState("sun", (hour - DAWN) / (DUSK - DAWN))
    night = (hour - DUSK) % 24                 # horas desde las 21: de 0 a 9
    return SkyState("moon", night / (24 - DUSK + DAWN))


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


def _alpha(color: QColor, alpha: float) -> QColor:
    out = QColor(color)
    out.setAlphaF(max(0.0, min(1.0, alpha)))
    return out


class SkyWidget(QWidget):
    W, H = 92, 50                   # tamano del dibujo en coordenadas logicas
    SCALE = 1.15                    # y cuanto se amplia en pantalla
    BASE = 46                       # la linea del horizonte

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(round(self.W * self.SCALE), round(self.H * self.SCALE))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._hour = 12.0
        self._animated = True
        self._phase = 0.0
        self._start = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self._refresh_description()

    # -- estado ------------------------------------------------------------
    @property
    def state(self) -> SkyState:
        return sky_state(self._hour)

    @property
    def kind(self) -> str:
        return self.state.kind

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    def set_hour(self, hour: float) -> None:
        self._hour = hour
        self._refresh_description()
        self.update()

    def set_animated(self, on: bool) -> None:
        self._animated = on
        self._sync_timer()
        self.update()

    def _refresh_description(self) -> None:
        state = self.state
        text = tr("Es de día: sol") if state.kind == "sun" else tr("Es de noche: luna")
        self.setAccessibleName(tr("Cielo"))
        self.setAccessibleDescription(text)
        self.setToolTip("")

    def sizeHint(self) -> QSize:
        return QSize(round(self.W * self.SCALE), round(self.H * self.SCALE))

    # -- animacion: solo corre mientras se ve ---------------------------------
    def _sync_timer(self) -> None:
        if self._animated and charts.ANIMATIONS and self.isVisible():
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def _tick(self) -> None:
        self._phase = time.monotonic() - self._start
        self.update()

    # -- pintado --------------------------------------------------------------
    def _arc_point(self, progress: float) -> QPointF:
        """El astro sale por el horizonte (izquierda), sube hasta lo alto del arco y se pone por el otro lado (derecha):
        al principio y al final del recorrido su centro queda por debajo del horizonte, oculto."""
        low = self.BASE + RADIUS + 4
        high = 18.0
        x = 12 + progress * (self.W - 24)
        y = low - math.sin(math.pi * progress) ** 0.85 * (low - high)
        return QPointF(x, y)

    def paintEvent(self, _event) -> None:
        pal = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(self.SCALE, self.SCALE)
        t = self._phase if (self._animated and charts.ANIMATIONS) else 0.0
        state = self.state
        self._paint_horizon(p, pal)
        p.setClipRect(QRectF(0, 0, self.W, self.BASE + 2))     # lo que queda bajo el horizonte no se ve: sale y se pone
        if state.kind == "sun":
            self._paint_sun(p, pal, state.progress, t)
        else:
            self._paint_moon(p, pal, state.progress, t)

    def _paint_horizon(self, p: QPainter, pal) -> None:
        pen = QPen(_alpha(QColor(pal.muted), 0.35), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(6, self.BASE + 2), QPointF(self.W - 6, self.BASE + 2))

    def _elevation(self, center: QPointF) -> float:
        """0 cuando el astro esta del todo bajo el horizonte y 1 cuando ya asoma por completo: sirve para que el brillo
        y los rayos aparezcan poco a poco al salir y se apaguen al ponerse (sin 'dientes' sueltos sobre la linea)."""
        return max(0.0, min(1.0, (self.BASE + RADIUS + 4 - center.y()) / (RADIUS * 2.4)))

    def _paint_sun(self, p: QPainter, pal, progress: float, t: float) -> None:
        low = 1 - math.sin(math.pi * progress) ** 0.55         # 0 a mediodia, 1 en el horizonte
        high = SUN_HIGH_LIGHT if pal.name == "light" else SUN_HIGH
        color = _mix(high, SUN_LOW, low * 1.15)
        center = self._arc_point(progress) + QPointF(0, math.sin(t * 1.3) * 1.3)   # un ligero vaiven
        radius = RADIUS

        vis = self._elevation(center)
        pulse = 1 + 0.07 * math.sin(t * 2.2)
        glow = QRadialGradient(center, 26 * pulse)
        glow.setColorAt(0.0, _alpha(color, 0.55 * vis))
        glow.setColorAt(0.45, _alpha(color, 0.16 * vis))
        glow.setColorAt(1.0, _alpha(color, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(center, 26 * pulse, 26 * pulse)

        angle = t * 0.35                                       # los rayos giran muy despacio
        ray = QPen(_alpha(color, 0.9 * vis), 2.2)
        ray.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(ray)
        for i in range(10):
            a = angle + i * math.tau / 10
            reach = 4.5 + 1.6 * math.sin(t * 2.2 + i * 0.9)
            c, s = math.cos(a), math.sin(a)
            p.drawLine(center + QPointF(c * (radius + 3.5), s * (radius + 3.5)),
                       center + QPointF(c * (radius + 3.5 + reach), s * (radius + 3.5 + reach)))

        disc = QRadialGradient(center - QPointF(2.5, 3), radius * 1.5)
        disc.setColorAt(0.0, _mix(color, QColor("#FFFFFF"), 0.45))
        disc.setColorAt(1.0, color)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(disc)
        p.drawEllipse(center, radius, radius)

        self._paint_cloud(p, pal, t)

    def _paint_cloud(self, p: QPainter, pal, t: float) -> None:
        """Una nube suave cruza el cielo cada medio minuto, por delante del sol, y se funde en los bordes."""
        span = self.W + 44
        x = ((t * 3.2) % span) - 28
        fade = max(0.0, min(1.0, (x + 6) / 18, (self.W - x - 20) / 18))
        if fade <= 0:
            return
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, round(70 * fade)))
        for dx, dy, r in ((4, 0, 4.5), (10, -3, 5.5), (17, -1, 4.8), (23, 0, 3.8)):
            p.drawEllipse(QPointF(x + dx, 15 + dy), r, r)
        p.drawRoundedRect(QRectF(x, 15, 26, 5), 2.5, 2.5)

    def _paint_moon(self, p: QPainter, pal, progress: float, t: float) -> None:
        moon_color = MOON_LIGHT if pal.name == "light" else MOON
        center = self._arc_point(progress) + QPointF(0, math.sin(t * 1.0) * 1.2)
        radius = RADIUS
        night_fade = min(1.0, math.sin(math.pi * progress) * 2.4)     # al anochecer y al amanecer hay menos estrellas

        stars = ((14, 12, 0.0), (30, 22, 1.7), (58, 9, 3.1), (76, 21, 4.4), (68, 38, 2.3), (22, 36, 5.2))
        for x, y, shift in stars:
            twinkle = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(t * 1.8 + shift)) ** 2
            size = 1.6 + 0.9 * twinkle
            pen = QPen(_alpha(moon_color, twinkle * 0.9 * night_fade), 1.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(x - size, y), QPointF(x + size, y))
            p.drawLine(QPointF(x, y - size), QPointF(x, y + size))

        vis = self._elevation(center)
        glow = QRadialGradient(center, 24)
        glow.setColorAt(0.0, QColor(130, 150, 240, round(90 * vis)))
        glow.setColorAt(1.0, QColor(130, 150, 240, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(center, 24, 24)

        moon = QPainterPath()
        moon.addEllipse(center, radius, radius)
        bite = QPainterPath()
        bite.addEllipse(center + QPointF(4.2, -2.6), radius * 0.86, radius * 0.86)
        crescent = moon.subtracted(bite)
        p.setBrush(moon_color)
        p.drawPath(crescent)
