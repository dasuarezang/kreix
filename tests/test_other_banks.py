"""Importar de cualquier banco: sugerencias de columnas, lectura con un formato propio, formatos guardados y el asistente."""
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from core import i18n
from core.entities import FileKind
from data.database import init_db, make_engine, make_session_factory, session_scope
from data.models import Account, Transaction
from etl.common import ParseError
from etl.dispatcher import UnknownFormatError, parse_file
from etl.generic_parser import parse as parse_generic
from etl.common import build_table
from etl.mapping import (
    ColumnMapping, FileSample, dump_formats, find_header, guess_day_first, guess_decimal_comma, guess_header_row,
    guess_mapping, load_formats, parse_amount, parse_date,
)
from services.import_service import ImportService
from tests.conftest import dispose_windows

SPANISH = (
    "Extracto de movimientos;;;;;\n"
    "Cuenta: ES00 0000 0000 0000;;;;;\n"
    ";;;;;\n"
    "Fecha operación;Fecha valor;Concepto;Cargo;Abono;Saldo\n"
    "03/04/2026;03/04/2026;COMPRA MERCADONA;23,40;;1.976,60\n"
    "02/04/2026;02/04/2026;NOMINA EMPRESA;;1.500,00;2.000,00\n"
    "01/04/2026;01/04/2026;RECIBO LUZ;45,10;;500,00\n"
    "Total;;;68,50;1.500,00;\n"
)
ENGLISH = (
    "Date,Description,Amount,Balance\n"
    '04/13/2026,Coffee shop,-3.50,"1,200.00"\n'
    '04/12/2026,Salary,"2,500.00","1,203.50"\n'
    '04/11/2026,Rent,"-900.00",-1296.50\n'
)
SINGLE = (
    "Data;Concepte;Import;Saldo\n"
    "10/05/2026;Supermercat;-12,30 EUR;100,00\n"
    "09/05/2026;Sou;1.100,00 EUR;112,30\n"
)


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def service():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    return ImportService(factory), factory


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)


# ---------------------------------------------------------------- numeros y fechas
@pytest.mark.parametrize("text, comma, expected", [
    ("-2,99 EUR", True, D("-2.99")), ("1.234,56", True, D("1234.56")), ("(12,50)", True, D("-12.50")),
    ("12,50-", True, D("-12.50")), ("1,234.56", False, D("1234.56")), ("-1,234.5 USD", False, D("-1234.5")),
    ("€ 7", True, D("7")), (12.5, True, D("12.5")), (3, False, D(3)),
])
def test_amounts_in_many_styles(text, comma, expected):
    assert parse_amount(text, comma) == expected


@pytest.mark.parametrize("bad", [None, "", "  ", "abc", True])
def test_bad_amounts_are_rejected(bad):
    with pytest.raises(ParseError):
        parse_amount(bad)


def test_dates_in_many_styles():
    assert parse_date("03/04/2026") == date(2026, 4, 3)
    assert parse_date("03/04/2026", day_first=False) == date(2026, 3, 4)
    assert parse_date("2026-04-03 10:15:00") == date(2026, 4, 3)
    assert parse_date("3.4.26") == date(2026, 4, 3) and parse_date("3-4-99") == date(1999, 4, 3)
    assert parse_date(date(2026, 1, 2)) == date(2026, 1, 2)
    for bad in ("", "ayer", "32/13/2026", None):
        with pytest.raises(ParseError):
            parse_date(bad)


def test_decimal_and_date_order_are_guessed_from_the_samples():
    assert guess_decimal_comma(["-12,30 EUR", "1.100,00"]) is True
    assert guess_decimal_comma(["-3.50", "2,500.00"]) is False
    assert guess_decimal_comma([1.5, None]) is True
    assert guess_day_first(["03/04/2026", "13/04/2026"]) is True
    assert guess_day_first(["04/13/2026", "04/12/2026"]) is False
    assert guess_day_first(["03/04/2026", "04/05/2026"]) is True       # ambiguo: se queda dia/mes


# ---------------------------------------------------------------- sugerencias de columnas
def sample_of(text: str, tmp_path, service) -> FileSample:
    return service.sample(write(tmp_path, "x.csv", text))


def test_header_row_is_found_below_a_preamble(tmp_path, service):
    svc, _ = service
    sample = sample_of(SPANISH, tmp_path, svc)
    assert sample.header_index == 3 and sample.headers[0] == "Fecha operación" and sample.keys[0] == "fecha operacion"
    assert len(sample.body()) == 4 and len(sample.body(2)) == 2


def test_columns_are_suggested_by_name(tmp_path, service):
    svc, _ = service
    guess = guess_mapping(sample_of(SPANISH, tmp_path, svc))
    assert (guess.date, guess.description, guess.income, guess.expense, guess.balance) == (
        "fecha operacion", "concepto", "abono", "cargo", "saldo") and guess.amount == "" and guess.problem() is None
    english = guess_mapping(sample_of(ENGLISH, tmp_path, svc))
    assert (english.date, english.description, english.amount, english.balance) == ("date", "description", "amount", "balance")
    assert english.decimal_comma is False and english.day_first is False
    catalan = guess_mapping(sample_of(SINGLE, tmp_path, svc))
    assert (catalan.date, catalan.description, catalan.amount) == ("data", "concepte", "import") and catalan.decimal_comma


def test_columns_are_suggested_by_content_when_the_names_say_nothing(tmp_path, service):
    svc, _ = service
    text = "A;B;C\n03/04/2026;Compra grande en la tienda;-23,40\n02/04/2026;Otra compra distinta;-5,00\n"
    guess = guess_mapping(sample_of(text, tmp_path, svc))
    assert (guess.date, guess.description, guess.amount) == ("a", "b", "c")


def test_header_row_guess_ignores_titles_and_numbers():
    rows = [["Banco X"], ["Cuenta", "123"], ["Fecha", "Concepto", "Importe", "Saldo"], ["01/01/2026", "Algo", "1,00", "5,00"]]
    assert guess_header_row(rows) == 2


# ---------------------------------------------------------------- mapa: validacion y guardado
def test_mapping_problems_are_explained():
    ok = ColumnMapping("B", "fecha", "concepto", amount="importe")
    assert ok.problem() is None and ok.required == {"fecha", "concepto", "importe"}
    assert ColumnMapping("B", "", "c", amount="i").problem()
    assert ColumnMapping("B", "f", "", amount="i").problem()
    assert ColumnMapping("B", "f", "c").problem()
    assert ColumnMapping("B", "f", "c", amount="i", income="x").problem()
    assert ColumnMapping("B", "f", "f", amount="i").problem()                    # una columna para dos cosas
    assert ColumnMapping("B", "f", "c", income="a").problem() is None            # basta una de ingresos/gastos


def test_formats_roundtrip_through_json_and_ignore_garbage():
    a = ColumnMapping("A", "fecha", "concepto", amount="importe", day_first=False, decimal_comma=False, invert_sign=True)
    b = ColumnMapping("B", "f", "c", income="i", expense="g", balance="s")
    assert load_formats(dump_formats([a, b])) == [a, b]
    assert load_formats("") == [] and load_formats("{}") == [] and load_formats("[1, 2, null]") == []
    assert load_formats('[{"name": "x"}]') == []                                 # incompleto
    assert load_formats('[{"name":"A","date":"f","description":"c","amount":"i"}, {"name":""}]') == [
        ColumnMapping("A", "f", "c", amount="i")]


def test_find_header_needs_every_mapped_column():
    rows = [["x"], ["Fecha", "Concepto", "Importe"]]
    assert find_header(rows, ColumnMapping("B", "fecha", "concepto", amount="importe")) == 1
    assert find_header(rows, ColumnMapping("B", "fecha", "concepto", amount="importe", balance="saldo")) is None


# ---------------------------------------------------------------- lectura
def test_two_columns_spanish_statement_reads_signs_dates_and_balances(tmp_path, service):
    svc, _ = service
    sample = sample_of(SPANISH, tmp_path, svc)
    mapping = replace(guess_mapping(sample, "Mi caja"))
    parsed = svc.try_mapping(tmp_path / "x.csv", sample, mapping)
    assert parsed.kind is FileKind.BANK_STATEMENT and parsed.format_name == "Mi caja"
    assert [(t.booking_date, t.description, t.amount, t.balance_after) for t in parsed.transactions] == [
        (date(2026, 4, 3), "COMPRA MERCADONA", D("-23.40"), D("1976.60")),
        (date(2026, 4, 2), "NOMINA EMPRESA", D("1500.00"), D("2000.00")),
        (date(2026, 4, 1), "RECIBO LUZ", D("-45.10"), D("500.00"))]
    assert parsed.ignored_rows == 1 and any("ignorada" in w for w in parsed.warnings)      # la fila "Total"
    from core.enums import TxCategory

    assert parsed.transactions[0].category is TxCategory.GROCERIES and parsed.transactions[1].category is TxCategory.INCOME


def test_one_amount_column_with_dot_decimals_and_month_first_dates(tmp_path, service):
    svc, _ = service
    sample = sample_of(ENGLISH, tmp_path, svc)
    parsed = svc.try_mapping(tmp_path / "x.csv", sample, guess_mapping(sample, "US"))
    assert [(t.booking_date, t.amount) for t in parsed.transactions] == [
        (date(2026, 4, 13), D("-3.50")), (date(2026, 4, 12), D("2500.00")), (date(2026, 4, 11), D("-900.00"))]
    assert parsed.ignored_rows == 0 and not parsed.warnings                     # el saldo encadena


def test_inverting_the_sign_and_missing_balance_column(tmp_path, service):
    svc, _ = service
    sample = sample_of(SINGLE, tmp_path, svc)
    mapping = replace(guess_mapping(sample, "Cat"), invert_sign=True, balance="")
    parsed = svc.try_mapping(tmp_path / "x.csv", sample, mapping)
    assert [t.amount for t in parsed.transactions] == [D("12.30"), D("-1100.00")]
    assert all(t.balance_after is None for t in parsed.transactions)


def test_a_wrong_format_explains_instead_of_importing_garbage(tmp_path, service):
    svc, _ = service
    sample = sample_of(SINGLE, tmp_path, svc)
    wrong = replace(guess_mapping(sample, "Mal"), date="concepte", description="data")   # fecha y concepto cambiados
    with pytest.raises(ParseError) as caught:
        svc.try_mapping(tmp_path / "x.csv", sample, wrong)
    assert "ningún movimiento" in str(caught.value)
    with pytest.raises(ParseError):
        svc.try_mapping(tmp_path / "x.csv", sample, ColumnMapping("M", "", ""))


def test_many_ignored_rows_are_summarised(tmp_path, service):
    svc, _ = service
    rows = "".join(f"nope;Algo {i};-1,00\n" for i in range(25))
    text = "Fecha;Concepto;Importe\n01/01/2026;Bueno;-2,00\n" + rows
    sample = sample_of(text, tmp_path, svc)
    parsed = svc.try_mapping(tmp_path / "x.csv", sample, guess_mapping(sample, "M"))
    assert parsed.ignored_rows == 25 and len(parsed.warnings) == 11 and "15" in parsed.warnings[-1]


def test_excel_files_with_real_dates_and_numbers_work_too(tmp_path, service):
    from datetime import datetime
    from openpyxl import Workbook

    svc, _ = service
    book = Workbook()
    sheet = book.active
    sheet.append(["Informe del banco"])
    sheet.append(["Fecha", "Descripción", "Importe", "Saldo"])
    sheet.append([datetime(2026, 5, 2), "Cafe", -2.5, 97.5])
    sheet.append([datetime(2026, 5, 1), "Ingreso", 100, 100])
    path = tmp_path / "banco.xlsx"
    book.save(path)
    sample = svc.sample(path)
    assert sample.header_index == 1
    parsed = svc.try_mapping(path, sample, guess_mapping(sample, "Excel"))
    assert [(t.booking_date, t.amount) for t in parsed.transactions] == [(date(2026, 5, 2), D("-2.5")), (date(2026, 5, 1), D("100"))]


# ---------------------------------------------------------------- guardar y reconocer solo
def test_unknown_file_is_flagged_then_recognised_after_saving_the_format(tmp_path, service):
    svc, _ = service
    path = write(tmp_path, "mi-banco.csv", SPANISH)
    [before] = svc.preview([path])
    assert not before.ok and before.unknown_format and before.path == str(path)
    with pytest.raises(UnknownFormatError):
        parse_file(path)
    sample = svc.sample(path)
    svc.save_format(guess_mapping(sample, "Caja Sur"))
    [after] = svc.preview([path])
    assert after.ok and after.kind is FileKind.BANK_STATEMENT and after.kind_label == "Extracto de otro banco"
    assert (after.rows, after.new, after.existing) == (3, 3, 0) and (after.first, after.last) == (date(2026, 4, 1), date(2026, 4, 3))
    assert svc.formats()[0].name == "Caja Sur"


def test_importing_creates_the_account_with_the_format_name_and_never_duplicates(tmp_path, service):
    svc, factory = service
    path = write(tmp_path, "mi-banco.csv", SPANISH)
    svc.save_format(guess_mapping(svc.sample(path), "Caja Sur"))
    report = svc.import_files([path])
    assert report.files[0].ok and (report.files[0].inserted, report.files[0].skipped) == (3, 0)
    with session_scope(factory) as s:
        [account] = s.query(Account).all()
        assert account.name == "Caja Sur" and s.query(Transaction).count() == 3
    again = svc.import_files([path])
    assert (again.files[0].inserted, again.files[0].skipped) == (0, 3)
    [p] = svc.preview([path])
    assert (p.new, p.existing) == (0, 3) and not p.changes_data


def test_saved_formats_survive_a_restart_and_can_be_replaced_or_forgotten(tmp_path, service):
    svc, factory = service
    path = write(tmp_path, "mi-banco.csv", SPANISH)
    mapping = guess_mapping(svc.sample(path), "Caja Sur")
    svc.save_format(mapping)
    svc.save_format(replace(mapping, name="caja sur", balance=""))              # mismo nombre: se reemplaza
    again = ImportService(factory)                                               # "reiniciar": se lee de la base
    assert [f.name for f in again.formats()] == ["caja sur"] and again.formats()[0].balance == ""
    assert again.delete_format("caja sur") and not again.delete_format("caja sur")
    [p] = again.preview([path])
    assert not p.ok and p.unknown_format
    with pytest.raises(ParseError):
        again.save_format(ColumnMapping("", "f", "c", amount="i"))
    with pytest.raises(ParseError):
        again.save_format(ColumnMapping("X", "", "c", amount="i"))


def test_known_banks_still_win_over_saved_formats(tmp_path, service):
    svc, _ = service
    svc.save_format(ColumnMapping("Raro", "fecha", "concepto", amount="importe"))
    [p] = svc.preview([Path(__file__).parent / "fixtures" / "imagin_sample.csv"])
    assert p.kind is FileKind.IMAGIN_STATEMENT


def test_pdf_and_empty_files_still_fail_clearly(tmp_path, service):
    svc, _ = service
    empty = write(tmp_path, "vacio.csv", "")
    with pytest.raises(ParseError):
        svc.sample(empty)
    [p] = svc.preview([empty])
    assert not p.ok


# ---------------------------------------------------------------- pantalla de importar y asistente
@pytest.fixture()
def view(window, qapp):
    yield window.import_view


def test_unknown_file_offers_to_assign_columns_and_then_previews_it(view, tmp_path, monkeypatch):
    from ui.mapping_dialog import MappingDialog

    path = write(tmp_path, "mi-banco.csv", SPANISH)
    view.preview_paths([str(path)])
    [row] = [view._preview.itemAt(i).widget() for i in range(view._preview.count())]
    assert row.map_button is not None and not view.confirm_button.isEnabled()

    def accept(self):                                         # el usuario revisa lo propuesto y pulsa "Guardar y usar"
        assert self.ok.isEnabled() and self.name.text() == "Mi banco"
        self.name.setText("Caja Sur")
        self._save()
        return MappingDialog.DialogCode.Accepted

    monkeypatch.setattr(MappingDialog, "exec", accept)
    row.map_button.click()
    assert view._service.formats()[0].name == "Caja Sur" and not view._formats_box.isHidden()
    [row2] = [view._preview.itemAt(i).widget() for i in range(view._preview.count())]
    assert row2.map_button is None and view.confirm_button.isEnabled() and "3" in view.confirm_button.text()
    report = view.confirm_import()
    assert report.total_inserted == 3


def test_cancelling_the_assistant_saves_nothing(view, tmp_path, monkeypatch):
    from ui.mapping_dialog import MappingDialog

    path = write(tmp_path, "mi-banco.csv", SPANISH)
    view.preview_paths([str(path)])
    monkeypatch.setattr(MappingDialog, "exec", lambda self: MappingDialog.DialogCode.Rejected)
    assert view.open_mapping(str(path)) is False and view._service.formats() == [] and view._formats_box.isHidden()


def test_the_assistant_shows_the_file_and_explains_mistakes_live(view, tmp_path, qapp):
    from ui.mapping_dialog import MappingDialog

    path = write(tmp_path, "mi-banco.csv", SPANISH)
    dialog = MappingDialog(view._service, str(path))
    assert dialog.header_row.currentText() == "4" and dialog.table.columnCount() == 6 and dialog.table.rowCount() == 4
    assert dialog.table.item(0, 2).text() == "COMPRA MERCADONA"
    assert dialog.amount_mode.currentData() == "two" and not dialog.amount.isEnabled() and dialog.income.isEnabled()
    assert dialog.ok.isEnabled() and "3 movimientos" in dialog.result.text() and "01/04/2026" in dialog.result.text()
    assert "MERCADONA" in dialog.result_rows.text() and "1 fila se ha ignorado" in dialog.result_rows.text()
    dialog.date.setCurrentIndex(0)                           # sin fecha
    assert not dialog.ok.isEnabled() and "fecha" in dialog.result.text()
    dialog._select(dialog.date, "fecha operacion")
    dialog.name.setText("")
    assert not dialog.ok.isEnabled() and "nombre" in dialog.error.text() and not dialog.error.isHidden()
    dialog.name.setText("Otra")
    dialog.date_order.setCurrentIndex(1)                     # mes/dia: 03/04 pasa a ser 4 de marzo
    assert "03/03/2026" not in dialog.result.text() and dialog.ok.isEnabled()
    dialog.header_row.setCurrentIndex(4)                            # fila equivocada: se recalculan columnas y se explica
    assert dialog.table.columnCount() == 6
    dialog.deleteLater()


def test_the_assistant_switches_between_one_and_two_amount_columns(view, tmp_path, qapp):
    from ui.mapping_dialog import MappingDialog

    dialog = MappingDialog(view._service, str(write(tmp_path, "otro.csv", ENGLISH)))
    assert dialog.amount_mode.currentData() == "one" and dialog.amount.isEnabled() and not dialog.income.isEnabled()
    assert dialog.decimals.currentData() is False and dialog.date_order.currentData() is False
    assert dialog.mapping().amount == "amount" and dialog.mapping().income == ""
    dialog.amount_mode.setCurrentIndex(1)
    assert not dialog.ok.isEnabled()                         # faltan las columnas de ingresos o gastos
    dialog._select(dialog.income, "amount")
    assert dialog.mapping().income == "amount" and dialog.mapping().amount == ""
    dialog.deleteLater()


def test_unreadable_file_in_the_assistant_warns_instead_of_crashing(view, tmp_path):
    shown = []
    QMessageBox.warning = lambda *a, **k: shown.append(a)
    assert view.open_mapping(str(write(tmp_path, "vacio.csv", ""))) is False and shown


def test_forgetting_a_format_can_be_undone(view, tmp_path):
    path = write(tmp_path, "mi-banco.csv", SPANISH)
    view._service.save_format(guess_mapping(view._service.sample(path), "Caja Sur"))
    view.refresh_formats()
    assert not view._formats_box.isHidden() and view._formats.count() == 1
    row = view._formats.itemAt(0).widget()
    assert "fecha operacion" in row.layout().itemAt(1).widget().text()
    row.remove.click()
    assert view._formats_box.isHidden() and view._service.formats() == []
    window = view.window()
    window.feedback.undo()
    assert [f.name for f in view._service.formats()] == ["Caja Sur"] and not view._formats_box.isHidden()


def test_account_names_in_the_import_page_do_not_say_only_imagin(view):
    assert "Imagin" not in view.account_combo.itemText(0)


def test_texts_of_the_assistant_exist_in_every_language(view, tmp_path):
    from ui.mapping_dialog import MappingDialog

    for code in ("ca", "en"):
        i18n.set_language(code)
        dialog = MappingDialog(view._service, str(write(tmp_path, f"{code}.csv", SPANISH)))
        assert dialog.windowTitle() != "Importar de otro banco" and "Se leen" not in dialog.result.text()
        dialog.deleteLater()
