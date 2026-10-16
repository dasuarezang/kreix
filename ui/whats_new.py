"""Novedades de cada version, en palabras sencillas. Se muestran una vez tras actualizar y desde el buscador (Ctrl+K)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
from core.i18n import tr, N_
from ui.widgets.brand_dialog import BrandDialog

VERSION = "0.5.0"

RELEASES: dict[str, tuple[tuple[str, str], ...]] = {
    "0.5.0": (
        (N_("Sueldo y muchos más comercios"),
         N_("Kreix reconoce muchos más comercios, recibos y trámites, separa tu sueldo de otros ingresos y deja menos movimientos sin categoría.")),
        (N_("Por clasificar, con el cargo completo"),
         N_("Cada propuesta muestra el concepto entero tal como sale en tu extracto, y se puede marcar como sueldo.")),
        (N_("Más bancos"),
         N_("Kreix reconoce solo los extractos de CaixaBank, Santander, Revolut y Trade Republic, y lee los .xls antiguos, como los de ING. Si no reconoce un archivo, te pregunta qué columna es cada cosa.")),
        (N_("Privacidad con difuminado"),
         N_("Con el ojo, las cantidades se ven difuminadas en vez de tapadas con puntos: se nota que hay una cifra, pero no cuál.")),
        (N_("Quitar pagos recurrentes"),
         N_("Cualquier pago de Próximos pagos o de Pagos recurrentes se quita con clic derecho, lo haya detectado Kreix o lo hayas marcado tú.")),
    ),
    "0.4.0": (
        (N_("Modo privacidad"),
         N_("El ojo de la barra lateral (o Ctrl+H) oculta todas las cantidades en euros, para mirar Kreix con alguien al lado o "
            "compartir la pantalla.")),
        (N_("Previsión a fin de mes"),
         N_("Inicio calcula cuánto dinero tendrás a final de mes con tus pagos fijos, tus ingresos fijos y tu gasto de cada día.")),
        (N_("Por clasificar"),
         N_("Inicio te dice cuántos movimientos no tienen categoría y, si un comercio se repite, te propone una regla para "
            "clasificarlos de una vez.")),
        (N_("Traspasos entre tus cuentas"),
         N_("Si mueves dinero de una cuenta tuya a otra, Kreix lo reconoce y no lo cuenta ni como gasto ni como ingreso.")),
        (N_("Copias de seguridad a la vista"),
         N_("Abajo a la izquierda ves cuándo se hizo la última copia, y en Ajustes puedes comprobar que se abre de verdad.")),
        (N_("Se bloquea con Windows"),
         N_("Si bloqueas Windows (Win+L) o el equipo se suspende, Kreix también se bloquea.")),
        (N_("Tamaño del texto"),
         N_("En Ajustes puedes hacer más grande la letra de toda la aplicación, también en la pantalla de la contraseña.")),
        (N_("Cambio de tema más rápido"),
         N_("Pasar del modo claro al oscuro, y al revés, tarda ahora aproximadamente una cuarta parte.")),
    ),
    "0.3.0": (
        (N_("Importa de cualquier banco"),
         N_("Si Kreix no reconoce un CSV o Excel, te enseña sus primeras filas y te deja decir qué columna es la fecha, el "
            "concepto y el importe. Recuerda el formato: la próxima vez, ese banco se lee solo.")),
        (N_("Copias de seguridad automáticas"),
         N_("Kreix guarda copias cifradas, con la fecha en el nombre, en la carpeta que elijas y conserva las últimas. "
            "Las recuperas desde Ajustes con tu contraseña maestra.")),
        (N_("Bloqueo automático"),
         N_("Tras unos minutos sin usar el equipo, o al minimizar la ventana, Kreix vuelve a pedir la contraseña. Con "
            "Ctrl+L lo bloqueas al momento. Si fallas la contraseña varias veces, tendrás que esperar unos segundos.")),
        (N_("Un medidor para tu contraseña"),
         N_("Al crear o cambiar la contraseña maestra, un medidor te dice lo difícil que sería adivinarla y cómo mejorarla.")),
        (N_("Kreix como programa de Windows"),
         N_("Ahora se instala con un instalador, con su acceso directo en el menú Inicio y en el escritorio. Ya no hace "
            "falta tener Python.")),
    ),
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


class WhatsNewDialog(BrandDialog):
    def __init__(self, version: str = VERSION, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        heading_text = tr("Novedades de Kreix {version}").format(version=version)
        self.setWindowTitle(heading_text)
        self.setMinimumSize(600, 600)
        body = QWidget()
        body.setObjectName("Page")
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 12, 0)
        column.setSpacing(16)
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
        col = self.frame(heading_text, tr("Esto es lo que hay de nuevo desde la última vez:"))
        col.addWidget(scroll, 1)
        col.addWidget(ok, 0, Qt.AlignmentFlag.AlignRight)
