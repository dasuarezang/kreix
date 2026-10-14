import os

# Qt sin pantalla para poder probar la interfaz en cualquier equipo / CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
