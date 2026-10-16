"""Buscador de todo (Ctrl+K): escribe y salta a una pagina, ejecuta una accion, busca un movimiento o abre la ayuda."""
from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from core.categorizer import normalize
from ui import theme
from ui.widgets.cards import repolish
from core.i18n import tr, N_

MAX_SHOWN = 9
ROW_HEIGHT = 40
MOVEMENT_MIN_CHARS = 2


@dataclass(frozen=True, slots=True)
class Command:
    title: str
    subtitle: str
    run: Callable[[], None]
    keywords: str = ""        # sinonimos para encontrarlo ("tema" -> modo oscuro)
    group: str = N_("Acciones")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Z0-9]+", normalize(text))


def rank_commands(commands: Sequence[Command], query: str) -> list[Command]:
    """Los comandos que contienen cada palabra de la busqueda como inicio de palabra (sin acentos ni mayusculas).
    Primero los que coinciden en el titulo, luego en los sinonimos; sin busqueda, todos en su orden."""
    words = _tokens(query)
    if not words:
        return list(commands)
    ranked: list[tuple[int, int, Command]] = []
    for position, cmd in enumerate(commands):
        title = _tokens(cmd.title)
        rest = _tokens(f"{cmd.subtitle} {cmd.keywords}")
        if not all(any(t.startswith(w) for t in title + rest) for w in words):
            continue
        tier = 0 if all(any(t.startswith(w) for t in title) for w in words) else 1
        ranked.append((tier, position, cmd))
    return [c for _, _, c in sorted(ranked, key=lambda r: (r[0], r[1]))]


class CommandPalette(QDialog):
    def __init__(self, commands: Sequence[Command], movements: Callable[[str], list[Command]] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self._commands = list(commands)
        self._movements = movements
        self._shown: list[Command] = []

        card = QFrame(self)
        card.setObjectName("PaletteCard")
        self.input = QLineEdit()
        self.input.setPlaceholderText(tr("Busca una página, una acción, un movimiento o una palabra de la ayuda…"))
        self.input.setAccessibleName(tr("Buscar o ir a"))
        self.input.setClearButtonEnabled(True)
        self.list = QListWidget()
        self.list.setObjectName("PaletteList")
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.hint = QLabel(tr("↑ ↓ para moverte  ·  Intro para elegir  ·  Esc para cerrar"))
        self.hint.setObjectName("Small")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(16, 16, 16, 12)
        inner.setSpacing(10)
        inner.addWidget(self.input)
        inner.addWidget(self.list, 1)
        inner.addWidget(self.hint)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        self.resize(640, 460)

        self._timer = QTimer(self)                      # los movimientos se buscan al dejar de teclear
        self._timer.setSingleShot(True)
        self._timer.setInterval(160)
        self._timer.timeout.connect(self._refresh)
        self.input.textChanged.connect(self._on_text)
        self.input.installEventFilter(self)
        self.list.currentRowChanged.connect(self._mark_selected)
        self.list.itemActivated.connect(self._on_item)
        self.list.itemClicked.connect(self._on_item)
        self._refresh()

    # -- contenido --------------------------------------------------------
    def _on_text(self, _text: str) -> None:
        self._refresh(with_movements=False)
        if self._movements and len(self.input.text().strip()) >= MOVEMENT_MIN_CHARS:
            self._timer.start()

    def _refresh(self, with_movements: bool = True) -> None:
        query = self.input.text().strip()
        found = rank_commands(self._commands, query)[:MAX_SHOWN]
        if with_movements and self._movements and len(query) >= MOVEMENT_MIN_CHARS:
            found = (found + self._movements(query))[: MAX_SHOWN + 5]
        self._shown = found
        self.list.clear()
        for cmd in found:
            item = QListWidgetItem()
            label = QLabel(_row_html(cmd, selected=False))
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setObjectName("PaletteRow")
            label.setContentsMargins(12, 0, 12, 0)
            item.setSizeHint(QSize(label.sizeHint().width(), ROW_HEIGHT))
            self.list.addItem(item)
            self.list.setItemWidget(item, label)
        if found:
            self.list.setCurrentRow(0)
        elif query:
            empty = QListWidgetItem(tr("No encuentro nada con esas palabras."))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(empty)

    def _mark_selected(self, row: int) -> None:
        """La fila elegida lleva el texto sobre el amarillo; las demas, el texto normal (el estilo de Qt no sabe distinguirlas)."""
        for index in range(min(self.list.count(), len(self._shown))):
            label = self.list.itemWidget(self.list.item(index))
            if label is not None and bool(label.property("selected")) != (index == row):
                label.setProperty("selected", index == row)
                label.setText(_row_html(self._shown[index], selected=index == row))
                repolish(label)

    def _on_item(self, _item) -> None:
        self.run_selected()

    # -- teclado ----------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                step = 1 if key == Qt.Key.Key_Down else -1
                row = max(0, min(self.list.count() - 1, self.list.currentRow() + step))
                self.list.setCurrentRow(row)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.run_selected()
                return True
        return super().eventFilter(obj, event)

    def run_selected(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self._shown):
            command = self._shown[row]
            self.accept()
            QTimer.singleShot(0, command.run)           # tras cerrar el dialogo: la accion puede abrir otro

    def popup(self, anchor: QWidget) -> None:
        """Se muestra centrado arriba en la ventana, como un buscador."""
        top_left = anchor.mapToGlobal(QPoint((anchor.width() - self.width()) // 2, max(anchor.height() // 7, 24)))
        self.move(top_left)
        self.input.setFocus()
        self.exec()


def _row_html(cmd: Command, selected: bool) -> str:
    """Titulo en negrita y, al lado, el atajo o la pagina en gris (sobre el amarillo, en el color del texto del boton)."""
    pal = theme.current()
    side = pal.on_accent if selected else pal.muted
    return f"<b>{_escape(cmd.title)}</b>&nbsp;&nbsp;<span style='color:{side}; font-weight:normal'>{_escape(cmd.subtitle)}</span>"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
