from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from ui import theme
from ui.format import fmt_eur
from ui.widgets.period_bar import PeriodBar

FIX = Path(__file__).parent / "fixtures"
AS_OF_FILES = [FIX / "imagin_sample.csv", FIX / "myinvestor_operaciones.csv", FIX / "myinvestor_cartera.csv"]

TWO_MONTHS = (
    "Concepto;Fecha;Importe;Saldo\n"
    "MERCADONA CL TEST;05/10/2026;-10,00EUR;90,00EUR\n"
    "NETFLIX.COM;20/09/2026;-12,00EUR;100,00EUR\n"
    "TRASPASO;01/09/2026;112,00EUR;112,00EUR\n"
)


@pytest.fixture()
def two_months(tmp_path):
    f = tmp_path / "extractImagin"
    f.write_text(TWO_MONTHS, encoding="utf-8")
    return f


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    """Los avisos modales bloquearian la prueba."""
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)


# ---------------------------------------------------------------- selector de periodo
def test_period_bar_keeps_selection_when_reloaded_and_steps_with_arrows(qapp):
    bar, got = PeriodBar(), []
    bar.changed.connect(got.append)
    months = [date(2026, 10, 1), date(2026, 9, 1), date(2026, 8, 1)]
    bar.set_months(months)
    assert bar.current_month() is None                       # arranca en "Todo el historial"
    bar.select_month(date(2026, 9, 1))
    assert got == [date(2026, 9, 1)]
    bar.set_months(months)                                   # recargar no debe perder el mes elegido
    assert bar.current_month() == date(2026, 9, 1)
    bar.older.click()
    assert bar.current_month() == date(2026, 8, 1) and not bar.older.isEnabled()
    bar.newer.click()
    bar.newer.click()
    assert bar.current_month() == date(2026, 10, 1) and not bar.newer.isEnabled()
    bar.set_months([date(2026, 7, 1)])                       # si el mes desaparece, vuelve a global
    assert bar.current_month() is None


# ---------------------------------------------------------------- pestana Cuentas
def test_accounts_tab_starts_empty_then_fills(window, two_months):
    v = window.accounts_view
    assert v._stack.currentIndex() == 0
    window.import_view.import_paths([str(two_months)])
    assert v._stack.currentIndex() == 1
    assert v.table.proxy.rowCount() == 3
    assert v.card_balance._value.text() == fmt_eur(Decimal("90"))
    assert v.table.cell_texts(0)[0] == "05/10/2026"           # el mas reciente primero


def test_month_selection_filters_everything_and_persists_across_reloads(window, two_months):
    window.import_view.import_paths([str(two_months)])
    v = window.accounts_view
    v.period.select_month(date(2026, 9, 1))
    assert v.table.proxy.rowCount() == 2
    assert [t.description for t in v.table.visible_rows()] == ["NETFLIX.COM", "TRASPASO"]
    assert v.card_balance._value.text() == fmt_eur(Decimal("100"))        # saldo al cierre de septiembre
    assert v.mini_average._title.text().startswith("GASTO MEDIO DIARIO")
    window.refresh()                                                        # p. ej. tras importar otro archivo
    assert v.period.current_month() == date(2026, 9, 1)
    assert v.table.proxy.rowCount() == 2
    v.period.select_month(None)
    assert v.table.proxy.rowCount() == 3 and v.mini_average._title.text().startswith("GASTO MEDIO MENSUAL")


def test_movements_search_category_filter_and_sorting(window, two_months):
    window.import_view.import_paths([str(two_months)])
    v = window.accounts_view
    v.search.setText("netflix")
    assert v.table.proxy.rowCount() == 1 and "1 de 3" in v._count.text()
    v.search.setText("")
    assert v.table.proxy.rowCount() == 3 and v._count.text() == "3 movimientos"

    index = next(i for i in range(v.category_filter.count()) if v.category_filter.itemText(i) == "Supermercado")
    v.category_filter.setCurrentIndex(index)
    assert [t.description for t in v.table.visible_rows()] == ["MERCADONA CL TEST"]
    window.refresh()                                                        # el filtro de categoria se conserva
    assert v.category_filter.currentText() == "Supermercado" and v.table.proxy.rowCount() == 1
    v.category_filter.setCurrentIndex(0)

    amount_col = 4
    v.table.sortByColumn(amount_col, v.table.horizontalHeader().sortIndicatorOrder().AscendingOrder)
    assert v.table.cell_texts(0)[amount_col].startswith("−12")         # el mayor gasto arriba al ordenar por importe


def test_several_accounts_selection_and_management(window, two_months):
    v, imp = window.accounts_view, window.import_view
    window.import_view.import_paths([str(two_months)])                       # crea la cuenta "Imagin"
    assert v.add_account_named("Compartida")
    assert not v.add_account_named("Compartida")                              # repetida: avisa y no la crea
    assert [imp.account_combo.itemText(i) for i in range(imp.account_combo.count())] == ["Imagin", "Compartida"]

    imp.account_combo.setCurrentIndex(1)                                      # destino: Compartida
    imp.import_paths([str(two_months)])                                       # mismo extracto, otra cuenta: no es duplicado
    v.account_combo.setCurrentIndex(0)
    assert v.table.proxy.rowCount() == 6 and not v.table.isColumnHidden(1)    # columna Cuenta visible con varias
    assert v.card_balance._value.text() == fmt_eur(Decimal("180"))            # 90 + 90, cada cuenta con su saldo
    assert {v.table.cell_texts(r)[1] for r in range(6)} == {"Imagin", "Compartida"}

    v.account_combo.setCurrentIndex(2)                                        # solo "Compartida"
    assert v.table.proxy.rowCount() == 3 and v.table.isColumnHidden(1)
    assert v.rename_selected("Piso")
    assert v.account_combo.currentText() == "Piso"
    assert v.delete_selected()
    assert [imp.account_combo.itemText(i) for i in range(imp.account_combo.count())] == ["Imagin"]
    assert v.table.proxy.rowCount() == 3


# ---------------------------------------------------------------- pestana Inversion
def test_investment_tab_global_and_month(window):
    v = window.investment_view
    assert v._stack.currentIndex() == 0
    window.import_view.import_paths([str(p) for p in AS_OF_FILES])
    assert v._stack.currentIndex() == 1
    assert v.card_value._value.text() == fmt_eur(Decimal("1630"))
    assert v.operations_table.proxy.rowCount() == 3 and v.positions_table.proxy.rowCount() == 2
    assert v.operations_table.cell_texts(0)[0] == "01/03/2026"               # la mas reciente arriba
    assert v._banner.isVisibleTo(v)                                           # Fondo Test Dos no cuadra: hay aviso

    v.period.select_month(date(2026, 2, 1))
    assert v.operations_table.proxy.rowCount() == 1
    assert v.card_gain._title.text() == "VARIACIÓN DEL MES" and v.card_contrib._value.text().startswith("+")
    window.refresh()
    assert v.period.current_month() == date(2026, 2, 1)                       # persiste al recargar


def test_unreliable_returns_are_hidden_when_portfolio_does_not_match(window):
    window.import_view.import_paths([str(p) for p in AS_OF_FILES])           # Fondo Test Dos no tiene operaciones
    v = window.investment_view
    assert v.card_twr._value.text() == "—" and "no cuadra" in v.card_twr._sub.text()


# ---------------------------------------------------------------- estabilidad
def test_every_page_paints_in_both_themes(window, two_months):
    """Regresion: un grafico mal gestionado cerraba la aplicacion al dibujarse."""
    window.import_view.import_paths([str(two_months)] + [str(p) for p in AS_OF_FILES[1:]])
    window.resize(1280, 900)
    window.show()
    for name in ("dark", "light", "dark"):
        window.apply_theme(name)
        for page in range(len(window.PAGES)):
            window.navigate(page)
            QTest.qWait(20)
            assert not window.grab().isNull()
    window.accounts_view.period.select_month(date(2026, 9, 1))
    window.investment_view.period.select_month(date(2026, 2, 1))
    QTest.qWait(20)
    assert not window.grab().isNull()
    assert theme.current() is theme.DARK


def test_refresh_only_reloads_the_visible_page_and_the_rest_on_entering(window, two_months, monkeypatch):
    window.eager = False
    calls = []
    monkeypatch.setattr(window.accounts_view, "reload", lambda: calls.append("accounts"))
    monkeypatch.setattr(window.investment_view, "reload", lambda: calls.append("investment"))
    window.navigate(window.SUMMARY)
    calls.clear()
    window.refresh()
    assert calls == []                                   # Inicio esta a la vista: no se tocan las demas
    window.navigate(window.ACCOUNTS)
    assert calls == ["accounts"]
    window.navigate(window.SUMMARY)
    window.navigate(window.ACCOUNTS)
    assert calls == ["accounts"]                         # ya cargada: no se recalcula al volver
    window.refresh()
    assert calls == ["accounts", "accounts"]             # la visible se recarga de inmediato
    window.navigate(window.INVESTMENT)
    assert calls[-1] == "investment"
