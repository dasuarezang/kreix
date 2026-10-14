"""Punto de entrada de Kreix: compone las capas y arranca la interfaz."""
from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtWidgets import QApplication

from data.database import default_db_path, init_db, make_engine, make_session_factory
from services.dashboard_service import DashboardService
from services.import_service import ImportService
from services.settings_service import SettingsService
from ui import assets
from ui.main_window import MainWindow, Services


def build_window(db_url: str | None = None, db_label: str | None = None) -> MainWindow:
    engine = make_engine(db_url)
    init_db(engine)
    factory = make_session_factory(engine)
    services = Services(ImportService(factory), DashboardService(factory), SettingsService(factory))
    return MainWindow(services, db_label or str(default_db_path()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kreix")
    parser.add_argument("--db", help="ruta de una base de datos alternativa (pruebas)")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Kreix")
    app.setWindowIcon(assets.app_icon())
    db = args.db or os.environ.get("KREIX_DB")
    window = build_window(f"sqlite:///{db}" if db else None, db)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
