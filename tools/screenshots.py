"""Genera las capturas del README con datos de demostracion (nunca datos reales).

Uso:  python tools/screenshots.py
Salida: docs/screenshots/*.png
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from decimal import Decimal  # noqa: E402

from PySide6.QtCore import QDate  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import demo_data  # noqa: E402
from core.enums import TxCategory  # noqa: E402
from main import build_window  # noqa: E402


def main() -> None:
    out = ROOT / "docs" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    as_of = demo_data.build(tmp / "demo")

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    from ui import fonts

    fonts.setup_application(app)
    window = build_window(f"sqlite:///{tmp / 'demo.db'}", "demo")
    window.show()
    window._apply_user_name("Ana", announce=False)             # nombre inventado para el saludo de Inicio

    def shot(name: str) -> None:
        QTest.qWait(1800)  # espera a que terminen las animaciones de los graficos
        window.grab().save(str(out / f"{name}.png"))

    window.resize(1280, 1180)
    shot("bienvenida-oscuro")                                   # la app vacia: la guia de tres pasos

    window.navigate(window.IMPORT)
    window.import_view.as_of.setDate(QDate(as_of.year, as_of.month, as_of.day))
    files = [str(p) for p in sorted((tmp / "demo").glob("*.csv"))]
    window.import_view.preview_paths(files)                     # lo que Kreix ha leido, antes de guardar nada
    shot("importar-oscuro")
    window.import_view.confirm_import()

    # presupuestos de demostracion, para que se vean los paneles de Inicio y Cuentas
    window._svc.categories.save_budgets({TxCategory.GROCERIES: Decimal(250), TxCategory.LEISURE: Decimal(30),
                                         TxCategory.DINING: Decimal(60), TxCategory.TRANSPORT: Decimal(40)})
    window.refresh()

    tabs = (("inicio", window.SUMMARY), ("cuentas", window.ACCOUNTS), ("inversion", window.INVESTMENT),
            ("ayuda", window.HELP), ("exportar", window.EXPORT))
    for theme_name, suffix in (("dark", "oscuro"), ("light", "claro")):
        window.apply_theme(theme_name)
        for name, page in tabs:
            window.resize(1280, 1900 if page == window.ACCOUNTS else 1180)    # Cuentas es la pagina mas larga
            window.navigate(page)
            shot(f"{name}-{suffix}")
    window.apply_theme("dark")
    other_bank_and_lock_screenshots(window, tmp, out)
    app.quit()
    print(f"Capturas en {out}")


BANK_CSV = (
    "Extracto de movimientos;;;;;\n"
    "Fecha operación;Fecha valor;Concepto;Cargo;Abono;Saldo\n"
    "03/04/2026;03/04/2026;COMPRA SUPERMERCADO CENTRO;23,40;;1.976,60\n"
    "02/04/2026;02/04/2026;NOMINA EMPRESA DEMO SL;;1.500,00;2.000,00\n"
    "01/04/2026;01/04/2026;RECIBO ELECTRICIDAD;45,10;;500,00\n"
    "Total;;;68,50;1.500,00;\n"
)


def other_bank_and_lock_screenshots(window, tmp: Path, out: Path) -> None:
    """El asistente de otro banco y la pantalla de bloqueo con el medidor de contrasena (datos inventados)."""
    from ui.lock_screen import LockDialog, LockMode
    from ui.mapping_dialog import MappingDialog

    csv = tmp / "otro-banco.csv"
    csv.write_text(BANK_CSV, encoding="utf-8")
    dialog = MappingDialog(window._svc.importer, str(csv), window)
    dialog.show()
    QTest.qWait(600)
    dialog.grab().save(str(out / "otro-banco-oscuro.png"))
    dialog.close()
    lock = LockDialog(LockMode.CREATE, lambda _password: None)
    lock.password.setText("correcto caballo bateria grapa")
    lock.confirm.setText("correcto caballo bateria grapa")
    lock.show()
    QTest.qWait(600)
    lock.grab().save(str(out / "bloqueo-oscuro.png"))
    lock.close()


if __name__ == "__main__":
    main()
