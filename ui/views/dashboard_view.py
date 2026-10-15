"""Pantalla principal: indicadores y graficos."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedLayout, QVBoxLayout, QWidget,
)

from services.dashboard_service import DashboardData
from ui.format import fmt_eur, fmt_pct, month_long
from ui.headlines import allocation_headline, flow_headline, wealth_headline
from ui.widgets.cards import ChartCard, HeroCard, PageHeader, StatCard
from ui.widgets.charts import DonutChart, FlowChart, WealthChart
from ui.widgets.onboarding import Onboarding, SetupPanel
from ui.widgets.panels import AlertsPanel, UpcomingPanel


class DashboardView(QWidget):
    go_import = Signal()
    demo_requested = Signal()
    navigate_requested = Signal(str)      # "import" | "accounts": acceso directo desde los primeros pasos
    setup_dismissed = Signal()
    category_clicked = Signal(object)     # desde un presupuesto del Resumen: ver esos movimientos en Cuentas

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._setup_hidden = False
        self._stack = QStackedLayout(self)
        self._stack.addWidget(self._build_empty())
        self._stack.addWidget(self._build_content())

    # ------------------------------------------------------------------ construccion
    def _build_empty(self) -> QWidget:
        self.onboarding = Onboarding()
        self.onboarding.go_import.connect(self.go_import)
        self.onboarding.demo_requested.connect(self.demo_requested)
        return self.onboarding

    def _build_content(self) -> QWidget:
        body = QWidget()
        body.setObjectName("Page")
        root = QVBoxLayout(body)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(18)

        self.header = PageHeader("Resumen", eyebrow="Visión general")
        root.addWidget(self.header)

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

        self.card_net = HeroCard("Patrimonio neto")
        self.card_return = StatCard("Rendimiento global")
        self.card_savings = StatCard("Tasa de ahorro del mes")
        side = QVBoxLayout()
        side.setSpacing(16)
        side.addWidget(self.card_return, 1)
        side.addWidget(self.card_savings, 1)
        top = QHBoxLayout()
        top.setSpacing(16)
        top.addWidget(self.card_net, 6)
        top.addLayout(side, 4)
        root.addLayout(top)

        self.setup = SetupPanel()
        self.setup.navigate_requested.connect(self.navigate_requested)
        self.setup.dismissed.connect(self.setup_dismissed)
        root.addWidget(self.setup)

        self.upcoming = UpcomingPanel()
        self.alerts = AlertsPanel()
        attention = QHBoxLayout()
        attention.setSpacing(16)
        attention.addWidget(self.upcoming, 5)
        attention.addWidget(self.alerts, 5)
        root.addLayout(attention)
        self.alerts.bars.category_clicked.connect(self.category_clicked)

        self.donut, self.flow, self.wealth = DonutChart(), FlowChart(), WealthChart()
        row = QHBoxLayout()
        row.setSpacing(16)
        self.allocation_card = ChartCard("Distribución de activos", "Liquidez en Imagin frente a inversión en MyInvestor", self.donut)
        self.flow_card = ChartCard("Flujo de caja mensual", "Ingresos, gastos y aportaciones a MyInvestor", self.flow)
        self.wealth_card = ChartCard("Evolución patrimonial", "Lo aportado frente a lo que vale hoy: la diferencia es el efecto de la rentabilidad compuesta", self.wealth)
        row.addWidget(self.allocation_card, 4)
        row.addWidget(self.flow_card, 6)
        root.addLayout(row)
        root.addWidget(self.wealth_card)
        root.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        return scroll

    # ------------------------------------------------------------------ datos
    def set_data(self, d: DashboardData) -> None:
        self._stack.setCurrentIndex(1 if d.has_data else 0)
        if not d.has_data:
            return
        self.header.set_subtitle(f"Datos hasta {month_long(d.report_month)}" if d.report_month else "Cartera de inversión")

        reliable = not d.warnings and d.xirr is not None and d.twr is not None
        net = self.card_net
        net.set_content(fmt_eur(d.net_worth), "Todo lo que tienes: cuentas más inversiones")
        chips: list[tuple[str, str]] = []
        if d.simple_return is not None:
            chips.append((f"{fmt_pct(d.simple_return, 2, signed=True)} rendimiento", "negative" if d.simple_return < 0 else "positive"))
        if reliable:
            chips.append((f"TIR {fmt_pct(d.xirr)} anual", ""))
        net.set_chips(chips)
        net.trend.set_values([float(w.net_worth) for w in d.wealth])
        total = float(d.net_worth) or 1.0
        net.split.set_parts([
            ("Liquidez", fmt_eur(d.cash or 0), max(float(d.cash or 0), 0) / total, "neutral"),
            ("Inversión", fmt_eur(d.portfolio_value), float(d.portfolio_value) / total, "accent"),
        ])

        if d.simple_return is None:
            self.card_return.set_content("—", "Importa el extracto de cartera de MyInvestor")
        else:
            sub = (f"TIR {fmt_pct(d.xirr)} anual  ·  TWR {fmt_pct(d.twr)}" if reliable else "Sobre el capital invertido")
            self.card_return.set_content(fmt_pct(d.simple_return, 2, signed=True), sub,
                                         negative=d.simple_return < 0, positive=d.simple_return > 0)
        if d.month_savings_rate is None:
            self.card_savings.set_content("—", "Este mes aún no hay ingresos registrados")
        else:
            rate = d.month_savings_rate
            self.card_savings.set_content(
                fmt_pct(rate, 0),
                f"Ingresos {fmt_eur(d.month_income)}  ·  Gastos {fmt_eur(d.month_expenses)}",
                negative=rate < 0, positive=rate > 0,
            )

        self._banner.setVisible(bool(d.warnings))
        if d.warnings:
            extra = len(d.warnings) - 1
            more = f" Hay {extra} aviso{'s' if extra > 1 else ''} más en Importar." if extra else ""
            self._banner_text.setText(
                f"<b>La cartera no cuadra con las operaciones importadas.</b> {d.warnings[0]}{more} "
                "La TIR y el TWR no se muestran hasta que cuadre."
            )
        steps = [
            ("Importa el extracto de tu cuenta", d.has_transactions, "import"),
            ("Importa tus operaciones de MyInvestor", d.has_operations, "import"),
            ("Importa la cartera de MyInvestor", d.has_portfolio, "import"),
            ("Define un presupuesto mensual en Cuentas", d.has_budgets, "accounts"),
        ]
        self.setup.set_steps(steps)
        self.setup.setVisible(not self._setup_hidden and not all(done for _, done, _ in steps))
        self.upcoming.set_items(d.upcoming)
        self.alerts.set_state(d.budget_alerts, d.has_budgets)
        self.allocation_card.set_headline(allocation_headline(d.cash, d.portfolio_value, d.net_worth))
        self.flow_card.set_headline(flow_headline(d.flows))
        self.wealth_card.set_headline(wealth_headline(d.wealth))
        self.donut.set_data(d.allocation)
        self.flow.set_data(d.flows)
        self.wealth.set_data(d.wealth)

    def set_setup_hidden(self, hidden: bool) -> None:
        self._setup_hidden = hidden
        if hidden:
            self.setup.hide()

    def refresh_theme(self) -> None:
        for chart in (self.donut, self.flow, self.wealth):
            chart.refresh_theme()
        self.card_net.refresh_theme()
        self.upcoming.refresh_theme()
        self.alerts.bars.update()
