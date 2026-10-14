"""Tablas de datos: un modelo generico por columnas, con orden por cabecera y filtro."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from ui import fonts, theme

SORT_ROLE = Qt.ItemDataRole.UserRole
LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
ROW_HEIGHT = 38
HEADER_HEIGHT = 38


@dataclass(frozen=True, slots=True)
class Column:
    title: str
    text: Callable[[Any], str]                           # lo que se ve
    sort: Callable[[Any], Any] | None = None             # clave de orden (por defecto, el texto)
    align: Qt.AlignmentFlag = LEFT
    tone: Callable[[Any], str | None] | None = None      # "negative" | "positive" | "muted" | "accent"
    stretch: bool = False                                # la columna que absorbe el ancho sobrante


class RowsModel(QAbstractTableModel):
    def __init__(self, columns: Sequence[Column], rows: Sequence[Any] = ()) -> None:
        super().__init__()
        self.columns = list(columns)
        self._rows = list(rows)

    def set_rows(self, rows: Sequence[Any]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, row: int) -> Any:
        return self._rows[row]

    def sort_key(self, row: int, column: int) -> Any:
        col, item = self.columns[column], self._rows[row]
        return col.sort(item) if col.sort else col.text(item)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self.columns[section].title
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return self.columns[section].align
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        col, item = self.columns[index.column()], self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return col.text(item)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return col.align
        if role == Qt.ItemDataRole.ToolTipRole:
            return col.text(item)          # el texto completo, por si la celda lo recorta
        if role == SORT_ROLE:
            return col.sort(item) if col.sort else col.text(item)
        if role == Qt.ItemDataRole.ForegroundRole and col.tone:
            p = theme.current()
            color = {"negative": p.red, "positive": p.green, "muted": p.muted, "accent": p.accent}.get(col.tone(item) or "")
            return QColor(color) if color else None
        return None


class FilterProxy(QSortFilterProxyModel):
    """Orden por la clave de cada columna y filtro por una funcion sobre la fila."""

    def __init__(self) -> None:
        super().__init__()
        self.setSortRole(SORT_ROLE)
        self._predicate: Callable[[Any], bool] | None = None

    def set_predicate(self, predicate: Callable[[Any], bool] | None) -> None:
        self.beginFilterChange()
        self._predicate = predicate
        self.endFilterChange()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """Compara los valores de Python (Decimal, date...): Qt no sabe ordenarlos como variantes."""
        model: RowsModel = self.sourceModel()
        a, b = model.sort_key(left.row(), left.column()), model.sort_key(right.row(), right.column())
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self._predicate is None:
            return True
        return self._predicate(self.sourceModel().row_at(source_row))


class DataTable(QTableView):
    def __init__(self, columns: Sequence[Column], min_height: int = 320) -> None:
        super().__init__()
        self.model_ = RowsModel(columns)
        self.proxy = FilterProxy()
        self.proxy.setSourceModel(self.model_)
        self.setModel(self.proxy)
        self.setAlternatingRowColors(False)
        self.setFont(fonts.qfont(fonts.BODY_MEDIUM, 13, tabular=True))   # cifras de ancho fijo: las columnas se alinean
        self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setWordWrap(False)
        self.setMinimumHeight(min_height)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setFixedHeight(HEADER_HEIGHT)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.setSortingEnabled(True)
        self.proxy.sort(-1)  # arranca en el orden recibido (mas reciente primero)
        self._apply_widths()

    def _apply_widths(self) -> None:
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        for i, col in enumerate(self.model_.columns):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch if col.stretch else QHeaderView.ResizeMode.ResizeToContents)

    def set_rows(self, rows: Sequence[Any]) -> None:
        self.model_.set_rows(rows)
        self._apply_widths()

    def set_filter(self, predicate: Callable[[Any], bool] | None) -> None:
        self.proxy.set_predicate(predicate)

    def visible_rows(self) -> list[Any]:
        return [self.model_.row_at(self.proxy.mapToSource(self.proxy.index(r, 0)).row()) for r in range(self.proxy.rowCount())]

    def cell_texts(self, row: int) -> list[str]:
        return [str(self.proxy.index(row, c).data() or "") for c in range(self.proxy.columnCount())]

    def fit_height(self, max_rows: int = 8) -> None:
        """Ajusta el alto a las filas (para tablas pequenas que no deben tener scroll propio)."""
        rows = min(max(self.model_.rowCount(), 1), max_rows)
        height = HEADER_HEIGHT + rows * ROW_HEIGHT + 4
        self.setMinimumHeight(height)
        self.setMaximumHeight(height if self.model_.rowCount() <= max_rows else 16777215)

    def refresh_theme(self) -> None:
        self.viewport().update()
