"""Graficos de las pestanas Cuentas e Inversion."""
from __future__ import annotations

from datetime import date

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QDateTimeAxis,
    QHorizontalBarSeries,
    QLineSeries,
    QValueAxis,
)
from PySide6.QtCore import QDateTime, QPointF, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QToolTip

from core.account_metrics import CategoryAmount
from core.metrics import MonthlyFlow, WealthPoint
from ui import theme
from ui.format import category_label, fmt_date, fmt_eur, fmt_pct, month_long, month_short
from ui.widgets.charts import BaseChart, _ms, _tip

MAX_CATEGORIES = 8


# ============================================================================ Cuentas
class CategoryBarsChart(BaseChart):
    """Gasto por categoria en barras horizontales, de mayor a menor."""

    EMPTY_TEXT = "Sin gastos en este periodo"

    def __init__(self) -> None:
        super().__init__(min_height=300)
        self._items: list[CategoryAmount] = []

    def set_data(self, items: list[CategoryAmount]) -> None:
        self._items = items
        self._render()

    def _render(self) -> None:
        p = theme.current()
        self._reset()
        self._has_data = bool(self._items)
        if self._has_data:
            shown = self._items[:MAX_CATEGORIES]
            labels = [category_label(i.category) for i in shown]
            values = [float(i.amount) for i in shown]
            rest = sum((float(i.amount) for i in self._items[MAX_CATEGORIES:]), 0.0)
            if rest:
                labels.append("Otras categorías")
                values.append(rest)
            total = float(sum((i.amount for i in self._items), start=0))
            labels, values = labels[::-1], values[::-1]       # en horizontales, la 1.a categoria queda abajo

            bar = QBarSet("Gasto")
            bar.append(values)
            bar.setColor(QColor(p.red))
            bar.setBorderColor(QColor(p.red))
            bar.hovered.connect(lambda state, idx: self._on_hover(state, labels[idx], values[idx], total))
            series = QHorizontalBarSeries()
            series.setBarWidth(0.62)
            series.append(bar)
            chart = self.chart()
            chart.addSeries(series)

            axis_y = QBarCategoryAxis()
            axis_y.append(labels)
            axis_x = QValueAxis()
            axis_x.setRange(0, max(values) * 1.1)
            axis_x.setLabelFormat("%.0f")
            axis_x.applyNiceNumbers()
            for axis, align in ((axis_y, Qt.AlignmentFlag.AlignLeft), (axis_x, Qt.AlignmentFlag.AlignBottom)):
                self._style_axis(axis)
                chart.addAxis(axis, align)
                series.attachAxis(axis)
            axis_y.setLabelsColor(QColor(p.text))
            axis_y.setGridLineVisible(False)
        self._style_chrome()
        self.chart().legend().setVisible(False)

    def _on_hover(self, state: bool, label: str, value: float, total: float) -> None:
        if state:
            _tip(self, f"{label}: {fmt_eur(value)} ({fmt_pct(value / total if total else 0)})")
        else:
            QToolTip.hideText()


class _DateValueChart(BaseChart):
    """Base de los graficos con eje de fechas y eje de valores."""

    def _axes(self, series_list, first: date, last: date, low: float, high: float, fmt: str, ticks: int) -> None:
        chart = self.chart()
        axis_x = QDateTimeAxis()
        axis_x.setFormat(fmt)
        # marcas separadas lo bastante para que cada etiqueta sea de un mes (o dia) distinto
        span_days = max((last - first).days, 1)
        ticks = max(2, min(8, span_days // 31 + 1)) if fmt.startswith("MMM") else max(2, min(7, span_days // 4 + 1))
        axis_x.setTickCount(ticks)
        pad_days = 15 if first == last else 0
        axis_x.setRange(
            QDateTime.fromMSecsSinceEpoch(_ms(first) - pad_days * 86_400_000),
            QDateTime.fromMSecsSinceEpoch(_ms(last) + pad_days * 86_400_000),
        )
        axis_y = QValueAxis()
        span = (high - low) or 1.0
        axis_y.setRange(low - (span * 0.08 if low < 0 else 0), high + span * 0.1)
        axis_y.setLabelFormat("%.0f")
        axis_y.applyNiceNumbers()
        for axis, align in ((axis_x, Qt.AlignmentFlag.AlignBottom), (axis_y, Qt.AlignmentFlag.AlignLeft)):
            self._style_axis(axis)
            chart.addAxis(axis, align)
            for series in series_list:
                series.attachAxis(axis)

    def _line(self, name: str, color: str, width: int, style=Qt.PenStyle.SolidLine) -> QLineSeries:
        line = QLineSeries()
        line.setName(name)
        pen = QPen(QColor(color), width)
        pen.setStyle(style)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line.setPen(pen)
        line.hovered.connect(lambda pt, state, name=name: self._on_line_hover(pt, state, name))
        return line

    def _on_line_hover(self, point: QPointF, state: bool, name: str) -> None:
        if state:
            when = QDateTime.fromMSecsSinceEpoch(int(point.x())).date()
            _tip(self, f"{name} · {fmt_date(date(when.year(), when.month(), when.day()))}: {fmt_eur(point.y())}")
        else:
            QToolTip.hideText()


class BalanceChart(_DateValueChart):
    """Saldo al cierre de cada dia con movimientos."""

    EMPTY_TEXT = "Sin movimientos en este periodo"

    def __init__(self) -> None:
        super().__init__(min_height=300)
        self._points: list[tuple[date, object]] = []
        self._daily = False

    def set_data(self, points: list[tuple[date, object]], daily: bool = False) -> None:
        self._points, self._daily = points, daily
        self._render()

    def _render(self) -> None:
        p = theme.current()
        self._reset()
        self._has_data = bool(self._points)
        if self._has_data:
            line = self._line("Saldo", p.accent, 4)
            values = [float(v) for _, v in self._points]
            for (d, _), v in zip(self._points, values):
                line.append(QPointF(_ms(d), v))
            line.setPointsVisible(len(self._points) <= 31)
            self.chart().addSeries(line)
            first, last = self._points[0][0], self._points[-1][0]
            self._axes([line], first, last, min(0.0, min(values)), max(values), "dd MMM" if self._daily else "MMM yy", len(self._points))
        self._style_chrome()
        self.chart().legend().setVisible(False)


class IncomeExpenseChart(BaseChart):
    """Ingresos frente a gastos de cada mes."""

    EMPTY_TEXT = "Importa un extracto para ver los meses"

    def __init__(self) -> None:
        super().__init__(min_height=280)
        self._flows: list[MonthlyFlow] = []

    def set_data(self, flows: list[MonthlyFlow]) -> None:
        self._flows = flows[-12:]
        self._render()

    def _render(self) -> None:
        p = theme.current()
        self._reset()
        self._has_data = bool(self._flows)
        if self._has_data:
            series = QBarSeries()
            series.setBarWidth(0.7)
            specs = (("Ingresos", p.accent, [f.income for f in self._flows]),
                     ("Gastos", p.red, [f.expenses for f in self._flows]))
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
            axis_x.append([month_short(f.month)[:3] for f in self._flows])
            axis_y = QValueAxis()
            top = max((float(max(f.income, f.expenses)) for f in self._flows), default=1.0) or 1.0
            axis_y.setRange(0, top * 1.1)
            axis_y.setLabelFormat("%.0f")
            axis_y.applyNiceNumbers()
            for axis, align in ((axis_x, Qt.AlignmentFlag.AlignBottom), (axis_y, Qt.AlignmentFlag.AlignLeft)):
                self._style_axis(axis)
                chart.addAxis(axis, align)
                series.attachAxis(axis)
        self._style_chrome()

    def _on_hover(self, state: bool, index: int, name: str, values) -> None:
        if state:
            _tip(self, f"{name} · {month_long(self._flows[index].month)}: {fmt_eur(values[index])}")
        else:
            QToolTip.hideText()


# ============================================================================ Inversion
class PortfolioChart(_DateValueChart):
    """Lo aportado frente a lo que vale la cartera, mes a mes."""

    EMPTY_TEXT = "Importa tus operaciones para ver la evolución"

    def __init__(self) -> None:
        super().__init__(min_height=300)
        self._points: list[WealthPoint] = []

    def set_data(self, points: list[WealthPoint]) -> None:
        self._points = points
        self._render()

    def _render(self) -> None:
        p = theme.current()
        self._reset()
        self._has_data = bool(self._points)
        if self._has_data:
            contributed = self._line("Aportado", p.neutral, 3, Qt.PenStyle.DashLine)
            value = self._line("Valor de la cartera", p.accent, 4)
            top = 1.0
            for w in self._points:
                contributed.append(QPointF(_ms(w.date), float(w.contributions)))
                value.append(QPointF(_ms(w.date), float(w.invested_value)))
                top = max(top, float(w.contributions), float(w.invested_value))
            value.setPointsVisible(len(self._points) <= 4)
            for line in (contributed, value):
                self.chart().addSeries(line)
            self._axes([contributed, value], self._points[0].date, self._points[-1].date, 0.0, top, "MMM yy", len(self._points))
        self._style_chrome()
