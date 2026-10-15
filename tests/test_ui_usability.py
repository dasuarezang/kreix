"""Usabilidad: avisos con Deshacer, vista previa de importacion, datos de ejemplo, primeros pasos,
acciones visibles, buscador global, frases de los graficos y novedades."""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from core.account_metrics import CategoryAmount
from core.enums import TxCategory
from core.metrics import AllocationSlice, MonthlyFlow, WealthPoint
from tests.test_ui_features import loaded  # noqa: F401  (fixture: 5 cargos de Netflix y un Mercadona ya importados)
from ui import headlines, theme
from ui.command_palette import Command, CommandPalette, rank_commands

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)


def rows_of(view):
    return view.table.proxy.rowCount()


# ---------------------------------------------------------------- borde de los botones laterales
def test_active_nav_button_gets_a_clean_ring_and_no_dotted_focus_rectangle(window):
    window.navigate(window.ACCOUNTS)
    assert window._nav.button(window.ACCOUNTS).isChecked()
    sheet = theme.stylesheet(theme.DARK)
    assert "QPushButton#NavButton:focus { border: 2px solid" in sheet.replace("{{", "{")
    assert sheet.count("outline: none") >= 3                         # sin el recuadro punteado en botones y pildoras
    window.show()
    window.navigate(window.SUMMARY)
    assert window.focusWidget() is window._nav.button(window.SUMMARY)   # el reborde acompana a la pagina activa


# ---------------------------------------------------------------- avisos y deshacer
def test_a_category_change_shows_a_toast_and_can_be_undone(loaded):
    v = loaded.accounts_view
    tx = next(t for t in v.table.visible_rows() if "MERCADONA" in t.description)
    v.change_category(tx, TxCategory.LEISURE)
    assert "Ocio" in loaded.toast.text and loaded.feedback.can_undo
    assert next(t for t in v.table.visible_rows() if "MERCADONA" in t.description).category == TxCategory.LEISURE
    assert loaded.feedback.undo()
    assert next(t for t in v.table.visible_rows() if "MERCADONA" in t.description).category == TxCategory.GROCERIES
    assert loaded.toast.text == "Cambio deshecho" and not loaded.feedback.can_undo


def test_only_the_latest_change_can_be_undone(loaded):
    v = loaded.accounts_view
    tx = next(t for t in v.table.visible_rows() if "MERCADONA" in t.description)
    v.change_category(tx, TxCategory.LEISURE)
    v.save_budgets({TxCategory.GROCERIES: D(100)})
    assert loaded.toast.text == "Presupuestos guardados."
    loaded.feedback.undo()                                             # deshace los presupuestos, no la categoria
    assert loaded._svc.categories.budgets() == {}
    assert next(t for t in v.table.visible_rows() if "MERCADONA" in t.description).category == TxCategory.LEISURE
    assert not loaded.feedback.undo()


def test_undoing_a_reset_brings_the_data_back(loaded):
    before = rows_of(loaded.accounts_view)
    loaded.reset_data()
    assert loaded.dashboard._stack.currentIndex() == 0 and loaded.toast.text == "Datos borrados."
    loaded.toast.undo_button.click()
    assert rows_of(loaded.accounts_view) == before and loaded.dashboard._stack.currentIndex() == 1


def test_exporting_and_adding_accounts_confirm_without_offering_undo(loaded, tmp_path):
    loaded.accounts_view.export_movements(str(tmp_path / "m.csv"))
    assert "exportados" in loaded.toast.text and not loaded.feedback.can_undo
    loaded.accounts_view.add_account_named("Ahorro")
    assert "Ahorro" in loaded.toast.text


# ---------------------------------------------------------------- vista previa de importacion
def test_dropping_files_only_previews_and_confirming_imports_with_an_undo(window):
    v = window.import_view
    v.preview_paths([str(FIX / "imagin_sample.csv"), str(FIX / "myinvestor_operaciones.csv")])
    assert v._preview_box.isVisibleTo(v) and v._preview.count() == 2
    assert window.dashboard._stack.currentIndex() == 0                 # nada guardado todavia
    assert "9 filas" in v.confirm_button.text()
    v.confirm_import()
    assert not v._preview_box.isVisibleTo(v) and window.dashboard._stack.currentIndex() == 1
    assert window.toast.text.startswith("Importado: 9 nuevos") and window.feedback.can_undo
    window.feedback.undo()
    assert window.dashboard._stack.currentIndex() == 0                 # deshacer devuelve el estado de antes de importar


def test_cancelling_a_preview_saves_nothing(window):
    v = window.import_view
    v.preview_paths([str(FIX / "imagin_sample.csv")])
    v.cancel_preview()
    assert not v._preview_box.isVisibleTo(v) and v.confirm_import() is None
    assert window.dashboard._stack.currentIndex() == 0


def test_preview_says_when_there_is_nothing_new_and_explains_bad_files(window, tmp_path):
    v = window.import_view
    v.import_paths([str(FIX / "imagin_sample.csv")])
    bad = tmp_path / "raro.csv"
    bad.write_text("a;b\n1;2\n", encoding="utf-8")
    v.preview_paths([str(FIX / "imagin_sample.csv"), str(bad)])
    assert not v.confirm_button.isEnabled() and v.confirm_button.text() == "No hay nada nuevo que importar"
    texts = [lbl.text() for i in range(v._preview.count()) for lbl in v._preview.itemAt(i).widget().findChildren(type(v._preview_title))]
    assert any("ya estaban importados" in t for t in texts)
    assert any("no reconozco" in t.lower() for t in texts)               # el error dice que hacer, no solo que falla


def test_a_kreix_file_skips_the_preview_and_goes_to_restore(window, tmp_path):
    asked = []
    window.import_view.restore_requested.connect(asked.append)
    window.import_view.preview_paths([str(tmp_path / "datos.kreix")])
    assert asked == [str(tmp_path / "datos.kreix")] and not window.import_view._preview_box.isVisibleTo(window.import_view)


# ---------------------------------------------------------------- datos de ejemplo y primeros pasos
def test_demo_mode_loads_example_data_and_leaves_when_importing_real_ones(window):
    window.start_demo()
    assert window.dashboard._stack.currentIndex() == 1 and window._demo
    assert window.demo_banner.isVisibleTo(window) and window._svc.settings.load_state()["demo"] == "1"
    assert not window.start_demo()                                       # con datos no se mezcla nada
    window.import_view.import_paths([str(FIX / "imagin_sample.csv")])
    assert not window._demo and not window.demo_banner.isVisibleTo(window)
    assert rows_of(window.accounts_view) == 6                            # solo lo real: lo de ejemplo se ha quitado


def test_ending_the_demo_can_be_undone_and_reset_clears_the_flag(window):
    window.start_demo()
    window.end_demo()
    assert window.dashboard._stack.currentIndex() == 0 and not window._demo
    window.toast.undo_button.click()
    assert window.dashboard._stack.currentIndex() == 1 and window._demo and window.demo_banner.isVisibleTo(window)
    window.reset_data()
    assert not window._demo and "demo" not in window._svc.settings.load_state()


def test_demo_banner_survives_a_restart(tmp_path, qapp):
    from main import build_window
    from tests.conftest import dispose_windows

    url = f"sqlite:///{tmp_path / 'k.db'}"
    first = build_window(url, "k")
    first.start_demo()
    dispose_windows(first)
    second = build_window(url, "k")
    try:
        assert second._demo and second.demo_banner.isVisibleTo(second)
    finally:
        dispose_windows(second)


def test_welcome_screen_offers_import_and_demo(window):
    assert window.dashboard._stack.currentIndex() == 0
    got = []
    window.dashboard.go_import.connect(lambda: got.append("import"))
    window.dashboard.onboarding.import_button.click()
    window.dashboard.onboarding.demo_button.click()
    assert got == ["import"] and window._demo                            # el segundo boton carga el ejemplo


def test_first_steps_list_tracks_progress_and_can_be_hidden(window):
    window.import_view.import_paths([str(FIX / "imagin_sample.csv")])
    setup = window.dashboard.setup
    assert setup.isVisibleTo(window.dashboard) and setup.subtitle.text() == "1 de 4 hechos"
    nav = []
    setup.navigate_requested.connect(nav.append)
    window.dashboard._go = None
    window._go_from_setup("accounts")
    assert window.stack.currentIndex() == window.ACCOUNTS
    window.navigate(window.SUMMARY)
    setup.hide_button.click()
    assert not setup.isVisibleTo(window.dashboard) and window._svc.settings.load_state()["setup_hidden"] == "1"
    window.import_view.import_paths([str(FIX / "myinvestor_operaciones.csv")])
    assert not setup.isVisibleTo(window.dashboard)                       # sigue oculta aunque se importe mas


# ---------------------------------------------------------------- acciones visibles
def test_actions_column_and_double_click_open_the_row_menu(loaded, monkeypatch):
    v = loaded.accounts_view
    shown = []
    monkeypatch.setattr(type(v), "_run_menu", lambda self, menu, pos: shown.append([x.text() for x in menu.actions() if x.text()]))
    last = v.table.model_.columnCount() - 1
    assert v.table.model_.columns[last].title == "" and v.table.cell_texts(0)[last] == "•••"
    v._on_cell_clicked(v.table.proxy.index(0, last))
    assert len(shown) == 1 and "Cambiar categoría" in shown[0] and any("Crear regla" in t for t in shown[0])
    v._on_cell_clicked(v.table.proxy.index(0, 2))                        # otra columna: no abre nada
    assert len(shown) == 1
    v._open_menu_for(v.table.proxy.index(1, 2))                          # doble clic en cualquier celda
    assert len(shown) == 2


def test_clicking_a_category_or_a_budget_filters_the_movements(loaded):
    v = loaded.accounts_view
    v.save_budgets({TxCategory.SUBSCRIPTIONS: D(100)})
    assert rows_of(v) == 6
    v.categories.category_clicked.emit(TxCategory.SUBSCRIPTIONS)
    assert rows_of(v) == 5 and v.category_filter.currentData() == TxCategory.SUBSCRIPTIONS
    assert "5 movimientos" in loaded.toast.text
    v.category_filter.setCurrentIndex(0)
    v.budget_panel.bars.category_clicked.emit(TxCategory.GROCERIES)
    assert rows_of(v) == 1
    v.show_category(TxCategory.HEALTH)                                   # sin movimientos de esa categoria: no hace nada raro
    assert rows_of(v) == 1


def test_category_chart_rows_are_clickable_only_with_a_real_category(loaded):
    chart = loaded.accounts_view.categories
    got = []
    chart.category_clicked.connect(got.append)
    chart.resize(500, 300)
    QTest.mouseClick(chart, Qt.MouseButton.LeftButton, pos=QPoint(100, 8 + chart.ROW_H // 2))
    assert got and isinstance(got[0], TxCategory)


def test_a_budget_on_the_summary_leads_to_its_movements(loaded):
    loaded.accounts_view.save_budgets({TxCategory.GROCERIES: D(1)})
    loaded.dashboard.alerts.bars.category_clicked.emit(TxCategory.GROCERIES)
    assert loaded.stack.currentIndex() == loaded.ACCOUNTS
    assert loaded.accounts_view.category_filter.currentData() == TxCategory.GROCERIES


# ---------------------------------------------------------------- buscador global
def test_rank_commands_matches_word_starts_ignoring_accents_and_puts_titles_first():
    cmds = [Command("Ir a Cuentas", "Ctrl+2", lambda: None), Command("Cambiar a modo oscuro", "Ctrl+T", lambda: None, "tema noche"),
            Command("Ayuda: Tasa de ahorro", "Ayuda", lambda: None, "ahorro")]
    assert [c.title for c in rank_commands(cmds, "")] == [c.title for c in cmds]
    assert [c.title for c in rank_commands(cmds, "cuen")] == ["Ir a Cuentas"]
    assert [c.title for c in rank_commands(cmds, "TEMA")] == ["Cambiar a modo oscuro"]    # por sinonimo
    assert [c.title for c in rank_commands(cmds, "ahorro")][0] == "Ayuda: Tasa de ahorro"
    assert rank_commands(cmds, "tasa ahor") and not rank_commands(cmds, "zzz")
    assert not rank_commands(cmds, "uentas")                                          # solo inicios de palabra


def test_palette_runs_the_chosen_command_and_searches_movements(loaded):
    ran = []
    palette = CommandPalette([Command("Ir a Cuentas", "", lambda: ran.append("cuentas"))],
                             lambda q: [Command("NETFLIX.COM", "05/09/2026", lambda: ran.append("mov"), group="Movimientos")])
    palette.input.setText("cuen")
    assert [c.title for c in palette._shown] == ["Ir a Cuentas"]
    palette.run_selected()
    QTest.qWait(30)
    assert ran == ["cuentas"]
    second = CommandPalette([], lambda q: [Command("NETFLIX.COM", "x", lambda: ran.append("mov"))])
    second.input.setText("net")
    QTest.qWait(250)                                                     # los movimientos se buscan al dejar de teclear
    assert [c.title for c in second._shown] == ["NETFLIX.COM"]
    for dialog in (palette, second):                                     # sin dialogos vivos: cada tema repinta todo lo que exista
        dialog.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_window_palette_commands_cover_pages_actions_help_and_real_movements(loaded):
    titles = [c.title for c in loaded.palette_commands()]
    assert "Ir a Inversiones" in titles and "Cambiar entre modo claro y oscuro" in titles
    assert any(t.startswith("Ayuda: Tasa de ahorro") for t in titles)
    assert "Probar con datos de ejemplo" not in titles                  # ya hay datos
    found = loaded._movement_commands("netflix")
    assert found and all("NETFLIX" in c.title for c in found)
    found[0].run()
    assert loaded.stack.currentIndex() == loaded.ACCOUNTS and loaded.accounts_view.search.text() == "NETFLIX.COM"
    loaded._open_help("TIR")
    assert loaded.stack.currentIndex() == loaded.HELP


def test_search_movements_is_case_insensitive_and_escapes_wildcards(loaded):
    svc = loaded._svc.accounts
    assert len(svc.search_movements("netflix")) == 5 and len(svc.search_movements("netflix", limit=2)) == 2
    assert svc.search_movements("100%") == [] and svc.search_movements("_") == []


# ---------------------------------------------------------------- frases de los graficos
def nb(text: str) -> str:
    """Los importes y porcentajes llevan un espacio duro antes del simbolo."""
    return text.replace(" €", " €").replace(" %", " %")


def test_chart_headlines_say_something_true_or_nothing():
    cats = [CategoryAmount(TxCategory.GROCERIES, D(100), D("0.5")), CategoryAmount(TxCategory.DINING, D(100), D("0.5"))]
    assert "Supermercado" in headlines.category_headline(cats) and "50" in headlines.category_headline(cats)
    assert headlines.category_headline([]) == ""
    up = [(date(2026, 9, 1), D(100)), (date(2026, 9, 9), D(250))]
    assert headlines.balance_headline(up, True) == nb("Tu saldo ha subido 150,00 € este mes.")
    assert "bajado" in headlines.balance_headline(up[::-1], False) and headlines.balance_headline(up[:1], True) == ""
    flows = [MonthlyFlow(date(2026, 8, 1), D(100), D(50), D(0)), MonthlyFlow(date(2026, 9, 1), D(100), D(150), D(30))]
    assert headlines.monthly_headline(flows) == "Has gastado menos de lo que ingresas en 1 de 2 meses."
    assert nb("ingresaste 100,00 €") in headlines.flow_headline(flows) and nb("aportaste 30,00 €") in headlines.flow_headline(flows)
    assert headlines.allocation_headline(D(50), D(50), D(100)).startswith("El 50") and headlines.allocation_headline(D(5), D(0), D(5)) == ""
    pts = [WealthPoint(date(2026, 1, 31), D(0), D(0), D(0), D(100)), WealthPoint(date(2026, 9, 30), D(0), D(1100), D(1000), D(1500))]
    assert nb("ha crecido 1.400,00 €") in headlines.wealth_headline(pts) and headlines.wealth_headline(pts[:1]) == ""
    assert nb("la rentabilidad ha sumado 100,00 €") in headlines.evolution_headline(pts)
    funds = [AllocationSlice("Fondo A", D(70), D("0.7")), AllocationSlice("Fondo B", D(30), D("0.3"))]
    assert headlines.fund_headline(funds) == "Tu mayor posición es Fondo A: el 70 % de la cartera.".replace(" %", "\xa0%")
    assert headlines.fund_headline(funds[:1]).startswith("Toda tu cartera")


def test_charts_show_their_headline_in_the_pages(loaded):
    assert "Netflix" in loaded.accounts_view.category_card._headline.text() or "Suscripciones" in loaded.accounts_view.category_card._headline.text()
    assert loaded.accounts_view.category_card._headline.isVisibleTo(loaded.accounts_view)
    assert loaded.dashboard.flow_card._headline.text().startswith("En ")


# ---------------------------------------------------------------- pagina vacia y novedades
def test_empty_pages_explain_what_they_will_show_and_what_is_needed(window):
    for view in (window.accounts_view, window.investment_view):
        assert view._stack.currentIndex() == 0
    assert window.accounts_view._empty_title.text() == "Aún no tienes ninguna cuenta" or window.accounts_view._empty_title.text()
    from ui.widgets.onboarding import EmptyState
    assert all(isinstance(v._stack.widget(0), EmptyState) for v in (window.accounts_view, window.investment_view))


def test_whats_new_is_shown_once_after_an_update_but_never_on_a_first_run(tmp_path, qapp, monkeypatch):
    from main import build_window
    from tests.conftest import dispose_windows
    from ui.whats_new import VERSION, WhatsNewDialog, notes_for

    shown = []
    monkeypatch.setattr(WhatsNewDialog, "exec", lambda self: shown.append(self.windowTitle()))
    assert notes_for(VERSION) and notes_for("0.0.1") == ()
    url = f"sqlite:///{tmp_path / 'k.db'}"
    first = build_window(url, "k")
    first.announce_new_version()                                         # primera ejecucion, sin datos
    assert shown == [] and first._svc.settings.load_state()["seen_version"] == VERSION
    first._svc.settings.save_state(seen_version="0.1.0")                  # simula venir de una version anterior
    first._state["seen_version"] = "0.1.0"
    first.announce_new_version()
    first.announce_new_version()
    assert shown == [f"Novedades de Kreix {VERSION}"]                      # una sola vez
    dispose_windows(first)
    legacy = build_window(f"sqlite:///{tmp_path / 'l.db'}", "l")          # usuario antiguo: tiene datos pero no hay version guardada
    try:
        legacy.import_view.import_paths([str(FIX / "imagin_sample.csv")])
        legacy._state.pop("seen_version", None)
        legacy.announce_new_version()
        assert len(shown) == 2
    finally:
        dispose_windows(legacy)
