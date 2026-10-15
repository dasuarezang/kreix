"""Mide el rendimiento de Kreix con un volumen grande de datos inventados.

Uso:  python tools/benchmark.py [filas]        (por defecto 20000 movimientos)

Crea un almacen cifrado temporal (nunca toca tus datos), importa un extracto sintetico y cronometra lo que mas se nota:
abrir, importar, cargar cada pagina, cambiar de tema, filtrar, guardar cifrado y redimensionar la ventana.
Sirve para comprobar que un cambio no empeora la fluidez.
"""
from __future__ import annotations

import os
import random
import sys
import tempfile
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import main  # noqa: E402
from data.secure_store import SecureStore  # noqa: E402
from data.tracker import tracker_for  # noqa: E402
from services.demo_data import build  # noqa: E402

MERCHANTS = ["MERCADONA CL", "NETFLIX.COM", "SPOTIFY", "REPSOL ESTACION", "BIZUM A JUAN", "BIZUM DE ANA", "AMAZON EU",
             "ZARA", "RENFE", "RESTAURANTE LA PLAZA", "FARMACIA CENTRAL", "IBERDROLA", "VODAFONE", "CAFETERIA SOL",
             "DECATHLON", "TRANSFERENCIA NOMINA EMPRESA", "GIMNASIO FIT", "ALQUILER PISO", "LIDL"]


def make_statement(path: Path, rows: int) -> None:
    rng = random.Random(7)
    day = date(2026, 10, 1) - timedelta(days=rows // 6)
    balance = Decimal(2000)
    data = []
    for i in range(rows):
        if i % 6 == 0:
            day += timedelta(days=1)
        name = rng.choice(MERCHANTS)
        amount = Decimal(rng.randint(150, 90000)) / 100
        amount = amount if "NOMINA" in name or "DE ANA" in name else -amount
        balance += amount
        data.append((name, day, amount, balance))
    lines = ["Concepto;Fecha;Importe;Saldo"] + [
        f"{n};{d:%d/%m/%Y};{str(a).replace('.', ',')}EUR;{str(b).replace('.', ',')}EUR" for n, d, a, b in reversed(data)]
    path.write_text("\n".join(lines), encoding="utf-8")


def timed(label: str, fn, *args):
    start = time.perf_counter()
    out = fn(*args)
    print(f"{label:<44}{(time.perf_counter() - start) * 1000:9.1f} ms")
    return out


def main_() -> None:
    rows = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 20000
    tmp = Path(tempfile.mkdtemp())
    app = QApplication([])
    app.setStyle("Fusion")
    from ui import fonts, theme

    fonts.setup_application(app)
    app.setStyleSheet(theme.stylesheet(theme.DARK))
    make_statement(tmp / "big.csv", rows)
    demo = tmp / "demo"
    build(demo)
    print(f"\nKreix - benchmark con {rows} movimientos\n" + "-" * 56)

    store = timed("crear almacen cifrado (PBKDF2 600k)", SecureStore.create, tmp / "k.krx", "clave-larga-1")
    window = timed("construir la ventana", main.build_window, None, "bench", store.engine)
    window.show()
    QTest.qWait(300)
    timed(f"importar {rows} movimientos", window._svc.importer.import_files, [tmp / "big.csv"])
    timed("importar operaciones y cartera", window._svc.importer.import_files,
          [demo / "myinvestor_operaciones.csv", demo / "myinvestor_cartera.csv"], date(2026, 10, 14))
    window.eager = False
    for name, page in (("Inicio", window.SUMMARY), ("Cuentas", window.ACCOUNTS), ("Inversiones", window.INVESTMENT)):
        window._stale = set(window.DATA_PAGES)
        tracker_for(store.engine).bump()                           # la primera vez: sin resultados guardados
        timed(f"{name}: primera carga", lambda p=page: (window.navigate(p), QTest.qWait(50)))
        window.navigate(window.SETTINGS)
        window._stale = set(window.DATA_PAGES)
        timed(f"{name}: al volver (resultados guardados)", lambda p=page: (window.navigate(p), QTest.qWait(50)))
    window.navigate(window.ACCOUNTS)
    QTest.qWait(300)
    view = window.accounts_view
    timed("filtrar movimientos por texto", lambda: (view.search.setText("MERCADONA"), QTest.qWait(30)))
    view.search.setText("")
    timed("cambiar a tema claro", lambda: (window.apply_theme("light"), QTest.qWait(30)))
    timed("cambiar a tema oscuro", lambda: (window.apply_theme("dark"), QTest.qWait(30)))
    timed("guardar cifrado (serializar + cifrar)", store.save)
    print(f"{'tamano del archivo .krx':<44}{store.path.stat().st_size / 1024:9.0f} KB")
    timed("abrir el almacen (clave + descifrar)", SecureStore.open, store.path, "clave-larga-1")
    for name, page in (("Cuentas", window.ACCOUNTS), ("Inversiones", window.INVESTMENT)):
        window.navigate(page)
        QTest.qWait(600)
        start = time.perf_counter()
        for k in range(20):
            window.resize(1100 + k * 20, 780 + k * 5)
            QTest.qWait(1)
        print(f"{'redimensionar ' + name + ' (por paso)':<44}{(time.perf_counter() - start) * 1000 / 20:9.1f} ms")
    print("-" * 56)


if __name__ == "__main__":
    main_()
