"""Graficos nativos (QtCharts). Cada grafico se redibuja entero al cambiar de tema."""
from __future__ import annotations

from datetime import date

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSet,
    QChart,
    QChartView,
    QDateTimeAxis,
    QLineSeries,
    QPieSeries,
    QStackedBarSeries,
    QValueAxis,
)
from PySide6.QtCore import QDate, QDateTime, QLocale, QMargins, QPointF, Qt, QTime
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLabel, QToolTip

from core.metrics import AllocationSlice, MonthlyFlow, WealthPoint
from ui import theme
from ui.format import fmt_eur, fmt_pct, month_long, month_short

SPANISH = QLocale(QLocale.Language.Spanish, QLocale.Country.Spain)


def _tip(widget, text: str) -> None:
    QToolTip.showText(QCursor.pos(), text, widget)


class BaseChart(QChartView):
    EMPTY_TEXT = "Sin datos todavía"

    def __init__(self, min_height: int = 280) -> None:
        super().__init__(QChart())
        chart = self.chart()
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(0, 0, 0, 0))
        chart.setLocale(SPANISH)
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(min_height)
        self._has_data = False

    # -- estilo comun ------------------------------------------------------
    def _reset(self) -> None:
        chart = self.chart()
        chart.removeAllSeries()
        for axis in chart.axes():
            chart.removeAxis(axis)
        chart.setTitle("")

    def _style_chrome(self) -> None:
        p = theme.current()
        chart = self.chart()
        legend = chart.legend()
        legend.setLabelColor(QColor(p.text))
        legend.setFont(QFont("Segoe UI", 10))
        legend.setVisible(self._has_data)
        if not self._has_data:
            chart.setTitleBrush(QColor(p.muted))
            chart.setTitleFont(QFont("Segoe UI", 11))
            chart.setTitle(self.EMPTY_TEXT)

    def _style_axis(self, axis) -> None:
        p = theme.current()
        axis.setLabelsColor(QColor(p.muted))
        axis.setLabelsFont(QFont("Segoe UI", 9))
        axis.setGridLineColor(QColor(p.border))
        axis.setLinePenColor(QColor(p.border))
        axis.setMinorGridLineVisible(False)

    def refresh_theme(self) -> None:
        self._render()

    def _render(self) -> None:  # pragma: no cover - lo implementa cada grafico
        raise NotImplementedError


# ============================================================================ donut
class DonutChart(BaseChart):
    EMPTY_TEXT = "Importa tus extractos para ver la distribución"

    def __init__(self) -> None:
        super().__init__(min_height=300)
        self._slices: list[AllocationSlice] = []
        self._center = QLabel(self)
        self._center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._center.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.chart().plotAreaChanged.connect(lambda _r: self._place_center())

    def set_data(self, slices: list[AllocationSlice]) -> None:
        self._slices = slices
        self._render()

    def _render(self) -> None:
        p = theme.current()
        self._reset()
        total = sum((s.value for s in self._slices), start=0)
        self._has_data = bool(total) and total > 0
        if self._has_data:
            series = QPieSeries()
            series.setHoleSize(0.62)
            series.setPieSize(0.92)
            colors = {"Inversión": p.accent, "Liquidez": p.neutral}
            for i, s in enumerate(self._slices):
                sl = series.append(s.label, float(s.value))
                sl.setColor(QColor(colors.get(s.label, p.red)))
                sl.setBorderColor(QColor(p.surface))
                sl.setBorderWidth(3)
                sl.setLabelVisible(False)
                sl.hovered.connect(lambda state, sl=sl, s=s: self._on_hover(sl, s, state))
                sl.setLabel(f"{s.label}  {fmt_pct(s.weight)}")
            self.chart().addSeries(series)
        self._style_chrome()
        self._center.setVisible(self._has_data)
        if self._has_data:
            self._center.setText(
                f'<div style="color:{p.muted}; font-size:12px;">Total</div>'
                f'<div style="color:{p.text}; font-size:22px; font-weight:800;">{fmt_eur(total, 0)}</div>'
            )
        self._place_center()

    def _on_hover(self, sl, s: AllocationSlice, state: bool) -> None:
        sl.setExploded(state)
        if state:
            _tip(self, f"{s.label}: {fmt_eur(s.value)} ({fmt_pct(s.weight)})")
        else:
            QToolTip.hideText()

    def _place_center(self) -> None:
        area = self.chart().plotArea()
        self._center.adjustSize()
        self._center.move(int(area.center().x() - self._center.width() / 2),
                          int(area.center().y() - self._center.height() / 2))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_center()


# ============================================================================ flujo mensual
class FlowChart(BaseChart):
    EMPTY_TEXT = "Importa un extracto para ver el flujo de caja"

    def __init__(self) -> None:
        super().__init__(min_height=300)
        self._flows: list[MonthlyFlow] = []

    def set_data(self, flows: list[MonthlyFlow]) -> None:
        self._flows = flows
        self._render()

    def _render(self) -> None:
        p = theme.current()
        self._reset()
        self._has_data = bool(self._flows)
        if self._has_data:
            specs = [
                ("Ingresos", p.accent, [f.income for f in self._flows]),
                ("Gastos", p.red, [f.expenses for f in self._flows]),
                ("Aportaciones", p.neutral, [f.contributions for f in self._flows]),
            ]
            series = QStackedBarSeries()
            series.setBarWidth(0.62)
            for name, color, values in specs:
                bar = QBarSet(name)
                bar.append([float(v) for v in values])
                bar.setColor(QColor(color))
                bar.setBorderColor(QColor(color))
                bar.hovered.connect(lambda state, idx, name=name, values=values: self._on_hover(state, idx, name, values))
                series.append(bar)
            chart = self.chart()
            chart.addSeries(series)

            axis_x = QBarCategoryAxis()
            axis_x.append([month_short(f.month)[:3] for f in self._flows])  # el ano va en el tooltip
            axis_x.setLabelsFont(QFont("Segoe UI", 8))
            axis_y = QValueAxis()
            top = max(float(f.income + f.expenses + f.contributions) for f in self._flows) or 1.0
            axis_y.setRange(0, top * 1.08)
            axis_y.setLabelFormat("%.0f")
            axis_y.applyNiceNumbers()
            for axis, align in ((axis_x, Qt.AlignmentFlag.AlignBottom), (axis_y, Qt.AlignmentFlag.AlignLeft)):
                self._style_axis(axis)
                if axis is axis_x:
                    axis.setLabelsFont(QFont("Segoe UI", 8))
                chart.addAxis(axis, align)
                series.attachAxis(axis)
        self._style_chrome()

    def _on_hover(self, state: bool, index: int, name: str, values) -> None:
        if state:
            _tip(self, f"{name} · {month_long(self._flows[index].month)}: {fmt_eur(values[index])}")
        else:
            QToolTip.hideText()


# ============================================================================ evolucion patrimonial
def _ms(d: date) -> int:
    return QDateTime(QDate(d.year, d.month, d.day), QTime(12, 0)).toMSecsSinceEpoch()


class WealthChart(BaseChart):
    EMPTY_TEXT = "Importa tus extractos para ver la evolución"

    def __init__(self) -> None:
        super().__init__(min_height=320)
        self._points: list[WealthPoint] = []

    def set_data(self, points: list[WealthPoint]) -> None:
        self._points = points
        self._render()

    def _render(self) -> None:
        p = theme.current()
        self._reset()
        self._has_data = bool(self._points)
        if self._has_data:
            chart = self.chart()
            specs = [
                # la roja (fina) va sobre la amarilla (gruesa): casi coinciden cuando la liquidez es poca
                ("Aportaciones acumuladas", p.neutral, Qt.PenStyle.DashLine, 3, lambda w: w.contributions),
                ("Valor de la cartera", p.accent, Qt.PenStyle.SolidLine, 6, lambda w: w.invested_value),
                ("Patrimonio neto", p.red, Qt.PenStyle.SolidLine, 2, lambda w: w.net_worth),
            ]
            top = 1.0
            all_series = []
            for name, color, style, width, getter in specs:
                line = QLineSeries()
                line.setName(name)
                pen = QPen(QColor(color), width)
                pen.setStyle(style)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                line.setPen(pen)
                line.setPointsVisible(len(self._points) <= 4)
                for w in self._points:
                    value = float(getter(w))
                    top = max(top, value)
                    line.append(QPointF(_ms(w.date), value))
                line.hovered.connect(lambda pt, state, name=name: self._on_hover(pt, state, name))
                chart.addSeries(line)
                all_series.append(line)

            first, last = self._points[0].date, self._points[-1].date
            axis_x = QDateTimeAxis()
            axis_x.setFormat("MMM yy")
            axis_x.setTickCount(min(max(len(self._points), 2), 8))
            pad_days = 15 if first == last else 0
            axis_x.setRange(
                QDateTime.fromMSecsSinceEpoch(_ms(first) - pad_days * 86_400_000),
                QDateTime.fromMSecsSinceEpoch(_ms(last) + pad_days * 86_400_000),
            )
            axis_y = QValueAxis()
            axis_y.setRange(0, top * 1.1)
            axis_y.setLabelFormat("%.0f")
            axis_y.applyNiceNumbers()
            for axis, align in ((axis_x, Qt.AlignmentFlag.AlignBottom), (axis_y, Qt.AlignmentFlag.AlignLeft)):
                self._style_axis(axis)
                chart.addAxis(axis, align)
                for line in all_series:
                    line.attachAxis(axis)
        self._style_chrome()

    def _on_hover(self, point: QPointF, state: bool, name: str) -> None:
        if state:
            when = QDateTime.fromMSecsSinceEpoch(int(point.x())).date()
            _tip(self, f"{name} · {month_long(date(when.year(), when.month(), when.day()))}: {fmt_eur(point.y())}")
        else:
            QToolTip.hideText()
