"""Bancos que Kreix reconoce solos. Los archivos son inventados, con las cabeceras habituales de cada exportacion;
si un banco cambia las suyas, el archivo cae al asistente de columnas (ultima prueba)."""
from datetime import date
from decimal import Decimal as D

import pytest

from etl.dispatcher import UnknownFormatError, parse_file

CAIXABANK = (
    "Número de cuenta;Oficina;Divisa;F. Operación;F. Valor;Ingreso;Gasto;Saldo;Saldo (Divisa);Concepto común;Concepto propio;"
    "Referencia 1;Referencia 2;Concepto complementario 1\n"
    "ES00;0001;EUR;03/04/2026;03/04/2026;;23,40;1.976,60;1.976,60;Compras;;123;456;MERCADONA CL TEST\n"
    "ES00;0001;EUR;02/04/2026;02/04/2026;1.500,00;;2.000,00;2.000,00;Nómina;NOMINA EMPRESA SL;123;456;\n"
)
SANTANDER = (
    "Cuenta: ES00 0000 0000 0000\n"
    "\n"
    "Fecha Operación;Fecha Valor;Concepto;Importe;Divisa;Saldo\n"
    "03/04/2026;03/04/2026;COMPRA TARJ. NETFLIX.COM;-12,99;EUR;987,01\n"
    "02/04/2026;02/04/2026;TRANSFERENCIA RECIBIDA;1000,00;EUR;1.000,00\n"
)
REVOLUT = (
    "Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance\n"
    "CARD_PAYMENT,Current,2026-04-03 10:00:00,2026-04-03 10:01:00,Spotify,-9.99,0.00,EUR,COMPLETED,90.01\n"
    "EXCHANGE,Current,2026-04-02 09:00:00,2026-04-02 09:00:00,Cambio a USD,-50.00,0.50,EUR,COMPLETED,100.00\n"
    "CARD_PAYMENT,Current,2026-04-01 08:00:00,2026-04-01 08:00:00,Coffee in London,-3.00,0.00,GBP,COMPLETED,150.50\n"
)
REVOLUT_ES = (
    "Tipo,Producto,Fecha de inicio,Fecha de finalización,Descripción,Importe,Comisión,Divisa,State,Saldo\n"
    "PAGO,Actual,2026-04-03 10:00:00,2026-04-03 10:01:00,Spotify,-9.99,0.00,EUR,COMPLETED,90.01\n"
)
TRADE_REPUBLIC = (
    "datetime,date,account_type,category,type,asset_class,name,symbol,shares,price,amount,fee,tax,currency,original_amount,"
    "original_currency,fx_rate,description,transaction_id,counterparty_name,counterparty_iban,payment_reference,mcc_code\n"
    "2026-04-03T10:00:00.000Z,2026-04-03,DEFAULT,CASH,CARD_TRANSACTION,,,,,,-12.50,,,EUR,,,,Panaderia Test,t1,,,,5462\n"
    "2026-04-02T10:00:00.000Z,2026-04-02,DEFAULT,CASH,CUSTOMER_INBOUND,,,,,,500.00,,,EUR,,,,Ingreso,t2,Ana Test,,,\n"
    "2026-04-01T10:00:00.000Z,2026-04-01,DEFAULT,TRADING,BUY,FUND,World ETF,IE00,1,100,-100.00,-1.00,,EUR,,,,Compra,t3,,,,\n"
)


def write(tmp_path, name, text, encoding="utf-8"):
    path = tmp_path / name
    path.write_text(text, encoding=encoding)
    return path


def rows_of(result):
    return [(t.booking_date, t.description, t.amount, t.balance_after) for t in result.transactions]


def test_caixabank_uses_income_and_expense_columns_and_the_best_concept(tmp_path):
    result = parse_file(write(tmp_path, "caixa.csv", CAIXABANK, "cp1252"))
    assert result.format_name == "CaixaBank"
    assert rows_of(result) == [
        (date(2026, 4, 3), "MERCADONA CL TEST", D("-23.40"), D("1976.60")),
        (date(2026, 4, 2), "NOMINA EMPRESA SL", D("1500.00"), D("2000.00"))]       # sin concepto complementario: cae al propio


def test_santander_skips_the_preamble_and_keeps_signed_amounts(tmp_path):
    result = parse_file(write(tmp_path, "santander.csv", SANTANDER))
    assert result.format_name == "Santander"
    assert rows_of(result) == [
        (date(2026, 4, 3), "COMPRA TARJ. NETFLIX.COM", D("-12.99"), D("987.01")),
        (date(2026, 4, 2), "TRANSFERENCIA RECIBIDA", D("1000.00"), D("1000.00"))]


@pytest.mark.parametrize("text", [REVOLUT, REVOLUT_ES])
def test_revolut_in_english_and_spanish_charges_the_fee_and_skips_other_currencies(tmp_path, text):
    result = parse_file(write(tmp_path, "revolut.csv", text))
    assert result.format_name == "Revolut"
    assert rows_of(result)[0] == (date(2026, 4, 3), "Spotify", D("-9.99"), D("90.01"))
    if text is REVOLUT:
        assert rows_of(result)[1][2] == D("-50.50")                          # importe y comision
        assert len(result.transactions) == 2 and any("divisa" in w for w in result.warnings)      # la libra no se mezcla con euros


def test_trade_republic_reads_the_cash_account_and_leaves_out_the_trades(tmp_path):
    result = parse_file(write(tmp_path, "tr.csv", TRADE_REPUBLIC))
    assert result.format_name == "Trade Republic"
    assert rows_of(result) == [
        (date(2026, 4, 3), "Panaderia Test", D("-12.50"), None),
        (date(2026, 4, 2), "Ingreso", D("500.00"), None)]
    assert any("1 filas" in w for w in result.warnings)                       # la compra del ETF no es un gasto


def test_an_unrecognised_file_still_goes_to_the_column_assistant(tmp_path):
    with pytest.raises(UnknownFormatError):
        parse_file(write(tmp_path, "otro.csv", "Dia;Texto;Cuanto\n03/04/2026;algo;-3,00\n"))
