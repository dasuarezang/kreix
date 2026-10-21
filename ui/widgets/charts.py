"""Graficos propios de Kreix, pintados con QPainter.

Se dibujan a mano (en vez de usar QtCharts) para controlar el estilo: barras con esquinas redondeadas y
degradado, curvas suaves con relleno degradado, donut con segmentos redondeados y leyenda con importes,
barras de categorias en forma de pildora. Todos animan su entrada y muestran una tarjeta de detalle al pasar
el raton. Usan la paleta y las tipografias del tema activo.
"""
from __future__ import annotations

import math
from ui import blur
from ui.blur import draw_text
from bisect import bisect_left
from types import SimpleNamespace
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from core.account_metrics import CategoryAmount
from core.metrics import AllocationSlice, MonthlyFlow, WealthPoint
from ui import fonts, theme
from ui.format import category_label, fmt_date, fmt_eur, fmt_pct, month_long, month_short
from ui.theme import Palette
from core.i18n import months_short, tr, N_

ANIMATIONS = True    # las pruebas lo desactivan: la animacion no aporta y las ralentiza
MAX_CATEGORIES = 8


# ============================================================================ utilidades
def nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    """Marcas de eje 'redondas' que cubren [low, high]."""
    if high <= low:
        high = low + 1.0
    raw = (high - low) / max(count, 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if raw <= m * magnitude)
    first = math.floor(low / step) * step
    n = int(round((math.ceil(high / step) * step - first) / step))
    return [first + i * step for i in range(n + 1)]


def axis_label(value: float) -> str:
    """Etiqueta corta de eje: 1500 -> '1,5k'. En modo privacidad, difuminada: los ejes tambien dicen cuanto dinero hay."""
    from ui.format import is_private

    if is_private():
        return blur.mark("8,8k")
    sign = "−" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000:
        text = f"{v / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    elif v >= 1000:
        text = f"{v / 1000:.1f}".rstrip("0").rstrip(".") + "k"
    else:
        text = f"{v:g}"
    return sign + text.replace(".", ",")


def color(pal: Palette, key: str, alpha: int = 255) -> QColor:
    c = QColor(getattr(pal, key, key))
    c.setAlpha(alpha)
    return c


def monotone_path(points: Sequence[QPointF]) -> QPainterPath:
    """Curva suave que pasa por los puntos sin pasarse (interpolacion monotona: no inventa picos ni valores negativos)."""
    return monotone_path_xy([p.x() for p in points], [p.y() for p in points])


def monotone_path_xy(xs: Sequence[float], ys: Sequence[float]) -> QPainterPath:
    """Lo mismo con listas de coordenadas (sin crear un QPointF por punto y por tangente: con miles de puntos es mucho mas rapido)."""
    path = QPainterPath()
    n = len(xs)
    if n == 0:
        return path
    path.moveTo(xs[0], ys[0])
    if n == 1:
        return path
    dx = [xs[i + 1] - xs[i] for i in range(n - 1)]
    slope = [(ys[i + 1] - ys[i]) / dx[i] if dx[i] else 0.0 for i in range(n - 1)]
    tangent = [slope[0]]
    for i in range(1, n - 1):
        a, b = slope[i - 1], slope[i]
        tangent.append(0.0 if a * b <= 0 else 2 * a * b / (a + b))
    tangent.append(slope[-1])
    cubic = path.cubicTo
    for i in range(n - 1):
        h = dx[i] / 3.0
        cubic(xs[i] + h, ys[i] + tangent[i] * h, xs[i + 1] - h, ys[i + 1] - tangent[i + 1] * h, xs[i + 1], ys[i + 1])
    return path


def decimate(xs: Sequence[float], ys: Sequence[float], buckets: int) -> tuple[list[float], list[float]]:
    """Reduce una serie larga a unos pocos puntos por cubeta de pantalla conservando los extremos (el primero, el ultimo y el
    minimo y el maximo de cada cubeta): a escala de pixel el trazo es el mismo, con muchos menos puntos que calcular."""
    n = len(xs)
    if n <= buckets * 4 or buckets < 1:
        return list(xs), list(ys)
    size = n / buckets
    keep: list[int] = [0]
    for b in range(buckets):
        lo, hi = int(b * size), min(int((b + 1) * size), n)
        if hi <= lo:
            continue
        chunk = ys[lo:hi]
        low, high = lo + chunk.index(min(chunk)), lo + chunk.index(max(chunk))
        keep.extend(sorted({low, high}))
    keep.append(n - 1)
    ordered = sorted(set(keep))
    return [xs[i] for i in ordered], [ys[i] for i in ordered]


def rounded_top(rect: QRectF, radius: float) -> QPainterPath:
    """Rectangulo con solo las esquinas superiores redondeadas (el pie de una barra)."""
    r = max(0.0, min(radius, rect.width() / 2, rect.height()))
    path = QPainterPath()
    path.moveTo(rect.left(), rect.bottom())
    path.lineTo(rect.left(), rect.top() + r)
    path.quadTo(rect.left(), rect.top(), rect.left() + r, rect.top())
    path.lineTo(rect.right() - r, rect.top())
    path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + r)
    path.lineTo(rect.right(), rect.bottom())
    path.closeSubpath()
    return path


# ============================================================================ base
class BaseChart(QWidget):
    EMPTY_TEXT = N_("Sin datos todavía")

    def __init__(self, min_height: int = 260) -> None:
        super().__init__()
        self.setMinimumHeight(min_height)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._progress = 1.0
        self._mouse: QPointF | None = None
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(750)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_progress)

    # -- animacion ---------------------------------------------------------
    def _on_progress(self, value) -> None:
        self._progress = float(value)
        self.update()

    def _restart_animation(self) -> None:
        self._anim.stop()
        if ANIMATIONS:
            self._progress = 0.0
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.start()
        else:
            self._progress = 1.0
        self.update()

    def refresh_theme(self) -> None:
        self.update()

    # -- raton -------------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:
        self._mouse = event.position()
        self.update()

    def leaveEvent(self, event) -> None:
        self._mouse = None
        self.update()

    # -- pintado -----------------------------------------------------------
    @property
    def has_data(self) -> bool:  # pragma: no cover - lo define cada grafico
        raise NotImplementedError

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.current()
        if self.has_data:
            self.paint_chart(painter, pal)
        else:
            self._paint_empty(painter, pal)

    def paint_chart(self, p: QPainter, pal: Palette) -> None:  # pragma: no cover
        raise NotImplementedError

    def _paint_empty(self, p: QPainter, pal: Palette) -> None:
        """Tres franjas inclinadas (el motivo del logotipo) y un mensaje."""
        cx, cy = self.width() / 2, self.height() / 2 - 12
        p.setPen(Qt.PenStyle.NoPen)
        for i, alpha in enumerate((150, 100, 60)):
            c = color(pal, "muted", alpha)
            p.setBrush(c)
            x = cx - 22 + i * 16
            path = QPainterPath()
            path.moveTo(x + 10, cy - 14)
            path.lineTo(x + 18, cy - 14)
            path.lineTo(x + 6, cy + 14)
            path.lineTo(x - 2, cy + 14)
            path.closeSubpath()
            p.drawPath(path)
        p.setFont(fonts.qfont(fonts.BODY_MEDIUM, 13))
        p.setPen(color(pal, "muted"))
        draw_text(p, QRectF(10, cy + 24, self.width() - 20, 30), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   tr(self.EMPTY_TEXT))

    # -- piezas comunes ----------------------------------------------------
    def draw_legend(self, p: QPainter, pal: Palette, items: Sequence[tuple[str, QColor]], x: float, y: float) -> float:
        """Leyenda en una fila: punto de color + nombre. Devuelve el ancho usado."""
        font = fonts.qfont(fonts.BODY_MEDIUM, 12)
        p.setFont(font)
        fm = QFontMetricsF(font)
        cursor = x
        for name, c in items:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(QRectF(cursor, y - 4, 10, 10), 3, 3)
            p.setPen(color(pal, "muted"))
            draw_text(p, QPointF(cursor + 16, y + 5), name)
            cursor += 16 + fm.horizontalAdvance(name) + 20
        return cursor - x

    def draw_tooltip(self, p: QPainter, pal: Palette, title: str, rows: Sequence[tuple[QColor | None, str, str]]) -> None:
        """Tarjeta de detalle junto al cursor: titulo y filas (punto, etiqueta, valor)."""
        if self._mouse is None:
            return
        title_font, label_font, value_font = (fonts.qfont(fonts.BODY_MEDIUM, 12), fonts.qfont(fonts.BODY, 12),
                                              fonts.qfont(fonts.BODY_MEDIUM, 12))
        tfm, lfm, vfm = QFontMetricsF(title_font), QFontMetricsF(label_font), QFontMetricsF(value_font)
        row_h, pad = 20.0, 12.0
        label_w = max((lfm.horizontalAdvance(r[1]) for r in rows), default=0)
        value_w = max((vfm.horizontalAdvance(r[2]) for r in rows), default=0)
        width = max(tfm.horizontalAdvance(title), 16 + label_w + 18 + value_w) + 2 * pad
        height = pad * 2 + 18 + row_h * len(rows) - (4 if rows else 0)
        x = self._mouse.x() + 16
        y = self._mouse.y() - height / 2
        if x + width > self.width() - 4:
            x = self._mouse.x() - 16 - width
        x = max(4.0, x)
        y = min(max(4.0, y), self.height() - height - 4)
        rect = QRectF(x, y, width, height)
        p.setPen(Qt.PenStyle.NoPen)
        p.setPen(QPen(color(pal, "field_edge"), 1))                 # sin sombra: el filo basta para separarlo del grafico
        p.setBrush(color(pal, "surface_alt"))
        p.drawRoundedRect(rect, 6, 6)
        mark = QLinearGradient(x + pad, 0, x + pad + 22, 0)         # el trazo de marca, amarillo a rojo, sobre el titulo
        mark.setColorAt(0.0, color(pal, "accent"))
        mark.setColorAt(1.0, color(pal, "red"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(mark)
        p.drawRoundedRect(QRectF(x + pad, y + 5, 22, 3), 1.5, 1.5)
        p.setFont(title_font)
        p.setPen(color(pal, "text"))
        draw_text(p, QPointF(x + pad, y + pad + 11), title)
        yy = y + pad + 26
        for dot, label, value in rows:
            if dot is not None:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(dot)
                p.drawEllipse(QRectF(x + pad, yy - 8, 8, 8))
            p.setFont(label_font)
            p.setPen(color(pal, "muted"))
            draw_text(p, QPointF(x + pad + 16, yy), label)
            p.setFont(value_font)
            p.setPen(color(pal, "text"))
            draw_text(p, QPointF(x + width - pad - vfm.horizontalAdvance(value), yy), value)
            yy += row_h


# ============================================================================ barras (apiladas o agrupadas)
@dataclass(frozen=True, slots=True)
class BarSeries:
    name: str
    color_key: str
    values: list[float]


class BarsChart(BaseChart):
    def __init__(self, stacked: bool, min_height: int = 280) -> None:
        super().__init__(min_height)
        self._stacked = stacked
        self._labels: list[str] = []
        self._titles: list[str] = []
        self._series: list[BarSeries] = []

    @property
    def has_data(self) -> bool:
        return bool(self._labels)

    def set_bars(self, labels: list[str], titles: list[str], series: list[BarSeries]) -> None:
        self._labels, self._titles, self._series = labels, titles, series
        self._restart_animation()

    def _column_totals(self) -> list[float]:
        n = len(self._labels)
        if self._stacked:
            return [sum(s.values[i] for s in self._series) for i in range(n)]
        return [max(s.values[i] for s in self._series) for i in range(n)]

    def paint_chart(self, p: QPainter, pal: Palette) -> None:
        n = len(self._labels)
        top_pad, bottom_pad = 34, 26
        ticks = nice_ticks(0, max(max(self._column_totals(), default=0), 1) * 1.04, 4)
        axis_font = fonts.qfont(fonts.BODY, 12)
        fm = QFontMetricsF(axis_font)
        left_pad = max(fm.horizontalAdvance(axis_label(t)) for t in ticks) + 14
        plot = QRectF(left_pad, top_pad, self.width() - left_pad - 6, self.height() - top_pad - bottom_pad)
        top = ticks[-1]

        self.draw_legend(p, pal, [(s.name, color(pal, s.color_key)) for s in self._series], left_pad, 14)

        # cuadricula y eje
        p.setFont(axis_font)
        for t in ticks:
            y = plot.bottom() - plot.height() * (t / top)
            p.setPen(QPen(color(pal, "grid" if t else "border"), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(color(pal, "muted"))
            draw_text(p, QRectF(0, y - 9, left_pad - 8, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       axis_label(t))

        slot = plot.width() / n
        hover = self._hover_index(plot, slot)
        n_groups = 1 if self._stacked else len(self._series)
        group_w = min(slot * (0.40 if self._stacked else 0.56), 40 if self._stacked else 64)
        bar_w = group_w if self._stacked else (group_w - 4 * (n_groups - 1)) / n_groups

        for i in range(n):
            cx = plot.left() + slot * (i + 0.5)
            if i == hover:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color(pal, "hover"))
                p.drawRoundedRect(QRectF(cx - slot / 2 + 3, plot.top() - 6, slot - 6, plot.height() + 6), 4, 4)
            local = max(0.0, min(1.0, self._progress * 1.35 - i * 0.025))
            grow = 1 - (1 - local) ** 3
            y_cursor = plot.bottom()
            for j, s in enumerate(self._series):
                value = s.values[i]
                if value <= 0:
                    continue
                height = plot.height() * (value / top) * grow
                if self._stacked:
                    rect = QRectF(cx - bar_w / 2, y_cursor - height, bar_w, height)
                    y_cursor -= height + 1.5
                else:
                    x0 = cx - group_w / 2 + j * (bar_w + 4)
                    rect = QRectF(x0, plot.bottom() - height, bar_w, height)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color(pal, s.color_key))
                top_segment = (not self._stacked) or all(t.values[i] <= 0 for t in self._series[j + 1:])
                p.drawPath(rounded_top(rect, 2 if top_segment else 0))
            p.setFont(fonts.qfont(fonts.BODY_MEDIUM if i == hover else fonts.BODY, 12))
            p.setPen(color(pal, "text" if i == hover else "muted"))
            draw_text(p, QRectF(cx - slot / 2, plot.bottom() + 6, slot, 18), Qt.AlignmentFlag.AlignCenter, self._labels[i])

        if hover is not None:
            rows = [(color(pal, s.color_key), s.name, fmt_eur(s.values[hover])) for s in self._series]
            if self._stacked and len(self._series) > 1:
                rows.append((None, tr("Total"), fmt_eur(sum(s.values[hover] for s in self._series))))
            self.draw_tooltip(p, pal, self._titles[hover], rows)

    def _hover_index(self, plot: QRectF, slot: float) -> int | None:
        if self._mouse is None or not plot.adjusted(0, -10, 0, 30).contains(self._mouse):
            return None
        index = int((self._mouse.x() - plot.left()) // slot)
        return index if 0 <= index < len(self._labels) else None


class FlowChart(BarsChart):
    """Inicio: ingresos, gastos y aportaciones a inversion, apilados por mes."""

    EMPTY_TEXT = N_("Importa un extracto para ver el flujo de caja")

    def __init__(self) -> None:
        super().__init__(stacked=True, min_height=300)

    def set_data(self, flows: list[MonthlyFlow], contributions: bool = True) -> None:
        series = [BarSeries(tr("Ingresos"), "accent", [float(f.income) for f in flows]),
                  BarSeries(tr("Gastos"), "red", [float(f.expenses) for f in flows])]
        if contributions:                                   # sin inversiones no hay aportaciones que mostrar
            series.append(BarSeries(tr("Aportaciones"), "neutral", [float(f.contributions) for f in flows]))
        self.set_bars([month_short(f.month)[:3] for f in flows], [month_long(f.month).capitalize() for f in flows],
                      series if flows else [])


class IncomeExpenseChart(BarsChart):
    """Cuentas: ingresos frente a gastos de cada mes (agrupadas)."""

    EMPTY_TEXT = N_("Importa un extracto para ver los meses")

    def __init__(self) -> None:
        super().__init__(stacked=False, min_height=280)

    def set_data(self, flows: list[MonthlyFlow]) -> None:
        flows = flows[-12:]
        self.set_bars(
            [month_short(f.month)[:3] for f in flows],
            [month_long(f.month).capitalize() for f in flows],
            [BarSeries(tr("Ingresos"), "accent", [float(f.income) for f in flows]),
             BarSeries(tr("Gastos"), "red", [float(f.expenses) for f in flows])] if flows else [],
        )


# ============================================================================ lineas suaves
@dataclass(frozen=True, slots=True)
class LineSeries:
    name: str
    color_key: str
    values: list[float]
    width: float = 1.8
    dashed: bool = False
    fill: bool = False


class LineChart(BaseChart):
    def __init__(self, min_height: int = 300, daily: bool = False) -> None:
        super().__init__(min_height)
        self._xs: list[date] = []
        self._series: list[LineSeries] = []
        self._daily = daily
        self._include_zero = True
        self._epoch = 0                                    # sube con cada cambio de datos: invalida la geometria guardada
        self._geo: SimpleNamespace | None = None
        self._geo_key: tuple | None = None

    @property
    def has_data(self) -> bool:
        return bool(self._xs)

    def set_lines(self, xs: list[date], series: list[LineSeries], daily: bool = False, include_zero: bool = True,
                  animate: bool = True) -> None:
        self._xs, self._series, self._daily, self._include_zero = xs, series, daily, include_zero
        self._epoch += 1
        self._geo = None
        if animate:
            self._restart_animation()
        else:
            self.update()                                  # solo cambian los colores (cambio de tema): sin repetir la entrada

    def _use_days(self) -> bool:
        """Etiquetas por dia si el rango es corto; por mes si es largo."""
        if self._daily:
            return True
        return len(self._xs) > 1 and (self._xs[-1] - self._xs[0]).days <= 75

    def _x_label(self, d: date) -> str:
        return f"{d.day} {months_short()[d.month - 1]}" if self._use_days() else month_short(d)

    # -- geometria: solo cambia con el tamano o con los datos, no con el raton ni con la animacion ----------------------
    def _geometry(self) -> SimpleNamespace:
        key = (self.width(), self.height(), self._epoch)
        if self._geo is not None and self._geo_key == key:
            return self._geo
        values = [v for s in self._series for v in s.values]
        low = min(0.0, min(values)) if self._include_zero else min(values)
        high = max(values)
        ticks = nice_ticks(low, high * 1.04 if high > 0 else 1, 4)
        low, high = ticks[0], ticks[-1]
        axis_font = fonts.qfont(fonts.BODY, 12)
        fm = QFontMetricsF(axis_font)
        left_pad = max(fm.horizontalAdvance(axis_label(t)) for t in ticks) + 14
        top_pad, bottom_pad = 34, 28
        plot = QRectF(left_pad + 6, top_pad, self.width() - left_pad - 20, self.height() - top_pad - bottom_pad)

        def y_of(v: float) -> float:
            return plot.bottom() - plot.height() * ((v - low) / (high - low))

        n = len(self._xs)
        ordinals = [d.toordinal() for d in self._xs]
        span = (ordinals[-1] - ordinals[0]) or 1
        xs_px = [plot.center().x()] if n == 1 else [plot.left() + plot.width() * (o - ordinals[0]) / span for o in ordinals]
        count = min(n, max(2, int(plot.width() // 95)))
        shown = sorted({round(k * (n - 1) / (count - 1)) for k in range(count)}) if n > 1 else [0]
        drawn = []                                          # por serie: sus puntos, la linea y (si lleva relleno) el area
        scale_y = plot.height() / (high - low)
        bottom = plot.bottom()
        for s in sorted(self._series, key=lambda s: not s.fill):          # el relleno, debajo de las lineas
            ys_px = [bottom - scale_y * (v - low) for v in s.values]
            pts = [QPointF(x, y) for x, y in zip(xs_px, ys_px)] if n <= 4 else []     # solo se pintan con pocos puntos
            line = QPainterPath()
            area = None
            if n > 1:
                # con miles de puntos (un saldo diario de anos) basta con unos pocos por pixel: ver `decimate`
                px, py = decimate(xs_px, ys_px, max(int(plot.width() * 0.6), 40))
                line = monotone_path_xy(px, py)
                if s.fill:
                    area = QPainterPath(line)
                    area.lineTo(px[-1], bottom)
                    area.lineTo(px[0], bottom)
                    area.closeSubpath()
            drawn.append((s, pts, line, area))
        self._geo_key = key
        self._geo = SimpleNamespace(ticks=ticks, axis_font=axis_font, left_pad=left_pad, plot=plot, y_of=y_of, n=n,
                                    xs_px=xs_px, shown=shown, drawn=drawn)
        return self._geo

    def paint_chart(self, p: QPainter, pal: Palette) -> None:
        g = self._geometry()
        plot, n, y_of, xs_px = g.plot, g.n, g.y_of, g.xs_px
        self.draw_legend(p, pal, [(s.name, color(pal, s.color_key)) for s in self._series], g.left_pad, 14)

        p.setFont(g.axis_font)
        for t in g.ticks:
            y = y_of(t)
            p.setPen(QPen(color(pal, "grid" if t else "border"), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(color(pal, "muted"))
            draw_text(p, QRectF(0, y - 9, g.left_pad - 2, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       axis_label(t))

        # etiquetas del eje X: unas pocas, repartidas
        shown = g.shown
        hover = self._nearest(xs_px, n)
        p.setFont(g.axis_font)
        for i in shown:
            p.setPen(color(pal, "text" if i == hover else "muted"))
            align = (Qt.AlignmentFlag.AlignLeft if i == shown[0] else Qt.AlignmentFlag.AlignRight if i == shown[-1]
                     else Qt.AlignmentFlag.AlignHCenter) if n > 1 else Qt.AlignmentFlag.AlignHCenter
            w = 70.0
            x = xs_px[i]
            left = x if align == Qt.AlignmentFlag.AlignLeft else x - w if align == Qt.AlignmentFlag.AlignRight else x - w / 2
            draw_text(p, QRectF(left, plot.bottom() + 8, w, 18), align, self._x_label(self._xs[i]))

        # revelado de izquierda a derecha
        p.save()
        p.setClipRect(QRectF(plot.left() - 8, 0, (plot.width() + 24) * self._progress, self.height()))
        for s, pts, line, area in g.drawn:
            base = color(pal, s.color_key)
            if area is not None:
                fill = QColor(base)
                fill.setAlpha(18)                                   # relleno plano y tenue, sin degradado
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(fill)
                p.drawPath(area)
            pen = QPen(base, s.width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            if s.dashed:
                pen.setStyle(Qt.PenStyle.CustomDashLine)
                pen.setDashPattern([2.2, 3.2])
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(line)
            if n == 1 or (n <= 4 and s.fill):
                p.setPen(QPen(color(pal, "surface"), 2))
                p.setBrush(base)
                for pt in pts:
                    p.drawEllipse(pt, 3.4, 3.4)
        p.restore()

        # punto final destacado (halo) en la serie principal
        main = next((s for s in self._series if s.fill), self._series[0])
        end = QPointF(xs_px[n - 1], y_of(main.values[-1]))
        if self._progress > 0.98 and hover is None:
            halo = color(pal, main.color_key, 60)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(end, 7, 7)
            p.setBrush(color(pal, main.color_key))
            p.setPen(QPen(color(pal, "surface"), 2))
            p.drawEllipse(end, 3.8, 3.8)

        if hover is not None:
            x = xs_px[hover]
            p.setPen(QPen(color(pal, "muted", 120), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            for s in self._series:
                p.setPen(QPen(color(pal, "surface"), 2))
                p.setBrush(color(pal, s.color_key))
                p.drawEllipse(QPointF(x, y_of(s.values[hover])), 4, 4)
            title = fmt_date(self._xs[hover]) if self._use_days() else month_long(self._xs[hover]).capitalize()
            self.draw_tooltip(p, pal, title, [(color(pal, s.color_key), s.name, fmt_eur(s.values[hover]))
                                              for s in self._series])

    def _nearest(self, xs_px: list[float], n: int) -> int | None:
        """El punto mas cercano al raton (los x van en orden: biseccion en vez de recorrerlos todos)."""
        if self._mouse is None or n == 0:
            return None
        if not (0 <= self._mouse.y() <= self.height()):
            return None
        x = self._mouse.x()
        i = bisect_left(xs_px, x)
        if i == 0:
            return 0
        if i == n:
            return n - 1
        return i - 1 if abs(xs_px[i - 1] - x) <= abs(xs_px[i] - x) else i


class WealthChart(LineChart):
    """Inicio: patrimonio neto (relleno), valor de la cartera y lo aportado."""

    EMPTY_TEXT = N_("Importa tus extractos para ver la evolución")

    def set_data(self, points: list[WealthPoint], value_line: bool = True, contributions: bool = True) -> None:
        """`value_line`: la linea del valor de la cartera (solo tiene sentido junto a las cuentas); `contributions`: lo aportado
        (solo si interesan las inversiones)."""
        if not points:
            self.set_lines([], [])
            return
        series = [LineSeries(tr("Patrimonio neto"), "accent", [float(w.net_worth) for w in points], 1.9, fill=True)]
        if value_line:
            series.append(LineSeries(tr("Valor de la cartera"), "text", [float(w.invested_value) for w in points], 1.3))
        if contributions:
            series.append(LineSeries(tr("Aportado"), "neutral", [float(w.contributions) for w in points], 1.2, dashed=True))
        self.set_lines([w.date for w in points], series)


class PortfolioChart(LineChart):
    """Inversiones: valor de la cartera (relleno) frente a lo aportado."""

    EMPTY_TEXT = N_("Importa tus operaciones para ver la evolución")

    def set_data(self, points: list[WealthPoint]) -> None:
        if not points:
            self.set_lines([], [])
            return
        self.set_lines([w.date for w in points], [
            LineSeries(tr("Valor de la cartera"), "accent", [float(w.invested_value) for w in points], 1.9, fill=True),
            LineSeries(tr("Aportado"), "neutral", [float(w.contributions) for w in points], 1.2, dashed=True),
        ])


class FundsChart(LineChart):
    """Inversiones: el valor de cada fondo de la cartera mes a mes. Con un fondo elegido, su valor frente a lo aportado."""

    EMPTY_TEXT = N_("Importa tus operaciones y tu cartera para ver cada fondo")

    def __init__(self) -> None:
        super().__init__()
        self._funds: list = []
        self._only: str | None = None

    def set_data(self, funds: list, only: str | None = None) -> None:
        """`funds`: lista de FundHistory; `only`: ISIN del fondo a mostrar solo (None = todos a la vez)."""
        self._funds, self._only = funds, only
        self._apply()

    def refresh_theme(self) -> None:
        self._apply(animate=False)          # los colores de cada fondo salen de la paleta del tema
        super().refresh_theme()

    def _apply(self, animate: bool = True) -> None:
        shown = [f for f in self._funds if self._only in (None, f.isin)]
        if not shown or not shown[0].points:
            self.set_lines([], [], animate=animate)
            return
        xs = [w.date for w in shown[0].points]
        if len(shown) == 1:
            f = shown[0]
            self.set_lines(xs, [
                LineSeries(f.name, "accent", [float(w.invested_value) for w in f.points], 1.9, fill=True),
                LineSeries(tr("Aportado"), "neutral", [float(w.contributions) for w in f.points], 1.2, dashed=True),
            ], animate=animate)
            return
        palette = theme.current().series
        self.set_lines(xs, [LineSeries(f.name, palette[i % len(palette)], [float(w.invested_value) for w in f.points], 1.7)
                            for i, f in enumerate(shown)], animate=animate)


class BalanceChart(LineChart):
    """Cuentas: saldo al cierre de cada dia con movimientos."""

    EMPTY_TEXT = N_("Sin movimientos en este periodo")

    def __init__(self) -> None:
        super().__init__(min_height=300)

    def set_data(self, points: list[tuple[date, object]], daily: bool = False) -> None:
        if not points:
            self.set_lines([], [])
            return
        self.set_lines([d for d, _ in points], [LineSeries(tr("Saldo"), "accent", [float(v) for _, v in points], 1.9, fill=True)],
                       daily=daily)


class Sparkline(BaseChart):
    """Mini curva sin ejes (para las tarjetas grandes)."""

    def __init__(self, color_key: str = "accent") -> None:
        super().__init__(min_height=56)
        self._values: list[float] = []
        self._color_key = color_key

    @property
    def has_data(self) -> bool:
        return len(self._values) > 1

    def set_values(self, values: list[float]) -> None:
        self._values = values
        self._restart_animation()

    def _paint_empty(self, p: QPainter, pal: Palette) -> None:
        return

    def paint_chart(self, p: QPainter, pal: Palette) -> None:
        lo, hi = min(self._values), max(self._values)
        span = (hi - lo) or 1.0
        n = len(self._values)
        rect = QRectF(4, 6, self.width() - 8, self.height() - 12)
        pts = [QPointF(rect.left() + rect.width() * i / (n - 1), rect.bottom() - rect.height() * (v - lo) / span)
               for i, v in enumerate(self._values)]
        base = color(pal, self._color_key)
        p.save()
        p.setClipRect(QRectF(0, 0, self.width() * self._progress, self.height()))
        area = QPainterPath(monotone_path(pts))
        area.lineTo(pts[-1].x(), self.height())
        area.lineTo(pts[0].x(), self.height())
        area.closeSubpath()
        fill = QColor(base)
        fill.setAlpha(22)                                           # relleno plano y tenue, sin degradado
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawPath(area)
        p.setPen(QPen(base, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(monotone_path(pts))
        p.restore()
        if self._progress > 0.98:
            p.setPen(QPen(color(pal, "surface"), 2))
            p.setBrush(base)
            p.drawEllipse(pts[-1], 3.4, 3.4)


# ============================================================================ donut
class DonutChart(BaseChart):
    EMPTY_TEXT = N_("Importa tus extractos para ver la distribución")
    LEGEND_MIN_WIDTH = 420

    def __init__(self) -> None:
        super().__init__(min_height=300)
        self._slices: list[AllocationSlice] = []
        self._geometry: tuple[QPointF, float, float] | None = None
        self._angles: list[tuple[float, float]] = []

    @property
    def has_data(self) -> bool:
        return sum((s.value for s in self._slices), start=0) > 0

    def set_data(self, slices: list[AllocationSlice]) -> None:
        self._slices = [s for s in slices if s.value > 0]
        self._restart_animation()

    def _color(self, pal: Palette, i: int, label: str) -> QColor:
        fixed = {"Inversión": pal.accent, "Liquidez": pal.neutral}
        return QColor(fixed.get(label) or pal.series[i % len(pal.series)])

    def paint_chart(self, p: QPainter, pal: Palette) -> None:
        total = float(sum((s.value for s in self._slices), start=0))
        side_legend = self.width() >= self.LEGEND_MIN_WIDTH
        legend_h = 0 if side_legend else 26 * len(self._slices) + 8
        area = QRectF(8, 8, (self.width() * 0.5 if side_legend else self.width()) - 16, self.height() - 16 - legend_h)
        diameter = max(60.0, min(area.width(), area.height()))
        center = QPointF(area.center().x(), area.top() + diameter / 2 + max(0, (area.height() - diameter) / 2))
        thickness = diameter * 0.105
        radius = diameter / 2 - thickness / 2 - 4
        self._geometry = (center, radius, thickness)

        hover = self._hover_slice()
        # extremos siempre planos: trozos de corte limpio, como el resto de barras (los redondeados parecian pildoras)
        rounded = False
        cap = math.degrees(thickness / 2 / max(radius, 1)) if rounded else 0.0
        gap = 0.0 if len(self._slices) == 1 else (2 * cap + 3.0 if rounded else 2.4)
        start = 0.0
        self._angles = []
        rect = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
        for i, s in enumerate(self._slices):
            span = 360.0 * float(s.value) / total
            self._angles.append((start, start + span))
            visible = max(span - gap, 0.8)
            offset = (span - visible) / 2                                  # centrado dentro de su trozo
            base = self._color(pal, i, s.label)
            if hover is not None and hover != i:
                base.setAlpha(110)
            width = thickness + (4 if hover == i else 0)
            p.setPen(QPen(base, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap if rounded else Qt.PenCapStyle.FlatCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            from_angle = 90.0 - (start + offset)
            path.arcMoveTo(rect, from_angle)
            path.arcTo(rect, from_angle, -min(visible, 359.99) * self._progress)
            p.drawPath(path)
            start += span

        # cifra central
        p.setPen(color(pal, "muted"))
        p.setFont(fonts.qfont(fonts.LABEL, 10, 1.2))
        draw_text(p, QRectF(center.x() - radius, center.y() - 30, 2 * radius, 16), Qt.AlignmentFlag.AlignCenter, "TOTAL")
        value_text = fmt_eur(total, 0)
        size = 26
        while size > 12 and QFontMetricsF(fonts.qfont(fonts.DISPLAY, size)).horizontalAdvance(value_text) > 2 * radius - thickness - 6:
            size -= 1
        p.setFont(fonts.qfont(fonts.DISPLAY, size))
        p.setPen(color(pal, "text"))
        draw_text(p, QRectF(center.x() - radius, center.y() - 12, 2 * radius, 36), Qt.AlignmentFlag.AlignCenter, value_text)

        # leyenda con importes
        x0 = area.right() + 28 if side_legend else 16
        y0 = (self.height() - 46 * len(self._slices)) / 2 + 8 if side_legend else area.bottom() + 14
        for i, s in enumerate(self._slices):
            row_y = y0 + i * (46 if side_legend else 26)
            c = self._color(pal, i, s.label)
            if hover is not None and hover != i:
                c.setAlpha(110)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(QRectF(x0, row_y + 4, 10, 10), 3, 3)
            label_font = fonts.qfont(fonts.BODY_MEDIUM, 13)
            p.setFont(label_font)
            p.setPen(color(pal, "text"))
            if side_legend:
                avail = self.width() - x0 - 44
            else:
                value_font = fonts.qfont(fonts.BODY_MEDIUM, 13)
                avail = self.width() - x0 - 20 - 16 - QFontMetricsF(value_font).horizontalAdvance(
                    f"{fmt_eur(s.value)}  ·  {fmt_pct(s.weight)}") - 16
            draw_text(p, QPointF(x0 + 20, row_y + 14), QFontMetricsF(label_font).elidedText(s.label, Qt.TextElideMode.ElideRight, max(avail, 40)))
            if side_legend:
                p.setFont(fonts.qfont(fonts.LABEL, 14))
                draw_text(p, QPointF(x0 + 20, row_y + 34), fmt_eur(s.value))
                p.setFont(fonts.qfont(fonts.BODY_MEDIUM, 12))
                p.setPen(color(pal, "muted"))
                amount_w = QFontMetricsF(fonts.qfont(fonts.LABEL, 14)).horizontalAdvance(fmt_eur(s.value))
                draw_text(p, QPointF(x0 + 20 + amount_w + 10, row_y + 34), fmt_pct(s.weight))
            else:
                p.setFont(fonts.qfont(fonts.BODY_MEDIUM, 13))
                text = f"{fmt_eur(s.value)}  ·  {fmt_pct(s.weight)}"
                draw_text(p, QPointF(self.width() - 16 - QFontMetricsF(p.font()).horizontalAdvance(text), row_y + 14), text)

        if hover is not None:
            s = self._slices[hover]
            self.draw_tooltip(p, pal, s.label, [(self._color(pal, hover, s.label), tr("Importe"), fmt_eur(s.value)),
                                                (None, tr("Peso"), fmt_pct(s.weight))])

    def _hover_slice(self) -> int | None:
        if self._mouse is None or self._geometry is None or not self._angles:
            return None
        center, radius, thickness = self._geometry
        dx, dy = self._mouse.x() - center.x(), self._mouse.y() - center.y()
        distance = math.hypot(dx, dy)
        if abs(distance - radius) > thickness / 2 + 6:
            return None
        angle = (math.degrees(math.atan2(dx, -dy))) % 360.0              # desde las 12 en sentido horario
        for i, (a, b) in enumerate(self._angles):
            if a <= angle < b:
                return i
        return None


# ============================================================================ barras de categorias
class CategoryBarsChart(BaseChart):
    """Gasto por categoria: filas con barra en forma de pildora, importe y porcentaje."""

    EMPTY_TEXT = N_("Sin gastos en este periodo")
    ROW_H = 40

    @property
    def row_h(self) -> int:
        return fonts.scaled(self.ROW_H)
    category_clicked = Signal(object)      # TxCategory: el usuario quiere ver los movimientos de esa categoria

    def __init__(self) -> None:
        super().__init__(min_height=300)
        self._items: list[tuple[str, float, float]] = []      # (nombre, importe, peso)
        self._categories: list[object] = []                   # categoria de cada fila (None en "Otras categorias")

    def _row_at(self, pos: QPointF) -> int | None:
        index = int((pos.y() - 8) // self.row_h)
        return index if 0 <= index < len(self._items) else None

    def mouseMoveEvent(self, event) -> None:
        row = self._row_at(event.position())
        clickable = row is not None and self._categories[row] is not None
        self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)
        self.setToolTip(tr("Clic para ver estos movimientos") if clickable else "")
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        row = self._row_at(event.position())
        if row is not None and self._categories[row] is not None and event.button() == Qt.MouseButton.LeftButton:
            self.category_clicked.emit(self._categories[row])

    @property
    def has_data(self) -> bool:
        return bool(self._items)

    def set_data(self, items: list[CategoryAmount]) -> None:
        shown = items[:MAX_CATEGORIES]
        rows = [(category_label(i.category), float(i.amount), float(i.share)) for i in shown]
        rest = items[MAX_CATEGORIES:]
        if rest:
            rows.append((tr("Otras categorías"), float(sum(i.amount for i in rest)), float(sum(i.share for i in rest))))
        self._items = rows
        self._categories = [i.category for i in shown] + ([None] if rest else [])
        self.setMinimumHeight(max(300, 16 + self.row_h * len(rows)))
        self._restart_animation()

    def paint_chart(self, p: QPainter, pal: Palette) -> None:
        label_font = fonts.qfont(fonts.BODY_MEDIUM, 13)
        amount_font = fonts.qfont(fonts.LABEL, 13)
        lfm, afm = QFontMetricsF(label_font), QFontMetricsF(amount_font)
        label_w = min(max(lfm.horizontalAdvance(n) for n, _, _ in self._items) + 14, max(self.width() - 230, 90))
        amount_w = max(afm.horizontalAdvance(fmt_eur(a)) for _, a, _ in self._items) + 8
        pct_w = 46.0
        bar_left = label_w + 12
        bar_right = self.width() - amount_w - pct_w - 12
        top = max(self._items, key=lambda r: r[1])[1]
        hover = None
        if self._mouse is not None:
            index = int((self._mouse.y() - 8) // self.row_h)
            hover = index if 0 <= index < len(self._items) else None

        for i, (name, amount, share) in enumerate(self._items):
            y = 8 + i * self.row_h
            mid = y + self.row_h / 2
            if i == hover:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color(pal, "hover"))
                p.drawRoundedRect(QRectF(0, y + 2, self.width(), self.row_h - 4), 4, 4)
            p.setFont(label_font)
            p.setPen(color(pal, "text"))
            draw_text(p, QRectF(10, y, label_w - 10, self.row_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       lfm.elidedText(name, Qt.TextElideMode.ElideRight, label_w - 10))
            track = QRectF(bar_left, mid - 3, max(bar_right - bar_left, 10), 6)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color(pal, "surface_alt"))
            p.drawRoundedRect(track, 1.5, 1.5)
            local = max(0.0, min(1.0, self._progress * 1.4 - i * 0.07))
            fill_w = max(8.0, track.width() * (amount / top)) * (1 - (1 - local) ** 3)
            fill = QRectF(track.left(), track.top(), fill_w, track.height())
            base = color(pal, "red")
            base.setAlpha(max(150, 255 - i * 14))
            p.setBrush(base)
            p.drawRoundedRect(fill, 1.5, 1.5)
            p.setFont(amount_font)
            p.setPen(color(pal, "text"))
            draw_text(p, QRectF(bar_right + 8, y, amount_w + 4, self.row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       fmt_eur(amount))
            p.setFont(fonts.qfont(fonts.BODY_MEDIUM, 12))
            p.setPen(color(pal, "muted"))
            draw_text(p, QRectF(self.width() - pct_w - 6, y, pct_w, self.row_h),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, fmt_pct(share, 0))
