"""Asistente para importar de cualquier banco: se ven las primeras filas del archivo y se dice que columna es cada cosa.

El formato queda guardado con un nombre: la proxima vez que llegue un archivo con esas columnas, Kreix lo lee solo.
"""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialogButtonBox, QGridLayout, QHeaderView, QLabel, QLineEdit, QTableWidget,
    QTableWidgetItem, QWidget,
)

from core.i18n import tr, trn
from etl.common import ParseError
from etl.mapping import MAX_PREAMBLE_ROWS, SAMPLE_ROWS, ColumnMapping, FileSample
from services.import_service import ImportService
from ui.format import fmt_date, fmt_eur
from ui.popups import Combo
from ui.widgets.brand_dialog import BrandDialog

NONE = ""          # valor de "esta columna no se usa"


def _combo(name: str) -> Combo:
    combo = Combo()
    combo.setAccessibleName(name)
    combo.setMinimumWidth(200)
    return combo


class MappingDialog(BrandDialog):
    def __init__(self, service: ImportService, path: str, parent: QWidget | None = None, name: str = "") -> None:
        super().__init__(parent)
        self._service = service
        self._path = path
        self.sample: FileSample = service.sample(path)             # ParseError si no se puede leer: lo gestiona quien abre el cuadro
        self.setWindowTitle(tr("Importar de otro banco"))
        self.setMinimumWidth(780)

        self.header_row = _combo(tr("Fila de los títulos"))
        self.header_row.setMinimumWidth(90)
        for number in range(1, max(1, min(MAX_PREAMBLE_ROWS, len(self.sample.rows))) + 1):
            self.header_row.addItem(str(number), number - 1)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().hide()
        self.table.setAccessibleName(tr("Primeras filas del archivo"))

        self.date = _combo(tr("Fecha"))
        self.description = _combo(tr("Concepto"))
        self.amount_mode = _combo(tr("El importe viene en"))
        self.amount_mode.addItem(tr("Una columna, con el signo (negativo = gasto)"), "one")
        self.amount_mode.addItem(tr("Dos columnas: ingresos y gastos"), "two")
        self.amount = _combo(tr("Importe"))
        self.income = _combo(tr("Ingresos"))
        self.expense = _combo(tr("Gastos"))
        self.balance = _combo(tr("Saldo"))
        self.decimals = _combo(tr("Decimales"))
        self.decimals.addItem(tr("Con coma: 1.234,56"), True)
        self.decimals.addItem(tr("Con punto: 1,234.56"), False)
        self.date_order = _combo(tr("Orden de la fecha"))
        self.date_order.addItem(tr("Día / mes / año"), True)
        self.date_order.addItem(tr("Mes / día / año"), False)
        self.invert = QCheckBox(tr("En este archivo los gastos aparecen como números positivos"))
        self.name = QLineEdit(name)
        self.name.setPlaceholderText(tr("p. ej. Mi banco"))
        self.name.setAccessibleName(tr("Nombre del formato"))
        self.name.setMaxLength(40)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        def label(text: str) -> QLabel:
            item = QLabel(text)
            item.setObjectName("Muted")
            return item

        self._amount_labels = {"amount": label(tr("Importe")), "income": label(tr("Ingresos")), "expense": label(tr("Gastos"))}
        grid.addWidget(label(tr("Fecha")), 0, 0)
        grid.addWidget(self.date, 0, 1)
        grid.addWidget(label(tr("Concepto")), 0, 2)
        grid.addWidget(self.description, 0, 3)
        grid.addWidget(label(tr("El importe viene en")), 1, 0)
        grid.addWidget(self.amount_mode, 1, 1, 1, 3)
        grid.addWidget(self._amount_labels["amount"], 2, 0)
        grid.addWidget(self.amount, 2, 1)
        grid.addWidget(self._amount_labels["income"], 3, 0)
        grid.addWidget(self.income, 3, 1)
        grid.addWidget(self._amount_labels["expense"], 3, 2)
        grid.addWidget(self.expense, 3, 3)
        grid.addWidget(label(tr("Saldo (opcional)")), 4, 0)
        grid.addWidget(self.balance, 4, 1)
        grid.addWidget(label(tr("Decimales")), 5, 0)
        grid.addWidget(self.decimals, 5, 1)
        grid.addWidget(label(tr("Orden de la fecha")), 5, 2)
        grid.addWidget(self.date_order, 5, 3)
        grid.addWidget(self.invert, 6, 0, 1, 4)
        grid.addWidget(label(tr("Nombre del formato")), 7, 0)
        grid.addWidget(self.name, 7, 1, 1, 3)

        row = QGridLayout()
        row.setHorizontalSpacing(12)
        row.addWidget(label(tr("Fila de los títulos")), 0, 0)
        row.addWidget(self.header_row, 0, 1)
        row.setColumnStretch(2, 1)

        self.result = QLabel()
        self.result.setObjectName("Muted")
        self.result.setWordWrap(True)
        self.result_rows = QLabel()
        self.result_rows.setObjectName("Small")
        self.result_rows.setWordWrap(True)
        self.error = QLabel()
        self.error.setObjectName("LockError")
        self.error.setWordWrap(True)
        self.error.hide()

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok.setText(tr("Guardar y usar"))
        self.ok.setObjectName("Primary")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancelar"))
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)

        col = self.frame(tr("Importar de otro banco"),
                         tr("Kreix no conoce este archivo todavía. Dime qué columna es cada cosa y lo recordaré: la próxima "
                            "vez que llegue un archivo con las mismas columnas se leerá solo."))
        col.addLayout(row)
        col.addWidget(self.table)
        col.addLayout(grid)
        col.addWidget(self.result)
        col.addWidget(self.result_rows)
        col.addWidget(self.error)
        col.addWidget(self.buttons)

        self._loading = False
        self._load(self.sample.header_index, name)
        self.header_row.currentIndexChanged.connect(self._on_header_row)
        for combo in (self.date, self.description, self.amount, self.income, self.expense, self.balance, self.decimals,
                      self.date_order, self.amount_mode):
            combo.currentIndexChanged.connect(self._refresh)
        self.invert.toggled.connect(self._refresh)
        self.name.textChanged.connect(self._refresh)

    # ------------------------------------------------------------------ cargar el archivo
    def _fill(self, combo: Combo, optional: bool) -> None:
        combo.clear()
        if optional:
            combo.addItem(tr("— No usar —"), NONE)
        else:
            combo.addItem(tr("— Elige una columna —"), NONE)
        for header, key in zip(self.sample.headers, self.sample.keys):
            combo.addItem(header, key)

    def _select(self, combo: Combo, key: str) -> None:
        combo.setCurrentIndex(max(0, combo.findData(key)))

    def _load(self, header_index: int, name: str = "") -> None:
        """Muestra el archivo con esta fila de titulos y propone las columnas."""
        self._loading = True
        self.sample = self._service.sample(self._path, header_index)
        self.header_row.setCurrentIndex(max(0, min(self.sample.header_index, self.header_row.count() - 1)))
        self._fill_table()
        for combo in (self.date, self.description, self.amount, self.income, self.expense):
            self._fill(combo, optional=False)
        self._fill(self.balance, optional=True)
        guess = self._service.suggest_mapping(self.sample, name or self.name.text().strip())
        self._select(self.date, guess.date)
        self._select(self.description, guess.description)
        self.amount_mode.setCurrentIndex(1 if guess.uses_two_columns and (guess.income or guess.expense) else 0)
        self._select(self.amount, guess.amount)
        self._select(self.income, guess.income)
        self._select(self.expense, guess.expense)
        self._select(self.balance, guess.balance)
        self.decimals.setCurrentIndex(0 if guess.decimal_comma else 1)
        self.date_order.setCurrentIndex(0 if guess.day_first else 1)
        if not self.name.text().strip():
            self.name.setText(tr("Mi banco"))
        self._loading = False
        self._refresh()

    def _fill_table(self) -> None:
        rows = self.sample.body(SAMPLE_ROWS)
        self.table.clear()
        self.table.setColumnCount(len(self.sample.headers))
        self.table.setRowCount(len(rows))
        self.table.setHorizontalHeaderLabels(self.sample.headers)
        for r, values in enumerate(rows):
            for c in range(len(self.sample.headers)):
                value = values[c] if c < len(values) else ""
                item = QTableWidgetItem("" if value is None else str(value))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(r, c, item)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setFixedHeight(self.table.horizontalHeader().height() + 30 * len(rows) + 22)     # justo lo que ocupan las filas

    def _on_header_row(self, index: int) -> None:
        if not self._loading:
            self._load(int(self.header_row.itemData(index)))

    # ------------------------------------------------------------------ el formato que se esta definiendo
    def mapping(self) -> ColumnMapping:
        two = self.amount_mode.currentData() == "two"
        return ColumnMapping(
            name=self.name.text().strip(),
            date=self.date.currentData() or "",
            description=self.description.currentData() or "",
            amount="" if two else (self.amount.currentData() or ""),
            income=(self.income.currentData() or "") if two else "",
            expense=(self.expense.currentData() or "") if two else "",
            balance=self.balance.currentData() or "",
            day_first=bool(self.date_order.currentData()),
            decimal_comma=bool(self.decimals.currentData()),
            invert_sign=self.invert.isChecked(),
        )

    def _refresh(self, *_args) -> None:
        if self._loading:
            return
        two = self.amount_mode.currentData() == "two"
        self.amount.setEnabled(not two)
        self._amount_labels["amount"].setEnabled(not two)
        for widget in (self.income, self.expense, self._amount_labels["income"], self._amount_labels["expense"]):
            widget.setEnabled(two)
        mapping = self.mapping()
        self.error.hide()
        self.result_rows.setText("")
        problem = mapping.problem() or (tr("Ponle un nombre al formato.") if not mapping.name else None)
        parsed = None
        if mapping.problem() is None:
            try:
                parsed = self._service.try_mapping(self._path, self.sample, mapping)
            except ParseError as exc:
                problem = str(exc)
        self.ok.setEnabled(problem is None and parsed is not None)
        if parsed is None:
            self.result.setText(problem or "")
            return
        dates = [t.booking_date for t in parsed.transactions]
        count = len(parsed.transactions)
        text = trn("Se lee {n} movimiento, del {first} al {last}.", "Se leen {n} movimientos, del {first} al {last}.", count)
        self.result.setText(text.format(n=count, first=fmt_date(min(dates)), last=fmt_date(max(dates))))
        lines = [f"{fmt_date(t.booking_date)}  ·  {t.description[:48]}  ·  {fmt_eur(t.amount)}" for t in parsed.transactions[:3]]
        if parsed.ignored_rows:
            lines.append(trn("{n} fila se ha ignorado (por ejemplo, un total al final).",
                             "{n} filas se han ignorado (por ejemplo, totales al final).", parsed.ignored_rows).format(n=parsed.ignored_rows))
        self.result_rows.setText("\n".join(lines))
        if problem:
            self.error.setText(problem)
            self.error.show()

    def _save(self) -> None:
        mapping = self.mapping()
        try:
            self._service.save_format(mapping)
        except ParseError as exc:
            self.error.setText(str(exc))
            self.error.show()
            return
        self.accept()
