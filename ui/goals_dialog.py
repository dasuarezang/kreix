"""Gestion de las metas de ahorro: crear, editar, apuntar lo ahorrado y borrar."""
from __future__ import annotations

from datetime import date
from functools import partial
from decimal import Decimal

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDateEdit, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from core.goals import Goal
from core.i18n import tr
from services.goals_service import MAX_NAME, GoalError, GoalsService
from ui.dialogs import _buttons
from ui.widgets.brand_dialog import BrandDialog
from ui.format import fmt_eur


def _money(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


class GoalEditDialog(BrandDialog):
    """Nombre, importe objetivo, lo ahorrado hasta ahora y una fecha opcional."""

    def __init__(self, goal: Goal | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Editar meta") if goal else tr("Nueva meta"))
        self.setMinimumWidth(520)
        self.name = QLineEdit(goal.name if goal else "")
        self.name.setMaxLength(MAX_NAME)
        self.name.setPlaceholderText(tr("Por ejemplo: Vacaciones"))
        self.name.setAccessibleName(tr("Nombre de la meta"))
        self.target = QDoubleSpinBox()
        self.target.setRange(0, 100_000_000)
        self.target.setDecimals(2)
        self.target.setSingleStep(50)
        self.target.setSuffix(" €")
        self.target.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.target.setValue(float(goal.target) if goal else 0)
        self.target.setAccessibleName(tr("Importe objetivo"))
        self.saved = QDoubleSpinBox()
        self.saved.setRange(0, 100_000_000)
        self.saved.setDecimals(2)
        self.saved.setSingleStep(50)
        self.saved.setSuffix(" €")
        self.saved.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.saved.setValue(float(goal.saved) if goal else 0)
        self.saved.setAccessibleName(tr("Ahorrado hasta ahora"))
        self.has_deadline = QCheckBox(tr("Quiero ponerle una fecha"))
        self.has_deadline.setChecked(bool(goal and goal.deadline))
        self.deadline = QDateEdit()
        self.deadline.setCalendarPopup(True)
        self.deadline.setDisplayFormat("dd/MM/yyyy")
        start = goal.deadline if goal and goal.deadline else date.today().replace(year=date.today().year + 1)
        self.deadline.setDate(QDate(start.year, start.month, start.day))
        self.deadline.setEnabled(self.has_deadline.isChecked())
        self.has_deadline.toggled.connect(self.deadline.setEnabled)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)    # los campos ocupan todo el ancho
        form.setSpacing(10)
        form.addRow(tr("Nombre"), self.name)
        form.addRow(tr("Quiero llegar a"), self.target)
        form.addRow(tr("Llevo ahorrado"), self.saved)
        form.addRow(self.has_deadline, self.deadline)
        self.error = QLabel("")
        self.error.setObjectName("LockError")
        self.error.hide()
        col = self.frame(tr("Editar meta") if goal else tr("Nueva meta"),
                         tr("Un objetivo con nombre, el importe al que quieres llegar y, si quieres, una fecha."))
        col.addLayout(form)
        col.addWidget(self.error)
        buttons = _buttons(self, tr("Guardar"))
        buttons.accepted.disconnect()
        buttons.accepted.connect(self._validate)
        col.addWidget(buttons)

    def _validate(self) -> None:
        if not self.name.text().strip():
            self.error.setText(tr("Ponle un nombre a la meta."))
        elif self.target.value() <= 0:
            self.error.setText(tr("El importe objetivo debe ser mayor que cero."))
        else:
            self.accept()
            return
        self.error.show()

    def values(self) -> tuple[str, Decimal, Decimal, date | None]:
        d = self.deadline.date()
        return (self.name.text(), _money(self.target.value()), _money(self.saved.value()),
                date(d.year(), d.month(), d.day()) if self.has_deadline.isChecked() else None)


class GoalsDialog(BrandDialog):
    changed = Signal()

    def __init__(self, service: GoalsService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self.did_change = False
        self.setWindowTitle(tr("Metas de ahorro"))
        self.setMinimumWidth(780)                    # que quepan los nombres, los importes y los tres botones de cada meta
        self._rows = QVBoxLayout()
        self._rows.setSpacing(10)
        self.add_button = QPushButton(tr("Nueva meta…"))
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.clicked.connect(self.prompt_add)
        self.done_button = QPushButton(tr("Hecho"))            # cierra el cuadro: lo apuntado ya esta guardado
        self.done_button.setObjectName("Primary")
        self.done_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.done_button.setDefault(True)
        self.done_button.setMinimumWidth(110)
        self.add_button.setMinimumWidth(self.add_button.sizeHint().width())
        self.done_button.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addWidget(self.add_button)
        bottom.addStretch(1)
        bottom.addWidget(self.done_button)
        col = self.frame(tr("Metas de ahorro"),
                         tr("Apunta lo que vas guardando para cada meta. Kreix no mueve dinero: solo lleva la cuenta."))
        col.addLayout(self._rows)
        col.addLayout(bottom)
        self.reload()

    # ------------------------------------------------------------------ lista
    def reload(self) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        goals = self._service.goals()
        if not goals:
            empty = QLabel(tr("Aún no tienes metas. Crea la primera."))
            empty.setObjectName("Muted")
            self._rows.addWidget(empty)
        for goal in goals:
            self._rows.addWidget(self._row(goal))

    def _row(self, goal: Goal) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 2, 0, 2)
        name = QLabel(goal.name)
        name.setObjectName("H2")
        amounts = QLabel(tr("{spent} de {budget}").format(spent=fmt_eur(goal.saved), budget=fmt_eur(goal.target)))
        amounts.setObjectName("Muted")
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(name)
        text.addWidget(amounts)
        name.setMinimumWidth(220)
        lay.addLayout(text, 1)
        lay.setSpacing(10)
        for label, slot in ((tr("Apuntar ahorro"), self._contribute), (tr("Editar"), self._edit), (tr("Eliminar"), self._delete)):
            button = QPushButton(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAccessibleName(f"{label}: {goal.name}")
            button.clicked.connect(partial(slot, goal))
            button.setMinimumWidth(button.sizeHint().width())      # nunca mas estrecho que su texto
            lay.addWidget(button)
        return row

    # ------------------------------------------------------------------ acciones (cada una se puede llamar sin dialogo)
    def _done(self) -> None:
        self.did_change = True
        self.changed.emit()
        self.reload()

    def add_goal(self, name: str, target: Decimal, saved: Decimal = Decimal(0), deadline: date | None = None) -> bool:
        try:
            self._service.save(name, target, saved, deadline)
        except GoalError:
            return False
        self._done()
        return True

    def contribute(self, goal_id: int, amount: Decimal) -> None:
        self._service.contribute(goal_id, amount)
        self._done()

    def delete_goal(self, goal_id: int) -> None:
        self._service.delete(goal_id)
        self._done()

    def prompt_add(self) -> None:
        dialog = GoalEditDialog(None, self)
        if dialog.exec():
            self.add_goal(*dialog.values())

    def _edit(self, goal: Goal) -> None:
        dialog = GoalEditDialog(goal, self)
        if dialog.exec():
            name, target, saved, deadline = dialog.values()
            try:
                self._service.save(name, target, saved, deadline, goal.id)
            except GoalError:
                return
            self._done()

    def _contribute(self, goal: Goal) -> None:
        amount, ok = QInputDialog.getDouble(
            self, tr("Apuntar ahorro"),
            tr("Importe que has guardado para «{name}» (usa un número negativo para restar):").format(name=goal.name),
            0.0, -100_000_000, 100_000_000, 2)
        if ok and amount != 0:
            self.contribute(goal.id, _money(amount))

    def _delete(self, goal: Goal) -> None:
        answer = QMessageBox.question(
            self, tr("Eliminar meta"), tr("¿Eliminar la meta «{name}»?").format(name=goal.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_goal(goal.id)
