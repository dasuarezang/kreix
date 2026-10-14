"""Pagina de Ayuda: que significa cada cifra, con buscador."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from ui.help_content import ENTRIES, HelpEntry, grouped, search


def _clear(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


class HelpView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._shown: list[HelpEntry] = []
        self._built = False        # las ~44 tarjetas se crean la primera vez que se abre la pagina

        title = QLabel("Ayuda")
        title.setObjectName("H1")
        intro = QLabel("Qué significa cada cifra y cada gráfico de Kreix, explicado sin tecnicismos.")
        intro.setObjectName("Muted")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Busca un término: TIR, patrimonio neto, tasa de ahorro…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Buscar en la ayuda")
        self.search.textChanged.connect(self.set_query)
        self._summary = QLabel("")
        self._summary.setObjectName("Small")

        self._list = QVBoxLayout()
        self._list.setSpacing(10)

        body = QWidget()
        body.setObjectName("Page")
        col = QVBoxLayout(body)
        col.setContentsMargins(32, 28, 32, 32)
        col.setSpacing(12)
        col.addWidget(title)
        col.addWidget(intro)
        col.addSpacing(4)
        col.addWidget(self.search)
        col.addWidget(self._summary)
        col.addSpacing(4)
        col.addLayout(self._list)
        col.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def ensure_built(self) -> None:
        if not self._built:
            self.set_query(self.search.text())

    def showEvent(self, event) -> None:
        self.ensure_built()
        super().showEvent(event)

    def set_query(self, text: str) -> None:
        self._built = True
        self._shown = search(ENTRIES, text)
        _clear(self._list)
        if not self._shown:
            empty = QLabel(f"No hay resultados para «{text.strip()}». Prueba con otra palabra.")
            empty.setObjectName("Muted")
            self._list.addWidget(empty)
            self._summary.setText("")
            return
        for section, entries in grouped(self._shown):
            heading = QLabel(section.upper())
            heading.setObjectName("SectionTitle")
            self._list.addSpacing(10)
            self._list.addWidget(heading)
            for entry in entries:
                self._list.addWidget(self._card(entry))
        total = len(ENTRIES)
        self._summary.setText("" if len(self._shown) == total else f"{len(self._shown)} de {total} términos")

    def entry_terms(self) -> list[str]:
        return [e.term for e in self._shown]

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
