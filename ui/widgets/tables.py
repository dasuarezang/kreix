"""Tablas de datos: un modelo generico por columnas, con orden por cabecera y filtro.

El orden lo hace el propio modelo con `list.sort` y claves precalculadas (20.000 filas en milisegundos);
el proxy solo filtra. Dejar que Qt ordene llamaria a Python en cada comparacion y tardaria segundos."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPoint, QSortFilterProxyModel, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QStyleOptionViewItem, QTableView

from ui import fonts, theme

SORT_ROLE = Qt.ItemDataRole.UserRole
LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
ROW_HEIGHT = 38
HEADER_HEIGHT = 38
RESIZE_REFIT_MS = 45      # al redimensionar, el alto de las filas con texto largo se reajusta como mucho cada tanto
SAMPLE_ROWS = 800        # filas que se miden para el ancho de las columnas


@dataclass(frozen=True, slots=True)
class Column:
    title: str
    text: Callable[[Any], str]                           # lo que se ve
    sort: Callable[[Any], Any] | None = None             # clave de orden (por defecto, el texto)
    align: Qt.AlignmentFlag = LEFT
    tone: Callable[[Any], str | None] | None = None      # "negative" | "positive" | "muted" | "accent"
    stretch: bool = False                                # la columna que absorbe el ancho sobrante
    tooltip: Callable[[Any], str] | None = None          # texto al pasar el raton (por defecto, el de la celda)


class RowsModel(QAbstractTableModel):
    def __init__(self, columns: Sequence[Column], rows: Sequence[Any] = ()) -> None:
        super().__init__()
        self.columns = list(columns)
        self._original = list(rows)                     # en el orden recibido
        self._rows = list(rows)                         # en el orden que se ve
        self._order: tuple[int, Qt.SortOrder] | None = None

    def set_rows(self, rows: Sequence[Any]) -> None:
        self.beginResetModel()
        self._original = list(rows)
        self._rows = self._sorted(self._original)
        self.endResetModel()

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Ordena por la clave de una columna; `column < 0` vuelve al orden recibido."""
        self._order = (column, order) if column >= 0 else None
        self.beginResetModel()
        self._rows = self._sorted(self._original)
        self.endResetModel()

    def _sorted(self, rows: list[Any]) -> list[Any]:
        if self._order is None:
            return list(rows)
        column, order = self._order
        col = self.columns[column]
        key = col.sort or col.text
        reverse = order == Qt.SortOrder.DescendingOrder
        try:
            return sorted(rows, key=key, reverse=reverse)
        except TypeError:                               # tipos mezclados (p. ej. importes y vacios): se ordena por texto
            return sorted(rows, key=lambda item: str(key(item)), reverse=reverse)

    def row_at(self, row: int) -> Any:
        return self._rows[row]

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
            return col.tooltip(item) if col.tooltip else col.text(item)   # el texto completo, por si la celda lo recorta
        if role == Qt.ItemDataRole.ForegroundRole and col.tone:
            p = theme.current()
            color = {"negative": p.red, "positive": p.green_text, "muted": p.muted, "accent": p.accent_text}.get(col.tone(item) or "")
            return QColor(color) if color else None
        return None


class FilterProxy(QSortFilterProxyModel):
    """Filtro por una funcion sobre la fila. Ordenar se delega en el modelo de origen."""

    def __init__(self) -> None:
        super().__init__()
        self.setDynamicSortFilter(False)
        self._predicate: Callable[[Any], bool] | None = None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        self.sourceModel().sort(column, order)

    def set_predicate(self, predicate: Callable[[Any], bool] | None) -> None:
        if predicate is None and self._predicate is None:
            return                                      # sigue sin filtro: no hay que volver a recorrer todas las filas
        self.beginFilterChange()
        self._predicate = predicate
        self.endFilterChange()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self._predicate is None:
            return True
        return self._predicate(self.sourceModel().row_at(source_row))


class DataTable(QTableView):
    context_requested = Signal(object, QPoint)      # (fila de datos, posicion global): menu contextual

    def __init__(self, columns: Sequence[Column], min_height: int = 320) -> None:
        super().__init__()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.model_ = RowsModel(columns)
        self.proxy = FilterProxy()
        self.proxy.setSourceModel(self.model_)
        self.setModel(self.proxy)
        self.setAlternatingRowColors(False)
        self.setFont(fonts.qfont(fonts.BODY, 13, tabular=True))   # cifras de ancho fijo: las columnas se alinean
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

    def row_data(self, proxy_row: int) -> Any:
        return self.model_.row_at(self.proxy.mapToSource(self.proxy.index(proxy_row, 0)).row())

    def _on_context_menu(self, pos: QPoint) -> None:
        index = self.indexAt(pos)
        if index.isValid():
            self.selectRow(index.row())
            self.context_requested.emit(self.row_data(index.row()), self.viewport().mapToGlobal(pos))

    def _apply_widths(self) -> None:
        """Las columnas con contenido toman el ancho que piden SUS textos una sola vez (al recibir las filas) y se quedan
        fijas. Con `ResizeToContents` Qt las recalculaba, mirando miles de filas, en cada cambio de estilo o de tema
        (con 20.000 movimientos, 10 segundos). El ancho es el mismo que calcularia Qt: el del delegado (con el relleno de la
        hoja de estilos) para las celdas mas largas, y el de la cabecera si es mayor."""
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        rows = self.model_._rows
        step = max(len(rows) // SAMPLE_ROWS, 1)
        candidates = range(0, len(rows), step)                  # filas repartidas por toda la tabla, no solo las primeras
        option = QStyleOptionViewItem()
        option.initFrom(self)
        option.widget = self                                    # la hoja de estilos (relleno de las celdas) se aplica por el widget
        option.font = self.font()
        delegate = self.itemDelegate()
        for i, col in enumerate(self.model_.columns):
            if col.stretch:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
                continue
            # la fuente es de cifras de ancho fijo: los textos mas largos son los mas anchos; basta medir unos pocos
            longest = sorted(candidates, key=lambda r: len(col.text(rows[r])), reverse=True)[:12]
            cell = max((delegate.sizeHint(option, self.model_.index(r, i)).width() for r in longest), default=0)
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(i, max(cell, header.sectionSizeHint(i)))

    def wrap_text(self) -> None:
        """Los textos largos pasan a una segunda linea (altura de fila automatica) en vez de cortarse."""
        self._wrap = True
        self.setWordWrap(True)
        # Las filas se miden de forma explicita (`resizeRowsToContents`, espaciada al redimensionar): con ResizeToContents Qt
        # las volvia a medir en cada cambio de ancho, imagen a imagen.
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        # la altura de fila depende del ancho de las columnas: se recalcula cuando el diseno ya se ha asentado
        self.horizontalHeader().sectionResized.connect(self._refit_soon)

    def set_rows(self, rows: Sequence[Any]) -> None:
        self.model_.set_rows(rows)
        self._apply_widths()
        if getattr(self, "_wrap", False):
            self.resizeRowsToContents()

    def set_filter(self, predicate: Callable[[Any], bool] | None) -> None:
        self.proxy.set_predicate(predicate)

    def visible_rows(self) -> list[Any]:
        return [self.model_.row_at(self.proxy.mapToSource(self.proxy.index(r, 0)).row()) for r in range(self.proxy.rowCount())]

    def cell_texts(self, row: int) -> list[str]:
        return [str(self.proxy.index(row, c).data() or "") for c in range(self.proxy.columnCount())]

    def fit_height(self, max_rows: int = 8) -> None:
        """Ajusta el alto a las filas (para tablas pequenas que no deben tener scroll propio).
        Se recalcula al cambiar el ancho: con texto en varias lineas, la altura de fila depende del ancho."""
        self._fit_rows = max_rows
        self._refit()

    def _refit_soon(self, *_args, delay: int = 0) -> None:
        """Reajusta el alto en cuanto el diseno se asiente. El temporizador cuelga de la tabla: si la tabla desaparece antes,
        no se ejecuta (un QTimer.singleShot suelto disparaba sobre una tabla ya destruida). Con `delay` (al redimensionar la
        ventana) los reajustes se espaciaron: durante un arrastre se recalcula unas pocas veces por segundo, no en cada imagen."""
        timer = getattr(self, "_refit_timer", None)
        if timer is None:
            timer = self._refit_timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._refit)
        if delay and timer.isActive():
            return                                      # ya hay uno pendiente: se aprovecha
        timer.start(delay)

    def _refit(self) -> None:
        max_rows = getattr(self, "_fit_rows", None)
        if max_rows is None or getattr(self, "_refitting", False):
            return
        self._refitting = True
        try:
            self._do_refit(max_rows)
        finally:
            self._refitting = False

    def _do_refit(self, max_rows: int) -> None:
        count = self.model_.rowCount()
        if getattr(self, "_wrap", False) and count:
            self.resizeRowsToContents()
            body = sum(self.rowHeight(r) for r in range(min(count, max_rows)))
        else:
            body = min(max(count, 1), max_rows) * ROW_HEIGHT
        height = HEADER_HEIGHT + body + 4
        if height != self.minimumHeight() or height != self.maximumHeight():
            self.setMinimumHeight(height)
            self.setMaximumHeight(height if count <= max_rows else 16777215)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if getattr(self, "_fit_rows", None) is not None and getattr(self, "_wrap", False):
            self._refit_soon(delay=RESIZE_REFIT_MS)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refit_soon()

    def refresh_theme(self) -> None:
        self.viewport().update()
