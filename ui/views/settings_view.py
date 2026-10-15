"""Pantalla de ajustes."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from data.repositories import RuleError
from services.category_service import CategoryService
from services.settings_service import AppSettings
from ui.dialogs import RuleDialog
from ui.format import category_label
from ui.widgets.cards import PageHeader
from ui.widgets.switch import SwitchToggle

VERSION = "0.1.0"


class SettingRow(QWidget):
    def __init__(self, title: str, description: str, checked: bool) -> None:
        super().__init__()
        self.switch = SwitchToggle(checked)
        self.switch.setAccessibleName(title)
        name = QLabel(title)
        name.setObjectName("H2")
        desc = QLabel(description)
        desc.setObjectName("Small")
        desc.setWordWrap(True)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(name)
        col.addWidget(desc)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 6, 0, 6)
        row.setSpacing(18)
        row.addLayout(col, 1)
        row.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)


class RulesList(QWidget):
    """Reglas de categoria del usuario: palabra clave -> categoria, con alta y baja."""

    rules_changed = Signal()

    def __init__(self, service: CategoryService) -> None:
        super().__init__()
        self._service = service
        self._rows = QVBoxLayout()
        self._rows.setSpacing(2)
        self._empty = QLabel("Aún no tienes reglas propias. Crea una desde aquí o con clic derecho sobre un movimiento.")
        self._empty.setObjectName("Small")
        self._empty.setWordWrap(True)
        self.add_button = QPushButton("Añadir regla…")
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.clicked.connect(self.prompt_add)
        add_row = QHBoxLayout()
        add_row.addWidget(self.add_button)
        add_row.addStretch(1)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        col.addWidget(self._empty)
        col.addLayout(self._rows)
        col.addSpacing(4)
        col.addLayout(add_row)
        self.reload()

    def reload(self) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rules = self._service.rules()
        self._empty.setVisible(not rules)
        for rule in rules:
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 2, 0, 2)
            word = QLabel(rule.keyword)
            word.setObjectName("H2")
            arrow = QLabel(f"→  {category_label(rule.category)}")
            arrow.setObjectName("Muted")
            remove = QPushButton("Eliminar")
            remove.setCursor(Qt.CursorShape.PointingHandCursor)
            remove.setAccessibleName(f"Eliminar la regla {rule.keyword}")
            remove.clicked.connect(lambda _=False, rid=rule.id: self.remove(rid))
            lay.addWidget(word)
            lay.addWidget(arrow, 1)
            lay.addWidget(remove)
            self._rows.addWidget(row)

    def remove(self, rule_id: int) -> None:
        self._service.delete_rule(rule_id)
        self.reload()
        self.rules_changed.emit()

    def add(self, keyword: str, category) -> bool:
        try:
            self._service.add_rule(keyword, category)
        except RuleError as exc:
            QMessageBox.warning(self, "No se pudo guardar la regla", str(exc))
            return False
        self.reload()
        self.rules_changed.emit()
        return True

    def prompt_add(self) -> None:
        dialog = RuleDialog(parent=self)
        if dialog.exec() == RuleDialog.DialogCode.Accepted:
            self.add(*dialog.result_rule())


class SettingsView(QWidget):
    settings_changed = Signal(object)
    reset_requested = Signal()
    rules_changed = Signal()

    def __init__(self, settings: AppSettings, db_path: str, categories: CategoryService | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._settings = settings

        header = PageHeader("Ajustes", eyebrow="Preferencias")

        self.p2p = SettingRow(
            "Contar Bizum como ingresos y gastos",
            "Si lo desactivas, los Bizum no entran en el cálculo de la tasa de ahorro.",
            settings.include_p2p,
        )
        self.transfers = SettingRow(
            "Contar traspasos entrantes como ingresos",
            "Útil si tu dinero llega por traspasos desde otra cuenta. Los traspasos salientes nunca cuentan.",
            settings.transfers_in_as_income,
        )
        self.p2p.switch.toggled.connect(lambda v: self._update(include_p2p=v))
        self.transfers.switch.toggled.connect(lambda v: self._update(transfers_in_as_income=v))

        calc = self._card("Cálculo del ahorro", self.p2p, self.transfers)

        self.rules = RulesList(categories) if categories is not None else None
        if self.rules is not None:
            self.rules.rules_changed.connect(self.rules_changed)
            rules_intro = QLabel("Las reglas mandan sobre las que trae Kreix: si el concepto de un movimiento contiene "
                                 "la palabra clave, va a la categoría que elijas. Los movimientos que clasifiques a mano nunca cambian.")
            rules_intro.setObjectName("Small")
            rules_intro.setWordWrap(True)
            rules_card = self._card("Reglas de categorías", rules_intro, self.rules)

        path = QLabel(db_path)
        path.setObjectName("Muted")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path.setWordWrap(True)
        privacy = QLabel("Todo se guarda solo en este equipo. Kreix no envía datos a ningún servidor.")
        privacy.setObjectName("Small")
        privacy.setWordWrap(True)
        self.reset_button = QPushButton("Borrar todos los datos")
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setToolTip("Elimina movimientos, operaciones y cartera. Los ajustes se conservan.")
        self.reset_button.clicked.connect(self.reset_requested)
        reset_row = QHBoxLayout()
        reset_row.addWidget(self.reset_button)
        reset_row.addStretch(1)
        reset_box = QWidget()
        reset_box.setLayout(reset_row)
        reset_row.setContentsMargins(0, 6, 0, 0)
        data = self._card("Tus datos", path, privacy, reset_box)

        about = self._card("Acerca de", QLabel(f"Kreix {VERSION}"))

        body = QWidget()
        body.setObjectName("Page")
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 28)
        col.setSpacing(16)
        col.addWidget(calc)
        if self.rules is not None:
            col.addWidget(rules_card)
        col.addWidget(data)
        col.addWidget(about)
        col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 0)
        outer.setSpacing(16)
        outer.addWidget(header)
        outer.addWidget(scroll, 1)

    @staticmethod
    def _card(title: str, *widgets: QWidget) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(8)
        heading = QLabel(title.upper())
        heading.setObjectName("CardTitle")
        lay.addWidget(heading)
        for w in widgets:
            lay.addWidget(w)
        return card

    def _update(self, **changes: bool) -> None:
        self._settings = replace(self._settings, **changes)
        self.settings_changed.emit(self._settings)

    def set_settings(self, settings: AppSettings) -> None:
        """Refleja unos ajustes cargados desde fuera (p. ej. tras restaurar datos) sin emitir cambios."""
        self._settings = settings
        for row, value in ((self.p2p, settings.include_p2p), (self.transfers, settings.transfers_in_as_income)):
            row.switch.blockSignals(True)
            row.switch.setChecked(value)
            row.switch.blockSignals(False)
            row.switch.update()

    def reload_rules(self) -> None:
        if self.rules is not None:
            self.rules.reload()

    def set_theme(self, theme_name: str) -> None:
        self._settings = replace(self._settings, theme=theme_name)
