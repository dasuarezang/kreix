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

from PySide6.QtCore import QDate  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import demo_data  # noqa: E402
from main import build_window  # noqa: E402


def main() -> None:
    out = ROOT / "docs" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    as_of = demo_data.build(tmp / "demo")

    app = QApplication(sys.argv[:1])
    from ui import fonts

    fonts.setup_application(app)
    window = build_window(f"sqlite:///{tmp / 'demo.db'}", "demo")
    window.show()

    def shot(name: str) -> None:
        QTest.qWait(1800)  # espera a que terminen las animaciones de los graficos
        window.grab().save(str(out / f"{name}.png"))

    window.resize(1280, 1180)
    window.navigate(window.IMPORT)
    window.import_view.as_of.setDate(QDate(as_of.year, as_of.month, as_of.day))
    window.import_view.import_paths([str(p) for p in sorted((tmp / "demo").glob("*.csv"))])
    shot("importar-oscuro")

    tabs = (("resumen", window.SUMMARY), ("cuentas", window.ACCOUNTS), ("inversion", window.INVESTMENT),
            ("ayuda", window.HELP), ("exportar", window.EXPORT))
    for theme_name, suffix in (("dark", "oscuro"), ("light", "claro")):
        window.apply_theme(theme_name)
        for name, page in tabs:
            window.navigate(page)
            shot(f"{name}-{suffix}")
    app.quit()
    print(f"Capturas en {out}")


if __name__ == "__main__":
    main()
