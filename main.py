"""Punto de entrada de Kreix: compone las capas y arranca la interfaz.

El arranque esta pensado para que la pantalla de bloqueo salga cuanto antes: aqui arriba solo se importa lo imprescindible
(Qt, la pantalla de bloqueo y el cifrado). SQLAlchemy, los servicios y la ventana principal se cargan en un hilo mientras el
usuario escribe la contrasena, asi que al desbloquear ya estan listos."""
from __future__ import annotations

import argparse
import gc
import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from core import i18n
from core.i18n import tr
from data.paths import default_db_path, default_vault_path, legacy_db_path
from data.vault import CorruptVaultError, WrongPasswordError
from ui import assets, fonts, theme
from ui.lock_screen import LockDialog, LockMode
from ui.widgets.nav_button import install_keyboard_rings
from ui.system_language import system_language


def build_window(db_url: str | None = None, db_label: str | None = None, engine=None):
    from data.database import init_db, make_engine, make_session_factory
    from services.accounts_service import AccountsService
    from services.category_service import CategoryService
    from services.dashboard_service import DashboardService
    from services.data_service import DataService
    from services.demo_service import DemoService
    from services.goals_service import GoalsService
    from services.import_service import ImportService
    from services.investment_service import InvestmentService
    from services.settings_service import SettingsService
    from services.transfer_service import TransferService
    from ui.main_window import MainWindow, Services

    if engine is None:
        engine = make_engine(db_url)
        init_db(engine)
    factory = make_session_factory(engine)
    import_service = ImportService(factory)
    services = Services(
        import_service, DashboardService(factory), SettingsService(factory), DataService(factory),
        AccountsService(factory), InvestmentService(factory), TransferService(engine, factory),
        CategoryService(factory), DemoService(import_service), GoalsService(factory),
    )
    return MainWindow(services, db_label or str(default_db_path()))


def preload() -> None:
    """Carga en segundo plano lo pesado (SQLAlchemy, servicios, ventana principal) mientras se escribe la contrasena.
    Solo importa modulos: no crea ningun widget fuera del hilo de la interfaz."""
    try:
        import data.secure_store  # noqa: F401
        import services.accounts_service  # noqa: F401
        import services.dashboard_service  # noqa: F401
        import services.goals_service  # noqa: F401
        import services.import_service  # noqa: F401
        import services.investment_service  # noqa: F401
        import services.transfer_service  # noqa: F401
        import ui.main_window  # noqa: F401
    except Exception:                                      # pragma: no cover - si falla, se importara al usarlo y se vera ahi
        pass


def unlock_store(path: Path, legacy: Path, parent=None, on_open=None):
    """Pantalla de bloqueo: abre el almacen cifrado (o lo crea, cifrando de paso los datos sin cifrar de versiones
    anteriores). Devuelve None si el usuario sale sin entrar.

    `on_open(store)` se llama cuando la contrasena es correcta y con la pantalla de bloqueo todavia a la vista: ahi se
    prepara y muestra la ventana principal, asi la entrada es continua, sin huecos ni parpadeos."""
    opened: list = []

    def unlock(password: str) -> str | None:
        from data.secure_store import SecureStore

        try:
            opened.append(SecureStore.open(path, password))
        except WrongPasswordError:
            return tr("Contraseña incorrecta. Inténtalo de nuevo.")
        except CorruptVaultError:
            return tr("Este archivo de datos no es válido o está dañado.")
        return None

    def create(password: str) -> str | None:
        from data.secure_store import SecureStore, erase_legacy_db, read_legacy_db

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
        from data.secure_store import erase_vault

        erase_vault(path)
        dialog = LockDialog(LockMode.CREATE, create, parent, finish)
        dialog.exec()
    return opened[0] if opened else None


def settle_memory() -> None:
    """Lo creado al arrancar (ventana, widgets, modulos) vive hasta el final: se aparta del recolector de basura para que sus
    pasadas, durante cargas grandes, no lo recorran una y otra vez."""
    gc.collect()
    gc.freeze()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kreix")
    parser.add_argument("--db", help="ruta de una base de datos alternativa (pruebas)")
    args = parser.parse_args(argv)

    gc.set_threshold(20000, 20, 20)                         # menos pasadas del recolector al cargar miles de movimientos
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")          # mismo aspecto en todos los sistemas y sin el recuadro punteado de foco de Windows
    fonts.setup_application(app)
    app.setApplicationName("Kreix")
    app.setWindowIcon(assets.app_icon())
    install_keyboard_rings(app)
    app.setStyleSheet(theme.stylesheet(theme.DARK))        # la pantalla de bloqueo ya sale con el estilo de la app
    db = args.db or os.environ.get("KREIX_DB")
    threading.Thread(target=preload, name="kreix-preload", daemon=True).start()

    def launch(store) -> None:
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
        window.attach_store(store)                          # activa en Ajustes el cambio de contrasena
        window.detect_language = True                       # la primera vez se propone el idioma del sistema
        app.kreix_window = window
        window.show()
        window._later(400, window.start_up)                 # tras pintar la ventana: nombre y novedades
        window._later(2500, settle_memory)                  # y, ya asentada, se saca de la vigilancia del recolector todo lo de arranque

    if db:
        launch(None)
    elif unlock_store(default_vault_path(), legacy_db_path(), on_open=launch) is None:
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
