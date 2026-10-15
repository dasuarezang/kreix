"""Punto de entrada de Kreix: compone las capas y arranca la interfaz."""
from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from data.database import default_db_path, init_db, make_engine, make_session_factory
from services.accounts_service import AccountsService
from services.dashboard_service import DashboardService
from services.category_service import CategoryService
from services.data_service import DataService
from services.demo_service import DemoService
from services.import_service import ImportService
from services.investment_service import InvestmentService
from services.settings_service import SettingsService
from services.transfer_service import TransferService
from ui import assets, fonts
from ui.main_window import MainWindow, Services


def build_window(db_url: str | None = None, db_label: str | None = None) -> MainWindow:
    engine = make_engine(db_url)
    init_db(engine)
    factory = make_session_factory(engine)
    import_service = ImportService(factory)
    services = Services(
        import_service, DashboardService(factory), SettingsService(factory), DataService(factory),
        AccountsService(factory), InvestmentService(factory), TransferService(engine, factory),
        CategoryService(factory), DemoService(import_service),
    )
    return MainWindow(services, db_label or str(default_db_path()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kreix")
    parser.add_argument("--db", help="ruta de una base de datos alternativa (pruebas)")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")          # mismo aspecto en todos los sistemas y sin el recuadro punteado de foco de Windows
    fonts.setup_application(app)
    app.setApplicationName("Kreix")
    app.setWindowIcon(assets.app_icon())
    db = args.db or os.environ.get("KREIX_DB")
    window = build_window(f"sqlite:///{db}" if db else None, db)
    window.show()
    QTimer.singleShot(400, window.announce_new_version)     # tras pintar la ventana
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
