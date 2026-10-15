"""Pantalla de ajustes."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from data.repositories import RuleError
from services.category_service import CategoryService
from services.settings_service import AppSettings
from ui.dialogs import RuleDialog
from ui.feedback import Feedback, snapshot_of, tell
from ui.format import category_label
from core.greeting import MAX_NAME, clean_name
from ui.widgets.cards import PageHeader
from ui.widgets.interests import InterestPicker
from ui.widgets.language_picker import LanguagePicker
from ui.widgets.section_card import GroupHeading, SectionCard
from ui.widgets.setting_row import SettingRow

from ui.whats_new import VERSION  # noqa: E402  (la version vive en un solo sitio)
from core.i18n import tr, trn


class RulesList(QWidget):
    """Reglas de categoria del usuario: palabra clave -> categoria, con alta y baja."""

    rules_changed = Signal()
    feedback: Feedback | None = None

    def __init__(self, service: CategoryService) -> None:
        super().__init__()
        self._service = service
        self._rows = QVBoxLayout()
        self._rows.setSpacing(2)
        self._empty = QLabel(tr("Aún no tienes reglas propias. Crea una desde aquí o con clic derecho sobre un movimiento."))
        self._empty.setObjectName("Small")
        self._empty.setWordWrap(True)
        self.add_button = QPushButton(tr("Añadir regla…"))
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
            remove = QPushButton(tr("Eliminar"))
            remove.setCursor(Qt.CursorShape.PointingHandCursor)
            remove.setAccessibleName(tr("Eliminar la regla {keyword}").format(keyword=rule.keyword))
            remove.clicked.connect(lambda _=False, rid=rule.id: self.remove(rid))
            lay.addWidget(word)
            lay.addWidget(arrow, 1)
            lay.addWidget(remove)
            self._rows.addWidget(row)

    def remove(self, rule_id: int) -> None:
        snapshot = snapshot_of(self.feedback)
        changed = self._service.delete_rule(rule_id)
        self.reload()
        self.rules_changed.emit()
        tell(self.feedback, trn("Regla eliminada: {changed} movimiento vuelve a su categoría automática.",
                                "Regla eliminada: {changed} movimientos vuelven a su categoría automática.",
                                changed).format(changed=changed), snapshot)

    def add(self, keyword: str, category) -> bool:
        snapshot = snapshot_of(self.feedback)
        try:
            changed = self._service.add_rule(keyword, category)
        except RuleError as exc:
            QMessageBox.warning(self, tr("No se pudo guardar la regla"), str(exc))
            return False
        self.reload()
        self.rules_changed.emit()
        tell(self.feedback, trn("Regla creada: {changed} movimiento cambiado a «{category}».",
                                "Regla creada: {changed} movimientos cambiados a «{category}».",
                                changed).format(changed=changed, category=category_label(category)), snapshot)
        return True

    def prompt_add(self) -> None:
        dialog = RuleDialog(parent=self)
        if dialog.exec() == RuleDialog.DialogCode.Accepted:
            self.add(*dialog.result_rule())


class SettingsView(QWidget):
    settings_changed = Signal(object)
    reset_requested = Signal()
    rules_changed = Signal()
    whats_new_requested = Signal()
    name_changed = Signal(str)          # el usuario ha guardado su nombre (vacio = quitarlo)
    interests_changed = Signal(bool, bool)   # (cuentas, inversiones)
    language_changed = Signal(str)           # "es" | "ca" | "en"

    def __init__(self, settings: AppSettings, db_path: str, categories: CategoryService | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._settings = settings

        header = PageHeader(tr("Ajustes"), eyebrow=tr("Preferencias"))

        self.p2p = SettingRow(
            tr("Contar Bizum como ingresos y gastos"),
            tr("Si lo desactivas, los Bizum no entran en el cálculo de la tasa de ahorro."),
            settings.include_p2p,
        )
        self.transfers = SettingRow(
            tr("Contar traspasos entrantes como ingresos"),
            tr("Útil si tu dinero llega por traspasos desde otra cuenta. Los traspasos salientes nunca cuentan."),
            settings.transfers_in_as_income,
        )
        self.ambient = SettingRow(
            tr("Cielo animado y luz según la hora"),
            tr("Anima el sol y la luna de Inicio y baja muy ligeramente el brillo por la tarde y por la noche. No cambia el tema."),
            settings.ambient,
        )
        self.ambient.switch.toggled.connect(lambda v: self._update(ambient=v))
        self.p2p.switch.toggled.connect(lambda v: self._update(include_p2p=v))
        self.transfers.switch.toggled.connect(lambda v: self._update(transfers_in_as_income=v))

        calc = self._card(tr("Cálculo del ahorro"), self.p2p, self.transfers)
        look = self._card(tr("Ambiente"), self.ambient)

        name_hint = tr("Kreix te saluda por tu nombre en Inicio. Se guarda con tus datos y viaja con ellos al exportar "
                       "e importar.")
        self.name_edit = QLineEdit(settings.user_name)
        self.name_edit.setMaxLength(MAX_NAME)
        self.name_edit.setPlaceholderText(tr("Tu nombre"))
        self.name_edit.setAccessibleName(tr("Tu nombre"))
        self.name_edit.setClearButtonEnabled(True)
        self.name_save = QPushButton(tr("Guardar"))
        self.name_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.name_save.setEnabled(False)
        self.name_edit.textChanged.connect(self._on_name_typed)
        self.name_edit.returnPressed.connect(self.save_name)
        self.name_save.clicked.connect(self.save_name)
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        name_row.addWidget(self.name_edit, 1)
        name_row.addWidget(self.name_save)
        name_box = QWidget()
        name_box.setLayout(name_row)
        name_row.setContentsMargins(0, 4, 0, 0)
        profile = self._card(tr("Tu nombre"), name_box, description=name_hint)

        interest_hint = tr("Elige qué quieres gestionar. Lo que desactives no desaparece: sus pestañas siguen ahí y "
                           "puedes activarlo cuando quieras, aquí o desde la propia pestaña.")
        self.interests = InterestPicker(settings.interest_accounts, settings.interest_investments)
        self.interests.changed.connect(self.interests_changed)
        interests_card = self._card(tr("Lo que te interesa"), self.interests, description=interest_hint)

        language_hint = tr("Cambia el idioma de toda la aplicación al instante. Se guarda con tus datos.")
        self.language = LanguagePicker(settings.language)
        self.language.changed.connect(self.language_changed)
        language_card = self._card(tr("Idioma"), self.language, description=language_hint)

        self.rules = RulesList(categories) if categories is not None else None
        if self.rules is not None:
            self.rules.rules_changed.connect(self.rules_changed)
            rules_intro = tr("Las reglas mandan sobre las que trae Kreix: si el concepto de un movimiento contiene "
                             "la palabra clave, va a la categoría que elijas. Los movimientos que clasifiques a mano nunca cambian.")
            rules_card = self._card(tr("Reglas de categorías"), self.rules, description=rules_intro)

        path = QLabel(db_path)
        path.setObjectName("Muted")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path.setWordWrap(True)
        privacy = QLabel(tr("Todo se guarda solo en este equipo. Kreix no envía datos a ningún servidor."))
        privacy.setObjectName("Small")
        privacy.setWordWrap(True)
        self.reset_button = QPushButton(tr("Borrar todos los datos"))
        self.reset_button.setObjectName("Danger")
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setToolTip(tr("Elimina movimientos, operaciones y cartera. Los ajustes se conservan."))
        self.reset_button.clicked.connect(self.reset_requested)
        reset_row = QHBoxLayout()
        reset_row.addWidget(self.reset_button)
        reset_row.addStretch(1)
        reset_box = QWidget()
        reset_box.setLayout(reset_row)
        reset_row.setContentsMargins(0, 6, 0, 0)
        data = self._card(tr("Tus datos"), path, privacy, reset_box, rows=True)

        self.whats_new_button = QPushButton(tr("Ver las novedades"))
        self.whats_new_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.whats_new_button.clicked.connect(self.whats_new_requested)
        whats_row = QHBoxLayout()
        whats_row.addWidget(self.whats_new_button)
        whats_row.addStretch(1)
        whats_box = QWidget()
        whats_box.setLayout(whats_row)
        whats_row.setContentsMargins(0, 4, 0, 0)
        about = self._card(tr("Acerca de"), QLabel(tr("Kreix {VERSION}").format(VERSION=VERSION)), whats_box)

        body = QWidget()
        body.setObjectName("Page")
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 44)
        col.setSpacing(26)
        col.addWidget(GroupHeading(tr("Tú")))
        col.addWidget(profile)
        col.addWidget(language_card)
        col.addWidget(interests_card)
        col.addWidget(GroupHeading(tr("Aspecto y cálculos")))
        col.addWidget(look)
        col.addWidget(calc)
        if self.rules is not None:
            col.addWidget(rules_card)
        col.addWidget(GroupHeading(tr("Datos y aplicación")))
        col.addWidget(data)
        col.addWidget(about)
        col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 40, 48, 0)
        outer.setSpacing(24)
        outer.addWidget(header)
        outer.addWidget(scroll, 1)

    @staticmethod
    def _card(title: str, *widgets: QWidget, description: str = "", rows: bool = False) -> SectionCard:
        """Tarjeta tematica: cabecera con titulo y explicacion; los ajustes con interruptor (o `rows`) van separados por lineas."""
        card = SectionCard(title, description)
        for w in widgets:
            (card.add_row if rows or isinstance(w, SettingRow) else card.add)(w)
        return card

    def _update(self, **changes: bool) -> None:
        self._settings = replace(self._settings, **changes)
        self.settings_changed.emit(self._settings)

    def _on_name_typed(self, text: str) -> None:
        self.name_save.setEnabled(clean_name(text) != self._settings.user_name)

    def save_name(self) -> None:
        name = clean_name(self.name_edit.text())
        if name == self._settings.user_name and self._settings.name_asked:
            return
        self._settings = replace(self._settings, user_name=name, name_asked=True)
        self.name_edit.setText(name)
        self.name_save.setEnabled(False)
        self.name_changed.emit(name)

    def focus_interests(self) -> None:
        self.interests.accounts.switch.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def focus_name(self) -> None:
        self.name_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.name_edit.selectAll()

    def set_settings(self, settings: AppSettings) -> None:
        """Refleja unos ajustes cargados desde fuera (p. ej. tras restaurar datos) sin emitir cambios."""
        self._settings = settings
        self.name_edit.blockSignals(True)
        self.name_edit.setText(settings.user_name)
        self.name_edit.blockSignals(False)
        self.name_save.setEnabled(False)
        self.interests.set_values(settings.interest_accounts, settings.interest_investments)
        self.language.set_language(settings.language)
        for row, value in ((self.p2p, settings.include_p2p), (self.transfers, settings.transfers_in_as_income),
                           (self.ambient, settings.ambient)):
            row.switch.blockSignals(True)
            row.switch.setChecked(value)
            row.switch.blockSignals(False)
            row.switch.update()

    @property
    def feedback(self) -> Feedback | None:
        return self.rules.feedback if self.rules is not None else None

    @feedback.setter
    def feedback(self, value: Feedback | None) -> None:
        if self.rules is not None:
            self.rules.feedback = value

    def reload_rules(self) -> None:
        if self.rules is not None:
            self.rules.reload()

    def set_theme(self, theme_name: str) -> None:
        self._settings = replace(self._settings, theme=theme_name)
