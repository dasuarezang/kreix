"""Pestana Cuentas: metricas de las cuentas bancarias, por mes o en global, y sus movimientos."""
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QScrollArea, QStackedLayout, QVBoxLayout, QWidget,
)

from core.entities import TransactionDraft
from core.metrics import FlowOptions
from data.repositories import AccountError
from services.accounts_service import AccountsService, AccountsViewData
from ui import assets
from ui.format import category_label, fmt_date, fmt_eur, fmt_pct, month_long
from ui.widgets.cards import ChartCard, StatCard
from ui.widgets.charts_period import BalanceChart, CategoryBarsChart, IncomeExpenseChart
from ui.widgets.period_bar import PeriodBar
from ui.widgets.tables import RIGHT, Column, DataTable

ALL_CATEGORIES = "Todas las categorías"


def signed_eur(value: Decimal) -> str:
    return f"+{fmt_eur(value)}" if value > 0 else fmt_eur(value)


class AccountsView(QWidget):
    accounts_changed = Signal()
    go_import = Signal()

    def __init__(self, service: AccountsService, options: Callable[[], FlowOptions], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._service = service
        self._options = options
        self._data = AccountsViewData()
        self._names: dict[int, str] = {}

        self._stack = QStackedLayout()
        self._stack.addWidget(self._build_empty())
        self._stack.addWidget(self._build_content())

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 0)
        root.setSpacing(14)
        root.addLayout(self._build_header())
        root.addLayout(self._stack, 1)

    # ------------------------------------------------------------------ construccion
    def _build_header(self) -> QVBoxLayout:
        title = QLabel("Cuentas")
        title.setObjectName("H1")
        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(230)
        self.account_combo.setAccessibleName("Cuenta")
        self.manage = QPushButton("Gestionar cuentas")
        menu = QMenu(self.manage)
        self.act_add = menu.addAction("Añadir cuenta…")
        self.act_rename = menu.addAction("Renombrar cuenta…")
        self.act_delete = menu.addAction("Eliminar cuenta…")
        self.manage.setMenu(menu)
        self.act_add.triggered.connect(self.prompt_add)
        self.act_rename.triggered.connect(self.prompt_rename)
        self.act_delete.triggered.connect(self.prompt_delete)

        self.period = PeriodBar()
        self._subtitle = QLabel("")
        self._subtitle.setObjectName("Muted")

        top = QHBoxLayout()
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.account_combo)
        top.addWidget(self.manage)
        bottom = QHBoxLayout()
        bottom.addWidget(self.period)
        bottom.addSpacing(8)
        bottom.addWidget(self._subtitle, 1)

        col = QVBoxLayout()
        col.setSpacing(12)
        col.addLayout(top)
        col.addLayout(bottom)
        self.account_combo.currentIndexChanged.connect(lambda _i: self.reload())
        self.period.changed.connect(lambda _m: self.reload())
        return col

    def _build_empty(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        logo = QLabel()
        logo.setPixmap(assets.mark(72))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_title = QLabel("Aún no hay movimientos")
        self._empty_title.setObjectName("H1")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QLabel("Importa el extracto de tu cuenta de Imagin para ver aquí tus métricas y todos tus movimientos.")
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
        for w in (logo, self._empty_title, text):
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

        self.card_balance = StatCard("Saldo", "yellow")
        self.card_income = StatCard("Ingresos", "yellow")
        self.card_expenses = StatCard("Gastos", "red")
        self.card_rate = StatCard("Tasa de ahorro", "neutral")
        self.mini_moves = StatCard("Movimientos", "neutral", compact=True)
        self.mini_largest = StatCard("Mayor gasto", "red", compact=True)
        self.mini_category = StatCard("Categoría principal", "red", compact=True)
        self.mini_average = StatCard("Gasto medio", "neutral", compact=True)
        for cards in ((self.card_balance, self.card_income, self.card_expenses, self.card_rate),
                      (self.mini_moves, self.mini_largest, self.mini_category, self.mini_average)):
            row = QHBoxLayout()
            row.setSpacing(16)
            for c in cards:
                row.addWidget(c, 1)
            root.addLayout(row)

        self.categories = CategoryBarsChart()
        self.balance = BalanceChart()
        self.monthly = IncomeExpenseChart()
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(ChartCard("Gastos por categoría", "Dónde se va el dinero en el periodo", self.categories), 5)
        row.addWidget(ChartCard("Evolución del saldo", "Saldo al cierre de cada día con movimientos", self.balance), 5)
        root.addLayout(row)
        root.addWidget(ChartCard("Ingresos y gastos por mes", "Los últimos 12 meses de las cuentas seleccionadas", self.monthly))
        root.addWidget(self._build_movements())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        return scroll

    def _build_movements(self) -> QFrame:
        columns = [
            Column("FECHA", lambda t: fmt_date(t.booking_date), lambda t: t.booking_date),
            Column("CUENTA", lambda t: self._names.get(t.account_id, ""), tone=lambda t: "muted"),
            Column("CONCEPTO", lambda t: t.description, lambda t: t.description.lower(), stretch=True),
            Column("CATEGORÍA", lambda t: category_label(t.category), lambda t: category_label(t.category)),
            Column("IMPORTE", lambda t: signed_eur(t.amount), lambda t: t.amount, RIGHT,
                   tone=lambda t: "negative" if t.amount < 0 else "positive"),
            Column("SALDO", lambda t: fmt_eur(t.balance_after), lambda t: t.balance_after or Decimal(0), RIGHT,
                   tone=lambda t: "muted"),
        ]
        self.table = DataTable(columns, min_height=440)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por concepto…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Buscar movimientos")
        self.category_filter = QComboBox()
        self.category_filter.setAccessibleName("Filtrar por categoría")
        self._count = QLabel("")
        self._count.setObjectName("Small")
        self.search.textChanged.connect(lambda _t: self._apply_filter())
        self.category_filter.currentIndexChanged.connect(lambda _i: self._apply_filter())

        heading = QLabel("Movimientos")
        heading.setObjectName("H2")
        bar = QHBoxLayout()
        bar.setSpacing(10)
        bar.addWidget(heading)
        bar.addWidget(self._count)
        bar.addStretch(1)
        bar.addWidget(self.search, 2)
        bar.addWidget(self.category_filter, 1)

        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(10)
        lay.addLayout(bar)
        lay.addWidget(self.table)
        return card

    # ------------------------------------------------------------------ datos
    def selected_account_ids(self) -> list[int] | None:
        data = self.account_combo.currentData()
        return None if data is None else [data]

    def reload(self) -> None:
        self._fill_account_combo()
        month = self.period.current_month()
        data = self._service.view(self.selected_account_ids(), month, self._options())
        self.period.set_months(data.months)
        if month is not None and self.period.current_month() is None:       # ese mes ya no existe
            data = self._service.view(self.selected_account_ids(), None, self._options())
        self._data = data
        self._render(data)

    def _fill_account_combo(self) -> None:
        accounts = self._service.accounts()
        self._names = {a.id: a.name for a in accounts}
        keep = self.account_combo.currentData()
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        self.account_combo.addItem("Todas las cuentas", None)
        for a in accounts:
            self.account_combo.addItem(a.name, a.id)
        index = self.account_combo.findData(keep) if keep is not None else 0
        self.account_combo.setCurrentIndex(max(index, 0))
        self.account_combo.blockSignals(False)
        single = self.account_combo.currentData() is not None
        self.act_rename.setEnabled(single)
        self.act_delete.setEnabled(single)
        self.table.setColumnHidden(1, single or len(accounts) < 2)      # la columna Cuenta solo aporta con varias

    def _render(self, d: AccountsViewData) -> None:
        self._stack.setCurrentIndex(1 if d.has_movements else 0)
        self._empty_title.setText("Aún no hay movimientos" if d.accounts else "Aún no tienes ninguna cuenta")
        self._subtitle.setText(self._describe(d))
        if not d.has_movements or d.summary is None:
            self.table.set_rows([])
            return
        s, options = d.summary, self._options()
        month = d.period.start
        scope = f"al cierre de {month_long(month)}" if month else "saldo actual"
        self.card_balance.set_content(fmt_eur(s.balance), scope, negative=bool(s.balance and s.balance < 0))
        parts = (["Bizum"] if options.include_p2p else []) + (["traspasos entrantes"] if options.transfers_in_as_income else [])
        self.card_income.set_content(fmt_eur(s.income), "Incluye " + " y ".join(parts) if parts else "Sin Bizum ni traspasos")
        avg = (f"Media {fmt_eur(s.avg_daily_expense)} al día" if month else f"Media {fmt_eur(s.avg_monthly_expense)} al mes") \
            if s.avg_daily_expense is not None else ""
        self.card_expenses.set_content(fmt_eur(s.expenses), avg)
        rate = s.savings_rate
        self.card_rate.set_content(fmt_pct(rate, 0) if rate is not None else "—",
                                   f"Flujo neto {signed_eur(s.net)}" if rate is not None else "Sin ingresos en el periodo",
                                   negative=rate is not None and rate < 0)

        ups = sum(1 for t in d.movements if t.amount > 0)
        self.mini_moves.set_content(str(s.movements), f"{ups} entradas · {s.movements - ups} salidas")
        if s.largest_expense:
            t = s.largest_expense
            self.mini_largest.set_content(fmt_eur(-t.amount), f"{t.description} · {fmt_date(t.booking_date)}")
        else:
            self.mini_largest.set_content("—", "Sin gastos")
        if s.top_category:
            self.mini_category.set_content(category_label(s.top_category.category),
                                           f"{fmt_eur(s.top_category.amount)} · {fmt_pct(s.top_category.share, 0)} del gasto")
        else:
            self.mini_category.set_content("—", "Sin gastos")
        if month:
            self.mini_average.set_title("Gasto medio diario")
            self.mini_average.set_content(fmt_eur(s.avg_daily_expense), "")
        else:
            self.mini_average.set_title("Gasto medio mensual")
            self.mini_average.set_content(fmt_eur(s.avg_monthly_expense),
                                          f"{fmt_eur(s.avg_daily_expense)} al día" if s.avg_daily_expense is not None else "")

        self.categories.set_data(d.categories)
        self.balance.set_data(d.balance_series, daily=month is not None)
        self.monthly.set_data(d.monthly)

        self.table.set_rows(d.movements)
        self._fill_category_filter(d.movements)
        self._apply_filter()

    def _describe(self, d: AccountsViewData) -> str:
        n = len(d.selected)
        names = f"{n} cuenta{'s' if n != 1 else ''}" if self.account_combo.currentData() is None else self.account_combo.currentText()
        return f"{month_long(d.period.start).capitalize()}  ·  {names}" if d.period.start else names

    def _fill_category_filter(self, movements: list[TransactionDraft]) -> None:
        keep = self.category_filter.currentData()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem(ALL_CATEGORIES, None)
        for cat in sorted({t.category for t in movements}, key=category_label):
            self.category_filter.addItem(category_label(cat), cat)
        index = self.category_filter.findData(keep) if keep is not None else 0
        self.category_filter.setCurrentIndex(max(index, 0))
        self.category_filter.blockSignals(False)

    def _apply_filter(self) -> None:
        text = self.search.text().strip().lower()
        category = self.category_filter.currentData()

        def accept(t: TransactionDraft) -> bool:
            return (category is None or t.category == category) and (not text or text in t.description.lower())

        self.table.set_filter(accept)
        shown, total = self.table.proxy.rowCount(), self.table.model_.rowCount()
        self._count.setText(f"{total} movimientos" if shown == total else f"{shown} de {total} movimientos")

    # ------------------------------------------------------------------ gestion de cuentas
    def add_account_named(self, name: str) -> bool:
        try:
            info = self._service.add(name)
        except AccountError as exc:
            QMessageBox.warning(self, "No se pudo añadir la cuenta", str(exc))
            return False
        self._fill_account_combo()
        self.account_combo.setCurrentIndex(self.account_combo.findData(info.id))
        self.accounts_changed.emit()
        return True

    def rename_selected(self, name: str) -> bool:
        ids = self.selected_account_ids()
        if not ids:
            return False
        try:
            self._service.rename(ids[0], name)
        except AccountError as exc:
            QMessageBox.warning(self, "No se pudo renombrar", str(exc))
            return False
        self.accounts_changed.emit()
        return True

    def delete_selected(self) -> bool:
        ids = self.selected_account_ids()
        if not ids:
            return False
        self._service.delete(ids[0])
        self.account_combo.setCurrentIndex(0)
        self.accounts_changed.emit()
        return True

    def prompt_add(self) -> None:
        name, ok = QInputDialog.getText(self, "Añadir cuenta", "Nombre de la cuenta:")
        if ok and name.strip():
            self.add_account_named(name)

    def prompt_rename(self) -> None:
        if not self.selected_account_ids():
            return
        name, ok = QInputDialog.getText(self, "Renombrar cuenta", "Nuevo nombre:", QLineEdit.EchoMode.Normal,
                                        self.account_combo.currentText())
        if ok and name.strip():
            self.rename_selected(name)

    def prompt_delete(self) -> None:
        if not self.selected_account_ids():
            return
        answer = QMessageBox.question(
            self, "Eliminar cuenta",
            f"Se eliminará la cuenta «{self.account_combo.currentText()}» y todos sus movimientos.\n"
            "Esta acción no se puede deshacer.\n\n¿Quieres continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_selected()

    def refresh_theme(self) -> None:
        for chart in (self.categories, self.balance, self.monthly):
            chart.refresh_theme()
        self.table.refresh_theme()
