"""Dialogos pequenos: regla de categoria y presupuestos mensuales."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from core.budget import BUDGETABLE
from core.enums import TxCategory
from ui.format import category_label
from ui.widgets.interests import InterestPicker
from ui.widgets.language_picker import LanguagePicker
from core.greeting import MAX_NAME, clean_name
from core import i18n
from core.i18n import tr

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
    box.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancelar"))
    box.accepted.connect(dialog.accept)
    box.rejected.connect(dialog.reject)
    return box


class RuleDialog(QDialog):
    """Nueva regla: los conceptos que contengan la palabra clave pasan a la categoria elegida."""

    def __init__(self, keyword: str = "", category: TxCategory | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Nueva regla de categoría"))
        self.setMinimumWidth(440)
        intro = QLabel(tr("Todos los movimientos cuyo concepto contenga esta palabra irán a la categoría elegida, "
                       "también los que importes en el futuro. Los que hayas clasificado tú a mano no se tocan."))
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        self.keyword = QLineEdit(keyword)
        self.keyword.setPlaceholderText(tr("p. ej. MERCADONA"))
        self.keyword.setAccessibleName(tr("Palabra clave"))
        self.category = category_combo(category)
        self.category.setAccessibleName(tr("Categoría"))
        form = QFormLayout()
        form.setSpacing(10)
        form.addRow(tr("Si el concepto contiene"), self.keyword)
        form.addRow(tr("Va a la categoría"), self.category)
        self._buttons = _buttons(self, tr("Guardar regla"))
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


class WelcomeDialog(QDialog):
    """Primera vez: idioma, como llamar al usuario y que quiere gestionar (cuentas, inversiones o ambas).
    El idioma se cambia al instante dentro del propio cuadro. Se puede omitir ("Ahora no") y cambiar todo en Ajustes."""

    def __init__(self, name: str = "", interests: tuple[bool, bool] = (True, True), parent: QWidget | None = None,
                 language: str | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(660)               # que las descripciones de los interruptores quepan en una linea
        start = i18n.normalize_language(language or system_language())
        i18n.set_language(start)                      # el cuadro ya sale en el idioma del sistema (o el elegido)
        self._title = QLabel()
        self._title.setObjectName("H1")
        self._title.setWordWrap(True)
        self._intro = QLabel()
        self._intro.setObjectName("Muted")
        self._intro.setWordWrap(True)
        self._ask_language = QLabel()
        self._ask_language.setObjectName("H2")
        self.languages = LanguagePicker(start)
        self._ask_name = QLabel()
        self._ask_name.setObjectName("H2")
        self.name = QLineEdit(name)
        self.name.setMaxLength(MAX_NAME)
        self._ask_interest = QLabel()
        self._ask_interest.setObjectName("H2")
        self.interests = InterestPicker(*interests)
        self._buttons = _buttons(self, "")
        col = QVBoxLayout(self)
        col.setContentsMargins(28, 26, 28, 22)
        col.setSpacing(10)
        col.addWidget(self._title)
        col.addWidget(self._intro)
        col.addSpacing(6)
        col.addWidget(self._ask_language)
        col.addWidget(self.languages)
        col.addSpacing(8)
        col.addWidget(self._ask_name)
        col.addWidget(self.name)
        col.addSpacing(8)
        col.addWidget(self._ask_interest)
        col.addWidget(self.interests)
        col.addSpacing(6)
        col.addWidget(self._buttons)
        self.languages.changed.connect(self._on_language)
        self._retranslate()

    def _on_language(self, code: str) -> None:
        i18n.set_language(code)
        self._retranslate()

    def _retranslate(self) -> None:
        """Vuelve a poner todos los textos en el idioma activo (se llama al elegir otro idioma)."""
        self.setWindowTitle(tr("Bienvenido a Kreix"))
        self._title.setText(tr("Bienvenido a Kreix"))
        self._intro.setText(tr("Tres preguntas rápidas para dejarlo a tu medida. Todo se queda en tu ordenador, viaja con tus datos "
                               "cuando los exportas y puedes cambiarlo cuando quieras en Ajustes."))
        self._ask_language.setText(tr("¿En qué idioma quieres Kreix?"))
        self._ask_name.setText(tr("¿Cómo te llamas?"))
        self.name.setPlaceholderText(tr("Tu nombre (Kreix te saludará con él)"))
        self.name.setAccessibleName(tr("Tu nombre"))
        self._ask_interest.setText(tr("¿Qué quieres gestionar?"))
        self.interests.retranslate()
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Empezar"))
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Ahora no"))
        self.layout().activate()
        self.adjustSize()                       # con otro idioma los textos miden otra cosa: el cuadro se reajusta

    def result_name(self) -> str:
        return clean_name(self.name.text())

    def result_interests(self) -> tuple[bool, bool]:
        return self.interests.values()

    def result_language(self) -> str:
        return self.languages.language()


def system_language() -> str:
    """El idioma del sistema si Kreix lo tiene (castellano, catalan o ingles); si no, castellano."""
    return i18n.normalize_language(QLocale.system().name()[:2].lower())


class BudgetDialog(QDialog):
    """Un tope mensual por categoria. Un importe a cero significa que esa categoria no tiene presupuesto."""

    def __init__(self, budgets: dict[TxCategory, Decimal], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Presupuestos mensuales"))
        self.setMinimumWidth(420)
        intro = QLabel(tr("Cuánto quieres gastar como máximo al mes en cada categoría. Deja a 0 las que no quieras vigilar."))
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
            spin.setAccessibleName(tr("Presupuesto de {cat}").format(cat=category_label(cat)))
            self.spins[cat] = spin
            form.addRow(category_label(cat), spin)
        col = QVBoxLayout(self)
        col.setContentsMargins(24, 22, 24, 20)
        col.setSpacing(14)
        col.addWidget(intro)
        col.addLayout(form)
        col.addWidget(_buttons(self, tr("Guardar")))

    def result_budgets(self) -> dict[TxCategory, Decimal]:
        return {cat: Decimal(str(round(spin.value(), 2))) for cat, spin in self.spins.items() if spin.value() > 0}
