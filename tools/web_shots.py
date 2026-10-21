"""Genera las capturas de la web (repositorio kreix-web) con datos de demostracion: cinco pantallas, en castellano, catalan e
ingles, con el tema oscuro y el claro, y sus recortes para movil.

Uso:  python tools/web_shots.py RUTA/kreix-web/assets/shots
Salida: <pantalla>-<tema>.webp (1280 x 860) y m-<pantalla>-<tema>.webp (el recorte para movil, a doble resolucion), en la carpeta de cada idioma
(castellano en la raiz, catalan en ca/ e ingles en en/). Inicio sale de noche: con la luna y Blitzen y Black durmiendo.
"""
from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["QT_SCALE_FACTOR"] = "2"          # todo se pinta al doble: los recortes para movil salen nitidos en pantallas densas
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtCore import QDate, QRect, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import demo_data  # noqa: E402
from main import build_window  # noqa: E402

SIZE = (1280, 860)
NAME = "Blitzen"                                             # el nombre del saludo de Inicio
NIGHT = datetime.now().replace(hour=22, minute=54, second=0, microsecond=0)   # hoy (el dia de los datos importados), de noche
LANGUAGES = {"es": "", "ca": "ca", "en": "en"}
# (nombre del archivo, pagina, recorte para movil: x, y, ancho, alto)
SCREENS = (
    ("inicio", "SUMMARY", (285, 192, 575, 500)),
    ("cuentas", "ACCOUNTS", (280, 528, 470, 332)),
    ("inversiones", "INVESTMENT", (280, 482, 372, 340)),
    ("importar", "IMPORT", (285, 122, 940, 252)),
    ("ajustes", "SETTINGS", (285, 296, 530, 140)),
)


PHONE_CARD_W = 575                                               # ancho (px de la app) de la tarjeta de Inicio para movil


def save_phone_card(card, path: Path) -> None:
    """Captura la tarjeta de patrimonio con el ancho de un movil: sus textos se ven a su tamano real, no reducidos."""
    card.setFixedWidth(PHONE_CARD_W)
    QTest.qWait(1800)                                            # se recoloca y repinta el grafico
    image = card.grab().toImage()
    image.setDevicePixelRatio(1.0)
    image.save(str(path), "webp", 85)
    card.setMinimumWidth(0)
    card.setMaximumWidth(16777215)
    QTest.qWait(300)
    print(f"  {path.name}: {image.width()} x {image.height()}", flush=True)


def shoot(app: QApplication, lang: str, out: Path) -> None:
    tmp = Path(tempfile.mkdtemp())
    as_of = demo_data.build(tmp / "demo")
    db = f"sqlite:///{tmp / 'demo.db'}"
    if lang != "es":                                             # el idioma se guarda antes: la ventana nace ya en el
        first = build_window(db, "demo")                         # (cambiarlo despues rehace la ventana y abre el aviso de
        first._svc.settings.save(replace(first._settings, language=lang))    # novedades, que se queda esperando)
        first.deleteLater()
    window = build_window(db, "demo")
    window.clock = window.dashboard.clock = lambda: NIGHT
    window.show()
    window._apply_user_name(NAME, announce=False)
    window.resize(*SIZE)

    window.navigate(window.IMPORT)                               # importar los extractos de demostracion: Importar
    window.import_view.as_of.setDate(QDate(as_of.year, as_of.month, as_of.day))   # se queda con el resultado a la vista
    window.import_view.preview_paths([str(p) for p in sorted((tmp / "demo").glob("*.csv"))])
    window.import_view.confirm_import()
    QTest.qWait(300)

    out.mkdir(parents=True, exist_ok=True)
    for theme_name in ("dark", "light"):
        window.apply_theme(theme_name)
        window.refresh()
        for name, page, crop in SCREENS:
            window.navigate(getattr(window, page))
            window.resize(*SIZE)
            QTest.qWait(1800)                                    # que terminen las animaciones de los graficos
            window.toast.hide()                                  # sin el aviso de "Importado" por encima
            if QApplication.focusWidget() is not None:           # ni el aro de foco de teclado en el primer boton
                QApplication.focusWidget().clearFocus()
            QTest.qWait(50)
            image = window.grab().toImage()                      # al doble de resolucion (QT_SCALE_FACTOR)
            image.setDevicePixelRatio(1.0)
            full = image.scaled(*SIZE, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            full.save(str(out / f"{name}-{theme_name}.webp"), "webp", 88)
            if page == "SUMMARY":                                # Inicio: la tarjeta, estrechada al ancho de un movil
                save_phone_card(window.dashboard.card_net, out / f"m-{name}-{theme_name}.webp")   # (recortada no se leia)
                continue
            x, y, w, h = crop                                    # el recorte para movil, a doble resolucion
            image.copy(QRect(2 * x, 2 * y, 2 * w, 2 * h)).save(str(out / f"m-{name}-{theme_name}.webp"), "webp", 85)
    window.close()
    window.deleteLater()


def main() -> None:
    target = Path(sys.argv[1])
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    from ui import fonts

    fonts.setup_application(app)
    for lang, folder in LANGUAGES.items():
        shoot(app, lang, target / folder if folder else target)
        print(f"{lang}: hecho", flush=True)
    app.quit()


if __name__ == "__main__":
    main()
