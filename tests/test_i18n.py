"""Idiomas: castellano, catalan e ingles. Catalogos completos, formatos, ayuda, banderas, selector y cambio en caliente."""
import ast
import sys
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal as D
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox

from core import i18n
from core.i18n import N_, tr, trn
from tests.conftest import dispose_windows
from ui.dialogs import WelcomeDialog
from ui.flags import flag_pixmap
from ui.format import category_label, fmt_datetime_long, fmt_eur, fmt_pct, fmt_units, month_long, month_short
from ui.help_content import ENTRIES, SECTIONS, localized_entries
from ui.widgets.language_picker import LanguagePicker

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import i18n_keys  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)


def pump(app: QApplication) -> None:
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QTest.qWait(30)


# ---------------------------------------------------------------- el mecanismo
def test_castellano_is_the_original_and_other_languages_translate_with_fallback():
    assert tr("Cuentas") == "Cuentas" and i18n.language() == "es"
    i18n.set_language("ca")
    assert tr("Cuentas") == "Comptes" and tr("texto sin traducir") == "texto sin traducir"
    i18n.set_language("en")
    assert tr("Cuentas") == "Accounts" and N_("Cuentas") == "Cuentas"
    assert trn("{n} cuenta", "{n} cuentas", 1) == "{n} account" and trn("{n} cuenta", "{n} cuentas", 3) == "{n} accounts"
    i18n.set_language("xx")                                                # un idioma desconocido se queda en castellano
    assert i18n.language() == "es" and i18n.normalize_language(None) == "es" and i18n.normalize_language("ca") == "ca"


def test_the_three_languages_have_a_name_and_a_catalog():
    assert i18n.LANGUAGES == ("es", "ca", "en")
    assert [i18n.NAMES[c] for c in i18n.LANGUAGES] == ["Castellano", "Català", "English"]
    assert i18n.catalog("es") == {} and len(i18n.catalog("ca")) > 500 and len(i18n.catalog("en")) > 500


# ---------------------------------------------------------------- catalogos completos
@pytest.mark.parametrize("language", ["ca", "en"])
def test_every_translatable_text_in_the_code_has_a_translation_with_the_same_placeholders(language):
    texts = i18n.catalog(language)
    keys = i18n_keys.collect()
    missing = [k for k in keys if k not in texts]
    assert not missing, f"faltan en {language}: {missing[:5]}"
    for key in keys:
        translated = texts[key]
        assert translated.strip(), key
        assert i18n_keys.placeholders(key) == i18n_keys.placeholders(translated), (language, key)
        assert ("\n" in key) == ("\n" in translated), (language, key)           # los saltos de linea se conservan


@pytest.mark.parametrize("language", ["ca", "en"])
def test_no_translation_is_left_over_in_the_catalog(language):
    """Un catalogo con claves que ya no existen en el codigo es basura que engana al revisar."""
    keys = set(i18n_keys.collect())
    stale = [k for k in i18n.catalog(language) if k not in keys]
    assert not stale, f"sobran en {language}: {stale[:5]}"


def test_translations_differ_from_the_spanish_for_ordinary_text():
    for language in ("ca", "en"):
        same = [k for k, v in i18n.catalog(language).items() if k == v and len(k) > 25 and "{" not in k and "<" not in k]
        assert len(same) < 8, same


# ---------------------------------------------------------------- no se escriben textos visibles sin traducir
UI_CALLS = {"QLabel", "QPushButton", "setText", "setToolTip", "setPlaceholderText", "setWindowTitle", "setAccessibleName",
            "PageHeader", "StatCard", "ChartCard", "HeroCard", "tell", "addAction", "addMenu"}
SPANISH = ("á", "é", "í", "ó", "ú", "ñ", "¿", "¡", " de ", " el ", " la ", " los ", " tu ", " tus ", " para ", " con ")


def test_visible_text_in_the_ui_always_goes_through_tr():
    offenders = []
    for path in sorted((ROOT / "ui").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(("ui/help_texts", "ui/theme", "ui/fonts", "ui/icons")) or rel in ("ui/help_content.py",):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if func not in UI_CALLS:
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    value = f" {arg.value} "
                    if any(word in value for word in SPANISH):
                        offenders.append(f"{rel}:{node.lineno} {arg.value[:50]!r}")
    assert not offenders, offenders


# ---------------------------------------------------------------- formatos
def test_numbers_dates_and_months_follow_the_language():
    assert fmt_eur(D("1234.5")) == "1.234,50\xa0€" and fmt_pct(D("0.0441")) == "4,4\xa0%" and fmt_units(D("2.5")) == "2,5000"
    assert month_long(date(2026, 9, 1)) == "septiembre 2026" and month_short(date(2026, 9, 1)) == "sep 26"
    i18n.set_language("ca")
    assert fmt_eur(D("1234.5")) == "1.234,50\xa0€" and month_long(date(2026, 3, 1)) == "març 2026"
    i18n.set_language("en")
    assert fmt_eur(D("1234.5")) == "€1,234.50" and fmt_eur(D("-5")) == "−€5.00" and fmt_pct(D("0.0441")) == "4.4%"
    assert fmt_pct(D("0.5"), 0, signed=True) == "+50%" and fmt_units(D("1234.5")) == "1,234.5000"
    assert month_long(date(2026, 9, 1)) == "September 2026" and month_short(date(2026, 9, 1)) == "Sep 26"


def test_category_labels_are_translated():
    from core.enums import TxCategory

    assert category_label(TxCategory.GROCERIES) == "Supermercado"
    i18n.set_language("ca")
    assert category_label(TxCategory.GROCERIES) == "Supermercat"
    i18n.set_language("en")
    assert category_label(TxCategory.GROCERIES) == "Groceries" and category_label(TxCategory.UNCATEGORIZED) == "Uncategorized"


def test_long_date_and_time_in_each_language():
    thursday = datetime(2027, 1, 7, 20, 20)
    assert fmt_datetime_long(thursday) == "Jueves 7 de Enero del 2027 - 20:20h"
    i18n.set_language("ca")
    assert fmt_datetime_long(thursday) == "Dijous 7 de Gener del 2027 - 20:20h"
    assert fmt_datetime_long(datetime(2027, 4, 12, 8, 5)) == "Dilluns 12 d'Abril del 2027 - 08:05h"      # elision delante de vocal
    i18n.set_language("en")
    assert fmt_datetime_long(thursday) == "Thursday 7 January 2027 - 20:20"


def test_greeting_in_each_language_ends_with_a_full_stop():
    from core.greeting import greeting

    assert greeting(datetime(2026, 1, 1, 9), "Ana") == "Buenos días, Ana."
    i18n.set_language("ca")
    assert [greeting(datetime(2026, 1, 1, h), "Ana") for h in (9, 16, 23)] == ["Bon dia, Ana.", "Bona tarda, Ana.", "Bona nit, Ana."]
    i18n.set_language("en")
    assert [greeting(datetime(2026, 1, 1, h)) for h in (9, 16, 23)] == ["Good morning.", "Good afternoon.", "Good evening."]


# ---------------------------------------------------------------- ayuda
@pytest.mark.parametrize("language", ["ca", "en"])
def test_every_help_entry_is_translated(language):
    i18n.set_language(language)
    translated = localized_entries()
    assert len(translated) == len(ENTRIES) and len({e.term for e in translated}) == len(ENTRIES)
    for original, entry in zip(ENTRIES, translated):
        assert entry.section == original.section
        assert entry.term != original.term or original.term in ("Bizum", "ISIN", "Saldo", "Valor de la cartera"), original.term
        for field in ("plain", "how", "example", "note", "todo"):
            has_original = bool(getattr(original, field))
            assert bool(getattr(entry, field)) == has_original, (language, original.term, field)
            if has_original and field != "example":
                assert getattr(entry, field) != getattr(original, field), (language, original.term, field)
        assert (entry.keywords or not original.keywords) and all(k == k.strip() for k in entry.keywords)


def test_help_in_other_languages_uses_translated_section_titles_and_search(window):
    i18n.set_language("en")
    window.help_view.set_query("savings")
    assert any(t == "Savings rate" for t in window.help_view.entry_terms())
    assert [tr(s) for s in SECTIONS][0] == "Your money at a glance"
    i18n.set_language("ca")
    window.help_view.set_query("estalvi")
    assert any(t == "Taxa d'estalvi" for t in window.help_view.entry_terms())


def test_shortcuts_help_lists_the_translated_page_names(window):
    for language, home in (("ca", "Inici"), ("en", "Home")):
        i18n.set_language(language)
        entry = next(e for e in localized_entries() if e.term in ("Dreceres de teclat", "Keyboard shortcuts"))
        assert f"Ctrl+1 {home}," in entry.plain and f"Ctrl+1 {tr(window.PAGES[0])}," in entry.plain


# ---------------------------------------------------------------- banderas
def test_flags_are_round_and_have_the_right_colors(qapp):
    spain, catalonia, uk = (flag_pixmap(c, 96).toImage() for c in ("es", "ca", "en"))
    for image in (spain, catalonia, uk):
        w = image.width()
        assert image.pixelColor(0, 0).alpha() == 0 and image.pixelColor(w - 1, w - 1).alpha() == 0     # las esquinas, fuera del circulo
        assert image.pixelColor(w // 2, w // 2).alpha() == 255
    # Espana: rojo arriba y abajo, amarillo en el centro
    assert spain.pixelColor(48, 14).name() == "#aa151b" and spain.pixelColor(48, 82).name() == "#aa151b"
    assert spain.pixelColor(30, 48).name() == "#f1bf00"
    # Cataluna: nueve franjas, doradas y rojas alternas, empezando y acabando en oro
    stripes = [catalonia.pixelColor(48, int(96 * (i + 0.5) / 9)).name() for i in range(9)]
    assert stripes == ["#fcdd09", "#da121a"] * 4 + ["#fcdd09"] and stripes.count("#da121a") == 4
    # Reino Unido: cruz roja en el centro, azul entre las cruces
    assert uk.pixelColor(48, 48).name() == "#c8102e" and uk.pixelColor(48, 20).name() == "#c8102e"
    assert uk.pixelColor(30, 8).name() in ("#012169", "#ffffff") or uk.pixelColor(30, 12).name() == "#012169"
    assert flag_pixmap("es", 24) is flag_pixmap("es", 24)                                   # en cache


def test_language_picker_shows_three_flagged_buttons_and_reports_the_choice(qapp):
    picker = LanguagePicker("ca")
    got = []
    picker.changed.connect(got.append)
    assert [b.text() for b in picker.buttons.values()] == ["Castellano", "Català", "English"]
    assert all(not b.icon().isNull() for b in picker.buttons.values())
    assert picker.language() == "ca" and picker.buttons["ca"].isChecked()
    picker.buttons["en"].click()
    assert got == ["en"] and picker.language() == "en" and not picker.buttons["ca"].isChecked()
    picker.set_language("es")
    assert got == ["en"] and picker.language() == "es"                                      # set_language no emite
    picker.set_language("zz")
    assert picker.language() == "es"
    picker.deleteLater()


# ---------------------------------------------------------------- cuadro de bienvenida
def test_the_welcome_dialog_changes_language_on_the_spot(qapp):
    dialog = WelcomeDialog(language="es")
    ok = dialog._buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert dialog._title.text() == "Bienvenido a Kreix" and ok.text() == "Empezar"
    dialog.languages.buttons["en"].click()
    assert i18n.language() == "en" and dialog._title.text() == "Welcome to Kreix" and ok.text() == "Start"
    assert dialog._ask_name.text() == "What's your name?" and dialog.interests.accounts.title_label.text() == "My bank accounts"
    assert dialog._buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == "Not now"
    dialog.languages.buttons["ca"].click()
    assert dialog._title.text() == "Et donem la benvinguda a Kreix" and dialog.result_language() == "ca"
    assert dialog._ask_language.text() == "En quin idioma vols Kreix?"
    dialog.deleteLater()


def test_welcome_dialog_starts_in_the_given_language(qapp):
    dialog = WelcomeDialog(language="ca")
    assert dialog.result_language() == "ca" and dialog._ask_interest.text() == "Què vols gestionar?"
    dialog.deleteLater()


def test_first_run_proposes_the_system_language_and_keeps_the_choice_even_with_not_now(window, monkeypatch, qapp):
    monkeypatch.setattr("ui.main_window.system_language", lambda: "ca")
    seen = []

    def fake(self):
        seen.append(self.result_language())
        self.languages.buttons["en"].click()                     # el usuario cambia a ingles y dice "ahora no"
        return WelcomeDialog.DialogCode.Rejected

    monkeypatch.setattr(WelcomeDialog, "exec", fake)
    monkeypatch.setattr(type(window), "rebuild", lambda self: seen.append("rebuild"))
    window.detect_language = True
    window.ask_name_if_needed()
    pump(qapp)
    assert seen == ["ca", "rebuild"]                                       # arranco en catalan (el del sistema) y se rehizo en ingles
    assert window._settings.language == "en" and window._svc.settings.load().language == "en"
    assert window._settings.name_asked


def test_without_detection_the_dialog_uses_the_saved_language(window, monkeypatch, qapp):
    monkeypatch.setattr("ui.main_window.system_language", lambda: "en")
    monkeypatch.setattr(WelcomeDialog, "exec", lambda self: WelcomeDialog.DialogCode.Rejected)
    window.ask_name_if_needed()
    assert window._settings.language == "es" and i18n.language() == "es"


# ---------------------------------------------------------------- toda la aplicacion cambia de idioma
def test_settings_language_card_has_the_picker_and_a_choice_rebuilds_the_window(window, monkeypatch, qapp):
    rebuilt = []
    monkeypatch.setattr(type(window), "rebuild", lambda self: rebuilt.append(self._settings.language))
    window.settings_view.language.buttons["ca"].click()
    pump(qapp)
    assert window._settings.language == "ca" and rebuilt == ["ca"]
    assert window._svc.settings.load().language == "ca" and i18n.language() == "ca"
    window.settings_view.language.buttons["ca"].click()                    # el mismo idioma: no hace nada
    pump(qapp)
    assert rebuilt == ["ca"]


def test_the_rebuilt_window_is_fully_in_the_new_language_and_keeps_data_and_page(tmp_path, qapp):
    from main import build_window

    window = build_window(f"sqlite:///{tmp_path / 'k.db'}", "k")
    window.eager = True
    window.import_view.import_paths([str(FIX / "imagin_sample.csv")])
    window.navigate(window.ACCOUNTS)
    window._svc.settings.save(replace(window._settings, language="en"))
    new = window.rebuild()
    try:
        assert i18n.language() == "en" and QApplication.instance().kreix_window is new
        assert [b.text() for b in new._nav.buttons()[:3]] == ["Home", "Accounts", "Investments"]
        assert new.stack.currentIndex() == new.ACCOUNTS and new.accounts_view.table.proxy.rowCount() == 6
        assert new.settings_view.language.language() == "en"
        assert new.accounts_view.card_balance._title.text() == "Balance" and new.toast.text == "Language changed to English."
        header = [c.title for c in new.accounts_view.table.model_.columns]
        assert header[:2] == ["DATE", "ACCOUNT"] and "€" in new.accounts_view.card_balance._value.text().replace("\xa0", "")
        new.navigate(new.SUMMARY)
        assert new.dashboard.header.title.text().startswith("Good ")
        assert new.dashboard.date_line.text().count(" ") >= 4
    finally:
        dispose_windows(new)
        QApplication.instance().kreix_window = None


def test_every_page_renders_in_catalan_and_english_without_leftover_spanish(tmp_path, qapp):
    """Recorre todas las paginas en cada idioma y mira los textos visibles: no puede colarse castellano."""
    import re

    from PySide6.QtWidgets import QAbstractButton, QLabel
    from shiboken6 import isValid
    from main import build_window

    shared = {
        "ca": r"Cuentas?|Gastos|Ingresos|Ajustes|Ayuda|Inversiones|Inicio|Movimientos?|Presupuestos?|Datos|Rentabilidad|Operaciones",
        "en": r"Cuentas?|Gastos|Ingresos|Saldo|Importar|Exportar|Ajustes|Ayuda|Inversiones|Inicio|Movimientos?|Presupuestos?|"
              r"Datos|Cartera|Rentabilidad|Operaciones",
    }
    for language in ("ca", "en"):
        leftovers = re.compile(rf"({shared[language]})")
        window = build_window(f"sqlite:///{tmp_path / (language + '.db')}", language)
        window.eager = True
        window._svc.settings.save(replace(window._settings, language=language))
        new = window.rebuild()
        try:
            new.start_demo()
            new.clock = lambda: datetime(2026, 10, 15, 22, 30)
            new.tick_clock()
            found = []
            for page in range(7):
                new.navigate(page)
                QTest.qWait(20)
                for widget in new.findChildren(QLabel) + new.findChildren(QAbstractButton):
                    if not isValid(widget):
                        continue
                    text = widget.text()
                    if text and leftovers.search(text):
                        found.append((page, text[:60]))
            assert not found, (language, found[:8])
        finally:
            dispose_windows(new)
            QApplication.instance().kreix_window = None


def test_the_language_travels_with_the_exported_file(tmp_path, qapp, monkeypatch):
    from main import build_window

    a = build_window(f"sqlite:///{tmp_path / 'a.db'}", "a")
    b = build_window(f"sqlite:///{tmp_path / 'b.db'}", "b")
    try:
        a.eager = b.eager = True
        a.import_view.import_paths([str(FIX / "imagin_sample.csv")])
        a._settings = replace(a._settings, language="ca")
        a._svc.settings.save(a._settings)
        file = tmp_path / "datos.kreix"
        a.export_view.export_to(str(file))
        i18n.set_language("es")
        rebuilt = []
        monkeypatch.setattr(type(b), "rebuild", lambda self: rebuilt.append(i18n.language()))
        assert b.restore_from(str(file)) is True
        pump(qapp)
        assert b._settings.language == "ca" and b._svc.settings.load().language == "ca"
        assert rebuilt == ["ca"]                                           # la ventana se rehace ya en catalan
        assert b.settings_view.language.language() == "ca"
    finally:
        dispose_windows(a, b)
