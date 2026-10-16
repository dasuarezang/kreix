"""Inicio: movimientos por clasificar, con las reglas que Kreix propone (un comercio que se repite) a un clic."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.i18n import tr, trn
from core.suggestions import RuleSuggestion
from ui.format import fmt_eur
from ui.widgets.panels import Panel


class SuggestionRow(QWidget):
    """Un comercio que se repite: su nombre, cuantos movimientos son y el boton para crear la regla."""

    create_requested = Signal(str)          # la palabra de la regla

    def __init__(self, suggestion: RuleSuggestion) -> None:
        super().__init__()
        self.suggestion = suggestion
        name = QLabel(suggestion.keyword)
        name.setObjectName("H2")
        detail = QLabel(trn("{n} movimiento · {total}", "{n} movimientos · {total}", suggestion.count)
                        .format(n=suggestion.count, total=fmt_eur(suggestion.total)))
        detail.setObjectName("Muted")
        self.button = QPushButton(tr("Crear regla…"))
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setAccessibleName(tr("Crear una regla para {word}").format(word=suggestion.keyword))
        self.button.setToolTip(suggestion.example)
        self.button.clicked.connect(self._emit)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 3, 0, 3)
        row.setSpacing(14)
        row.addWidget(name)
        row.addWidget(detail, 1)
        row.addWidget(self.button)

    def _emit(self) -> None:
        self.create_requested.emit(self.suggestion.keyword)


class ReviewPanel(Panel):
    rule_requested = Signal(str)            # crear una regla con esta palabra
    review_requested = Signal()             # ver los movimientos sin categoria

    def __init__(self) -> None:
        self.review_button = QPushButton(tr("Ver los movimientos"))
        self.review_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.review_button.setToolTip(tr("Abre Cuentas con los movimientos que aún no tienen categoría"))
        self._rows = QVBoxLayout()
        self._rows.setSpacing(2)
        self._hint = QLabel(tr("Cuando un mismo comercio se repita sin categoría, te propondré una regla para clasificarlo de una vez."))
        self._hint.setObjectName("Muted")
        self._hint.setWordWrap(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.addLayout(self._rows)
        col.addWidget(self._hint)
        col.addStretch(1)
        super().__init__(tr("Por clasificar"), "", body, self.review_button)
        self.review_button.clicked.connect(self.review_requested)
        self.rows: list[SuggestionRow] = []

    def set_data(self, count: int, total: Decimal, suggestions: list[RuleSuggestion]) -> None:
        """Se oculta solo si no hay nada por clasificar."""
        while self._rows.count():
            item = self._rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.rows = []
        self.setVisible(count > 0)
        self.subtitle.setText(trn("{n} movimiento sin categoría · {total}", "{n} movimientos sin categoría · {total}", count)
                              .format(n=count, total=fmt_eur(total)))
        self._hint.setVisible(not suggestions)
        for suggestion in suggestions:
            row = SuggestionRow(suggestion)
            row.create_requested.connect(self.rule_requested)
            self._rows.addWidget(row)
            self.rows.append(row)
