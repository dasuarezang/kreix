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
from ui.widgets import brand_message


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


def wire_store(app, window, store, autosave_ms: int = 2000, save_on_quit: bool = True):
    """Conecta la ventana con el almacen cifrado: guardado automatico, copias de seguridad y bloqueo por inactividad.
    Devuelve (copias, bloqueo). Todo cuelga de la aplicacion, no de la ventana, para que siga vivo si la ventana se rehace
    (por ejemplo, al cambiar de idioma)."""
    from data.paths import default_backup_folder
    from services.backup_service import BackupService, config_from
    from ui.autolock import AutoLock

    app.kreix_window = window                               # la ventana principal viva (evita que se recoja; las copias y el bloqueo la consultan)
    transfer = window._svc.transfer
    backups = BackupService(lambda target: transfer.export_to(target, store.seal_export),
                            lambda: config_from(app.kreix_window._settings), default_backup_folder(),
                            is_empty=lambda: transfer.summary().is_empty)
    store.on_saved(backups.note_saved)                      # cada guardado en disco cuenta como "hay cambios sin copiar"

    def persist() -> None:
        store.flush()
        if backups.run_if_due() is not None:                # como mucho una vez por hora, y solo si hubo cambios
            app.kreix_window.refresh_backups()

    def on_quit() -> None:
        store.flush()
        backups.on_quit()                                   # y al cerrar, si falta recoger algo

    autosave = QTimer(app)                                  # guarda cifrado poco despues de cada cambio
    autosave.setInterval(autosave_ms)
    autosave.timeout.connect(persist)
    autosave.start()
    if save_on_quit:
        app.aboutToQuit.connect(on_quit)
    window.attach_store(store, backups)                     # activa en Ajustes el cambio de contrasena y las copias
    lock = AutoLock(store, lambda: app.kreix_window._settings, lambda: app.kreix_window, app)
    app.kreix_autolock = lock                               # bloqueo por inactividad y al minimizar (sigue a la ventana vigente)
    lock.start()
    app.kreix_persist, app.kreix_autosave = persist, autosave      # (las pruebas los usan en lugar de esperar al reloj)
    return backups, lock


def settle_memory() -> None:
    """Lo creado al arrancar (ventana, widgets, modulos) vive hasta el final: se aparta del recolector de basura para que sus
    pasadas, durante cargas grandes, no lo recorran una y otra vez."""
    gc.collect()
    gc.freeze()


def selftest(report: Path) -> int:
    """Comprobacion del programa empaquetado: abre la ventana en los tres idiomas, recorre todas las paginas y dibuja el
    logotipo con las fuentes incluidas. Escribe OK (o el error) en `report`, porque el .exe no tiene consola."""
    import traceback

    try:
        from PySide6.QtGui import QFontDatabase

        from ui.help_content import localized_entries

        fonts_ok = all(name in QFontDatabase.families() for name in (fonts.DISPLAY, fonts.BODY))
        if not fonts_ok:
            raise RuntimeError("faltan las fuentes incluidas")
        for code in i18n.LANGUAGES:
            i18n.set_language(code)
            window = build_window("sqlite:///:memory:", "selftest")
            window.eager = True
            for index in range(len(window.PAGES)):
                window.navigate(index)
                QApplication.processEvents()
            if assets.wordmark(theme.current(), 46).isNull() or assets.app_icon().isNull():
                raise RuntimeError("no se pudo dibujar el logotipo")
            if not localized_entries():
                raise RuntimeError("falta la ayuda")
            window.close()
            window.deleteLater()
        report.write_text("OK\n", encoding="utf-8")
        return 0
    except Exception:                                      # noqa: BLE001 - lo que falle se cuenta en el informe
        report.write_text(traceback.format_exc(), encoding="utf-8")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kreix")
    parser.add_argument("--db", help="ruta de una base de datos alternativa (pruebas)")
    parser.add_argument("--selftest", metavar="INFORME", help="comprueba que el programa funciona y escribe el resultado en este archivo")
    args = parser.parse_args(argv)

    gc.set_threshold(20000, 20, 20)                         # menos pasadas del recolector al cargar miles de movimientos
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")          # mismo aspecto en todos los sistemas y sin el recuadro punteado de foco de Windows
    fonts.setup_application(app)
    app.setApplicationName("Kreix")
    app.setWindowIcon(assets.app_icon())
    install_keyboard_rings(app)
    brand_message.install()                                # avisos y cuadros de texto con la cara de Kreix, no los de Windows
    app.setStyleSheet(theme.stylesheet(theme.DARK))        # la pantalla de bloqueo ya sale con el estilo de la app
    if args.selftest:
        return selftest(Path(args.selftest))
    db = args.db or os.environ.get("KREIX_DB")
    threading.Thread(target=preload, name="kreix-preload", daemon=True).start()

    def launch(store) -> None:
        """Construye y muestra la ventana principal (con la pantalla de bloqueo todavia delante, si la hay)."""
        if store is None:                                   # solo pruebas/desarrollo: base alternativa sin cifrar
            window = build_window(f"sqlite:///{db}", db)
            app.kreix_window = window
            window.attach_store(None)
        else:
            window = build_window(engine=store.engine, db_label=str(store.path))
            wire_store(app, window, store)
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
