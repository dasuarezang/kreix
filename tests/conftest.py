import os

# Qt sin pantalla para poder probar la interfaz en cualquier equipo / CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def window(qapp):
    from main import build_window
    from ui import theme
    from ui.widgets import charts

    charts.ANIMATIONS = False

    w = build_window("sqlite:///:memory:", "memoria")
    yield w
    w.close()
    w.deleteLater()      # si no, las ventanas de pruebas anteriores siguen vivas y ralentizan cada cambio de tema
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    theme.set_current(theme.DARK)
