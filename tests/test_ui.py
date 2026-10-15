from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication

from ui import theme
from ui.format import fmt_eur, fmt_pct, month_long, month_short

FIX = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------- formato
@pytest.mark.parametrize(
    "value, expected",
    [
        (Decimal("5781.23"), "5.781,23 €"),
        (Decimal("-12.5"), "−12,50 €"),
        (Decimal("0"), "0,00 €"),
        (Decimal("-0.001"), "0,00 €"),   # sin "-0,00"
        (Decimal("1234567.8"), "1.234.567,80 €"),
        (None, "—"),
    ],
)
def test_fmt_eur(value, expected):
    assert fmt_eur(value) == expected


def test_fmt_pct_and_dates():
    assert fmt_pct(Decimal("0.0441"), 2) == "4,41 %"
    assert fmt_pct(-0.5, 0) == "−50 %"
    assert fmt_pct(0.1, 1, signed=True) == "+10,0 %"
    assert fmt_pct(None) == "—"
    assert month_short(date(2026, 10, 3)) == "oct 26"
    assert month_long(date(2026, 9, 1)) == "septiembre 2026"


# ---------------------------------------------------------------- ventana
def drop(zone, paths):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    event = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    zone.dropEvent(event)


def test_starts_with_empty_state(window):
    assert window.dashboard._stack.currentIndex() == 0
    assert window.stack.count() == 7


def test_drop_files_imports_and_fills_dashboard(window):
    got = []
    window.import_view.dropzone.files_dropped.connect(got.append)
    drop(window.import_view.dropzone, [FIX / "imagin_sample.csv", FIX / "myinvestor_operaciones.csv"])
    assert len(got) == 1 and len(got[0]) == 2
    assert window.dashboard._stack.currentIndex() == 0          # soltar solo ensena lo leido: aun no se ha guardado nada
    assert window.import_view._preview.count() == 2
    window.import_view.confirm_import()

    assert window.dashboard._stack.currentIndex() == 1          # el dashboard se actualizo solo
    assert window.dashboard.card_net._value.text() == fmt_eur(Decimal("117.51"))
    assert window.import_view._results.count() == 2              # una fila de resultado por archivo


def test_drop_ignores_folders(window, tmp_path):
    got = []
    window.import_view.dropzone.files_dropped.connect(got.append)
    drop(window.import_view.dropzone, [tmp_path])
    assert got == []


def test_theme_switch_applies_and_persists(window):
    assert theme.current() is theme.DARK
    window.theme_switch.setChecked(False)
    assert theme.current() is theme.LIGHT
    assert theme.LIGHT.bg in QApplication.instance().styleSheet()          # se aplico la hoja del modo claro
    assert window._svc.settings.load().theme == "light"
    window.theme_switch.setChecked(True)
    assert theme.current() is theme.DARK
    assert window._svc.settings.load().theme == "dark"


def test_savings_options_update_dashboard(window):
    window.import_view.import_paths([str(FIX / "imagin_sample.csv")])
    with_all = window.dashboard.card_savings._value.text()
    assert with_all != "—"
    window.settings_view.p2p.switch.setChecked(False)
    window.settings_view.transfers.switch.setChecked(False)
    assert window.dashboard.card_savings._value.text() == "—"   # sin ingresos computables
    assert window._svc.settings.load().include_p2p is False


def test_keyboard_navigation(window):
    window.navigate(window.SETTINGS)
    assert window.stack.currentIndex() == window.SETTINGS and window._nav.button(window.SETTINGS).isChecked()


def test_logo_assets_load(qapp):
    from ui import assets

    assert not assets.mark(64).isNull()
    assert not assets.wordmark(theme.DARK).isNull()
    assert not assets.wordmark(theme.LIGHT).isNull()
    assert not assets.app_icon().isNull()


def test_reset_button_empties_the_dashboard(window):
    window.import_view.import_paths([str(FIX / "imagin_sample.csv")])
    assert window.dashboard._stack.currentIndex() == 1
    window.reset_data()
    assert window.dashboard._stack.currentIndex() == 0


def test_file_dialog_shows_extensionless_files_by_default():
    from ui.widgets.dropzone import FILE_FILTER

    assert FILE_FILTER.split(";;")[0] == "Todos los archivos (*)"


def test_drop_accepts_file_without_extension(window, tmp_path):
    plain = tmp_path / "extractImagin"
    plain.write_text((FIX / "imagin_sample.csv").read_text(encoding="utf-8"), encoding="utf-8")
    drop(window.import_view.dropzone, [plain])
    window.import_view.confirm_import()
    assert window.dashboard._stack.currentIndex() == 1
