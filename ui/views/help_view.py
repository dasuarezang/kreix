"""Pagina de Ayuda: un menu de secciones y, dentro de cada una, el glosario de esa seccion."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QStackedLayout,
    QVBoxLayout, QWidget,
)

from ui import icons, theme
from ui.widgets.cards import PageHeader
from ui.help_content import ENTRIES, SECTION_INFO, SECTIONS, HelpEntry, grouped, search

ICON_PX = 26


def entries_of(section: str) -> list[HelpEntry]:
    return [e for e in ENTRIES if e.section == section]


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _clear(item.layout())


class IconChip(QLabel):
    """Icono dentro de un circulo del color de acento. Se repinta al cambiar de tema."""

    def __init__(self, name: str, size: int = 48) -> None:
        super().__init__()
        self._name = name
        self.setObjectName("IconChip")
        self.setFixedSize(size, size)
        self.setStyleSheet(f"border-radius: {size // 2}px;")      # circulo exacto: la hoja global no lo hace bien
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.refresh_theme()

    def set_icon(self, name: str) -> None:
        self._name = name
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.setPixmap(icons.pixmap(self._name, theme.current().on_accent, ICON_PX, 1.9))


class HubCard(QPushButton):
    """Boton grande de una seccion: icono, titulo y descripcion."""

    def __init__(self, section: str) -> None:
        super().__init__()
        icon_name, description = SECTION_INFO[section]
        self.section = section
        self.setObjectName("HubCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(92)
        self.setAccessibleName(section)
        self.setToolTip(section)

        self.chip = IconChip(icon_name)
        title = QLabel(section)
        title.setObjectName("HubTitle")
        title.setWordWrap(True)
        sub = QLabel(f"{description}  ·  {len(entries_of(section))} términos")
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
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(16)
        row.addWidget(self.chip)
        row.addLayout(text, 1)
        row.addWidget(self.chevron)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.chip.refresh_theme()
        self.chevron.setPixmap(icons.pixmap("chevron", theme.current().muted, 18, 2.0))


class HelpView(QWidget):
    section_opened = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._section: str | None = None
        self._shown: list[HelpEntry] = []

        self._stack = QStackedLayout(self)
        self._stack.addWidget(self._build_hub())
        self._stack.addWidget(self._build_section())

    # ------------------------------------------------------------------ menu (hub)
    def _build_hub(self) -> QWidget:
        header = PageHeader("Ayuda", eyebrow="Glosario",
                            subtitle="Qué significa cada cifra y cada gráfico de Kreix, explicado sin tecnicismos. Elige un tema.")

        self.search = QLineEdit()
        self.search.setPlaceholderText("O busca un término: TIR, patrimonio neto, tasa de ahorro…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Buscar en la ayuda")
        self.search.textChanged.connect(self._on_query)

        self._grid_holder = QWidget()
        self._grid_holder.setObjectName("Page")
        grid = QGridLayout(self._grid_holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(14)
        self.cards: list[HubCard] = []
        for i, section in enumerate(SECTIONS):
            card = HubCard(section)
            card.clicked.connect(lambda _=False, s=section: self.open_section(s))
            self.cards.append(card)
            grid.addWidget(card, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

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
        col.setContentsMargins(32, 28, 32, 32)
        col.setSpacing(14)
        for w in (header, self.search, self._summary, self._grid_holder, self._results_holder):
            col.addWidget(w)
        col.addStretch(1)
        return self._scroll(body)

    # ------------------------------------------------------------------ seccion
    def _build_section(self) -> QWidget:
        self.back_button = QPushButton("  Ayuda")
        self.back_button.setObjectName("BackButton")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.setToolTip("Volver al menú de Ayuda")
        self.back_button.setAccessibleName("Volver al menú de Ayuda")
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
        col.setContentsMargins(32, 24, 32, 32)
        col.setSpacing(14)
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

    def open_section(self, section: str) -> None:
        entries = entries_of(section)
        self._section = section
        self._shown = entries
        icon_name, description = SECTION_INFO[section]
        self._section_chip.set_icon(icon_name)
        self._section_title.setText(section)
        self._section_sub.setText(f"{description}  ·  {len(entries)} términos")
        _clear(self._entries)
        for entry in entries:
            self._entries.addWidget(self._card(entry))
        self._stack.setCurrentIndex(1)
        self.section_opened.emit(section)

    # ------------------------------------------------------------------ busqueda
    def _on_query(self, text: str) -> None:
        query = text.strip()
        searching = bool(query)
        self._grid_holder.setVisible(not searching)
        self._results_holder.setVisible(searching)
        _clear(self._results)
        if not searching:
            self._summary.setText("")
            if self.is_hub():
                self._shown = []
            return
        found = search(ENTRIES, query)
        if self.is_hub():
            self._shown = found
        if not found:
            empty = QLabel(f"No hay resultados para «{query}». Prueba con otra palabra.")
            empty.setObjectName("Muted")
            self._results.addWidget(empty)
            self._summary.setText("")
            return
        self._summary.setText(f"{len(found)} de {len(ENTRIES)} términos")
        for section, entries in grouped(found):
            heading = QLabel(section.upper())
            heading.setObjectName("SectionTitle")
            self._results.addSpacing(8)
            self._results.addWidget(heading)
            for entry in entries:
                self._results.addWidget(self._card(entry))

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
        self._section_chip.refresh_theme()

    # ------------------------------------------------------------------ tarjeta de termino
    @staticmethod
    def _card(entry: HelpEntry) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)
        term = QLabel(entry.term)
        term.setObjectName("H2")
        term.setWordWrap(True)
        lay.addWidget(term)
        plain = QLabel(entry.plain)
        plain.setWordWrap(True)
        lay.addWidget(plain)
        for label, text in (("Cómo lo calcula", entry.how), ("Ejemplo", entry.example),
                            ("Ojo", entry.note), ("Qué hacer", entry.todo)):
            if text:
                line = QLabel(f"<b>{label}:</b> {text}")
                line.setObjectName("Small")
                line.setWordWrap(True)
                line.setTextFormat(Qt.TextFormat.RichText)
                lay.addWidget(line)
        card.setAccessibleName(entry.term)
        return card
