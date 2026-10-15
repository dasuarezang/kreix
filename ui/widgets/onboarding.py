"""Primera vez: la bienvenida en tres pasos y la lista de "primeros pasos" del Resumen."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui import theme
from ui.widgets.cards import StripeMark
from ui.widgets.panels import Panel

WELCOME_STEPS = (
    ("Descarga tus extractos",
     "En Imagin: tus movimientos, en CSV o Excel. En MyInvestor: tus operaciones y tu cartera, también en CSV o Excel."),
    ("Arrástralos a Kreix",
     "Ve a Importar y suelta los archivos. Kreix reconoce de qué banco son y te enseña lo que ha leído antes de guardar nada."),
    ("Explora tus finanzas",
     "El Resumen, Cuentas e Inversiones se rellenan solos. Si reimportas un extracto, no se duplica nada."),
)


class Onboarding(QWidget):
    """Pantalla de bienvenida cuando aun no hay datos: que hacer, en tres pasos, y una forma de probar sin datos propios."""

    go_import = Signal()
    demo_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Page")
        stripes = StripeMark(112, 58, centered=True)
        title = QLabel("Bienvenido a Kreix")
        title.setObjectName("H1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QLabel("Tus finanzas, en tu equipo y sin conexión. Así se empieza:")
        text.setObjectName("Muted")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        steps = QHBoxLayout()
        steps.setSpacing(16)
        for number, (heading, body) in enumerate(WELCOME_STEPS, start=1):
            steps.addWidget(self._step(number, heading, body), 1)

        self.import_button = QPushButton("Importar mis extractos")
        self.import_button.setObjectName("Primary")
        self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_button.clicked.connect(self.go_import)
        self.demo_button = QPushButton("Probar con datos de ejemplo")
        self.demo_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.demo_button.setToolTip("Carga datos inventados para explorar la app. Se quitan con un clic.")
        self.demo_button.clicked.connect(self.demo_requested)
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch(1)
        buttons.addWidget(self.import_button)
        buttons.addWidget(self.demo_button)
        buttons.addStretch(1)
        privacy = QLabel("Todo se queda en tu ordenador: Kreix no envía datos a ningún sitio.")
        privacy.setObjectName("Small")
        privacy.setAlignment(Qt.AlignmentFlag.AlignCenter)

        column = QVBoxLayout(self)
        column.setContentsMargins(48, 28, 48, 28)
        column.setSpacing(14)
        column.addStretch(1)
        column.addWidget(stripes, 0, Qt.AlignmentFlag.AlignCenter)
        column.addWidget(title)
        column.addWidget(text)
        column.addSpacing(10)
        column.addLayout(steps)
        column.addSpacing(10)
        column.addLayout(buttons)
        column.addWidget(privacy)
        column.addStretch(1)

    @staticmethod
    def _step(number: int, heading: str, body: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        badge = QLabel(str(number))
        badge.setObjectName("StepBadge")
        badge.setFixedSize(26, 26)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name = QLabel(heading)
        name.setObjectName("H2")
        name.setWordWrap(True)
        desc = QLabel(body)
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(badge)
        top.addWidget(name, 1)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        lay.addLayout(top)
        lay.addWidget(desc)
        lay.addStretch(1)
        card.setMinimumHeight(150)
        return card


class StepDot(QWidget):
    """Circulo de una lista de pasos: relleno con una marca si esta hecho, un aro si falta."""

    def __init__(self, done: bool) -> None:
        super().__init__()
        self.done = done
        self.setFixedSize(22, 22)

    def sizeHint(self) -> QSize:
        return QSize(22, 22)

    def paintEvent(self, _event) -> None:
        pal = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(2, 2, 18, 18)
        if self.done:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(pal.green))
            p.drawEllipse(rect)
            pen = QPen(QColor(pal.surface), 2.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawPolyline([rect.topLeft() + QPointF(4.6, 9.4), rect.topLeft() + QPointF(7.8, 12.6), rect.topLeft() + QPointF(13.6, 5.8)])
        else:
            p.setPen(QPen(QColor(pal.muted), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(rect)


class SetupPanel(Panel):
    """'Primeros pasos' del Resumen: que falta por importar o configurar, con un acceso directo a cada cosa."""

    navigate_requested = Signal(str)      # "import" | "accounts"
    dismissed = Signal()

    def __init__(self) -> None:
        self.hide_button = QPushButton("Ocultar")
        self.hide_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_button.setToolTip("No volver a mostrar esta lista")
        body = QWidget()
        self._rows = QVBoxLayout(body)
        self._rows.setContentsMargins(0, 4, 0, 0)
        self._rows.setSpacing(8)
        super().__init__("Primeros pasos", "Lo que te falta para tener Kreix al completo", body, self.hide_button)
        self.hide_button.clicked.connect(self.dismissed)

    def set_steps(self, steps: list[tuple[str, bool, str]]) -> None:
        """Cada paso: (texto, hecho, destino al que lleva el boton si falta)."""
        while self._rows.count():
            item = self._rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for text, done, target in steps:
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(12)
            lay.addWidget(StepDot(done))
            label = QLabel(text)
            label.setObjectName("Muted" if done else "H2")
            label.setWordWrap(True)
            lay.addWidget(label, 1)
            if not done:
                go = QPushButton("Hacerlo")
                go.setCursor(Qt.CursorShape.PointingHandCursor)
                go.setAccessibleName(f"{text}: ir")
                go.clicked.connect(lambda _=False, t=target: self.navigate_requested.emit(t))
                lay.addWidget(go)
            self._rows.addWidget(row)
        done_count = sum(1 for _, done, _ in steps if done)
        self.subtitle.setText(f"{done_count} de {len(steps)} hechos")


class EmptyState(QWidget):
    """Pagina vacia con sentido: que verias aqui, que hace falta y un boton para empezar."""

    action = Signal()

    def __init__(self, title: str, will_show: str, needs: str, button: str = "Importar extractos") -> None:
        super().__init__()
        self.setObjectName("Page")
        from ui import assets

        logo = QLabel()
        logo.setPixmap(assets.mark(72))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("H1")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        show = QLabel(will_show)
        show.setObjectName("Muted")
        show.setAlignment(Qt.AlignmentFlag.AlignCenter)
        show.setWordWrap(True)
        card = QFrame()
        card.setObjectName("Card")
        heading = QLabel("QUÉ NECESITAS")
        heading.setObjectName("CardTitle")
        need = QLabel(needs)
        need.setObjectName("Muted")
        need.setWordWrap(True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(6)
        lay.addWidget(heading)
        lay.addWidget(need)
        card.setMaximumWidth(560)
        self.button = QPushButton(button)
        self.button.setObjectName("Primary")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.action)
        col = QVBoxLayout(self)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.setSpacing(12)
        col.addWidget(logo)
        col.addWidget(self.title_label)
        col.addWidget(show)
        col.addSpacing(6)
        col.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        col.addSpacing(6)
        col.addWidget(self.button, 0, Qt.AlignmentFlag.AlignCenter)
