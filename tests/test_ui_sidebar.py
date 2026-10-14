import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent, QShortcut
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from core.categorizer import normalize
from tests.conftest import dispose_windows
from ui import theme
from ui.help_content import ENTRIES, SECTIONS, search
from ui.main_window import MainWindow

FIX = Path(__file__).parent / "fixtures"
FILES = [FIX / "imagin_sample.csv", FIX / "myinvestor_operaciones.csv", FIX / "myinvestor_cartera.csv"]


class Dialogs:
    """Sustituye los cuadros modales (que bloquearian la prueba) y anota lo que se mostro."""

    def __init__(self, monkeypatch, answer=QMessageBox.StandardButton.Yes):
        self.shown: list[tuple[str, str]] = []
        self.answer = answer

        def record(kind):
            def fake(parent, title, text, *a, **k):
                self.shown.append((kind, title))
                return self.answer if kind == "question" else None
            return fake

        for kind in ("question", "information", "warning"):
            monkeypatch.setattr(QMessageBox, kind, record(kind))

    def kinds(self):
        return [k for k, _ in self.shown]


@pytest.fixture()
def dialogs(monkeypatch):
    return Dialogs(monkeypatch)


def build(tmp_path, name):
    from main import build_window

    return build_window(f"sqlite:///{tmp_path / (name + '.db')}", name)


def drop(zone, paths):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    zone.dropEvent(QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))


# ---------------------------------------------------------------- barra lateral
def test_sidebar_layout_top_buttons_and_bottom_pills_in_order(window):
    window.resize(1280, 900)
    window.show()
    QApplication.processEvents()
    nav = [b for b in window.findChildren(QPushButton) if b.objectName() == "NavButton"]
    pills = [b for b in window.findChildren(QPushButton) if b.objectName() == "PillButton"]
    assert [b.text() for b in sorted(nav, key=lambda b: b.y())] == ["Resumen", "Cuentas", "Inversiones"]
    assert [b.text() for b in sorted(pills, key=lambda b: b.y())] == ["Importar", "Exportar", "Ajustes", "Ayuda"]
    assert max(b.mapTo(window, b.rect().topLeft()).y() for b in nav) < min(b.mapTo(window, b.rect().topLeft()).y() for b in pills)
    toggle_y = window.theme_switch.mapTo(window, window.theme_switch.rect().topLeft()).y()
    assert toggle_y > max(p.mapTo(window, p.rect().topLeft()).y() for p in pills)    # el conmutador, debajo de las pildoras


def test_pills_have_icons_and_follow_the_theme(window):
    pills = [b for b in window.findChildren(QPushButton) if b.objectName() == "PillButton"]
    assert len(pills) == 4 and all(not p.icon().isNull() for p in pills)
    assert all(p.isCheckable() and p.toolTip() for p in pills)
    window.apply_theme("light")
    assert all(not p.icon().isNull() for p in pills)


def test_theme_toggle_is_visual_without_text(window):
    assert window.theme_switch.text() == ""
    assert not [lbl for lbl in window.findChildren(QLabel) if "Modo" in lbl.text()]
    assert window.theme_switch.accessibleName() == "Modo oscuro" and window.theme_switch.toolTip()
    window.theme_switch.toggle()
    assert theme.current() is theme.LIGHT
    window.theme_switch.toggle()
    assert theme.current() is theme.DARK


def test_only_one_page_button_is_active_at_a_time(window):
    for page, name in enumerate(window.PAGES):
        window.navigate(page)
        checked = [b.text() for b in window.findChildren(QPushButton) if b.isCheckable() and b.isChecked()]
        assert checked == [name]


def test_keyboard_shortcuts_follow_the_page_order(window):
    """Cada Ctrl+N existe y lleva a la N-esima pagina (se dispara la senal: en pruebas sin pantalla
    la ventana no recibe el foco del sistema y las teclas simuladas no llegan)."""
    shortcuts = {sc.key().toString(): sc for sc in window.findChildren(QShortcut)}
    for number, name in enumerate(window.PAGES, start=1):
        shortcuts[f"Ctrl+{number}"].activated.emit()
        assert window.stack.currentIndex() == number - 1 and window._nav.button(number - 1).text() == name
    assert "Ctrl+T" in shortcuts
    assert window.PAGES[window.INVESTMENT] == "Inversiones"                      # en plural


# ---------------------------------------------------------------- ayuda
REQUIRED_TERMS = [
    "Patrimonio neto", "Liquidez", "Distribución de activos", "Saldo", "Ingresos", "Gastos", "Flujo neto", "Tasa de ahorro",
    "Gasto medio", "Mayor gasto", "Categoría principal", "Movimientos", "Valor liquidativo", "Precio medio", "Aportado",
    "Valor de la cartera", "Aportación media mensual", "Posición mayor", "Operaciones", "ISIN", "Plusvalía",
    "Rentabilidad global", "TWR", "TIR", "Variación del mes", "Valor estimado", "Bizum", "Traspaso", "Participación",
]


def test_help_covers_every_figure_the_app_shows():
    terms = [normalize(e.term) for e in ENTRIES]
    for wanted in REQUIRED_TERMS:
        assert any(t.startswith(normalize(wanted)) for t in terms), f"falta en la ayuda: {wanted}"


def test_help_entries_are_complete_unique_and_organised():
    assert len({e.term for e in ENTRIES}) == len(ENTRIES)
    assert all(e.plain.strip() and e.section in SECTIONS for e in ENTRIES)
    # los conceptos con calculo o con numeros llevan formula o ejemplo
    explained = {e.term: e for e in ENTRIES}
    for term in ("Tasa de ahorro", "TIR (tasa interna de retorno)", "TWR (rentabilidad ponderada en el tiempo)",
                 "Rentabilidad global", "Patrimonio neto"):
        assert explained[term].how and explained[term].example or explained[term].note


def test_help_search_matches_word_starts_ignoring_accents_and_ranks_titles_first():
    tir = [e.term for e in search(ENTRIES, "tir")]
    assert tir[0].startswith("TIR") and "Participación" not in tir       # "invertir" no cuenta
    assert [e.term for e in search(ENTRIES, "PLUSVALIA")] == [e.term for e in search(ENTRIES, "plusvalía")] != []
    assert search(ENTRIES, "zzzzz") == []
    assert len(search(ENTRIES, "")) == len(ENTRIES)
    assert search(ENTRIES, "tasa de ahorro")[0].term == "Tasa de ahorro"      # varias palabras: todas deben aparecer


def test_help_shortcuts_text_matches_the_real_shortcuts(window):
    entry = next(e for e in ENTRIES if e.term == "Atajos de teclado")
    expected = ", ".join(f"Ctrl+{i + 1} {name}" for i, name in enumerate(window.PAGES))
    assert expected in entry.plain.replace("\n", " ")


def test_help_opens_on_a_menu_of_section_buttons(window):
    view = window.help_view
    window.navigate(window.HELP)
    assert view.is_hub() and view.section_titles() == list(SECTIONS)                 # un boton por apartado, con su titulo
    assert all(not c.chip.pixmap().isNull() for c in view.cards)                     # y su icono
    assert view.entry_terms() == []                                                  # el menu no lista terminos


def test_each_section_button_opens_its_own_content_and_back_returns_to_the_menu(window):
    view = window.help_view
    window.navigate(window.HELP)
    for card in view.cards:
        card.click()
        assert view.current_section() == card.section and not view.is_hub()
        assert view.entry_terms() == [e.term for e in ENTRIES if e.section == card.section]
        assert view._section_title.text() == card.section
        view.back_button.click()
        assert view.is_hub() and view.current_section() is None
    # el contenido repartido entre secciones es todo el glosario, sin perder nada
    assert sum(len([e for e in ENTRIES if e.section == s]) for s in SECTIONS) == len(ENTRIES)


def test_entering_help_always_shows_the_menu(window):
    view = window.help_view
    window.navigate(window.HELP)
    view.cards[2].click()
    assert not view.is_hub()
    window.navigate(window.SUMMARY)
    window.navigate(window.HELP)
    assert view.is_hub()


def test_help_search_lives_on_the_menu_and_hides_the_buttons(window):
    view = window.help_view
    window.navigate(window.HELP)
    view.set_query("tir")
    assert view.entry_terms()[0].startswith("TIR") and len(view.entry_terms()) < len(ENTRIES)
    assert not view._grid_holder.isVisibleTo(view) and view._results_holder.isVisibleTo(view)
    view.set_query("zzzz")
    assert view.entry_terms() == []
    assert any("No hay resultados" in lbl.text() for lbl in view.findChildren(QLabel))
    view.set_query("")
    assert view._grid_holder.isVisibleTo(view) and not view._results_holder.isVisibleTo(view)


# ---------------------------------------------------------------- exportar
def test_export_page_exports_a_file_and_reflects_the_data(window, tmp_path, dialogs):
    v = window.export_view
    assert not v.button.isEnabled() and "Todavía no hay datos" in v._status.text()
    window.import_view.import_paths([str(p) for p in FILES], )
    window.navigate(window.EXPORT)
    assert v.button.isEnabled() and v._status.text() == ""
    assert "6 movimientos" in v._contents.text() and "3 operaciones" in v._contents.text()

    target = tmp_path / "copia"
    assert v.export_to(str(target))
    assert (tmp_path / "copia.kreix").is_file() and "Exportado" in v._status.text()
    assert re.fullmatch(r"kreix-datos-\d{4}-\d{2}-\d{2}\.kreix", v.suggested_name())


def test_data_moves_between_two_instances_through_the_kreix_file(tmp_path, dialogs, qapp):
    from ui.widgets import charts

    charts.ANIMATIONS = False
    a, b = build(tmp_path, "origen"), build(tmp_path, "destino")
    try:
        a.import_view.import_paths([str(p) for p in FILES])
        a.settings_view.p2p.switch.setChecked(False)                 # un ajuste distinto del de fabrica
        a.theme_switch.setChecked(False)                             # y modo claro
        file = tmp_path / "datos.kreix"
        assert a.export_view.export_to(str(file))

        assert b.dashboard._stack.currentIndex() == 0                # el destino arranca vacio
        drop(b.import_view.dropzone, [file])                         # se suelta el archivo en Importar
        assert dialogs.kinds() == ["information"]                    # sin datos previos: no pide confirmar

        assert b.dashboard._stack.currentIndex() == 1
        assert b.dashboard.card_net._value.text() == a.dashboard.card_net._value.text()
        assert b.accounts_view.table.proxy.rowCount() == a.accounts_view.table.proxy.rowCount() == 6
        assert b.investment_view.operations_table.proxy.rowCount() == 3
        assert theme.current() is theme.LIGHT and not b.settings_view.p2p.switch.isChecked()   # ajustes y tema viajan
        assert b.stack.currentIndex() == b.SUMMARY
    finally:
        dispose_windows(a, b)


def test_restoring_over_existing_data_asks_first(tmp_path, monkeypatch, qapp):
    from ui.widgets import charts

    charts.ANIMATIONS = False
    a, b = build(tmp_path, "origen"), build(tmp_path, "destino")
    try:
        a.import_view.import_paths([str(p) for p in FILES])
        file = tmp_path / "datos.kreix"
        a.export_view.export_to(str(file))
        b.import_view.import_paths([str(FIX / "imagin_overlap.csv")])          # el destino ya tiene otros datos
        assert b.accounts_view.table.proxy.rowCount() == 4

        refuse = Dialogs(monkeypatch, QMessageBox.StandardButton.Cancel)
        assert b.restore_from(str(file)) is False
        assert refuse.kinds() == ["question"] and b.accounts_view.table.proxy.rowCount() == 4   # no se toco nada

        accept = Dialogs(monkeypatch, QMessageBox.StandardButton.Yes)
        assert b.restore_from(str(file)) is True
        assert accept.kinds() == ["question", "information"]
        assert b.accounts_view.table.proxy.rowCount() == 6                    # ahora son los del archivo
    finally:
        dispose_windows(a, b)


def test_invalid_kreix_file_is_rejected_with_a_message_and_changes_nothing(window, tmp_path, dialogs):
    window.import_view.import_paths([str(FIX / "imagin_sample.csv")])
    fake = tmp_path / "falso.kreix"
    fake.write_text("no soy un export", encoding="utf-8")
    drop(window.import_view.dropzone, [fake])
    assert dialogs.kinds() == ["warning"]
    assert window.accounts_view.table.proxy.rowCount() == 6
    assert theme.current() is theme.DARK
