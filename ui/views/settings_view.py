"""Pantalla de ajustes."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from data.repositories import RuleError
from services.category_service import CategoryService
from services.settings_service import BACKUP_KEEP, LOCK_MINUTES, TEXT_SCALES, AppSettings
from ui.dialogs import RuleDialog
from ui.feedback import Feedback, snapshot_of, tell
from ui.format import category_label
from ui.popups import Combo
from core.greeting import MAX_NAME, clean_name
from ui.widgets.backup_list import BackupList
from ui.widgets.cards import PageHeader
from ui.widgets.interests import InterestPicker
from ui.widgets.language_picker import LanguagePicker
from ui.widgets.section_card import GroupCard, GroupHeading, SectionCard
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
    text_scale_changed = Signal(int)         # 100 | 110 | 125
    change_password_requested = Signal()
    lock_requested = Signal()
    backup_now_requested = Signal()
    backup_check_requested = Signal()
    restore_backup_requested = Signal(str)     # ruta de la copia que se quiere restaurar

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
        name_row.setContentsMargins(0, 0, 0, 0)

        interest_hint = tr("Elige qué quieres gestionar. Lo que desactives no desaparece: sus pestañas siguen ahí y "
                           "puedes activarlo cuando quieras, aquí o desde la propia pestaña.")
        self.interests = InterestPicker(settings.interest_accounts, settings.interest_investments)
        self.interests.changed.connect(self.interests_changed)

        language_hint = tr("Cambia el idioma de toda la aplicación al instante. Se guarda con tus datos.")
        self.language = LanguagePicker(settings.language)
        self.language.changed.connect(self.language_changed)

        text_hint = tr("Hace más grande la letra de toda la aplicación (menús, tablas y gráficos). Se aplica al momento.")
        self.text_size = Combo()
        self.text_size.setAccessibleName(tr("Tamaño del texto"))
        self.text_size.setFixedWidth(300)
        for percent, label in zip(TEXT_SCALES, (tr("Normal"), tr("Grande"), tr("Muy grande"))):
            self.text_size.addItem(f"{label} ({percent} %)", percent)
        self._select_text_size(settings.text_scale)
        self.text_size.activated.connect(self._on_text_size)

        you = GroupCard()                                    # un grupo = una tarjeta; cada ajuste, una fila
        you.add_field(tr("Tu nombre"), name_hint, name_box)
        you.add_field(tr("Idioma"), language_hint, self.language)
        you.add_field(tr("Lo que te interesa"), interest_hint, self.interests)

        self.rules = RulesList(categories) if categories is not None else None
        look = GroupCard()
        look.add_field(tr("Tamaño del texto"), text_hint, self.text_size)
        look.add_setting(self.ambient)
        look.add_setting(self.p2p)
        look.add_setting(self.transfers)
        if self.rules is not None:
            self.rules.rules_changed.connect(self.rules_changed)
            rules_intro = tr("Las reglas mandan sobre las que trae Kreix: si el concepto de un movimiento contiene "
                             "la palabra clave, va a la categoría que elijas. Los movimientos que clasifiques a mano nunca cambian.")
            look.add_field(tr("Reglas de categorías"), rules_intro, self.rules)

        path = QLabel(db_path)
        path.setObjectName("Muted")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path.setWordWrap(True)
        self.reset_button = QPushButton(tr("Borrar todos los datos"))
        self.reset_button.setObjectName("Danger")
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setToolTip(tr("Elimina movimientos, operaciones y cartera. Los ajustes se conservan."))
        self.reset_button.clicked.connect(self.reset_requested)
        data_box = QWidget()
        data_col = QVBoxLayout(data_box)
        data_col.setContentsMargins(0, 0, 0, 0)
        data_col.setSpacing(12)
        data_col.addWidget(path)
        reset_row = QHBoxLayout()
        reset_row.addWidget(self.reset_button)
        reset_row.addStretch(1)
        data_col.addLayout(reset_row)

        self.password_button = QPushButton(tr("Cambiar contraseña maestra…"))
        self.password_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.password_button.clicked.connect(self.change_password_requested)
        self.lock_now_button = QPushButton(tr("Bloquear ahora"))
        self.lock_now_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lock_now_button.setToolTip(tr("Atajo: Ctrl+L"))
        self.lock_now_button.clicked.connect(self.lock_requested)
        password_box = QWidget()
        password_row = QHBoxLayout(password_box)
        password_row.setContentsMargins(0, 0, 0, 0)
        password_row.setSpacing(10)
        password_row.addWidget(self.password_button)
        password_row.addWidget(self.lock_now_button)
        password_row.addStretch(1)

        self.lock_after = Combo()
        self.lock_after.setAccessibleName(tr("Bloqueo automático"))
        self.lock_after.setFixedWidth(240)
        for minutes in LOCK_MINUTES:
            self.lock_after.addItem(self.lock_minutes_label(minutes), minutes)
        self._select_lock_minutes(settings.auto_lock_minutes)
        self.lock_after.activated.connect(self._on_lock_after)
        self.lock_minimize = SettingRow(
            tr("Bloquear al minimizar"),
            tr("Al minimizar la ventana, Kreix vuelve a pedir la contraseña maestra antes de mostrar tus datos."),
            settings.lock_on_minimize,
        )
        self.lock_minimize.switch.toggled.connect(lambda v: self._update(lock_on_minimize=v))
        self.lock_session = SettingRow(
            tr("Bloquear al bloquear o suspender Windows"),
            tr("Si bloqueas Windows (Win+L) o el equipo se suspende, Kreix también se bloquea y pide la contraseña al volver."),
            settings.lock_on_session,
        )
        self.lock_session.switch.toggled.connect(lambda v: self._update(lock_on_session=v))

        self.backup_enabled = SettingRow(
            tr("Copias de seguridad automáticas"),
            tr("Kreix guarda una copia cifrada de tus datos al abrirlo, como mucho una por hora si hay cambios, y al cerrarlo. "
               "Se abre con tu contraseña maestra."),
            settings.backup_enabled,
        )
        self.backup_enabled.switch.toggled.connect(lambda v: self._update(backup_enabled=v))
        self.backup_path = QLabel()
        self.backup_path.setObjectName("Muted")
        self.backup_path.setWordWrap(True)
        self.backup_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.backup_status = QLabel()
        self.backup_status.setObjectName("Small")
        self.backup_status.setWordWrap(True)
        self.backup_status.hide()
        self.backup_choose = QPushButton(tr("Cambiar carpeta…"))
        self.backup_open = QPushButton(tr("Abrir carpeta"))
        self.backup_now = QPushButton(tr("Hacer una copia ahora"))
        self.backup_check = QPushButton(tr("Comprobar la última copia"))
        self.backup_check.setToolTip(tr("La abre de verdad con tu contraseña y mira que tenga tus datos: así sabes que sirve."))
        for button in (self.backup_choose, self.backup_open, self.backup_now, self.backup_check):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.backup_choose.clicked.connect(self.choose_backup_folder)
        self.backup_open.clicked.connect(self.open_backup_folder)
        self.backup_now.clicked.connect(self.backup_now_requested)
        self.backup_check.clicked.connect(self.backup_check_requested)
        self.backup_keep = Combo()
        self.backup_keep.setAccessibleName(tr("Copias que se conservan"))
        self.backup_keep.setFixedWidth(300)
        for keep in BACKUP_KEEP:
            self.backup_keep.addItem(tr("Conservar las últimas {n} copias").format(n=keep), keep)
        self._select_backup_keep(settings.backup_keep)
        self.backup_keep.activated.connect(self._on_backup_keep)
        backup_buttons = QHBoxLayout()
        backup_buttons.setSpacing(10)
        for button in (self.backup_choose, self.backup_open, self.backup_now, self.backup_check):
            backup_buttons.addWidget(button)
        backup_buttons.addStretch(1)
        backup_box = QWidget()
        backup_col = QVBoxLayout(backup_box)
        backup_col.setContentsMargins(0, 0, 0, 0)
        backup_col.setSpacing(10)
        backup_col.addWidget(self.backup_path)
        backup_col.addLayout(backup_buttons)
        backup_col.addWidget(self.backup_keep)
        backup_col.addWidget(self.backup_status)
        self.backup_list = BackupList()
        self.backup_list.restore_requested.connect(self.restore_backup_requested)

        self.whats_new_button = QPushButton(tr("Ver las novedades"))
        self.whats_new_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.whats_new_button.clicked.connect(self.whats_new_requested)
        whats_box = QWidget()
        whats_row = QHBoxLayout(whats_box)
        whats_row.setContentsMargins(0, 0, 0, 0)
        whats_row.addWidget(self.whats_new_button)
        whats_row.addStretch(1)

        app = GroupCard()
        self.security_card = app.add_field(           # solo se ofrece cuando hay almacen cifrado (set_security)
            tr("Seguridad"), tr("Tus datos están cifrados con tu contraseña maestra. Puedes cambiarla cuando quieras."),
            password_box)
        self.lock_card = app.add_field(
            tr("Bloqueo automático"),
            tr("Si no tocas el equipo durante este tiempo, Kreix esconde tus datos y vuelve a pedir la contraseña."),
            self.lock_after)
        self.lock_minimize_card = app.add_setting(self.lock_minimize)
        self.lock_session_card = app.add_setting(self.lock_session)
        self._security_rows = (self.security_card, self.lock_card, self.lock_minimize_card, self.lock_session_card)
        for row in self._security_rows:
            row.hide()
        app.add_field(tr("Tus datos"), tr("Todo se guarda solo en este equipo. Kreix no envía datos a ningún servidor."), data_box)
        app.add_field(tr("Acerca de"), tr("Kreix {VERSION}").format(VERSION=VERSION), whats_box)

        body = QWidget()
        body.setObjectName("Page")
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 44)
        col.setSpacing(26)
        col.addWidget(GroupHeading(tr("Tú")))
        col.addWidget(you)
        col.addWidget(GroupHeading(tr("Aspecto y cálculos")))
        col.addWidget(look)
        self.backup_heading = GroupHeading(tr("Copias de seguridad"))
        self.backup_group = GroupCard()
        self.backup_group.add_setting(self.backup_enabled)
        self.backup_group.add_field(tr("Dónde y cuántas"), tr("Elige la carpeta (por ejemplo, una unidad externa o una carpeta "
                                    "sincronizada) y cuántas copias se guardan; las más viejas se borran solas."), backup_box)
        self.backup_group.add_field(tr("Copias guardadas"), tr("Para recuperar una, pulsa Restaurar y escribe tu contraseña "
                                    "maestra. Reemplaza los datos actuales, y puedes deshacerlo."), self.backup_list)
        self._backup_widgets = (self.backup_heading, self.backup_group)
        for widget in self._backup_widgets:
            widget.hide()
        col.addWidget(self.backup_heading)
        col.addWidget(self.backup_group)
        col.addWidget(GroupHeading(tr("Datos y aplicación")))
        col.addWidget(app)
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

    def _update(self, **changes: bool | int) -> None:
        self._settings = replace(self._settings, **changes)
        self.settings_changed.emit(self._settings)

    @staticmethod
    def lock_minutes_label(minutes: int) -> str:
        if minutes == 0:
            return tr("Nunca")
        return trn("{n} minuto", "{n} minutos", minutes).format(n=minutes)

    def _select_lock_minutes(self, minutes: int) -> None:
        self.lock_after.setCurrentIndex(max(0, LOCK_MINUTES.index(minutes) if minutes in LOCK_MINUTES else 0))

    def _on_lock_after(self, index: int) -> None:
        self._update(auto_lock_minutes=int(self.lock_after.itemData(index)))

    def _select_text_size(self, percent: int) -> None:
        self.text_size.setCurrentIndex(TEXT_SCALES.index(percent) if percent in TEXT_SCALES else 0)

    def _on_text_size(self, index: int) -> None:
        self.text_scale_changed.emit(int(self.text_size.itemData(index)))

    def _select_backup_keep(self, keep: int) -> None:
        self.backup_keep.setCurrentIndex(BACKUP_KEEP.index(keep) if keep in BACKUP_KEEP else BACKUP_KEEP.index(10))

    def _on_backup_keep(self, index: int) -> None:
        self._update(backup_keep=int(self.backup_keep.itemData(index)))

    def choose_backup_folder(self) -> None:
        start = self._settings.backup_folder or self.backup_path.text()
        folder = QFileDialog.getExistingDirectory(self, tr("Carpeta de las copias de seguridad"), start)
        if folder:
            self._update(backup_folder=str(Path(folder)))

    def open_backup_folder(self) -> None:
        folder = Path(self.backup_path.text())
        if folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def show_backups(self, folder: Path, files, status: str = "") -> None:
        """Pone al dia la carpeta, la lista de copias y el aviso (error o nota) de la ultima copia."""
        self.backup_path.setText(str(folder))
        self.backup_list.set_files(files)
        self.backup_status.setText(status)
        self.backup_status.setVisible(bool(status))

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
        self._select_lock_minutes(settings.auto_lock_minutes)
        self._select_backup_keep(settings.backup_keep)
        self._select_text_size(settings.text_scale)
        for row, value in ((self.p2p, settings.include_p2p), (self.transfers, settings.transfers_in_as_income),
                           (self.ambient, settings.ambient), (self.lock_minimize, settings.lock_on_minimize),
                           (self.lock_session, settings.lock_on_session),
                           (self.backup_enabled, settings.backup_enabled)):
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

    def set_security(self, available: bool) -> None:
        """Muestra la tarjeta de seguridad solo si los datos estan en un almacen cifrado."""
        for row in self._security_rows + self._backup_widgets:
            row.setVisible(available)

    def reload_rules(self) -> None:
        if self.rules is not None:
            self.rules.reload()

    def set_theme(self, theme_name: str) -> None:
        self._settings = replace(self._settings, theme=theme_name)
