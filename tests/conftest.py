import gc
import os

# Qt sin pantalla para poder probar la interfaz en cualquier equipo / CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    if QApplication.instance():
        return QApplication.instance()
    from ui import blur

    app = QApplication([])
    blur.install(app)
    return app


def dispose_windows(*windows):
    """Cierra y destruye ventanas: si no, siguen vivas y cada cambio de tema repinta todas las anteriores."""
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    from ui import theme

    for w in windows:
        w.close()
        w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    theme.set_current(theme.DARK)


@pytest.fixture()
def window(qapp):
    from main import build_window
    from ui.widgets import charts

    charts.ANIMATIONS = False
    from ui import fonts

    fonts.setup_application(qapp)
    w = build_window("sqlite:///:memory:", "memoria")
    w.eager = True
    yield w
    dispose_windows(w)


@pytest.fixture(autouse=True)
def _freeze_garbage_after_each_test():
    """Con PySide, recoger mas tarde ventanas ya destruidas puede recorrer objetos C++ liberados y tumbar el proceso.
    Se congela lo que ha quedado de cada prueba para que el recolector no vuelva a recorrerlo."""
    yield
    gc.freeze()


@pytest.fixture(autouse=True)
def _language_hint_in_a_temp_folder(tmp_path, monkeypatch):
    """Las pruebas nunca escriben el archivo de idioma de verdad (el del usuario, en %APPDATA%)."""
    import data.paths

    monkeypatch.setattr(data.paths, "language_hint_path", lambda: tmp_path / "idioma.txt")
    monkeypatch.setattr(data.paths, "scale_hint_path", lambda: tmp_path / "texto.txt")


@pytest.fixture(autouse=True)
def _spanish_by_default():
    """Cada prueba empieza (y termina) en castellano: el idioma es un estado global."""
    from core import i18n

    from ui import fonts, format as formatting

    i18n.set_language("es")
    fonts.set_scale(100)
    formatting.set_private(False)
    yield
    i18n.set_language("es")
    fonts.set_scale(100)
    formatting.set_private(False)
