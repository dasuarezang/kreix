import os

# Qt sin pantalla para poder probar la interfaz en cualquier equipo / CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


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
    w = build_window("sqlite:///:memory:", "memoria")
    yield w
    dispose_windows(w)
