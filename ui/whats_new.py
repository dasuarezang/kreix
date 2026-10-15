"""Novedades de cada version, en palabras sencillas. Se muestran una vez tras actualizar y desde el buscador (Ctrl+K)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
from core.i18n import tr, N_

VERSION = "0.2.0"

RELEASES: dict[str, tuple[tuple[str, str], ...]] = {
    "0.2.0": (
        (N_("Castellano, català o English"),
         N_("Kreix ya está en tres idiomas. Los eliges la primera vez, junto al nombre y a lo que te interesa, y puedes "
            "cambiarlos cuando quieras en Ajustes. Cada idioma lleva la bandera de su país o región.")),
        (N_("La K con cuatro barras"),
         N_("El logotipo y las franjas de las cabeceras llevan ahora las cuatro barras de la senyera, como la bandera.")),
        (N_("Elige qué quieres gestionar"),
         N_("La primera vez, Kreix te pregunta si te interesan tus cuentas, tus inversiones o las dos cosas. Inicio se adapta a "
         "lo que elijas. Puedes cambiarlo en Ajustes o, si entras en una pestaña que tienes desactivada, con un botón para "
         "activarla.")),
        (N_("Un Inicio más vivo"),
         N_("Junto a tu nombre hay un sol que sale por la mañana, baja por la tarde y se pone, y una luna con estrellas por la "
         "noche: recorren su ciclo completo con la hora real, aunque dejes la app abierta. Debajo ves el día y la hora, siempre "
         "al día, y la fecha de la última actualización de tus datos. La pantalla baja su brillo un poquito con la hora (sin "
         "cambiar el tema; se desactiva en Ajustes). Los presupuestos de Inicio pasan solos, uno a uno, y tú también puedes "
         "pasarlos.")),
        (N_("Inicio y tu nombre"),
         N_("El Resumen ahora se llama Inicio y te saluda según la hora del día: buenos días, buenas tardes o buenas noches. "
         "Kreix te pregunta tu nombre la primera vez; puedes cambiarlo en Ajustes y viaja con tus datos al exportar e importar.")),
        (N_("Datos de ejemplo"),
         N_("Si aún no has importado nada, puedes explorar Kreix con datos inventados y quitarlos con un clic.")),
        (N_("Primeros pasos"),
         N_("Inicio te dice qué te falta por importar o configurar, con un botón para hacerlo.")),
        (N_("Revisa antes de importar"),
         N_("Al soltar un extracto, Kreix te enseña qué ha leído, de qué fechas y cuántos movimientos son nuevos. "
         "No se guarda nada hasta que pulsas Importar. Si un archivo falla, te explica por qué y qué hacer.")),
        (N_("Todo se confirma y se puede deshacer"),
         N_("Cada cambio importante avisa con un mensaje breve y, casi siempre, con un botón Deshacer.")),
        (N_("Más a mano"),
         N_("Cada movimiento tiene un botón ••• para cambiar su categoría. Pulsa una categoría en un gráfico o en un "
         "presupuesto para ver sus movimientos. Con Ctrl+K buscas cualquier cosa: páginas, acciones, movimientos y ayuda.")),
        (N_("Categorías, presupuestos y pagos recurrentes"),
         N_("Cambia categorías a tu gusto y crea reglas, fija un tope mensual por categoría y mira cuánto te cuestan "
         "tus suscripciones. Compara cada mes con el anterior y exporta tus movimientos a CSV o Excel.")),
        (N_("Más rápido"),
         N_("Las tablas y los cálculos van mucho más fluidos con muchos movimientos, y la ventana recuerda su tamaño.")),
    ),
}


def notes_for(version: str) -> tuple[tuple[str, str], ...]:
    return tuple((tr(heading), tr(text)) for heading, text in RELEASES.get(version, ()))


class WhatsNewDialog(QDialog):
    def __init__(self, version: str = VERSION, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Novedades de Kreix {version}").format(version=version))
        self.setMinimumSize(560, 520)
        title = QLabel(tr("Novedades de Kreix {version}").format(version=version))
        title.setObjectName("H1")
        intro = QLabel(tr("Esto es lo que hay de nuevo desde la última vez:"))
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
        ok = QPushButton(tr("Entendido"))
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
