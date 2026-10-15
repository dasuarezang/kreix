"""Primera vez: la bienvenida en tres pasos y la lista de "primeros pasos" de Inicio."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui import theme
from ui.widgets.cards import StripeMark
from ui.widgets.panels import Panel
from ui.widgets.sky import SkyWidget
from core.i18n import tr, N_

WELCOME_STEPS = (
    (N_("Descarga tus extractos"),
     N_("En Imagin: tus movimientos, en CSV o Excel. En MyInvestor: tus operaciones y tu cartera, también en CSV o Excel.")),
    (N_("Arrástralos a Kreix"),
     N_("Ve a Importar y suelta los archivos. Kreix reconoce de qué banco son y te enseña lo que ha leído antes de guardar nada.")),
    (N_("Explora tus finanzas"),
     N_("Inicio, Cuentas e Inversiones se rellenan solos. Si reimportas un extracto, no se duplica nada.")),
)


class Onboarding(QWidget):
    """Pantalla de bienvenida cuando aun no hay datos: que hacer, en tres pasos, y una forma de probar sin datos propios."""

    go_import = Signal()
    demo_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Page")
        stripes = StripeMark(112, 58, centered=True)
        self.title = QLabel(tr("Bienvenido a Kreix"))
        title = self.title
        title.setObjectName("H1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sky = SkyWidget()
        self.date_line = QLabel("")
        self.date_line.setObjectName("DateLine")
        self.date_line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row = QHBoxLayout()
        title_row.setSpacing(14)
        title_row.addStretch(1)
        title_row.addWidget(title)
        title_row.addWidget(self.sky, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch(1)
        text = QLabel(tr("Bienvenido a Kreix: tus finanzas, en tu equipo y sin conexión. Así se empieza:"))
        text.setObjectName("Muted")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        steps = QHBoxLayout()
        steps.setSpacing(16)
        steps_labels: list[QLabel] = []
        for number, (heading, body) in enumerate(WELCOME_STEPS, start=1):
            card = self._step(number, tr(heading), tr(body))
            steps_labels.append(card.desc_label)                          # el texto explicativo de cada paso
            steps.addWidget(card, 1)

        self._step1 = steps_labels[0]
        self._step3 = steps_labels[2]
        self.import_button = QPushButton(tr("Importar mis extractos"))
        self.import_button.setObjectName("Primary")
        self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_button.clicked.connect(self.go_import)
        self.demo_button = QPushButton(tr("Probar con datos de ejemplo"))
        self.demo_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.demo_button.setToolTip(tr("Carga datos inventados para explorar la app. Se quitan con un clic."))
        self.demo_button.clicked.connect(self.demo_requested)
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch(1)
        buttons.addWidget(self.import_button)
        buttons.addWidget(self.demo_button)
        buttons.addStretch(1)
        privacy = QLabel(tr("Todo se queda en tu ordenador: Kreix no envía datos a ningún sitio."))
        privacy.setObjectName("Small")
        privacy.setAlignment(Qt.AlignmentFlag.AlignCenter)

        column = QVBoxLayout(self)
        column.setContentsMargins(48, 28, 48, 28)
        column.setSpacing(14)
        column.addStretch(1)
        column.addWidget(stripes, 0, Qt.AlignmentFlag.AlignCenter)
        column.addLayout(title_row)
        column.addWidget(self.date_line)
        column.addWidget(text)
        column.addSpacing(10)
        column.addLayout(steps)
        column.addSpacing(10)
        column.addLayout(buttons)
        column.addWidget(privacy)
        column.addStretch(1)

    def set_interests(self, accounts: bool, investments: bool) -> None:
        """Adapta los pasos a lo que el usuario quiere gestionar."""
        if accounts and investments:
            first, third = tr(WELCOME_STEPS[0][1]), tr(WELCOME_STEPS[2][1])
        elif accounts:
            first = tr("En Imagin: tus movimientos, en CSV o Excel.")
            third = tr("Inicio y Cuentas se rellenan solos. Si reimportas un extracto, no se duplica nada.")
        else:
            first = tr("En MyInvestor: tus operaciones y tu cartera, también en CSV o Excel.")
            third = tr("Inicio e Inversiones se rellenan solos. Si reimportas un extracto, no se duplica nada.")
        self._step1.setText(first)
        self._step3.setText(third)

    def set_date(self, text: str) -> None:
        self.date_line.setText(text)

    def set_greeting(self, text: str) -> None:
        self.title.setText(text)

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
        card.desc_label = desc
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
    """'Primeros pasos' de Inicio: que falta por importar o configurar, con un acceso directo a cada cosa."""

    navigate_requested = Signal(str)      # "import" | "accounts"
    dismissed = Signal()

    def __init__(self) -> None:
        self.hide_button = QPushButton(tr("Ocultar"))
        self.hide_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_button.setToolTip(tr("No volver a mostrar esta lista"))
        body = QWidget()
        self._rows = QVBoxLayout(body)
        self._rows.setContentsMargins(0, 4, 0, 0)
        self._rows.setSpacing(8)
        super().__init__(tr("Primeros pasos"), tr("Lo que te falta para tener Kreix al completo"), body, self.hide_button, raised=True)
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
                go = QPushButton(tr("Hacerlo"))
                go.setCursor(Qt.CursorShape.PointingHandCursor)
                go.setAccessibleName(f"{text}: ir")
                go.clicked.connect(lambda _=False, t=target: self.navigate_requested.emit(t))
                lay.addWidget(go)
            self._rows.addWidget(row)
        done_count = sum(1 for _, done, _ in steps if done)
        self._rows.insertWidget(0, StepsBar(done_count, len(steps)))
        self.subtitle.setText(tr("{done_count} de {steps} hechos").format(done_count=done_count, steps=len(steps)))


class InterestOffState(QWidget):
    """Lo que se ve en Cuentas o Inversiones si el usuario dijo que ese tema no le interesa: un boton para activarlo."""

    activate_requested = Signal()

    def __init__(self, title: str, text: str, button: str) -> None:
        super().__init__()
        self.setObjectName("Page")
        from ui import assets

        logo = BrandHalo()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("H1")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        body = QLabel(text)
        body.setObjectName("Muted")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        body.setFixedWidth(520)
        self.button = QPushButton(button or tr("Importar extractos"))
        self.button.setObjectName("Primary")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.activate_requested)
        note = QLabel(tr("También puedes cambiarlo en Ajustes, en «Lo que te interesa»."))
        note.setObjectName("Small")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col = QVBoxLayout(self)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.setSpacing(12)
        col.addWidget(logo, 0, Qt.AlignmentFlag.AlignCenter)
        col.addWidget(StripeMark(112, 40, centered=True), 0, Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.title_label)
        col.addWidget(body, 0, Qt.AlignmentFlag.AlignCenter)
        col.addSpacing(6)
        col.addWidget(self.button, 0, Qt.AlignmentFlag.AlignCenter)
        col.addWidget(note)


class BrandHalo(QWidget):
    """El icono de Kreix sobre un resplandor amarillo suave: la cara de las paginas vacias."""

    def __init__(self) -> None:
        super().__init__()
        from ui import assets

        self.setFixedSize(190, 130)
        self._mark = assets.mark(72)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, _event) -> None:
        pal = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        glow = QRadialGradient(self.width() / 2, self.height() / 2, self.height() / 2)    # circular: sin bordes rectos
        inner, outer = QColor(pal.accent), QColor(pal.accent)
        inner.setAlpha(70)
        outer.setAlpha(0)
        glow.setColorAt(0.0, inner)
        glow.setColorAt(1.0, outer)
        painter.fillRect(self.rect(), glow)
        x = (self.width() - self._mark.width() / self._mark.devicePixelRatio()) / 2
        y = (self.height() - self._mark.height() / self._mark.devicePixelRatio()) / 2
        painter.drawPixmap(int(x), int(y), self._mark)


class StepsBar(QWidget):
    """Barra fina con lo que llevas hecho de los primeros pasos (va del amarillo al rojo de la marca)."""

    def __init__(self, done: int, total: int) -> None:
        super().__init__()
        self._done, self._total = done, max(total, 1)
        self.setFixedHeight(8)

    def paintEvent(self, _event) -> None:
        pal = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(pal.border))
        painter.drawRoundedRect(QRectF(0, 2, self.width(), 5), 2.5, 2.5)
        width = self.width() * self._done / self._total
        if width > 0:
            fill = QLinearGradient(0, 0, self.width(), 0)
            fill.setColorAt(0.0, QColor(pal.accent))
            fill.setColorAt(1.0, QColor(pal.red))
            painter.setBrush(fill)
            painter.drawRoundedRect(QRectF(0, 2, max(width, 6), 5), 2.5, 2.5)


class EmptyState(QWidget):
    """Pagina vacia con sentido: que verias aqui, que hace falta y un boton para empezar."""

    action = Signal()

    def __init__(self, title: str, will_show: str, needs: str, button: str | None = None) -> None:
        super().__init__()
        self.setObjectName("Page")
        from ui import assets

        logo = BrandHalo()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("H1")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        show = QLabel(will_show)
        show.setObjectName("Muted")
        show.setAlignment(Qt.AlignmentFlag.AlignCenter)
        show.setWordWrap(True)
        card = QFrame()
        card.setObjectName("Card")
        heading = QLabel(tr("QUÉ NECESITAS"))
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
        self.button = QPushButton(button or tr("Importar extractos"))
        self.button.setObjectName("Primary")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.action)
        col = QVBoxLayout(self)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.setSpacing(12)
        col.addWidget(logo, 0, Qt.AlignmentFlag.AlignCenter)
        col.addWidget(StripeMark(112, 40, centered=True), 0, Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.title_label)
        col.addWidget(show)
        col.addSpacing(6)
        col.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        col.addSpacing(6)
        col.addWidget(self.button, 0, Qt.AlignmentFlag.AlignCenter)
