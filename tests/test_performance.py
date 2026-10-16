"""Rendimiento: garantias deterministas (no cronometros) de que las optimizaciones siguen en pie.

Cada prueba cuenta trabajo (llamadas, consultas, objetos reutilizados), no milisegundos: asi no dependen de la maquina."""
from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QHeaderView
from sqlalchemy import event

from data.database import init_db, make_engine, make_session_factory
from services.accounts_service import AccountsService
from services.import_service import ImportService
from ui.widgets.charts import LineChart, LineSeries, decimate, monotone_path, monotone_path_xy

MERCHANTS = ["MERCADONA", "NETFLIX.COM", "REPSOL", "ZARA", "RENFE", "IBERDROLA", "LIDL", "GIMNASIO"]


def _big_statement(path: Path, rows: int) -> None:
    rng = random.Random(3)
    day = date(2026, 9, 1) - timedelta(days=rows // 4)
    balance = Decimal(1000)
    data = []
    for i in range(rows):
        if i % 4 == 0:
            day += timedelta(days=1)
        amount = -(Decimal(rng.randint(100, 9000)) / 100)
        balance += amount
        data.append((rng.choice(MERCHANTS), day, amount, balance))
    lines = ["Concepto;Fecha;Importe;Saldo"] + [
        f"{n};{d:%d/%m/%Y};{str(a).replace('.', ',')}EUR;{str(b).replace('.', ',')}EUR" for n, d, a, b in reversed(data)]
    path.write_text("\n".join(lines), encoding="utf-8")


def test_a_big_import_is_inserted_in_a_few_statements_not_one_per_row(tmp_path):
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    statements: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda c, cur, st, p, ctx, many: statements.append(st))
    _big_statement(tmp_path / "big.csv", 3000)
    report = ImportService(factory).import_files([tmp_path / "big.csv"])
    assert report.total_inserted == 3000
    assert len(statements) < 60                                          # antes: mas de 3.000 sentencias
    again = ImportService(factory).import_files([tmp_path / "big.csv"])
    assert again.total_inserted == 0 and again.files[0].skipped == 3000   # y sigue sin duplicar


def test_preview_and_import_read_the_file_only_once(tmp_path, monkeypatch):
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    service = ImportService(make_session_factory(engine))
    calls = []
    import services.import_service as module
    real = module.parse_file
    monkeypatch.setattr(module, "parse_file", lambda *a, **k: calls.append(a[0]) or real(*a, **k))
    _big_statement(tmp_path / "x.csv", 200)
    service.preview([tmp_path / "x.csv"])
    service.import_files([tmp_path / "x.csv"])
    assert len(calls) == 1


def test_views_are_reused_until_the_data_changes(tmp_path):
    from data.secure_store import SecureStore

    store = SecureStore.create(tmp_path / "k.krx", "clave-larga-1", iterations=1000)
    factory = make_session_factory(store.engine)
    _big_statement(tmp_path / "x.csv", 300)
    ImportService(factory).import_files([tmp_path / "x.csv"])
    svc = AccountsService(factory)
    first = svc.view()
    assert svc.view() is first and svc.view(None, date(2026, 8, 1)) is svc.view(None, date(2026, 8, 1))
    store.dirty = False
    svc.view()
    assert store.dirty is False                                          # leer no obliga a volver a guardar cifrado


def test_theme_change_applies_the_stylesheet_once_or_not_at_all(window, monkeypatch):
    """La hoja va en la ventana, no en toda la aplicacion (cambiarla en la aplicacion obliga a Qt a repulir TODO y tarda ~4 veces mas)."""
    app = QApplication.instance()
    app_calls, calls = [], []
    real_app, real = app.setStyleSheet, window.setStyleSheet
    monkeypatch.setattr(app, "setStyleSheet", lambda s: app_calls.append(1) or real_app(s))
    monkeypatch.setattr(window, "setStyleSheet", lambda s: calls.append(1) or real(s))
    window.apply_theme("light")
    assert len(calls) == 1
    window.apply_theme("light")
    assert len(calls) == 1                                               # misma hoja: no se vuelve a repulir la interfaz
    window.theme_switch.toggle()                                         # el usuario cambia a oscuro: una sola aplicacion
    assert len(calls) == 2
    assert window.theme_switch.isChecked()
    assert app_calls == []                                               # y nunca se toca la hoja de toda la aplicacion


def test_table_columns_get_a_fixed_width_once_instead_of_resizing_to_contents(window):
    from ui.widgets.tables import RIGHT, Column, DataTable

    table = DataTable([Column("A", lambda r: r[0], stretch=True), Column("IMPORTE", lambda r: r[1], align=RIGHT)])
    table.set_rows([("x" * 5, "1.234,56 €"), ("y", "99,00 €")])
    header = table.horizontalHeader()
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Fixed      # ancho calculado una vez, no recalculado en cada cambio de estilo
    assert header.sectionSize(1) >= table.fontMetrics().horizontalAdvance("1.234,56 €")


def test_line_chart_geometry_is_built_once_per_size_and_data(qapp):
    chart = LineChart()
    chart.resize(700, 300)
    xs = [date(2020, 1, 1) + timedelta(days=i) for i in range(5000)]
    chart.set_lines(xs, [LineSeries("Saldo", "accent", [float(i % 97) for i in range(5000)], fill=True)])
    first = chart._geometry()
    assert chart._geometry() is first                                    # el raton o la animacion no la recalculan
    chart.resize(800, 300)
    assert chart._geometry() is not first                                # solo cambia con el tamano o con los datos
    drawn_line = chart._geometry().drawn[0][2]
    assert drawn_line.elementCount() < 5000 * 3 // 2                     # una serie larga se reduce a pocos puntos por pixel


def test_decimate_keeps_the_extremes_and_the_ends():
    xs = [float(i) for i in range(10_000)]
    ys = [0.0] * 10_000
    ys[4321], ys[7777] = 50.0, -30.0
    px, py = decimate(xs, ys, 200)
    assert len(px) < 1000 and px[0] == 0 and px[-1] == 9999
    assert max(py) == 50.0 and min(py) == -30.0                          # los picos no se pierden
    short_x, short_y = decimate(xs[:50], ys[:50], 200)
    assert short_x == xs[:50]                                            # lo corto no se toca


def test_monotone_path_from_coordinates_matches_the_points_version():
    pts = [QPointF(0, 5), QPointF(10, 1), QPointF(20, 9), QPointF(30, 9), QPointF(40, 2)]
    a = monotone_path(pts)
    b = monotone_path_xy([p.x() for p in pts], [p.y() for p in pts])
    assert a.elementCount() == b.elementCount() and a.boundingRect() == b.boundingRect()


def test_the_greeting_clock_only_runs_while_home_is_visible(window):
    window.show()
    window.navigate(window.SUMMARY)
    QApplication.processEvents()
    assert window.dashboard._greeting_timer.isActive()
    window.navigate(window.SETTINGS)
    QApplication.processEvents()
    assert not window.dashboard._greeting_timer.isActive()
    window.navigate(window.SUMMARY)
    QApplication.processEvents()
    assert window.dashboard._greeting_timer.isActive()


def test_startup_imports_stay_light_until_the_password_is_entered():
    import subprocess
    import sys

    code = "import sys, main; print(any(m == 'sqlalchemy' or m.startswith('sqlalchemy.') for m in sys.modules))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(Path(__file__).parent.parent),
                         env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"})
    assert out.stdout.strip() == "False", out.stderr[-400:]              # SQLAlchemy se carga en segundo plano, no antes del bloqueo
