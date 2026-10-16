"""Pantalla principal: indicadores y graficos."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedLayout, QVBoxLayout, QWidget,
)

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

from core.metrics import WealthPoint
from services.dashboard_service import DashboardData
from ui.format import fmt_date, fmt_datetime_long, fmt_eur, fmt_pct
from ui.views.accounts_view import signed_eur
from core.greeting import greeting
from ui.headlines import allocation_headline, flow_headline, wealth_headline
from ui.widgets.cards import ChartCard, HeroCard, PageHeader, StatCard
from ui.widgets.charts import DonutChart, FlowChart, WealthChart
from ui.widgets.onboarding import Onboarding, SetupPanel
from ui.widgets.budget_carousel import BudgetCarousel
from ui.widgets.goals_panel import GoalsPanel
from ui.widgets.panels import UpcomingPanel
from ui.widgets.sky import SkyWidget
from ui.widgets.ambient import hour_of
from core.i18n import tr, trn


class DashboardView(QWidget):
    go_import = Signal()
    demo_requested = Signal()
    navigate_requested = Signal(str)      # "import" | "accounts": acceso directo desde los primeros pasos
    setup_dismissed = Signal()
    category_clicked = Signal(object)     # desde un presupuesto de Inicio: ver esos movimientos en Cuentas
    goals_requested = Signal()            # abrir la gestion de metas de ahorro

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._setup_hidden = False
        self._data: DashboardData | None = None
        self._user_name = ""
        self._interests = (True, True)       # (cuentas, inversiones)
        self.clock: Callable[[], datetime] = datetime.now      # las pruebas lo sustituyen
        self._stack = QStackedLayout(self)
        self._stack.addWidget(self._build_empty())
        self._stack.addWidget(self._build_content())
        self._greeting_timer = QTimer(self)
        self._greeting_timer.setInterval(1000)       # el reloj de Inicio se actualiza cada segundo (solo repinta si cambia)
        self._greeting_timer.timeout.connect(self.update_greeting)
        self.update_greeting()                         # el reloj solo corre mientras Inicio esta a la vista (ver showEvent)

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
        root.setContentsMargins(48, 40, 48, 48)
        root.setSpacing(28)

        self.header = PageHeader(greeting(datetime.now()), eyebrow=tr("Inicio"))
        self.sky = SkyWidget()                              # sol o luna animados, a la derecha del nombre
        self.header.add_side_accessory(self.sky)
        root.setContentsMargins(48, max(0, 40 - self.sky.inset_top), 48, 48)     # el margen vacio del cielo (para su luz) ocupa parte del de la pagina
        self.date_line = QLabel("")                         # el dia y la hora, siempre al dia
        self.date_line.setObjectName("DateLine")
        self.header.add_line(self.date_line)
        root.addWidget(self.header)

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

        self.card_net = HeroCard(tr("Patrimonio neto")).set_help("Patrimonio neto")
        self.card_return = StatCard(tr("Rendimiento global")).set_help("Rentabilidad global")
        self.card_savings = StatCard(tr("Tasa de ahorro del mes")).set_help("Tasa de ahorro")
        side = QVBoxLayout()
        side.setSpacing(28)
        side.addWidget(self.card_return, 1)
        side.addWidget(self.card_savings, 1)
        top = QHBoxLayout()
        top.setSpacing(28)
        top.addWidget(self.card_net, 6)
        top.addLayout(side, 4)
        root.addLayout(top)

        self.setup = SetupPanel()
        self.setup.navigate_requested.connect(self.navigate_requested)
        self.setup.dismissed.connect(self.setup_dismissed)
        root.addWidget(self.setup)

        self.upcoming = UpcomingPanel()
        self.budgets = BudgetCarousel()
        attention = QHBoxLayout()
        attention.setSpacing(28)
        attention.addWidget(self.upcoming, 5)
        attention.addWidget(self.budgets, 5)
        root.addLayout(attention)
        self.budgets.category_clicked.connect(self.category_clicked)
        self.goals = GoalsPanel()
        self.goals.manage_requested.connect(self.goals_requested)
        root.addWidget(self.goals)

        self.donut, self.flow, self.wealth = DonutChart(), FlowChart(), WealthChart()
        row = QHBoxLayout()
        row.setSpacing(28)
        self.allocation_card = ChartCard(tr("Distribución de activos"), tr("Liquidez en Imagin frente a inversión en MyInvestor"), self.donut)
        self.flow_card = ChartCard(tr("Flujo de caja mensual"), tr("Ingresos, gastos y aportaciones a MyInvestor"), self.flow)
        self.wealth_card = ChartCard(tr("Evolución patrimonial"), tr("Lo aportado frente a lo que vale hoy: la diferencia es el efecto de la rentabilidad compuesta"), self.wealth)
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
        self._data = d                                      # se recuerda: al cambiar lo que interesa, Inicio se vuelve a pintar
        self._stack.setCurrentIndex(1 if d.has_data else 0)
        if not d.has_data:
            return
        self._render(d)

    def _shown(self, d: DashboardData) -> SimpleNamespace:
        """Los numeros de Inicio segun lo que le interesa al usuario. Los datos no se tocan: lo que no interesa solo deja de
        contar y de mostrarse (si vuelve a interesar, vuelve con todo)."""
        accounts, investments = self._interests
        cash = (d.cash or Decimal(0)) if accounts else Decimal(0)
        invested = d.portfolio_value if investments else Decimal(0)
        points = [WealthPoint(w.date, w.cash if accounts else Decimal(0), w.invested_value if investments else Decimal(0),
                              w.contributions if investments else Decimal(0),
                              (w.cash if accounts else Decimal(0)) + (w.invested_value if investments else Decimal(0)))
                  for w in d.wealth]
        flows = [f if investments else replace(f, contributions=Decimal(0)) for f in d.flows]
        change = points[-1].net_worth - points[-2].net_worth if len(points) >= 2 else None
        return SimpleNamespace(cash=cash, invested=invested, net_worth=cash + invested, points=points, flows=flows,
                               change=change)

    def _render(self, d: DashboardData) -> None:
        shown = self._shown(d)
        self.header.set_subtitle(tr("Fecha de última actualización de datos: {date}").format(date=fmt_date(d.last_update)) if d.last_update else "")

        reliable = not d.warnings and d.xirr is not None and d.twr is not None
        net = self.card_net
        net.set_content(fmt_eur(shown.net_worth), {
            (True, True): tr("Todo lo que tienes: cuentas más inversiones"),
            (True, False): tr("Lo que tienes en tus cuentas"),
            (False, True): tr("Lo que tienes invertido"),
        }[self._interests])
        chips: list[tuple[str, str]] = []
        if d.simple_return is not None:
            chips.append((tr("{signed} rendimiento").format(signed=fmt_pct(d.simple_return, 2, signed=True)), "negative" if d.simple_return < 0 else "positive"))
        if reliable:
            chips.append((tr("TIR {xirr} anual").format(xirr=fmt_pct(d.xirr)), ""))
        if not self._interests[1]:
            chips = []                              # el rendimiento y la TIR son de las inversiones
        if shown.change is not None and shown.change != 0:
            chips.insert(0, (tr("{amount} frente al mes pasado").format(amount=signed_eur(shown.change)),
                             "negative" if shown.change < 0 else "positive"))
        net.set_chips(chips)
        net.trend.set_values([float(w.net_worth) for w in shown.points])
        total = float(shown.net_worth) or 1.0
        cash, invested = float(shown.cash), float(shown.invested)
        parts = [   # el importe y, a su lado, lo que supone sobre el patrimonio neto que se muestra
            (tr("Liquidez"), f"{fmt_eur(shown.cash)}  ·  {fmt_pct(cash / total)}", max(cash, 0) / total, "neutral"),
            (tr("Inversión"), f"{fmt_eur(shown.invested)}  ·  {fmt_pct(invested / total)}", invested / total, "accent"),
        ]
        accounts, investments = self._interests
        net.split.set_parts([part for part, keep in zip(parts, (accounts, investments)) if keep])

        if d.simple_return is None:
            self.card_return.set_content("—", tr("Importa el extracto de cartera de MyInvestor"))
        else:
            sub = (tr("TIR {xirr} anual  ·  TWR {twr}").format(xirr=fmt_pct(d.xirr), twr=fmt_pct(d.twr)) if reliable else tr("Sobre el capital invertido"))
            self.card_return.set_content(fmt_pct(d.simple_return, 2, signed=True), sub,
                                         negative=d.simple_return < 0, positive=d.simple_return > 0)
        if d.month_savings_rate is None:
            self.card_savings.set_content("—", tr("Este mes aún no hay ingresos registrados"))
        else:
            rate = d.month_savings_rate
            self.card_savings.set_content(
                fmt_pct(rate, 0),
                tr("Ingresos {month_income}  ·  Gastos {month_expenses}").format(month_income=fmt_eur(d.month_income), month_expenses=fmt_eur(d.month_expenses)),
                negative=rate < 0, positive=rate > 0,
            )

        self._banner.setVisible(bool(d.warnings))
        if d.warnings:
            extra = len(d.warnings) - 1
            more = trn(" Hay {extra} aviso más en Importar.", " Hay {extra} avisos más en Importar.", extra).format(extra=extra) if extra else ""
            self._banner_text.setText(
                tr("<b>La cartera no cuadra con las operaciones importadas.</b> {warnings}{more} La TIR y el TWR no se muestran hasta que cuadre.").format(warnings=d.warnings[0], more=more)
            )
        accounts, investments = self._interests
        steps = []
        if accounts:
            steps.append((tr("Importa el extracto de tu cuenta"), d.has_transactions, "import"))
        if investments:
            steps += [(tr("Importa tus operaciones de MyInvestor"), d.has_operations, "import"),
                      (tr("Importa la cartera de MyInvestor"), d.has_portfolio, "import")]
        if accounts:
            steps.append((tr("Define un presupuesto mensual en Cuentas"), d.has_budgets, "accounts"))
        self.setup.set_steps(steps)
        self.setup.setVisible(not self._setup_hidden and not all(done for _, done, _ in steps))
        self.upcoming.set_items(d.upcoming)
        self.budgets.set_state(d.budgets, d.has_budgets)
        self.goals.set_goals(d.goals, self.clock().date())
        self.allocation_card.set_headline(allocation_headline(d.cash, d.portfolio_value, d.net_worth))
        self.flow_card.set_headline(flow_headline(shown.flows))
        self.wealth_card.set_headline(wealth_headline(shown.points))
        self.donut.set_data(d.allocation)
        self.flow.set_data(shown.flows, contributions=investments)               # sin inversiones, no hay aportaciones
        self.wealth.set_data(shown.points, value_line=accounts and investments, contributions=investments)

    def set_interests(self, accounts: bool, investments: bool) -> None:
        """Muestra solo lo que le interesa al usuario: sin inversiones no hay rendimiento ni reparto de activos; sin
        cuentas no hay tasa de ahorro, flujo de caja, pagos recurrentes ni presupuestos."""
        self._interests = (accounts, investments)
        self.onboarding.set_interests(accounts, investments)
        self.card_return.setVisible(investments)
        self.allocation_card.setVisible(accounts and investments)               # liquidez frente a inversion: con las dos
        self.card_savings.setVisible(accounts)
        self.flow_card.setVisible(accounts)
        self.upcoming.setVisible(accounts)
        self.budgets.setVisible(accounts)
        self.goals.setVisible(accounts)
        if getattr(self, "_data", None) is not None and self._data.has_data:
            self._render(self._data)                                            # el patrimonio y las graficas dejan de contar lo que no interesa

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.update_greeting()                          # al volver, la hora ya esta al dia
        self._greeting_timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._greeting_timer.stop()                     # en otra pagina no hay nada que repintar cada segundo

    def set_user_name(self, name: str) -> None:
        self._user_name = name
        self.update_greeting()

    def update_greeting(self) -> None:
        """Pone el saludo de la hora actual. Se repite cada minuto para que cambie solo al pasar de turno."""
        now = self.clock()
        text = greeting(now, self._user_name)
        self.header.title.setText(text)
        self.onboarding.set_greeting(text)
        stamp = fmt_datetime_long(now)
        if self.date_line.text() != stamp:
            self.date_line.setText(stamp)
            self.onboarding.set_date(stamp)
        for sky in (self.sky, self.onboarding.sky):
            sky.set_hour(hour_of(now))

    def set_animated(self, on: bool) -> None:
        """Activa o quita el movimiento del cielo y del carrusel de presupuestos (el resto de la app no cambia)."""
        for sky in (self.sky, self.onboarding.sky):
            sky.set_animated(on)

    def set_setup_hidden(self, hidden: bool) -> None:
        self._setup_hidden = hidden
        if hidden:
            self.setup.hide()

    def refresh_theme(self) -> None:
        for chart in (self.donut, self.flow, self.wealth):
            chart.refresh_theme()
        self.card_net.refresh_theme()
        self.upcoming.refresh_theme()
        self.budgets.refresh_theme()
