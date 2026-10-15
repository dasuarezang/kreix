"""El orden de las tablas lo hace el modelo (rapido) y el proxy solo filtra."""
import time
from datetime import date
from decimal import Decimal as D

from PySide6.QtCore import Qt

from ui.widgets.tables import RIGHT, Column, DataTable

COLUMNS = [
    Column("FECHA", lambda r: r[0].isoformat(), lambda r: r[0]),
    Column("IMPORTE", lambda r: str(r[1]), lambda r: r[1], RIGHT),
    Column("CONCEPTO", lambda r: r[2], lambda r: r[2].lower(), stretch=True),
]
ROWS = [(date(2026, 9, 3), D("-5"), "b"), (date(2026, 9, 1), D("20"), "A"), (date(2026, 9, 2), D("-5"), "c")]


def amounts(table):
    return [r[1] for r in table.visible_rows()]


def test_header_sort_orders_by_the_column_key_and_can_go_back_to_the_received_order(qapp):
    table = DataTable(COLUMNS)
    table.set_rows(ROWS)
    assert table.visible_rows() == ROWS                                  # sin orden: el recibido
    table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
    assert amounts(table) == [D("-5"), D("-5"), D("20")]
    table.sortByColumn(1, Qt.SortOrder.DescendingOrder)
    assert amounts(table)[0] == D("20")
    table.sortByColumn(2, Qt.SortOrder.AscendingOrder)                   # por la clave (minusculas): a, b, c
    assert [r[2] for r in table.visible_rows()] == ["A", "b", "c"]
    table.model_.sort(-1)
    assert table.visible_rows() == ROWS


def test_sorting_survives_new_rows_and_composes_with_the_filter(qapp):
    table = DataTable(COLUMNS)
    table.set_rows(ROWS)
    table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
    table.set_rows(ROWS + [(date(2026, 9, 9), D("1"), "z")])             # recargar mantiene el orden elegido
    assert table.visible_rows()[0][2] == "z"
    table.set_filter(lambda r: r[1] < 0)
    assert [r[2] for r in table.visible_rows()] == ["b", "c"]
    assert table.cell_texts(0)[2] == "b"


def test_mixed_types_do_not_break_the_sort(qapp):
    table = DataTable([Column("X", lambda r: str(r), lambda r: r)])
    table.set_rows([3, "a", 1])
    table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    assert table.visible_rows() == [1, 3, "a"]


def test_sorting_twenty_thousand_rows_is_fast(qapp):
    rows = [(date(2020, 1, 1 + i % 28), D(i % 977), f"concepto {i}") for i in range(20000)]
    table = DataTable(COLUMNS)
    table.set_rows(rows)
    start = time.perf_counter()
    table.sortByColumn(1, Qt.SortOrder.DescendingOrder)
    assert time.perf_counter() - start < 1.5                             # con el orden de Qt en Python tardaba ~4 s
    assert table.proxy.rowCount() == 20000 and amounts(table)[0] == D(976)
