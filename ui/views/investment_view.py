"""Pestana Inversion: metricas de la cartera, por mes o en global, posiciones y operaciones."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedLayout, QVBoxLayout, QWidget

from core.entities import PositionSnapshot
from services.investment_service import InvestmentService, InvestmentViewData
from ui import assets
from ui.format import EMPTY, OPERATION_LABELS, fmt_date, fmt_eur, fmt_pct, fmt_units, month_long
from ui.views.accounts_view import signed_eur
from ui.widgets.cards import ChartCard, PageHeader, StatBand, StatCard
from ui.widgets.charts import DonutChart
from ui.widgets.charts_period import PortfolioChart
from ui.widgets.period_bar import PeriodBar
from ui.widgets.tables import RIGHT, Column, DataTable


def _gain(p: PositionSnapshot) -> Decimal:
    return p.market_value - p.invested


def _ret(p: PositionSnapshot) -> Decimal | None:
    return _gain(p) / p.invested if p.invested else None


class InvestmentView(QWidget):
    go_import = Signal()

    def __init__(self, service: InvestmentService, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._service = service
        self._data = InvestmentViewData()

        self._stack = QStackedLayout()
        self._stack.addWidget(self._build_empty())
        self._stack.addWidget(self._build_content())

        self.header = PageHeader("Inversiones", eyebrow="Tu cartera")
        self.period = PeriodBar()
        bar = QHBoxLayout()
        bar.addWidget(self.period)
        bar.addStretch(1)
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 0)
        root.setSpacing(14)
        root.addWidget(self.header)
        root.addLayout(bar)
        root.addLayout(self._stack, 1)
        self.period.changed.connect(lambda _m: self.reload())

    # ------------------------------------------------------------------ construccion
    def _build_empty(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        logo = QLabel()
        logo.setPixmap(assets.mark(72))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Aún no hay datos de inversión")
        title.setObjectName("H1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QLabel("Importa las operaciones y la cartera de MyInvestor para ver aquí tus métricas y movimientos.")
        text.setObjectName("Muted")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setWordWrap(True)
        button = QPushButton("Importar extractos")
        button.setObjectName("Primary")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(self.go_import)
        col = QVBoxLayout(page)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.setSpacing(12)
        for w in (logo, title, text):
            col.addWidget(w)
        col.addSpacing(8)
        col.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
        return page

    def _build_content(self) -> QWidget:
        body = QWidget()
        body.setObjectName("Page")
        root = QVBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 28)
        root.setSpacing(16)

        self._banner = QFrame()
        self._banner.setObjectName("Banner")
        banner_row = QHBoxLayout(self._banner)
        banner_row.setContentsMargins(16, 12, 16, 12)
        self._banner_text = QLabel("")
        self._banner_text.setWordWrap(True)
        self._banner_text.setTextFormat(Qt.TextFormat.RichText)
        fix = QPushButton("Ir a Importar")
        fix.clicked.connect(self.go_import)
        banner_row.addWidget(self._banner_text, 1)
        banner_row.addWidget(fix)
        root.addWidget(self._banner)

        self.card_value = StatCard("Valor de la cartera", band=True)
        self.card_contrib = StatCard("Aportado", band=True)
        self.card_gain = StatCard("Plusvalía", band=True)
        self.card_twr = StatCard("Rentabilidad", band=True)
        self.mini_ops = StatCard("Operaciones", compact=True, band=True)
        self.mini_avg = StatCard("Aportación media mensual", compact=True, band=True)
        self.mini_funds = StatCard("Fondos en cartera", compact=True, band=True)
        self.mini_largest = StatCard("Posición mayor", compact=True, band=True)
        root.addWidget(StatBand((self.card_value, self.card_contrib, self.card_gain, self.card_twr)))
        root.addWidget(StatBand((self.mini_ops, self.mini_avg, self.mini_funds, self.mini_largest)))

        self.donut = DonutChart()
        self.donut.EMPTY_TEXT = "Importa la cartera de MyInvestor"
        self.evolution = PortfolioChart()
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(ChartCard("Distribución por fondo", "Cartera actual", self.donut), 4)
        row.addWidget(ChartCard("Aportado frente a valor", "La diferencia es lo que ha aportado la rentabilidad", self.evolution), 6)
        root.addLayout(row)

        self.positions_table = DataTable([
            Column("FONDO", lambda p: p.product_name, lambda p: p.product_name.lower(), stretch=True),
            Column("PARTIC.", lambda p: fmt_units(p.units), lambda p: p.units, RIGHT),
            Column("P. MEDIO", lambda p: fmt_eur(p.avg_cost), lambda p: p.avg_cost, RIGHT),
            Column("VL ACTUAL", lambda p: fmt_eur(p.unit_price), lambda p: p.unit_price, RIGHT),
            Column("INVERTIDO", lambda p: fmt_eur(p.invested), lambda p: p.invested, RIGHT),
            Column("VALOR", lambda p: fmt_eur(p.market_value), lambda p: p.market_value, RIGHT),
            Column("PLUSVALÍA", lambda p: signed_eur(_gain(p)), lambda p: _gain(p), RIGHT,
                   tone=lambda p: "negative" if _gain(p) < 0 else "positive"),
            Column("RENTAB.", lambda p: fmt_pct(_ret(p), 2, signed=True) if _ret(p) is not None else EMPTY,
                   lambda p: _ret(p) or Decimal(0), RIGHT, tone=lambda p: "negative" if (_ret(p) or 0) < 0 else "positive"),
        ], min_height=120)
        self.positions_table.wrap_text()
        self.positions_title = QLabel("Posiciones actuales")
        root.addWidget(self._table_card(self.positions_title, "Según el último extracto de cartera importado", self.positions_table))

        self.operations_table = DataTable([
            Column("FECHA", lambda o: fmt_date(o.trade_date), lambda o: o.trade_date),
            Column("FONDO", lambda o: o.product_name, lambda o: o.product_name.lower(), stretch=True),
            Column("ISIN", lambda o: o.isin, tone=lambda o: "muted"),
            Column("TIPO", lambda o: OPERATION_LABELS.get(o.op_type, o.op_type.value), tone=lambda o: "accent"),
            Column("PARTIC.", lambda o: fmt_units(o.units), lambda o: o.units, RIGHT),
            Column("VL", lambda o: fmt_eur(o.unit_price), lambda o: o.unit_price or Decimal(0), RIGHT),
            Column("IMPORTE", lambda o: fmt_eur(abs(o.amount)), lambda o: abs(o.amount), RIGHT),
        ], min_height=380)
        self.operations_table.wrap_text()
        self.operations_title = QLabel("Operaciones")
        self._ops_count = QLabel("")
        root.addWidget(self._table_card(self.operations_title, "", self.operations_table, self._ops_count))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        return scroll

    @staticmethod
    def _table_card(title: QLabel, subtitle: str, table: DataTable, extra: QLabel | None = None) -> QFrame:
        title.setObjectName("H2")
        head = QHBoxLayout()
        head.addWidget(title)
        if extra is not None:
            extra.setObjectName("Small")
            head.addWidget(extra)
        head.addStretch(1)
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(6)
        lay.addLayout(head)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("Small")
            lay.addWidget(sub)
        lay.addWidget(table)
        return card

    # ------------------------------------------------------------------ datos
    def reload(self) -> None:
        month = self.period.current_month()
        data = self._service.view(month)
        self.period.set_months(data.months)
        if month is not None and self.period.current_month() is None:
            data = self._service.view(None)
        self._data = data
        self._render(data)

    def _render(self, d: InvestmentViewData) -> None:
        self._stack.setCurrentIndex(1 if d.has_data else 0)
        if not d.has_data or d.summary is None:
            return
        s = d.summary
        month = d.period.start
        self.header.set_subtitle("")      # el selector de periodo ya lo indica

        self._banner.setVisible(bool(d.warnings))
        if d.warnings:
            extra = len(d.warnings) - 1
            more = f" Hay {extra} aviso{'s' if extra > 1 else ''} más en Importar." if extra else ""
            self._banner_text.setText(
                f"<b>La cartera no cuadra con las operaciones importadas.</b> {d.warnings[0]}{more} "
                "La rentabilidad (TIR y TWR) no se muestra hasta que cuadre."
            )
        reliable = not d.warnings

        if month:
            self.card_value.set_content(fmt_eur(s.value), f"al cierre de {month_long(month)} (estimado)")
            self.card_contrib.set_content(signed_eur(s.contributions_period), f"Acumulado: {fmt_eur(s.contributions_total)}")
            gain = s.period_gain
            self.card_gain.set_title("Variación del mes")
            self.card_gain.set_content(signed_eur(gain) if gain is not None else EMPTY, "Sin contar las aportaciones",
                                       negative=gain is not None and gain < 0, positive=gain is not None and gain > 0)
            self.card_twr.set_title("Rentabilidad del mes")
            twr = s.twr if reliable else None
            self.card_twr.set_content(fmt_pct(twr, 2, signed=True) if twr is not None else EMPTY,
                                      "Ponderada en el tiempo" if reliable else "No disponible: la cartera no cuadra",
                                      negative=twr is not None and twr < 0, positive=twr is not None and twr > 0)
        else:
            self.card_value.set_content(fmt_eur(s.value), "Valor de mercado actual")
            self.card_contrib.set_content(fmt_eur(s.contributions_total), "Compras menos ventas")
            self.card_gain.set_title("Plusvalía")
            self.card_gain.set_content(signed_eur(s.gain) if s.gain is not None else EMPTY,
                                       f"Rentabilidad {fmt_pct(s.simple_return, 2, signed=True)}" if s.simple_return is not None
                                       else "Importa la cartera de MyInvestor",
                                       negative=s.gain is not None and s.gain < 0, positive=s.gain is not None and s.gain > 0)
            self.card_twr.set_title("Rentabilidad (TWR)")
            twr = s.twr if reliable else None
            sub = (f"TIR {fmt_pct(s.xirr)} anual" if s.xirr is not None else "Ponderada en el tiempo") if reliable \
                else "No disponible: la cartera no cuadra"
            self.card_twr.set_content(fmt_pct(twr, 2, signed=True) if twr is not None else EMPTY, sub,
                                      negative=twr is not None and twr < 0, positive=twr is not None and twr > 0)

        self.mini_ops.set_content(str(s.operations), f"{s.buys} compras · {s.sells} ventas")
        self.mini_avg.set_content(fmt_eur(s.avg_monthly_contribution) if s.avg_monthly_contribution is not None else EMPTY, "")
        self.mini_funds.set_content(str(s.positions), "")
        lp = s.largest_position
        self.mini_largest.set_content(lp.label if lp else EMPTY, f"{fmt_pct(lp.weight, 1)} de la cartera" if lp else "")

        self.donut.set_data(d.allocation)
        self.evolution.set_data(d.evolution)
        self.positions_table.set_rows(d.positions)
        self.positions_table.fit_height()
        self.operations_table.set_rows(d.operations)
        self.operations_table.fit_height(max_rows=10)
        self._ops_count.setText(f"{len(d.operations)} operaciones")

    def refresh_theme(self) -> None:
        self.donut.refresh_theme()
        self.evolution.refresh_theme()
        self.positions_table.refresh_theme()
        self.operations_table.refresh_theme()

