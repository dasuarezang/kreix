"""Punto de entrada de Kreix: compone las capas y arranca la interfaz."""
from __future__ import annotations

import argparse
import os
import sys

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from core import i18n
from core.i18n import tr
from data.database import default_db_path, init_db, make_engine, make_session_factory
from data.secure_store import SecureStore, default_vault_path, erase_legacy_db, erase_vault, legacy_db_path, read_legacy_db
from data.vault import CorruptVaultError, WrongPasswordError
from services.accounts_service import AccountsService
from services.dashboard_service import DashboardService
from services.category_service import CategoryService
from services.data_service import DataService
from services.demo_service import DemoService
from services.import_service import ImportService
from services.investment_service import InvestmentService
from services.settings_service import SettingsService
from services.transfer_service import TransferService
from ui import assets, fonts, theme
from ui.dialogs import system_language
from ui.lock_screen import LockDialog, LockMode
from ui.main_window import MainWindow, Services


def build_window(db_url: str | None = None, db_label: str | None = None, engine=None) -> MainWindow:
    if engine is None:
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


def unlock_store(path: Path, legacy: Path, parent=None, on_open=None) -> SecureStore | None:
    """Pantalla de bloqueo: abre el almacen cifrado (o lo crea, cifrando de paso los datos sin cifrar de versiones
    anteriores). Devuelve None si el usuario sale sin entrar.

    `on_open(store)` se llama cuando la contrasena es correcta y con la pantalla de bloqueo todavia a la vista: ahi se
    prepara y muestra la ventana principal, asi la entrada es continua, sin huecos ni parpadeos."""
    opened: list[SecureStore] = []

    def unlock(password: str) -> str | None:
        try:
            opened.append(SecureStore.open(path, password))
        except WrongPasswordError:
            return tr("Contraseña incorrecta. Inténtalo de nuevo.")
        except CorruptVaultError:
            return tr("Este archivo de datos no es válido o está dañado.")
        return None

    def create(password: str) -> str | None:
        try:
            plain = read_legacy_db(legacy) if legacy.is_file() else None
            store = SecureStore.create(path, password, plain)
        except Exception:                                 # que un fallo nunca deje la pantalla "colgada" sin explicacion
            return tr("No se pudieron leer los datos anteriores. No se ha borrado nada: cierra Kreix y vuelve a intentarlo.")
        try:
            SecureStore.open(path, password)              # se comprueba que el archivo cifrado se abre antes de borrar nada
        except Exception:                                 # pragma: no cover - disco o permisos
            return tr("No se pudo guardar el archivo cifrado. Revisa el espacio y los permisos de la carpeta de datos.")
        if plain is not None:
            erase_legacy_db(legacy)
        opened.append(store)
        return None

    if path.is_file():
        mode, attempt = LockMode.UNLOCK, unlock
    else:
        mode, attempt = (LockMode.MIGRATE if legacy.is_file() else LockMode.CREATE), create
    i18n.set_language(system_language())                   # el idioma elegido esta dentro de los datos cifrados: aun no se conoce
    finish = (lambda: on_open(opened[0])) if on_open else None
    dialog = LockDialog(mode, attempt, parent, finish)
    dialog.exec()
    if dialog.reset_requested:                              # "He olvidado la contraseña": se borra todo y se empieza de cero
        erase_vault(path)
        dialog = LockDialog(LockMode.CREATE, create, parent, finish)
        dialog.exec()
    return opened[0] if opened else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kreix")
    parser.add_argument("--db", help="ruta de una base de datos alternativa (pruebas)")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")          # mismo aspecto en todos los sistemas y sin el recuadro punteado de foco de Windows
    fonts.setup_application(app)
    app.setApplicationName("Kreix")
    app.setWindowIcon(assets.app_icon())
    app.setStyleSheet(theme.stylesheet(theme.DARK))        # la pantalla de bloqueo ya sale con el estilo de la app
    db = args.db or os.environ.get("KREIX_DB")

    def launch(store: SecureStore | None) -> None:
        """Construye y muestra la ventana principal (con la pantalla de bloqueo todavia delante, si la hay)."""
        if store is None:                                   # solo pruebas/desarrollo: base alternativa sin cifrar
            window = build_window(f"sqlite:///{db}", db)
        else:
            window = build_window(engine=store.engine, db_label=str(store.path))
            autosave = QTimer(window)                       # guarda cifrado poco despues de cada cambio
            autosave.setInterval(2000)
            autosave.timeout.connect(store.flush)
            autosave.start()
            app.aboutToQuit.connect(store.flush)            # y al cerrar
        window.detect_language = True                       # la primera vez se propone el idioma del sistema
        app.kreix_window = window
        window.show()
        window._later(400, window.start_up)                 # tras pintar la ventana: nombre y novedades

    if db:
        launch(None)
    elif unlock_store(default_vault_path(), legacy_db_path(), on_open=launch) is None:
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
