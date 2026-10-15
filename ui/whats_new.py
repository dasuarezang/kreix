"""Novedades de cada version, en palabras sencillas. Se muestran una vez tras actualizar y desde el buscador (Ctrl+K)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

VERSION = "0.2.0"

RELEASES: dict[str, tuple[tuple[str, str], ...]] = {
    "0.2.0": (
        ("Datos de ejemplo",
         "Si aún no has importado nada, puedes explorar Kreix con datos inventados y quitarlos con un clic."),
        ("Primeros pasos",
         "El Resumen te dice qué te falta por importar o configurar, con un botón para hacerlo."),
        ("Revisa antes de importar",
         "Al soltar un extracto, Kreix te enseña qué ha leído, de qué fechas y cuántos movimientos son nuevos. "
         "No se guarda nada hasta que pulsas Importar. Si un archivo falla, te explica por qué y qué hacer."),
        ("Todo se confirma y se puede deshacer",
         "Cada cambio importante avisa con un mensaje breve y, casi siempre, con un botón Deshacer."),
        ("Más a mano",
         "Cada movimiento tiene un botón ••• para cambiar su categoría. Pulsa una categoría en un gráfico o en un "
         "presupuesto para ver sus movimientos. Con Ctrl+K buscas cualquier cosa: páginas, acciones, movimientos y ayuda."),
        ("Categorías, presupuestos y pagos recurrentes",
         "Cambia categorías a tu gusto y crea reglas, fija un tope mensual por categoría y mira cuánto te cuestan "
         "tus suscripciones. Compara cada mes con el anterior y exporta tus movimientos a CSV o Excel."),
        ("Más rápido",
         "Las tablas y los cálculos van mucho más fluidos con muchos movimientos, y la ventana recuerda su tamaño."),
    ),
}


def notes_for(version: str) -> tuple[tuple[str, str], ...]:
    return RELEASES.get(version, ())


class WhatsNewDialog(QDialog):
    def __init__(self, version: str = VERSION, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Novedades de Kreix {version}")
        self.setMinimumSize(560, 520)
        title = QLabel(f"Novedades de Kreix {version}")
        title.setObjectName("H1")
        intro = QLabel("Esto es lo que hay de nuevo desde la última vez:")
        intro.setObjectName("Muted")
        body = QWidget()
        body.setObjectName("Page")
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 8, 0)
        column.setSpacing(14)
        for heading, text in notes_for(version):
            name = QLabel(heading)
            name.setObjectName("H2")
            desc = QLabel(text)
            desc.setObjectName("Muted")
            desc.setWordWrap(True)
            column.addWidget(name)
            column.addWidget(desc)
        column.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        ok = QPushButton("Entendido")
        ok.setObjectName("Primary")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.clicked.connect(self.accept)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(10)
        root.addWidget(title)
        root.addWidget(intro)
        root.addWidget(scroll, 1)
        root.addWidget(ok, 0, Qt.AlignmentFlag.AlignRight)
