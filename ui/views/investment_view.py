"""Pestana Inversion: metricas de la cartera, por mes o en global, posiciones y operaciones."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedLayout, QVBoxLayout, QWidget

from core.entities import PositionSnapshot
from services.investment_service import InvestmentService, InvestmentViewData
from ui.popups import Combo
from ui.format import EMPTY, fmt_date, fmt_eur, fmt_pct, fmt_units, month_long, operation_label
from ui.views.accounts_view import signed_eur
from ui.headlines import evolution_headline, fund_headline
from ui.widgets.cards import flatten, ChartCard, PageHeader, StatBand, StatCard
from ui.widgets.onboarding import EmptyState, InterestOffState
from ui.widgets.charts import DonutChart
from ui.widgets.charts_period import FundsChart, PortfolioChart
from ui.widgets.period_bar import PeriodBar
from ui.widgets.tables import RIGHT, Column, DataTable
from core.i18n import tr, trn


def _gain(p: PositionSnapshot) -> Decimal:
    return p.market_value - p.invested


def _ret(p: PositionSnapshot) -> Decimal | None:
    return _gain(p) / p.invested if p.invested else None


class InvestmentView(QWidget):
    go_import = Signal()
    interest_requested = Signal()      # "Activar inversiones": el usuario habia dicho que no le interesaban

    def __init__(self, service: InvestmentService, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._service = service
        self._data = InvestmentViewData()

        self._stack = QStackedLayout()
        self._interested = True
        self._stack.addWidget(self._owned(self._build_empty()))
        self._stack.addWidget(self._owned(self._build_content()))
        self.off_state = InterestOffState(
            tr("Las inversiones están desactivadas"),
            tr("Dijiste que no te interesaba gestionar tus inversiones. Si has cambiado de idea, actívalas y verás aquí el valor "
            "de tu cartera, lo que has aportado, tu plusvalía y tu rentabilidad."),
            tr("Activar inversiones"))
        self.off_state.activate_requested.connect(self.interest_requested)
        self._stack.addWidget(self._owned(self.off_state))

        self.header = PageHeader(tr("Inversiones"), eyebrow=tr("Tu cartera"))
        self.period = PeriodBar()
        bar = QHBoxLayout()
        bar.addWidget(self.period)
        bar.addStretch(1)
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 40, 48, 0)
        root.setSpacing(22)
        root.addWidget(self.header)
        root.addLayout(bar)
        root.addLayout(self._stack, 1)
        self.period.changed.connect(lambda _m: self.reload())

    def _owned(self, widget: QWidget) -> QWidget:
        """Le da a la pagina como padre antes de meterla en la pila: sin padre, la pila la abriria como ventana suelta
        (un parpadeo al arrancar)."""
        widget.setParent(self)
        return widget

    # ------------------------------------------------------------------ construccion
    def _build_empty(self) -> QWidget:
        page = EmptyState(
            tr("Aún no hay datos de inversión"),
            tr("Aquí verás el valor de tu cartera, lo que has aportado, tu plusvalía y tu rentabilidad (TWR y TIR), "
            "con todas tus posiciones y operaciones."),
            tr("Dos archivos de MyInvestor, en CSV o Excel: tus operaciones (el historial de compras) y tu cartera "
            "(las posiciones de hoy). Arrástralos a Importar; la cartera te pedirá a qué día corresponde."))
        page.action.connect(self.go_import)
        return page

    def _build_content(self) -> QWidget:
        body = QWidget()
        body.setObjectName("Page")
        root = QVBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 44)
        root.setSpacing(28)

        self._banner = QFrame()
        self._banner.setObjectName("Banner")
        banner_row = QHBoxLayout(self._banner)
        banner_row.setContentsMargins(16, 12, 16, 12)
        self._banner_text = QLabel("")
        self._banner_text.setWordWrap(True)
        self._banner_text.setTextFormat(Qt.TextFormat.RichText)
        fix = QPushButton(tr("Ir a Importar"))
        fix.clicked.connect(self.go_import)
        banner_row.addWidget(self._banner_text, 1)
        banner_row.addWidget(fix)
        root.addWidget(self._banner)

        self.card_value = StatCard(tr("Valor de la cartera"), band=True).set_help("Valor de la cartera")
        self.card_contrib = StatCard(tr("Aportado"), band=True).set_help("Aportado (capital invertido)")
        self.card_gain = StatCard(tr("Plusvalía"), band=True).set_help("Plusvalía y minusvalía")
        self.card_twr = StatCard(tr("Rentabilidad"), band=True).set_help("TWR (rentabilidad ponderada en el tiempo)")
        self.mini_ops = StatCard(tr("Operaciones"), compact=True, band=True)
        self.mini_avg = StatCard(tr("Aportación media mensual"), compact=True, band=True)
        self.mini_funds = StatCard(tr("Fondos en cartera"), compact=True, band=True)
        self.mini_largest = StatCard(tr("Posición mayor"), compact=True, band=True)
        root.addWidget(StatBand((self.card_value, self.card_contrib, self.card_gain, self.card_twr)))
        root.addWidget(StatBand((self.mini_ops, self.mini_avg, self.mini_funds, self.mini_largest)))

        self.donut = DonutChart()
        self.donut.EMPTY_TEXT = tr("Importa la cartera de MyInvestor")
        self.evolution = PortfolioChart()
        row = QHBoxLayout()
        row.setSpacing(28)
        self.funds_card = ChartCard(tr("Distribución por fondo"), tr("Cartera actual"), self.donut)
        self.evolution_card = ChartCard(tr("Aportado frente a valor"), tr("La diferencia es lo que ha aportado la rentabilidad"), self.evolution)
        row.addWidget(self.funds_card, 4)
        row.addWidget(self.evolution_card, 6)
        root.addLayout(row)

        self.funds_chart = FundsChart()
        self.fund_combo = Combo()
        self.fund_combo.setAccessibleName(tr("Fondo"))
        self.fund_combo.setMinimumWidth(260)
        self.fund_combo.currentIndexChanged.connect(self._on_fund_picked)
        self.history_card = ChartCard(tr("Evolución de cada fondo"),
                                      tr("Valor de cada fondo al cierre de cada mes, según tus extractos. Entre extractos es una estimación."),
                                      self.funds_chart)
        pick = QHBoxLayout()
        pick.addWidget(self.fund_combo)
        pick.addStretch(1)
        self.history_card.layout().insertLayout(5, pick)               # tras el titulo y su explicacion (antes, la regla de marca y su separacion)
        root.addWidget(self.history_card)

        self.positions_table = DataTable([
            Column(tr("FONDO"), lambda p: p.product_name, lambda p: p.product_name.lower(), stretch=True),
            Column(tr("PARTIC."), lambda p: fmt_units(p.units), lambda p: p.units, RIGHT),
            Column(tr("P. MEDIO"), lambda p: fmt_eur(p.avg_cost), lambda p: p.avg_cost, RIGHT),
            Column(tr("VL ACTUAL"), lambda p: fmt_eur(p.unit_price), lambda p: p.unit_price, RIGHT),
            Column(tr("INVERTIDO"), lambda p: fmt_eur(p.invested), lambda p: p.invested, RIGHT),
            Column(tr("VALOR"), lambda p: fmt_eur(p.market_value), lambda p: p.market_value, RIGHT),
            Column(tr("PLUSVALÍA"), lambda p: signed_eur(_gain(p)), lambda p: _gain(p), RIGHT,
                   tone=lambda p: "negative" if _gain(p) < 0 else "positive"),
            Column(tr("RENTAB."), lambda p: fmt_pct(_ret(p), 2, signed=True) if _ret(p) is not None else EMPTY,
                   lambda p: _ret(p) or Decimal(0), RIGHT, tone=lambda p: "negative" if (_ret(p) or 0) < 0 else "positive"),
        ], min_height=120)
        self.positions_table.wrap_text()
        self.positions_title = QLabel(tr("Posiciones actuales"))
        root.addWidget(self._table_card(self.positions_title, tr("Según el último extracto de cartera importado"), self.positions_table))

        self.operations_table = DataTable([
            Column(tr("FECHA"), lambda o: fmt_date(o.trade_date), lambda o: o.trade_date),
            Column(tr("FONDO"), lambda o: o.product_name, lambda o: o.product_name.lower(), stretch=True),
            Column(tr("ISIN"), lambda o: o.isin, tone=lambda o: "muted"),
            Column(tr("TIPO"), lambda o: operation_label(o.op_type), tone=lambda o: "accent"),
            Column(tr("PARTIC."), lambda o: fmt_units(o.units), lambda o: o.units, RIGHT),
            Column(tr("VL"), lambda o: fmt_eur(o.unit_price), lambda o: o.unit_price or Decimal(0), RIGHT),
            Column(tr("IMPORTE"), lambda o: fmt_eur(abs(o.amount)), lambda o: abs(o.amount), RIGHT),
        ], min_height=380)
        self.operations_table.wrap_text()
        self.operations_title = QLabel(tr("Operaciones"))
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
        lay = QVBoxLayout(card)
        lay.setSpacing(10)
        flatten(card, lay, (0, 0, 0, 8))
        lay.addLayout(head)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("Small")
            lay.addWidget(sub)
        lay.addWidget(table)
        return card

    # ------------------------------------------------------------------ datos
    def set_interested(self, on: bool) -> None:
        """Con el interes desactivado la pestana solo ofrece activarlo (y no calcula nada)."""
        changed = on != self._interested
        self._interested = on
        self.header.setVisible(on)
        self.period.setVisible(on)
        if not on:
            self._stack.setCurrentIndex(2)
        elif changed:
            self.reload()

    def reload(self) -> None:
        if not self._interested:
            self._stack.setCurrentIndex(2)
            return
        month = self.period.current_month()
        data = self._service.view(month)
        self.period.set_months(data.months)
        if month is not None and self.period.current_month() is None:
            data = self._service.view(None)
        self._data = data
        self._render(data)

    def _fill_fund_combo(self, d: InvestmentViewData) -> None:
        keep = self.fund_combo.currentData()
        self.fund_combo.blockSignals(True)
        self.fund_combo.clear()
        self.fund_combo.addItem(tr("Todos los fondos"), None)
        for f in d.funds:
            self.fund_combo.addItem(f.name, f.isin)
        self.fund_combo.setCurrentIndex(max(self.fund_combo.findData(keep), 0) if keep is not None else 0)
        self.fund_combo.blockSignals(False)
        self.history_card.setVisible(bool(d.funds))
        self.funds_chart.set_data(d.funds, self.fund_combo.currentData())

    def _on_fund_picked(self, _index: int) -> None:
        self.funds_chart.set_data(self._data.funds, self.fund_combo.currentData())

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
            more = trn(" Hay {extra} aviso más en Importar.", " Hay {extra} avisos más en Importar.", extra).format(extra=extra) if extra else ""
            self._banner_text.setText(
                tr("<b>La cartera no cuadra con las operaciones importadas.</b> {warnings}{more} La rentabilidad (TIR y TWR) no se muestra hasta que cuadre.").format(warnings=d.warnings[0], more=more)
            )
        reliable = not d.warnings

        if month:
            self.card_value.set_content(fmt_eur(s.value), tr("al cierre de {month} (estimado)").format(month=month_long(month)))
            self.card_contrib.set_content(signed_eur(s.contributions_period), tr("Acumulado: {contributions_total}").format(contributions_total=fmt_eur(s.contributions_total)))
            gain = s.period_gain
            self.card_gain.set_title(tr("Variación del mes"))
            self.card_gain.set_content(signed_eur(gain) if gain is not None else EMPTY, tr("Sin contar las aportaciones"),
                                       negative=gain is not None and gain < 0, positive=gain is not None and gain > 0)
            self.card_twr.set_title(tr("Rentabilidad del mes"))
            twr = s.twr if reliable else None
            self.card_twr.set_content(fmt_pct(twr, 2, signed=True) if twr is not None else EMPTY,
                                      tr("Ponderada en el tiempo") if reliable else tr("No disponible: la cartera no cuadra"),
                                      negative=twr is not None and twr < 0, positive=twr is not None and twr > 0)
        else:
            self.card_value.set_content(fmt_eur(s.value), tr("Valor de mercado actual"))
            self.card_contrib.set_content(fmt_eur(s.contributions_total), tr("Compras menos ventas"))
            self.card_gain.set_title(tr("Plusvalía"))
            self.card_gain.set_content(signed_eur(s.gain) if s.gain is not None else EMPTY,
                                       tr("Rentabilidad {signed}").format(signed=fmt_pct(s.simple_return, 2, signed=True)) if s.simple_return is not None
                                       else tr("Importa la cartera de MyInvestor"),
                                       negative=s.gain is not None and s.gain < 0, positive=s.gain is not None and s.gain > 0)
            self.card_twr.set_title(tr("Rentabilidad (TWR)"))
            twr = s.twr if reliable else None
            sub = (tr("TIR {xirr} anual").format(xirr=fmt_pct(s.xirr)) if s.xirr is not None else tr("Ponderada en el tiempo")) if reliable \
                else tr("No disponible: la cartera no cuadra")
            self.card_twr.set_content(fmt_pct(twr, 2, signed=True) if twr is not None else EMPTY, sub,
                                      negative=twr is not None and twr < 0, positive=twr is not None and twr > 0)

        self.mini_ops.set_content(str(s.operations), tr("{buys} compras · {sells} ventas").format(buys=s.buys, sells=s.sells))
        self.mini_avg.set_content(fmt_eur(s.avg_monthly_contribution) if s.avg_monthly_contribution is not None else EMPTY, "")
        self.mini_funds.set_content(str(s.positions), "")
        lp = s.largest_position
        self.mini_largest.set_content(lp.label if lp else EMPTY, tr("{weight} de la cartera").format(weight=fmt_pct(lp.weight, 1)) if lp else "")

        self.funds_card.set_headline(fund_headline(d.allocation))
        self.evolution_card.set_headline(evolution_headline(d.evolution))
        self.donut.set_data(d.allocation)
        self.evolution.set_data(d.evolution)
        self._fill_fund_combo(d)
        self.positions_table.set_rows(d.positions)
        self.positions_table.fit_height()
        self.operations_table.set_rows(d.operations)
        self.operations_table.fit_height(max_rows=10)
        self._ops_count.setText(tr("{operations} operaciones").format(operations=len(d.operations)))

    def refresh_theme(self) -> None:
        self.donut.refresh_theme()
        self.evolution.refresh_theme()
        self.funds_chart.refresh_theme()
        self.positions_table.refresh_theme()
        self.operations_table.refresh_theme()

