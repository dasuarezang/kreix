"""Dialogos pequenos: regla de categoria y presupuestos mensuales."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from core.budget import BUDGETABLE
from core.enums import TxCategory
from ui.format import category_label

# Categorias entre las que se puede elegir al clasificar un movimiento (todas).
ALL_CATEGORIES = tuple(TxCategory)


def category_combo(selected: TxCategory | None = None, categories=ALL_CATEGORIES) -> QComboBox:
    combo = QComboBox()
    for cat in categories:
        combo.addItem(category_label(cat), cat)
    if selected is not None:
        combo.setCurrentIndex(max(combo.findData(selected), 0))
    return combo


def _buttons(dialog: QDialog, ok_text: str) -> QDialogButtonBox:
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    box.button(QDialogButtonBox.StandardButton.Ok).setText(ok_text)
    box.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Primary")
    box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
    box.accepted.connect(dialog.accept)
    box.rejected.connect(dialog.reject)
    return box


class RuleDialog(QDialog):
    """Nueva regla: los conceptos que contengan la palabra clave pasan a la categoria elegida."""

    def __init__(self, keyword: str = "", category: TxCategory | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nueva regla de categoría")
        self.setMinimumWidth(440)
        intro = QLabel("Todos los movimientos cuyo concepto contenga esta palabra irán a la categoría elegida, "
                       "también los que importes en el futuro. Los que hayas clasificado tú a mano no se tocan.")
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        self.keyword = QLineEdit(keyword)
        self.keyword.setPlaceholderText("p. ej. MERCADONA")
        self.keyword.setAccessibleName("Palabra clave")
        self.category = category_combo(category)
        self.category.setAccessibleName("Categoría")
        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("Si el concepto contiene", self.keyword)
        form.addRow("Va a la categoría", self.category)
        self._buttons = _buttons(self, "Guardar regla")
        col = QVBoxLayout(self)
        col.setContentsMargins(24, 22, 24, 20)
        col.setSpacing(14)
        col.addWidget(intro)
        col.addLayout(form)
        col.addWidget(self._buttons)
        self.keyword.textChanged.connect(self._validate)
        self._validate()

    def _validate(self) -> None:
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(len(self.keyword.text().strip()) >= 2)

    def result_rule(self) -> tuple[str, TxCategory]:
        return self.keyword.text().strip(), self.category.currentData()


class BudgetDialog(QDialog):
    """Un tope mensual por categoria. Un importe a cero significa que esa categoria no tiene presupuesto."""

    def __init__(self, budgets: dict[TxCategory, Decimal], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Presupuestos mensuales")
        self.setMinimumWidth(420)
        intro = QLabel("Cuánto quieres gastar como máximo al mes en cada categoría. Deja a 0 las que no quieras vigilar.")
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        form = QFormLayout()
        form.setSpacing(8)
        self.spins: dict[TxCategory, QDoubleSpinBox] = {}
        for cat in BUDGETABLE:
            spin = QDoubleSpinBox()
            spin.setRange(0, 1_000_000)
            spin.setDecimals(2)
            spin.setSingleStep(10)
            spin.setSuffix(" €")
            spin.setValue(float(budgets.get(cat, 0)))
            spin.setAlignment(Qt.AlignmentFlag.AlignRight)
            spin.setAccessibleName(f"Presupuesto de {category_label(cat)}")
            self.spins[cat] = spin
            form.addRow(category_label(cat), spin)
        col = QVBoxLayout(self)
        col.setContentsMargins(24, 22, 24, 20)
        col.setSpacing(14)
        col.addWidget(intro)
        col.addLayout(form)
        col.addWidget(_buttons(self, "Guardar"))

    def result_budgets(self) -> dict[TxCategory, Decimal]:
        return {cat: Decimal(str(round(spin.value(), 2))) for cat, spin in self.spins.items() if spin.value() > 0}
