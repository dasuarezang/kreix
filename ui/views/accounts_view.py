"""Pestana Cuentas: metricas de las cuentas bancarias, por mes o en global, y sus movimientos."""
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QScrollArea, QStackedLayout, QVBoxLayout, QWidget,
)

from core.entities import TransactionDraft
from core.metrics import FlowOptions
from core.recurring import merchant_key
from data.repositories import AccountError, RuleError
from services.accounts_service import AccountsService, AccountsViewData
from services.category_service import CategoryService
from services.movements_export import ExportError, write_movements
from ui.dialogs import ALL_CATEGORIES as CATEGORY_CHOICES
from ui.dialogs import BudgetDialog, RuleDialog
from ui.feedback import Feedback, snapshot_of, tell
from ui.headlines import balance_headline, category_headline, monthly_headline
from ui.format import category_label, fmt_date, fmt_eur, fmt_pct, month_long, month_short
from ui.widgets.cards import ChartCard, PageHeader, StatBand, StatCard
from ui.widgets.charts_period import BalanceChart, CategoryBarsChart, IncomeExpenseChart
from ui.widgets.onboarding import EmptyState, InterestOffState
from ui.widgets.panels import BudgetPanel, RecurringPanel
from ui.widgets.period_bar import PeriodBar
from ui.widgets.tables import RIGHT, Column, DataTable
from core.i18n import N_, tr, trn

ALL_CATEGORIES = N_("Todas las categorías")
DEBOUNCE_ROWS = 1500      # a partir de aqui el filtro espera a que dejes de teclear


def signed_eur(value: Decimal) -> str:
    return f"+{fmt_eur(value)}" if value > 0 else fmt_eur(value)


def delta_text(current: Decimal, previous: Decimal, month) -> str:
    """'+12 % frente a ago 26'; vacio si el mes anterior no tiene importe con el que comparar."""
    if previous <= 0:
        return ""
    change = (current - previous) / previous
    if round(change * 100) == 0:
        return tr("Igual que en {month}").format(month=month_short(month))
    return tr("{signed} frente a {month}").format(signed=fmt_pct(change, 0, signed=True), month=month_short(month))


class AccountsView(QWidget):
    accounts_changed = Signal()
    categories_changed = Signal()
    go_import = Signal()
    interest_requested = Signal()      # "Activar cuentas": el usuario habia dicho que no le interesaban
    feedback: Feedback | None = None       # lo asigna la ventana: avisos y "Deshacer"

    def __init__(self, service: AccountsService, options: Callable[[], FlowOptions],
                 categories: CategoryService | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._service = service
        self._categories = categories
        self._options = options
        self._data = AccountsViewData()
        self._names: dict[int, str] = {}

        self._stack = QStackedLayout()
        self._interested = True
        self._stack.addWidget(self._build_empty())
        self._stack.addWidget(self._build_content())
        self.off_state = InterestOffState(
            tr("Las cuentas bancarias están desactivadas"),
            tr("Dijiste que no te interesaba gestionar tus cuentas. Si has cambiado de idea, actívalas y verás aquí tu saldo, "
            "tus ingresos y gastos, tus presupuestos y todos tus movimientos."),
            tr("Activar cuentas bancarias"))
        self.off_state.activate_requested.connect(self.interest_requested)
        self._stack.addWidget(self.off_state)

        root = QVBoxLayout(self)
        root.setContentsMargins(48, 40, 48, 0)
        root.setSpacing(22)
        root.addLayout(self._build_header())
        root.addLayout(self._stack, 1)

    # ------------------------------------------------------------------ construccion
    def _build_header(self) -> QVBoxLayout:
        self.header = PageHeader(tr("Cuentas"), eyebrow=tr("Tus cuentas"))
        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(230)
        self.account_combo.setAccessibleName(tr("Cuenta"))
        self.manage = QPushButton(tr("Gestionar cuentas"))
        menu = QMenu(self.manage)
        self.act_add = menu.addAction(tr("Añadir cuenta…"))
        self.act_rename = menu.addAction(tr("Renombrar cuenta…"))
        self.act_delete = menu.addAction(tr("Eliminar cuenta…"))
        self.manage.setMenu(menu)
        self.act_add.triggered.connect(self.prompt_add)
        self.act_rename.triggered.connect(self.prompt_rename)
        self.act_delete.triggered.connect(self.prompt_delete)
        self.header.add_right(self.account_combo)
        self.header.add_right(self.manage)

        self.period = PeriodBar()
        col = QVBoxLayout()
        col.setSpacing(22)
        col.addWidget(self.header)
        bar = QHBoxLayout()
        bar.addWidget(self.period)
        bar.addStretch(1)
        col.addLayout(bar)
        self.account_combo.currentIndexChanged.connect(lambda _i: self.reload())
        self.period.changed.connect(lambda _m: self.reload())
        return col

    def _build_empty(self) -> QWidget:
        page = EmptyState(
            tr("Aún no hay movimientos"),
            tr("Aquí verás tu saldo, tus ingresos y gastos, a dónde se va el dinero, tus presupuestos y tus pagos "
            "recurrentes, con todos tus movimientos para buscar y ordenar."),
            tr("El extracto de movimientos de tu cuenta de Imagin, en CSV o Excel. Arrástralo a Importar: Kreix lo "
            "reconoce solo y te enseña lo que ha leído antes de guardar nada."))
        page.action.connect(self.go_import)
        self._empty_title = page.title_label
        return page

    def _build_content(self) -> QWidget:
        body = QWidget()
        body.setObjectName("Page")
        root = QVBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 44)
        root.setSpacing(28)

        self.card_balance = StatCard(tr("Saldo"), band=True)
        self.card_income = StatCard(tr("Ingresos"), band=True)
        self.card_expenses = StatCard(tr("Gastos"), band=True)
        self.card_rate = StatCard(tr("Tasa de ahorro"), band=True)
        self.mini_moves = StatCard(tr("Movimientos"), compact=True, band=True)
        self.mini_largest = StatCard(tr("Mayor gasto"), compact=True, band=True)
        self.mini_category = StatCard(tr("Categoría principal"), compact=True, band=True)
        self.mini_average = StatCard(tr("Gasto medio"), compact=True, band=True)
        root.addWidget(StatBand((self.card_balance, self.card_income, self.card_expenses, self.card_rate)))
        root.addWidget(StatBand((self.mini_moves, self.mini_largest, self.mini_category, self.mini_average)))

        self.categories = CategoryBarsChart()
        self.balance = BalanceChart()
        self.monthly = IncomeExpenseChart()
        row = QHBoxLayout()
        row.setSpacing(28)
        self.category_card = ChartCard(tr("Gastos por categoría"), tr("Dónde se va el dinero en el periodo. Pulsa una para ver sus movimientos"), self.categories)
        self.balance_card = ChartCard(tr("Evolución del saldo"), tr("Saldo al cierre de cada día con movimientos"), self.balance)
        self.monthly_card = ChartCard(tr("Ingresos y gastos por mes"), tr("Los últimos 12 meses de las cuentas seleccionadas"), self.monthly)
        row.addWidget(self.category_card, 5)
        row.addWidget(self.balance_card, 5)
        root.addLayout(row)
        root.addWidget(self.monthly_card)
        self.budget_panel = BudgetPanel()
        self.recurring_panel = RecurringPanel()
        self.budget_panel.edit_requested.connect(self.edit_budgets)
        self.budget_panel.bars.category_clicked.connect(self.show_category)
        self.categories.category_clicked.connect(self.show_category)
        panels = QHBoxLayout()
        panels.setSpacing(28)
        panels.addWidget(self.budget_panel, 5)
        panels.addWidget(self.recurring_panel, 5)
        root.addLayout(panels)
        root.addWidget(self._build_movements())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        self._scroll = scroll
        return scroll

    def _build_movements(self) -> QFrame:
        columns = [
            Column(tr("FECHA"), lambda t: fmt_date(t.booking_date), lambda t: t.booking_date),
            Column(tr("CUENTA"), lambda t: self._names.get(t.account_id, ""), tone=lambda t: "muted"),
            Column(tr("CONCEPTO"), lambda t: t.description, lambda t: t.description.lower(), stretch=True),
            Column(tr("CATEGORÍA"), lambda t: category_label(t.category), lambda t: category_label(t.category)),
            Column(tr("IMPORTE"), lambda t: signed_eur(t.amount), lambda t: t.amount, RIGHT,
                   tone=lambda t: "negative" if t.amount < 0 else "positive"),
            Column(tr("SALDO"), lambda t: fmt_eur(t.balance_after), lambda t: t.balance_after or Decimal(0), RIGHT,
                   tone=lambda t: "muted"),
            Column("", lambda t: "•••", lambda t: 0, Qt.AlignmentFlag.AlignCenter, tone=lambda t: "accent",
                   tooltip=lambda t: tr("Cambiar la categoría, crear una regla o copiar el concepto")),
        ]
        self.table = DataTable(columns, min_height=440)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Buscar por concepto…"))
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName(tr("Buscar movimientos"))
        self.category_filter = QComboBox()
        self.category_filter.setAccessibleName(tr("Filtrar por categoría"))
        self._count = QLabel("")
        self._count.setObjectName("Small")
        self._search_timer = QTimer(self)                     # espera a que dejes de teclear: con miles de filas, fluido
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(160)
        self._search_timer.timeout.connect(self._apply_filter)
        self.search.textChanged.connect(self._on_search_changed)
        self.category_filter.currentIndexChanged.connect(lambda _i: self._apply_filter())
        self.export_button = QPushButton(tr("Exportar"))
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.setToolTip(tr("Guarda en CSV o Excel los movimientos que se ven ahora"))
        self.export_button.clicked.connect(self.export_movements)
        self.table.context_requested.connect(self._show_row_menu)
        self.table.clicked.connect(self._on_cell_clicked)
        self.table.doubleClicked.connect(lambda index: self._open_menu_for(index))

        heading = QLabel(tr("Movimientos"))
        heading.setObjectName("H2")
        hint = QLabel(tr("Pulsa ••• (o haz doble clic o clic derecho) en un movimiento para cambiar su categoría o crear una regla."))
        hint.setObjectName("Small")
        hint.setWordWrap(True)
        bar = QHBoxLayout()
        bar.setSpacing(10)
        bar.addWidget(heading)
        bar.addWidget(self._count)
        bar.addStretch(1)
        bar.addWidget(self.search, 2)
        bar.addWidget(self.category_filter, 1)
        bar.addWidget(self.export_button)

        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(34, 30, 34, 24)
        lay.setSpacing(14)
        lay.addLayout(bar)
        lay.addWidget(hint)
        lay.addWidget(self.table)
        self.movements_card = card
        return card

    # ------------------------------------------------------------------ datos
    def selected_account_ids(self) -> list[int] | None:
        data = self.account_combo.currentData()
        return None if data is None else [data]

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
        self.account_combo.addItem(tr("Todas las cuentas"), None)
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
        self._empty_title.setText(tr("Aún no hay movimientos") if d.accounts else tr("Aún no tienes ninguna cuenta"))
        self.header.set_subtitle(self._describe(d))
        if not d.has_movements or d.summary is None:
            self.table.set_rows([])
            return
        s, options = d.summary, self._options()
        month = d.period.start
        scope = tr("al cierre de {month}").format(month=month_long(month)) if month else tr("saldo actual")
        self.card_balance.set_content(fmt_eur(s.balance), scope, negative=bool(s.balance and s.balance < 0))
        if options.include_p2p and options.transfers_in_as_income:
            income_note = tr("Incluye Bizum y traspasos entrantes")
        elif options.include_p2p:
            income_note = tr("Incluye Bizum")
        elif options.transfers_in_as_income:
            income_note = tr("Incluye traspasos entrantes")
        else:
            income_note = tr("Sin Bizum ni traspasos")
        avg = (tr("Media {avg_daily_expense} al día").format(avg_daily_expense=fmt_eur(s.avg_daily_expense)) if month else tr("Media {avg_monthly_expense} al mes").format(avg_monthly_expense=fmt_eur(s.avg_monthly_expense))) \
            if s.avg_daily_expense is not None else ""
        if d.previous is not None and d.previous_month is not None:
            income_delta = delta_text(s.income, d.previous.income, d.previous_month)
            expense_delta = delta_text(s.expenses, d.previous.expenses, d.previous_month)
            income_note = f"{income_delta}\n{income_note}" if income_delta else income_note
            avg = f"{expense_delta}\n{avg}" if expense_delta and avg else (expense_delta or avg)
        self.card_income.set_content(fmt_eur(s.income), income_note)
        self.card_expenses.set_content(fmt_eur(s.expenses), avg)
        rate = s.savings_rate
        self.card_rate.set_content(fmt_pct(rate, 0) if rate is not None else "—",
                                   tr("Flujo neto {net}").format(net=signed_eur(s.net)) if rate is not None else tr("Sin ingresos en el periodo"),
                                   negative=rate is not None and rate < 0, positive=rate is not None and rate > 0)

        ups = sum(1 for t in d.movements if t.amount > 0)
        self.mini_moves.set_content(str(s.movements), tr("{ups} entradas · {ups2} salidas").format(ups=ups, ups2=s.movements - ups))
        if s.largest_expense:
            t = s.largest_expense
            self.mini_largest.set_content(fmt_eur(-t.amount), f"{t.description} · {fmt_date(t.booking_date)}")
        else:
            self.mini_largest.set_content("—", tr("Sin gastos"))
        if s.top_category:
            self.mini_category.set_content(category_label(s.top_category.category),
                                           tr("{amount} · {share} del gasto").format(amount=fmt_eur(s.top_category.amount), share=fmt_pct(s.top_category.share, 0)))
        else:
            self.mini_category.set_content("—", tr("Sin gastos"))
        if month:
            self.mini_average.set_title(tr("Gasto medio diario"))
            self.mini_average.set_content(fmt_eur(s.avg_daily_expense), "")
        else:
            self.mini_average.set_title(tr("Gasto medio mensual"))
            self.mini_average.set_content(fmt_eur(s.avg_monthly_expense),
                                          tr("{avg_daily_expense} al día").format(avg_daily_expense=fmt_eur(s.avg_daily_expense)) if s.avg_daily_expense is not None else "")

        self.categories.set_data(d.categories)
        self.balance.set_data(d.balance_series, daily=month is not None)
        self.monthly.set_data(d.monthly)
        self.category_card.set_headline(category_headline(d.categories))
        self.balance_card.set_headline(balance_headline(d.balance_series, month is not None))
        self.monthly_card.set_headline(monthly_headline(d.monthly[-12:]))
        self.budget_panel.set_lines(d.budgets, monthly=month is not None)
        self.recurring_panel.set_items(d.recurring)

        self.table.set_rows(d.movements)
        self._fill_category_filter(d.movements)
        self._apply_filter()

    def _describe(self, d: AccountsViewData) -> str:
        n = len(d.selected)
        names = trn("{n} cuenta", "{n} cuentas", n).format(n=n) if self.account_combo.currentData() is None else self.account_combo.currentText()
        return f"{month_long(d.period.start).capitalize()}  ·  {names}" if d.period.start else names

    def _fill_category_filter(self, movements: list[TransactionDraft]) -> None:
        keep = self.category_filter.currentData()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem(tr(ALL_CATEGORIES), None)
        for cat in sorted({t.category for t in movements}, key=category_label):
            self.category_filter.addItem(category_label(cat), cat)
        index = self.category_filter.findData(keep) if keep is not None else 0
        self.category_filter.setCurrentIndex(max(index, 0))
        self.category_filter.blockSignals(False)

    def _on_search_changed(self, _text: str) -> None:
        if self.table.model_.rowCount() > DEBOUNCE_ROWS:
            self._search_timer.start()
        else:
            self._apply_filter()

    def _apply_filter(self) -> None:
        text = self.search.text().strip().lower()
        category = self.category_filter.currentData()

        def accept(t: TransactionDraft) -> bool:
            return (category is None or t.category == category) and (not text or text in t.description.lower())

        self.table.set_filter(accept)
        shown, total = self.table.proxy.rowCount(), self.table.model_.rowCount()
        self._count.setText(tr("{total} movimientos").format(total=total) if shown == total else tr("{shown} de {total} movimientos").format(shown=shown, total=total))

    # ------------------------------------------------------------------ categorias, presupuestos y exportacion
    def _on_cell_clicked(self, index) -> None:
        if index.column() == self.table.model_.columnCount() - 1:       # la columna de acciones (•••)
            self._open_menu_for(index)

    def _open_menu_for(self, index) -> None:
        self._show_row_menu(self.table.row_data(index.row()), QCursor.pos())

    def search_for(self, text: str) -> None:
        """Pone un texto en el buscador de movimientos (desde el buscador global) y lleva la vista hasta la tabla."""
        self.category_filter.setCurrentIndex(0)
        self.search.setText(text)
        self._apply_filter()
        self._scroll.ensureWidgetVisible(self.movements_card, 0, 40)

    def show_category(self, category) -> None:
        """Filtra la tabla por una categoria (desde un grafico o un presupuesto) y lleva la vista hasta ella."""
        pos = self.category_filter.findData(category)
        if pos < 0:
            return
        self.search.clear()
        self.category_filter.setCurrentIndex(pos)
        self._apply_filter()
        self._scroll.ensureWidgetVisible(self.movements_card, 0, 40)
        n = self.table.proxy.rowCount()
        tell(self.feedback, trn("Mostrando {n} movimiento de «{category}». Quita el filtro en el selector de categorías de la tabla.",
                                "Mostrando {n} movimientos de «{category}». Quita el filtro en el selector de categorías de la tabla.",
                                n).format(n=n, category=category_label(category)))

    def _show_row_menu(self, tx: TransactionDraft, pos: QPoint) -> None:
        menu = QMenu(self)
        if self._categories is not None:
            sub = menu.addMenu(tr("Cambiar categoría"))
            for cat in CATEGORY_CHOICES:
                action = sub.addAction(category_label(cat))
                action.setCheckable(True)
                action.setChecked(cat == tx.category)
                action.triggered.connect(lambda _=False, c=cat: self.change_category(tx, c))
            reset = menu.addAction(tr("Volver a la categoría automática"))
            reset.setEnabled(tx.is_manual)
            reset.triggered.connect(lambda _=False: self.change_category(tx, None))
            rule = menu.addAction(tr("Crear regla para «{description}»…").format(description=merchant_key(tx.description) or tx.description))
            rule.triggered.connect(lambda _=False: self.create_rule(tx))
            menu.addSeparator()
        copy = menu.addAction(tr("Copiar concepto"))
        copy.triggered.connect(lambda _=False: QGuiApplication.clipboard().setText(tx.description))
        self._run_menu(menu, pos)

    def _run_menu(self, menu: QMenu, pos: QPoint) -> None:
        menu.exec(pos)

    def change_category(self, tx: TransactionDraft, category) -> None:
        if self._categories is None:
            return
        snapshot = snapshot_of(self.feedback)
        self._categories.set_category(tx.tx_hash, category)
        self.categories_changed.emit()
        tell(self.feedback, tr("Categoría cambiada a «{category}».").format(category=category_label(category)) if category is not None
             else tr("Vuelve a la categoría automática."), snapshot)

    def create_rule(self, tx: TransactionDraft) -> bool:
        if self._categories is None:
            return False
        dialog = RuleDialog(merchant_key(tx.description) or tx.description, tx.category, self)
        if dialog.exec() != RuleDialog.DialogCode.Accepted:
            return False
        return self.add_rule(*dialog.result_rule())

    def add_rule(self, keyword: str, category) -> bool:
        snapshot = snapshot_of(self.feedback)
        try:
            changed = self._categories.add_rule(keyword, category)
        except RuleError as exc:
            QMessageBox.warning(self, tr("No se pudo guardar la regla"), str(exc))
            return False
        self.categories_changed.emit()
        tell(self.feedback, trn("Regla creada: {changed} movimiento cambiado a «{category}».",
                                "Regla creada: {changed} movimientos cambiados a «{category}».",
                                changed).format(changed=changed, category=category_label(category)), snapshot)
        return True

    def edit_budgets(self) -> None:
        if self._categories is None:
            return
        dialog = BudgetDialog(self._categories.budgets(), self)
        if dialog.exec() == BudgetDialog.DialogCode.Accepted:
            self.save_budgets(dialog.result_budgets())

    def save_budgets(self, budgets) -> None:
        snapshot = snapshot_of(self.feedback)
        self._categories.save_budgets(budgets)
        self.categories_changed.emit()          # Inicio tambien enseña los presupuestos
        tell(self.feedback, tr("Presupuestos guardados.") if budgets else tr("Presupuestos eliminados."), snapshot)

    def export_movements(self, path: str | None = None) -> int | None:
        """Guarda en CSV o Excel los movimientos que se ven (con el filtro y el orden de la tabla)."""
        rows = self.table.visible_rows()
        if not rows:
            QMessageBox.information(self, tr("Nada que exportar"), tr("No hay movimientos con el filtro actual."))
            return None
        if path is None:
            path, chosen = QFileDialog.getSaveFileName(
                self, tr("Exportar movimientos"), "movimientos.xlsx", tr("Excel (*.xlsx);;CSV (*.csv)"))
            if not path:
                return None
            if not path.lower().endswith((".csv", ".xlsx")):
                path += ".csv" if "csv" in chosen.lower() else ".xlsx"
        try:
            count = write_movements(path, rows, self._names, category_label)
        except ExportError as exc:
            QMessageBox.warning(self, tr("No se pudo exportar"), str(exc))
            return None
        tell(self.feedback, tr("{count} movimientos exportados a «{name}».").format(count=count, name=Path(path).name))
        return count

    # ------------------------------------------------------------------ gestion de cuentas
    def add_account_named(self, name: str) -> bool:
        try:
            info = self._service.add(name)
        except AccountError as exc:
            QMessageBox.warning(self, tr("No se pudo añadir la cuenta"), str(exc))
            return False
        self._fill_account_combo()
        self.account_combo.setCurrentIndex(self.account_combo.findData(info.id))
        self.accounts_changed.emit()
        tell(self.feedback, tr("Cuenta «{name}» añadida. Elígela al importar tus extractos.").format(name=info.name))
        return True

    def rename_selected(self, name: str) -> bool:
        ids = self.selected_account_ids()
        if not ids:
            return False
        try:
            self._service.rename(ids[0], name)
        except AccountError as exc:
            QMessageBox.warning(self, tr("No se pudo renombrar"), str(exc))
            return False
        self.accounts_changed.emit()
        return True

    def delete_selected(self) -> bool:
        ids = self.selected_account_ids()
        if not ids:
            return False
        name = self.account_combo.currentText()
        snapshot = snapshot_of(self.feedback)
        self._service.delete(ids[0])
        self.account_combo.setCurrentIndex(0)
        self.accounts_changed.emit()
        tell(self.feedback, tr("Cuenta «{name}» eliminada.").format(name=name), snapshot)
        return True

    def prompt_add(self) -> None:
        name, ok = QInputDialog.getText(self, tr("Añadir cuenta"), tr("Nombre de la cuenta:"))
        if ok and name.strip():
            self.add_account_named(name)

    def prompt_rename(self) -> None:
        if not self.selected_account_ids():
            return
        name, ok = QInputDialog.getText(self, tr("Renombrar cuenta"), tr("Nuevo nombre:"), QLineEdit.EchoMode.Normal,
                                        self.account_combo.currentText())
        if ok and name.strip():
            self.rename_selected(name)

    def prompt_delete(self) -> None:
        if not self.selected_account_ids():
            return
        answer = QMessageBox.question(
            self, tr("Eliminar cuenta"),
            tr("Se eliminará la cuenta «{currentText}» y todos sus movimientos.\nEsta acción no se puede deshacer.\n\n¿Quieres continuar?").format(currentText=self.account_combo.currentText()),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_selected()

    def refresh_theme(self) -> None:
        for chart in (self.categories, self.balance, self.monthly):
            chart.refresh_theme()
        self.table.refresh_theme()
        self.recurring_panel.refresh_theme()
        self.budget_panel.bars.update()
