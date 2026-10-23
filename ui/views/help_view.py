"""Pagina de Ayuda: un menu de secciones y, dentro de cada una, el glosario de esa seccion."""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QTransform
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QStackedLayout, QVBoxLayout, QWidget

from ui import icons, theme
from ui.widgets.cards import PageHeader
from ui.widgets.section_card import GroupCard, GroupHeading, divider
from ui.help_content import SECTION_INFO, SECTIONS, HelpEntry, grouped, localized_entries, search
from core.i18n import tr

ICON_PX = 26


def entries_of(section: str) -> list[HelpEntry]:
    return [e for e in localized_entries() if e.section == section]


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _clear(item.layout())


class HelpItem(QFrame):
    """Un termino del glosario, plegado: a la vista solo su nombre; la explicacion se despliega al pulsarlo (y se recoge
    al pulsar otra vez). Asi el menu de cada seccion se lee de un vistazo."""

    def __init__(self, entry: HelpEntry, expanded: bool = False) -> None:
        super().__init__()
        self.setObjectName("SectionCard")
        self.entry = entry
        self.toggle = QPushButton(entry.term)
        self.toggle.setObjectName("HelpToggle")
        self.toggle.setCheckable(True)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.setLayoutDirection(Qt.LayoutDirection.RightToLeft)       # la flecha, al final de la fila
        self.toggle.toggled.connect(self._on_toggled)
        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(32, 4, 32, 24)
        body.setSpacing(14)
        plain = QLabel(entry.plain)
        plain.setWordWrap(True)
        body.addWidget(plain)
        for label, text, tone in ((tr("Cómo lo calcula"), entry.how, ""), (tr("Ejemplo"), entry.example, ""),
                                  (tr("Ojo"), entry.note, "alert"), (tr("Qué hacer"), entry.todo, "tip")):
            if text:
                name = QLabel(label)
                name.setObjectName("DetailLabel")
                name.setProperty("tone", tone)
                name.setFixedWidth(116)
                name.setAlignment(Qt.AlignmentFlag.AlignTop)
                detail = QLabel(text)
                detail.setObjectName("Small")
                detail.setWordWrap(True)
                row = QWidget()
                lay = QHBoxLayout(row)
                lay.setContentsMargins(0, 0, 0, 0)
                lay.setSpacing(16)
                lay.addWidget(name, 0, Qt.AlignmentFlag.AlignTop)
                lay.addWidget(detail, 1)
                body.addWidget(divider())
                body.addWidget(row)
        self.body.hide()                        # (antes de tener padre, ocultar nunca abre una ventana suelta)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.toggle)
        outer.addWidget(self.body)
        self.setAccessibleName(entry.term)
        self.toggle.setChecked(expanded)
        self.refresh_theme()

    @property
    def expanded(self) -> bool:
        return self.toggle.isChecked()

    def _on_toggled(self, on: bool) -> None:
        self.body.setVisible(on)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        """La flecha apunta a la derecha plegado y hacia abajo desplegado."""
        pal = theme.current()
        pix = icons.pixmap("chevron", pal.accent_text if self.expanded else pal.muted, 18, 2.0)
        if self.expanded:
            pix = pix.transformed(QTransform().rotate(90))
        self.toggle.setIcon(QIcon(pix))


class IconChip(QLabel):
    """Icono dentro de un recuadro de filo fino. Se repinta al cambiar de tema."""

    def __init__(self, name: str, size: int = 48) -> None:
        super().__init__()
        self._name = name
        self.setObjectName("IconChip")
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.refresh_theme()

    def set_icon(self, name: str) -> None:
        self._name = name
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.setPixmap(icons.pixmap(self._name, theme.current().accent_text, ICON_PX, 1.5))


class HubCard(QPushButton):
    """Boton grande de una seccion: icono, titulo y descripcion."""

    def __init__(self, section: str) -> None:
        super().__init__()
        icon_name, description = SECTION_INFO[section]
        self.section = section
        self.setObjectName("HubCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(84)
        self.setAccessibleName(tr(section))
        self.setToolTip(tr(section))

        self.chip = IconChip(icon_name)
        title = QLabel(tr(section))
        title.setObjectName("HubTitle")
        title.setWordWrap(True)
        sub = QLabel(tr("{description}  ·  {count} términos").format(description=tr(description), count=len(entries_of(section))))
        sub.setObjectName("Small")
        sub.setWordWrap(True)
        self.chevron = QLabel()
        for child in (title, sub, self.chevron):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text = QVBoxLayout()
        text.setSpacing(3)
        text.addWidget(title)
        text.addWidget(sub)
        row = QHBoxLayout(self)
        row.setContentsMargins(26, 20, 26, 20)
        row.setSpacing(18)
        row.addWidget(self.chip)
        row.addLayout(text, 1)
        row.addWidget(self.chevron)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.chip.refresh_theme()
        self.chevron.setPixmap(icons.pixmap("chevron", theme.current().muted, 18, 1.5))


class HelpView(QWidget):
    section_opened = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._section: str | None = None
        self._shown: list[HelpEntry] = []
        self.items: list[HelpItem] = []          # los terminos que se ven ahora (de la seccion o de la busqueda)

        self._stack = QStackedLayout(self)
        self._stack.addWidget(self._build_hub())
        self._stack.addWidget(self._build_section())

    # ------------------------------------------------------------------ menu (hub)
    def _build_hub(self) -> QWidget:
        header = PageHeader(tr("Ayuda"), eyebrow=tr("Glosario"),
                            subtitle=tr("Qué significa cada cifra y cada gráfico de Kreix, explicado sin tecnicismos. Elige un tema."))

        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("O busca un término: TIR, patrimonio neto, tasa de ahorro…"))
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName(tr("Buscar en la ayuda"))
        self.search.textChanged.connect(self._on_query)

        # Los seis temas, en una sola tarjeta con filas separadas (antes, seis tarjetas iguales con un circulo amarillo cada una)
        self._grid_holder = GroupCard()
        self.cards: list[HubCard] = []
        for i, section in enumerate(SECTIONS):
            card = HubCard(section)
            card.clicked.connect(partial(self._open_from_card, section))
            self.cards.append(card)
            if i:
                self._grid_holder._col.addWidget(divider())
            self._grid_holder._col.addWidget(card)
        self._grid_holder._col.setContentsMargins(10, 10, 10, 10)

        self._results = QVBoxLayout()
        self._results.setSpacing(10)
        self._results_holder = QWidget()
        self._results_holder.setObjectName("Page")
        self._results_holder.setLayout(self._results)
        self._results_holder.hide()
        self._summary = QLabel("")
        self._summary.setObjectName("Small")

        body = QWidget()
        body.setObjectName("Page")
        col = QVBoxLayout(body)
        col.setContentsMargins(48, 40, 48, 48)
        col.setSpacing(22)
        for w in (header, self.search, self._summary, self._grid_holder, self._results_holder):
            col.addWidget(w)
        col.addStretch(1)
        return self._scroll(body)

    # ------------------------------------------------------------------ seccion
    def _build_section(self) -> QWidget:
        self.back_button = QPushButton(tr("  Ayuda"))
        self.back_button.setObjectName("BackButton")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.setToolTip(tr("Volver al menú de Ayuda"))
        self.back_button.setAccessibleName(tr("Volver al menú de Ayuda"))
        self.back_button.clicked.connect(self.show_hub)
        self.back_button.setIcon(icons.button_icon("back", theme.current(), 18))

        self._section_chip = IconChip("book", 52)
        self._section_title = QLabel("")
        self._section_title.setObjectName("H1")
        self._section_title.setWordWrap(True)
        self._section_sub = QLabel("")
        self._section_sub.setObjectName("Muted")
        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(self._section_title)
        heading.addWidget(self._section_sub)
        head_row = QHBoxLayout()
        head_row.setSpacing(16)
        head_row.addWidget(self._section_chip)
        head_row.addLayout(heading, 1)

        self._entries = QVBoxLayout()
        self._entries.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(self.back_button)
        top.addStretch(1)
        body = QWidget()
        body.setObjectName("Page")
        col = QVBoxLayout(body)
        col.setContentsMargins(48, 34, 48, 48)
        col.setSpacing(22)
        col.addLayout(top)
        col.addLayout(head_row)
        col.addSpacing(6)
        col.addLayout(self._entries)
        col.addStretch(1)
        return self._scroll(body)

    @staticmethod
    def _scroll(body: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        return scroll

    # ------------------------------------------------------------------ navegacion
    def is_hub(self) -> bool:
        return self._stack.currentIndex() == 0

    def current_section(self) -> str | None:
        return None if self.is_hub() else self._section

    def show_hub(self) -> None:
        self._section = None
        self._stack.setCurrentIndex(0)
        self._on_query(self.search.text())

    def _open_from_card(self, section: str, _checked: bool = False) -> None:
        self.open_section(section)

    def open_section(self, section: str) -> None:
        entries = entries_of(section)
        self._section = section
        self._shown = entries
        icon_name, description = SECTION_INFO[section]
        self._section_chip.set_icon(icon_name)
        self._section_title.setText(tr(section))
        self._section_sub.setText(tr("{description}  ·  {count} términos").format(description=tr(description), count=len(entries)))
        _clear(self._entries)
        self.items = []
        for entry in entries:
            self._entries.addWidget(self._item(entry))
        self._stack.setCurrentIndex(1)
        self.section_opened.emit(section)

    # ------------------------------------------------------------------ busqueda
    def _on_query(self, text: str) -> None:
        query = text.strip()
        searching = bool(query)
        self._grid_holder.setVisible(not searching)
        self._results_holder.setVisible(searching)
        _clear(self._results)
        self.items = []
        if not searching:
            self._summary.setText("")
            if self.is_hub():
                self._shown = []
            return
        everything = localized_entries()
        found = search(everything, query)
        if self.is_hub():
            self._shown = found
        if not found:
            empty = QLabel(tr("No hay resultados para «{query}». Prueba con otra palabra.").format(query=query))
            empty.setObjectName("Muted")
            self._results.addWidget(empty)
            self._summary.setText("")
            return
        self._summary.setText(tr("{found} de {total} términos").format(found=len(found), total=len(everything)))
        exact = [e for e in found if e.term.casefold() == query.casefold()]
        for section, entries in grouped(found):
            self._results.addSpacing(8)
            self._results.addWidget(GroupHeading(tr(section)))
            for entry in entries:
                # desde un «?» se busca el termino exacto: ese sale ya desplegado (o el unico resultado)
                self._results.addWidget(self._item(entry, expanded=entry in exact or len(found) == 1))

    def set_query(self, text: str) -> None:
        """Escribe en el buscador (vuelve al menu si se estaba dentro de una seccion)."""
        if not self.is_hub():
            self.show_hub()
        self.search.setText(text)

    def entry_terms(self) -> list[str]:
        """Terminos que se estan mostrando: los de la seccion abierta o los resultados de la busqueda."""
        return [e.term for e in self._shown]

    def section_titles(self) -> list[str]:
        return [c.section for c in self.cards]

    def refresh_theme(self) -> None:
        self.back_button.setIcon(icons.button_icon("back", theme.current(), 18))
        for card in self.cards:
            card.refresh_theme()
        for item in self.items:
            item.refresh_theme()
        self._section_chip.refresh_theme()

    # ------------------------------------------------------------------ termino (desplegable)
    def _item(self, entry: HelpEntry, expanded: bool = False) -> HelpItem:
        item = HelpItem(entry, expanded)
        self.items.append(item)
        return item
