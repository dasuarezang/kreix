"""Ventana principal: barra lateral, paginas y cambio de tema en caliente."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QPainter, QRadialGradient, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from services.accounts_service import AccountsService
from services.dashboard_service import DashboardService
from services.category_service import CategoryService
from services.data_service import DataService
from services.demo_service import DemoService
from services.import_service import ImportService
from services.investment_service import InvestmentService
from services.settings_service import AppSettings, SettingsService
from services.transfer_service import TransferError, TransferService
from ui import assets, icons, theme
from core import i18n
from core.greeting import clean_name
from ui.command_palette import Command, CommandPalette
from ui.dialogs import WelcomeDialog, system_language
from ui.feedback import Feedback, snapshot_of, tell
from ui.format import category_label, fmt_date, fmt_eur
from ui.help_content import localized_entries
from ui.views.accounts_view import AccountsView
from ui.views.dashboard_view import DashboardView
from ui.views.export_view import ExportView
from ui.views.help_view import HelpView
from ui.views.import_view import ImportView
from ui.views.investment_view import InvestmentView
from ui.views.settings_view import VERSION, SettingsView
from ui.whats_new import WhatsNewDialog
from ui.widgets import charts
from ui.widgets.ambient import AmbientLight, hour_of
from ui.widgets.data_menu import DataFlyout, DataMenuButton
from ui.widgets.switch import ThemeToggle
from ui.widgets.toast import Toast
from core.i18n import tr, N_


class Backdrop(QWidget):
    """Fondo de la ventana: el color base y un resplandor en la esquina superior derecha."""

    overlay: QWidget | None = None          # la luz ambiente cubre toda la ventana

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.overlay is not None:
            self.overlay.setGeometry(self.rect())

    def paintEvent(self, _event) -> None:
        pal = theme.current()
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(pal.bg))
        radius = max(self.width(), self.height()) * 0.85
        gradient = QRadialGradient(self.width() * 0.92, -self.height() * 0.05, radius)
        start = QColor(pal.glow)
        start.setAlpha(pal.glow_alpha)
        end = QColor(pal.glow)
        end.setAlpha(0)
        gradient.setColorAt(0.0, start)
        gradient.setColorAt(1.0, end)
        painter.fillRect(self.rect(), gradient)


@dataclass(frozen=True, slots=True)
class Services:
    importer: ImportService
    dashboard: DashboardService
    settings: SettingsService
    data: DataService
    accounts: AccountsService
    investment: InvestmentService
    transfer: TransferService
    categories: CategoryService
    demo: DemoService


class MainWindow(QMainWindow):
    # El orden es el de los atajos Ctrl+1..7: las tres vistas de datos, Importar y Exportar (agrupadas en el boton
    # "Datos" de la barra, con un submenu), Ajustes y Ayuda (las dos ultimas pildoras).
    PAGES = (N_("Inicio"), N_("Cuentas"), N_("Inversiones"), N_("Importar"), N_("Exportar"), N_("Ajustes"), N_("Ayuda"))
    SUMMARY, ACCOUNTS, INVESTMENT, IMPORT, EXPORT, SETTINGS, HELP = range(7)
    DATA_PAGES = (SUMMARY, ACCOUNTS, INVESTMENT)
    PILLS = ((SETTINGS, "gear"), (HELP, "help"))
    DATA_GROUP = ((IMPORT, "upload"), (EXPORT, "download"))             # las dos opciones del submenu "Datos"

    def __init__(self, services: Services, db_path: str) -> None:
        super().__init__()
        self._svc = services
        self._stale: set[int] = set()
        self.eager = False          # True: refresh() recarga todas las paginas (pruebas y capturas)
        self._settings = services.settings.load()
        i18n.set_language(self._settings.language)         # antes de crear ningun texto: todo sale en este idioma
        self._db_path = db_path
        self.rebuilding = False
        self.detect_language = False        # True (lo activa main): la primera vez se propone el idioma del sistema
        self.setWindowTitle("Kreix")
        self.setWindowIcon(assets.app_icon())
        self.resize(1280, 820)
        self.setMinimumSize(1040, 700)
        self._state = services.settings.load_state()
        self._restore_geometry()

        self.dashboard = DashboardView()
        self.accounts_view = AccountsView(services.accounts, lambda: self._settings.flow_options, services.categories)
        self.investment_view = InvestmentView(services.investment)
        self.settings_view = SettingsView(self._settings, db_path, services.categories)
        self.help_view = HelpView()
        self.import_view = ImportView(services.importer)
        self.export_view = ExportView(services.transfer)
        self.stack = QStackedWidget()
        for page in (self.dashboard, self.accounts_view, self.investment_view, self.import_view,
                     self.export_view, self.settings_view, self.help_view):
            self.stack.addWidget(page)

        for view in (self.dashboard, self.accounts_view, self.investment_view):
            view.go_import.connect(lambda: self.navigate(self.IMPORT))
        self.accounts_view.accounts_changed.connect(self.refresh)
        self.accounts_view.categories_changed.connect(self.refresh)
        self.import_view.imported.connect(self.refresh)
        self.import_view.restore_requested.connect(self.restore_from)
        self.import_view.before_import = self.leave_demo
        self.dashboard.demo_requested.connect(self.start_demo)
        self.dashboard.navigate_requested.connect(self._go_from_setup)
        self.dashboard.setup_dismissed.connect(self._dismiss_setup)
        self.dashboard.category_clicked.connect(self._show_category_in_accounts)
        self.settings_view.settings_changed.connect(self._on_settings_changed)
        self.settings_view.rules_changed.connect(self.refresh)
        self.settings_view.whats_new_requested.connect(self.show_whats_new)
        self.settings_view.name_changed.connect(self._apply_user_name)
        self.settings_view.interests_changed.connect(self._on_interests_picked)
        self.settings_view.language_changed.connect(self._on_language_picked)
        self.accounts_view.interest_requested.connect(lambda: self._activate_interest("accounts"))
        self.investment_view.interest_requested.connect(lambda: self._activate_interest("investments"))
        self.settings_view.reset_requested.connect(self.confirm_reset)

        self.demo_banner = self._build_demo_banner()
        right = QWidget()
        right.setObjectName("Page")
        right_col = QVBoxLayout(right)
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(0)
        right_col.addWidget(self.demo_banner)
        right_col.addWidget(self.stack, 1)

        root = Backdrop()
        root.setObjectName("Root")
        self._root = root
        self.ambient = AmbientLight(root)
        root.overlay = self.ambient
        self.toast = Toast(root)                  # creado despues: queda por encima de la luz
        self.feedback = Feedback(services.transfer, self.toast, self)
        self.feedback.restored.connect(self._after_undo)
        for view in (self.accounts_view, self.import_view, self.settings_view):
            view.feedback = self.feedback
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addWidget(right, 1)
        self.setCentralWidget(root)

        QShortcut(QKeySequence("Ctrl+T"), self, activated=lambda: self.theme_switch.toggle())
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.open_palette)
        QShortcut(QKeySequence("F5"), self, activated=self.reload_current)
        for i in range(len(self.PAGES)):
            QShortcut(QKeySequence(tr("Ctrl+{i}").format(i=i + 1)), self, activated=lambda i=i: self.navigate(i))

        self.apply_theme(self._settings.theme)
        self._demo = self._state.get("demo") == "1" and not self._svc.transfer.summary().is_empty
        self.demo_banner.setVisible(self._demo)
        self.dashboard.set_setup_hidden(self._state.get("setup_hidden") == "1")
        self.dashboard.set_user_name(self._settings.user_name)
        self._sync_interests()
        self.clock = datetime.now                  # las pruebas lo sustituyen
        self.dashboard.clock = lambda: self.clock()
        self._apply_ambient()
        self._clock_timer = QTimer(self)           # cada minuto: saludo, cielo y luz siguen a la hora real
        self._clock_timer.setInterval(60_000)
        self._clock_timer.timeout.connect(self.tick_clock)
        self._clock_timer.start()
        self.refresh()
        saved = self._state.get("page", "")
        if saved.isdigit() and int(saved) in self.DATA_PAGES:      # se vuelve a la ultima vista de datos
            self.stack.setCurrentIndex(int(saved))
            self._nav.button(int(saved)).setChecked(True)
            self._load_if_stale(int(saved))

    # ------------------------------------------------------------------ construccion
    def _nav_button(self, index: int, name: str, object_name: str) -> QPushButton:
        btn = QPushButton(tr(name))
        btn.setObjectName(object_name)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tr("{name} (Ctrl+{index})").format(name=tr(name), index=index + 1))
        btn.clicked.connect(lambda _=False, i=index: self.navigate(i))
        self._nav.addButton(btn, index)
        return btn

    def _build_data_group(self) -> QPushButton:
        """El boton "Datos" y su submenu con Importar y Exportar (que siguen siendo paginas con sus atajos Ctrl+4 y Ctrl+5)."""
        self.data_flyout = DataFlyout(self._root)
        self._fly_items: dict[int, tuple[QPushButton, str]] = {}
        for index, icon_name in self.DATA_GROUP:
            item = self._nav_button(index, self.PAGES[index], "FlyItem")
            item.setIconSize(QSize(18, 18))
            item.clicked.connect(self.data_flyout.hide)                        # al elegir, el submenu se cierra
            self._fly_items[index] = (item, icon_name)
            self.data_flyout.add_item(item)
        self.data_button = DataMenuButton(tr("Datos"), self.data_flyout)
        self.data_button.setObjectName("PillButton")
        self.data_button.setIconSize(QSize(18, 18))
        self.data_button.setToolTip(tr("Importar y exportar tus datos"))
        self.data_button.setAccessibleName(tr("Datos"))
        self.data_button.setAccessibleDescription(tr("Importar y exportar tus datos"))
        return self.data_button

    def _build_sidebar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(236)
        self._logo = QLabel()
        self._logo.setAccessibleName("Kreix")

        self._nav = QButtonGroup(self)
        self._nav.setExclusive(True)
        col = QVBoxLayout(bar)
        col.setContentsMargins(18, 24, 18, 18)
        col.setSpacing(6)
        col.addWidget(self._logo)
        col.addSpacing(22)
        for index in (self.SUMMARY, self.ACCOUNTS, self.INVESTMENT):          # arriba: las vistas de datos
            col.addWidget(self._nav_button(index, self.PAGES[index], "NavButton"))
        col.addStretch(1)

        self._pill_buttons: dict[int, tuple[QPushButton, str]] = {}
        col.addWidget(self._build_data_group())                                # abajo: "Datos" (Importar y Exportar)...
        for index, icon_name in self.PILLS:                                    # ...y pildoras con icono
            pill = self._nav_button(index, self.PAGES[index], "PillButton")
            pill.setIconSize(QSize(18, 18))
            self._pill_buttons[index] = (pill, icon_name)
            col.addWidget(pill)
        self._nav.button(self.SUMMARY).setChecked(True)

        col.addSpacing(10)
        self.theme_switch = ThemeToggle(self._settings.theme == "dark")
        self.theme_switch.setToolTip(tr("Cambiar entre modo oscuro y claro (Ctrl+T)"))
        self.theme_switch.toggled.connect(lambda on: self.apply_theme("dark" if on else "light", persist=True))
        col.addWidget(self.theme_switch, 0, Qt.AlignmentFlag.AlignHCenter)
        col.addSpacing(8)
        foot = QLabel(tr("Kreix {VERSION}  ·  datos solo en tu equipo").format(VERSION=VERSION))
        foot.setObjectName("SidebarFoot")
        foot.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        foot.setWordWrap(True)
        col.addWidget(foot)
        return bar

    # ------------------------------------------------------------------ comportamiento
    def navigate(self, index: int) -> None:
        changed = index != self.stack.currentIndex()
        self.stack.setCurrentIndex(index)
        self._load_if_stale(index)
        if changed:
            self._fade_in(self.stack.currentWidget())
        in_data_group = index in (self.IMPORT, self.EXPORT)
        self.data_button.set_active(in_data_group)                          # "Datos" se marca en Importar y en Exportar
        button = self._nav.button(index)
        button.setChecked(True)
        (self.data_button if in_data_group else button).setFocus(Qt.FocusReason.OtherFocusReason)   # el reborde acompana a la pagina
        if index == self.HELP:
            self.help_view.show_hub()          # al entrar en Ayuda siempre se ve el menu de secciones
        elif index == self.EXPORT:
            self.export_view.refresh()

    def _fade_in(self, page: QWidget) -> None:
        """Aparicion suave de la pagina (140 ms). El efecto se quita al terminar: no deja coste de pintado."""
        if not charts.ANIMATIONS or not self.isVisible():
            return
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", page)
        animation.setDuration(140)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: page.setGraphicsEffect(None))
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    # ------------------------------------------------------------------ buscador global (Ctrl+K)
    def palette_commands(self) -> list[Command]:
        go = [Command(tr("Ir a {name}").format(name=tr(name)), tr("Ctrl+{i}").format(i=i + 1), lambda i=i: self.navigate(i), group=tr("Páginas"))
              for i, name in enumerate(self.PAGES)]
        actions = [
            Command(tr("Cambiar entre modo claro y oscuro"), "Ctrl+T", self.theme_switch.toggle,
                    tr("tema aspecto color noche día"), tr("Acciones")),
            Command(tr("Buscar en mis movimientos"), "Ctrl+F", self.focus_search, tr("concepto pagos gastos")),
            Command(tr("Cambiar mi nombre"), tr("Ajustes"), self._edit_name, tr("usuario saludo perfil")),
            Command(tr("Cambiar lo que me interesa"), tr("Ajustes"), self._edit_interests,
                    tr("cuentas inversiones gestionar activar desactivar intereses")),
            Command(tr("Definir presupuestos mensuales"), tr("Cuentas"), self._edit_budgets, tr("tope límite gastar categoría")),
            Command(tr("Crear una regla de categoría"), tr("Ajustes"), self._new_rule, tr("clasificar categorizar palabra")),
            Command(tr("Exportar movimientos a CSV o Excel"), tr("Cuentas"), self._export_movements, tr("descargar hoja de cálculo xlsx")),
            Command(tr("Recalcular la página"), "F5", self.reload_current, tr("actualizar refrescar")),
            Command(tr("Ver las novedades de esta versión"), tr("Novedades"), self.show_whats_new, tr("cambios nuevo versión")),
        ]
        if self._svc.transfer.summary().is_empty:
            actions.append(Command(tr("Probar con datos de ejemplo"), tr("Sin importar nada"), self.start_demo, tr("demo explorar")))
        elif self._demo:
            actions.append(Command(tr("Quitar los datos de ejemplo"), tr("Empezar con mis datos"), self.end_demo, tr("demo borrar")))
        helps = [Command(tr("Ayuda: {term}").format(term=e.term), tr(e.section), lambda t=e.term: self._open_help(t), " ".join(e.keywords), tr("Ayuda"))
                 for e in localized_entries()]
        return go + actions + helps

    def _movement_commands(self, text: str) -> list[Command]:
        out = []
        for t in self._svc.accounts.search_movements(text):
            detail = f"{fmt_date(t.booking_date)}  ·  {fmt_eur(t.amount)}  ·  {category_label(t.category)}"
            out.append(Command(t.description, detail, lambda d=t.description: self._show_movement(d), group=tr("Movimientos")))
        return out

    def open_palette(self) -> None:
        palette = CommandPalette(self.palette_commands(), self._movement_commands, self)
        palette.popup(self)

    def _show_movement(self, description: str) -> None:
        self.navigate(self.ACCOUNTS)
        self.accounts_view.search_for(description)

    def _open_help(self, term: str) -> None:
        self.navigate(self.HELP)
        self.help_view.set_query(term)

    def _edit_budgets(self) -> None:
        self.navigate(self.ACCOUNTS)
        self.accounts_view.edit_budgets()

    def _edit_name(self) -> None:
        self.navigate(self.SETTINGS)
        self.settings_view.focus_name()

    def _edit_interests(self) -> None:
        self.navigate(self.SETTINGS)
        self.settings_view.focus_interests()

    def _new_rule(self) -> None:
        self.navigate(self.SETTINGS)
        if self.settings_view.rules is not None:
            self.settings_view.rules.prompt_add()

    def _export_movements(self) -> None:
        self.navigate(self.ACCOUNTS)
        self.accounts_view.export_movements()

    def focus_search(self) -> None:
        """Ctrl+F: lleva a Cuentas y pone el cursor en el buscador de movimientos."""
        self.navigate(self.ACCOUNTS)
        self.accounts_view.search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.accounts_view.search.selectAll()

    def reload_current(self) -> None:
        """F5: recalcula la pagina visible."""
        self._stale.add(self.stack.currentIndex())
        self.refresh()

    def refresh(self) -> None:
        """Marca los datos como caducados y recarga solo la pagina visible: el resto se carga al
        entrar en ella (asi importar o cambiar un ajuste no recalcula tres paginas a la vez)."""
        self._stale = set(self.DATA_PAGES)
        self.import_view.set_accounts(self._svc.accounts.accounts())
        self.export_view.refresh()
        self.settings_view.reload_rules()
        self._load_if_stale(self.stack.currentIndex())
        if self.eager:
            self.load_all()

    def _load_if_stale(self, index: int) -> None:
        if index not in self._stale:
            return
        self._stale.discard(index)
        if index == self.SUMMARY:
            self.dashboard.set_data(self._svc.dashboard.load(self._settings.flow_options))
        elif index == self.ACCOUNTS:
            self.accounts_view.reload()
        elif index == self.INVESTMENT:
            self.investment_view.reload()

    def load_all(self) -> None:
        """Carga ya todas las paginas de datos (para capturas y pruebas)."""
        for index in self.DATA_PAGES:
            self._load_if_stale(index)

    # ------------------------------------------------------------------ datos de ejemplo y primeros pasos
    def _build_demo_banner(self) -> QFrame:
        banner = QFrame()
        banner.setObjectName("DemoBanner")
        text = QLabel(tr("Estás viendo datos de ejemplo inventados. Nada de esto es tuyo."))
        text.setObjectName("DemoBannerText")
        self.demo_exit = QPushButton(tr("Empezar con mis datos"))
        self.demo_exit.setObjectName("Primary")
        self.demo_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.demo_exit.clicked.connect(self.end_demo)
        row = QHBoxLayout(banner)
        row.setContentsMargins(24, 8, 24, 8)
        row.addWidget(text, 1)
        row.addWidget(self.demo_exit)
        banner.hide()
        return banner

    def start_demo(self) -> bool:
        """Carga los datos de ejemplo. Solo con la app vacia: nunca se mezclan con datos reales."""
        if not self._svc.transfer.summary().is_empty:
            return False
        self._svc.demo.load()
        self._set_demo(True)
        self.refresh()
        self.navigate(self.SUMMARY)
        tell(self.feedback, tr("Datos de ejemplo cargados. Explora con calma: se quitan con «Empezar con mis datos»."))
        return True

    def leave_demo(self) -> None:
        """Quita los datos de ejemplo (sin avisar) antes de importar los reales."""
        if self._demo:
            self._svc.data.reset_all()
            self._set_demo(False)
            self.import_view.set_accounts(self._svc.accounts.accounts())     # la cuenta de ejemplo ya no existe

    def end_demo(self) -> None:
        snapshot = snapshot_of(self.feedback)
        self.leave_demo()
        self.refresh()
        self.navigate(self.SUMMARY)
        tell(self.feedback, tr("Datos de ejemplo eliminados. Importa tus extractos para empezar."), snapshot)

    def _set_demo(self, on: bool) -> None:
        self._demo = on
        self.demo_banner.setVisible(on)
        if on:
            self._svc.settings.save_state(demo=1)
        else:
            self._svc.settings.clear_state("demo")

    def _show_category_in_accounts(self, category) -> None:
        self.navigate(self.ACCOUNTS)
        self.accounts_view.show_category(category)

    def _go_from_setup(self, target: str) -> None:
        self.navigate(self.IMPORT if target == "import" else self.ACCOUNTS)

    def _dismiss_setup(self) -> None:
        self.dashboard.set_setup_hidden(True)
        self._svc.settings.save_state(setup_hidden=1)
        tell(self.feedback, tr("Lista de primeros pasos oculta."))

    # ------------------------------------------------------------------ nombre de usuario
    def ask_name_if_needed(self) -> bool:
        """La primera vez, pregunta como llamar al usuario y que quiere gestionar (cuentas, inversiones o ambas).
        Si dice "ahora no", se queda con ambas y no se le vuelve a insistir."""
        if self._settings.name_asked:
            return False
        language = system_language() if self.detect_language else self._settings.language
        dialog = WelcomeDialog(self._settings.user_name,
                               (self._settings.interest_accounts, self._settings.interest_investments), self, language)
        accepted = dialog.exec() == WelcomeDialog.DialogCode.Accepted
        if accepted:
            accounts, investments = dialog.result_interests()
            self._settings = replace(self._settings, interest_accounts=accounts, interest_investments=investments)
        self._apply_user_name(dialog.result_name() if accepted else self._settings.user_name, announce=False)
        self._sync_interests()
        chosen = dialog.result_language()                 # el idioma elegido se queda aunque diga "ahora no"
        if chosen != self._settings.language:
            self._apply_language(chosen)
        else:
            i18n.set_language(self._settings.language)
        return accepted

    # ------------------------------------------------------------------ idioma
    def _on_language_picked(self, code: str) -> None:
        if code != self._settings.language:
            self._apply_language(code)

    def _apply_language(self, code: str) -> None:
        """Guarda el idioma y rehace la ventana para que todo salga en el nuevo (los datos y la pagina se conservan)."""
        code = i18n.normalize_language(code)
        self._settings = replace(self._settings, language=code)
        self._svc.settings.save(self._settings)
        i18n.set_language(code)
        self.rebuilding = True
        self._later(0, self.rebuild)

    def _later(self, delay_ms: int, callback) -> None:
        """Ejecuta algo dentro de un momento. El temporizador cuelga de la ventana: si la ventana desaparece antes,
        no se ejecuta (un QTimer.singleShot suelto podia disparar sobre una ventana ya destruida)."""
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.timeout.connect(timer.deleteLater)
        timer.start(delay_ms)

    def _sync_language(self) -> bool:
        """Si lo que se acaba de cargar (restaurar un .kreix, deshacer) trae otro idioma, rehace la ventana en ese idioma."""
        if self._settings.language == i18n.language():
            return False
        i18n.set_language(self._settings.language)
        self.rebuilding = True
        self._later(0, self.rebuild)
        return True

    def _persist_state(self) -> None:
        if not self.isMaximized() and not self.isFullScreen():
            self._svc.settings.save_state(width=self.width(), height=self.height(), page=self.stack.currentIndex())
        else:
            self._svc.settings.save_state(page=self.stack.currentIndex())

    def rebuild(self) -> "MainWindow":
        """Sustituye esta ventana por otra igual construida en el idioma activo: mismos datos, misma pagina y tamano."""
        self._persist_state()
        new = MainWindow(self._svc, self._db_path)
        new.eager = self.eager
        new.detect_language = self.detect_language
        new.clock = self.clock
        new.dashboard.clock = lambda: new.clock()
        new.resize(self.size())
        if self.isMaximized():
            new.showMaximized()
        else:
            new.move(self.pos())
            new.show()
        new.navigate(self.stack.currentIndex())
        app = QApplication.instance()
        app.kreix_window = new                           # la ventana principal viva (evita que se recoja)
        self.feedback.close()
        self.hide()
        self.deleteLater()
        new._later(0, new.announce_new_version)
        tell(new.feedback, tr("Idioma cambiado a {language}.").format(language=i18n.NAMES[i18n.language()]))
        return new

    # ------------------------------------------------------------------ lo que le interesa al usuario
    def _sync_interests(self) -> None:
        """Lleva a las pestanas y a Inicio lo que el usuario quiere gestionar."""
        accounts, investments = self._settings.interest_accounts, self._settings.interest_investments
        self.dashboard.set_interests(accounts, investments)
        self.accounts_view.set_interested(accounts)
        self.investment_view.set_interested(investments)

    def _on_interests_picked(self, accounts: bool, investments: bool) -> None:
        self._apply_interests(accounts, investments, tr("Intereses guardados."))

    def _apply_interests(self, accounts: bool, investments: bool, message: str, undoable: bool = False) -> None:
        if not (accounts or investments):
            return
        snapshot = snapshot_of(self.feedback) if undoable else None
        self._settings = replace(self._settings, interest_accounts=accounts, interest_investments=investments)
        self._svc.settings.save(self._settings)
        self.settings_view.set_settings(self._settings)
        self._sync_interests()
        self.refresh()
        tell(self.feedback, message, snapshot)

    def _activate_interest(self, which: str) -> None:
        """Desde la propia pestana: activa solo el tema que faltaba, sin tocar el otro."""
        accounts = self._settings.interest_accounts or which == "accounts"
        investments = self._settings.interest_investments or which == "investments"
        self._apply_interests(accounts, investments, tr("Cuentas bancarias activadas.") if which == "accounts"
                              else tr("Inversiones activadas."), undoable=True)

    def _apply_user_name(self, name: str, announce: bool = True) -> None:
        name = clean_name(name)
        self._settings = replace(self._settings, user_name=name, name_asked=True)
        self._svc.settings.save(self._settings)
        self.settings_view.set_settings(self._settings)
        self.dashboard.set_user_name(name)
        if announce:
            tell(self.feedback, tr("Nombre guardado: {name}.").format(name=name) if name else tr("Nombre quitado: Kreix te saludará sin nombre."))

    def start_up(self) -> None:
        """Lo que se hace al abrir: pedir el nombre la primera vez y ensenar las novedades tras actualizar."""
        self.ask_name_if_needed()
        if not self.rebuilding:                        # si cambio el idioma, la ventana nueva ensena las novedades
            self.announce_new_version()

    def show_whats_new(self) -> None:
        WhatsNewDialog(VERSION, self).exec()

    def announce_new_version(self) -> None:
        """Tras actualizar, ensena las novedades una sola vez. En la primera ejecucion no hay nada que contar."""
        seen = self._state.get("seen_version")
        self._svc.settings.save_state(seen_version=VERSION)
        self._state["seen_version"] = VERSION
        upgraded = (seen is not None and seen != VERSION) or (
            seen is None and not self._demo and not self._svc.transfer.summary().is_empty)   # ya usaba una version antigua
        if upgraded:
            self.show_whats_new()

    def _after_undo(self) -> None:
        self._state = self._svc.settings.load_state()
        self._demo = self._state.get("demo") == "1" and not self._svc.transfer.summary().is_empty
        self.demo_banner.setVisible(self._demo)
        self._settings = self._svc.settings.load()
        self._sync_language()
        self.settings_view.set_settings(self._settings)
        self.dashboard.set_user_name(self._settings.user_name)
        self._sync_interests()
        self._apply_ambient()
        self.apply_theme(self._settings.theme)
        self.refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.toast.isVisible():
            self.toast.reposition()

    def confirm_reset(self) -> None:
        answer = QMessageBox.question(
            self, tr("Borrar todos los datos"),
            tr("Se eliminarán todos los movimientos, operaciones y la cartera importados.\n"
            "Tus ajustes se conservan. Esta acción no se puede deshacer.\n\n"
            "¿Quieres continuar?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.reset_data()

    def reset_data(self) -> None:
        snapshot = snapshot_of(self.feedback)
        self._svc.data.reset_all()
        if self._demo:
            self._set_demo(False)
        self.refresh()
        self.navigate(self.SUMMARY)
        tell(self.feedback, tr("Datos borrados."), snapshot)

    # ------------------------------------------------------------------ traspaso de datos
    def restore_from(self, path: str) -> bool:
        """Restaura los datos de un archivo .kreix (reemplaza los actuales, previa confirmacion)."""
        try:
            info = self._svc.transfer.inspect(path)
        except TransferError as exc:
            QMessageBox.warning(self, tr("No se puede importar el archivo"), str(exc))
            return False
        if not self._svc.transfer.summary().is_empty:
            s = info.summary
            answer = QMessageBox.question(
                self, tr("Reemplazar los datos de este ordenador"),
                tr("El archivo contiene {transactions} movimientos, {operations} operaciones y {accounts} cuentas.\n\nAl importarlo se reemplazarán TODOS los datos que hay ahora en Kreix. Esta acción no se puede deshacer.\n\n¿Quieres continuar?").format(transactions=s.transactions, operations=s.operations, accounts=s.accounts),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        snapshot = snapshot_of(self.feedback)
        try:
            self._svc.transfer.restore(path)
        except TransferError as exc:
            QMessageBox.warning(self, tr("No se pudo importar el archivo"), str(exc))
            return False
        if self._demo:
            self._set_demo(False)                                   # lo restaurado es de verdad
        self._settings = self._svc.settings.load()                 # los ajustes viajan con los datos
        self._sync_language()                                       # y con ellos, el idioma
        self.settings_view.set_settings(self._settings)
        self.dashboard.set_user_name(self._settings.user_name)       # el nombre viaja con los datos
        self._sync_interests()                                        # y tambien lo que le interesa
        self._apply_ambient()
        self.apply_theme(self._settings.theme)
        self.refresh()
        self.navigate(self.SUMMARY)
        tell(self.feedback, tr("Datos importados desde el archivo .kreix."), snapshot)
        return True

    # ------------------------------------------------------------------ tema
    def apply_theme(self, name: str, persist: bool = False) -> None:
        palette = theme.PALETTES[name]
        theme.set_current(palette)
        QApplication.instance().setStyleSheet(theme.stylesheet(palette))
        self.centralWidget().update()
        self._logo.setPixmap(assets.wordmark(palette, 46))
        self.data_button.setIcon(icons.button_icon("database", palette))
        for item, icon_name in self._fly_items.values():
            item.setIcon(icons.button_icon(icon_name, palette))
        for pill, icon_name in self._pill_buttons.values():
            pill.setIcon(icons.button_icon(icon_name, palette))
        if self.theme_switch.isChecked() != (name == "dark"):
            self.theme_switch.setChecked(name == "dark")
        self.theme_switch.update()
        self.dashboard.refresh_theme()
        self.accounts_view.refresh_theme()
        self.investment_view.refresh_theme()
        self.help_view.refresh_theme()
        self._settings = replace(self._settings, theme=name)
        self.settings_view.set_theme(name)
        if persist:
            self._svc.settings.save(self._settings)

    # ------------------------------------------------------------------ estado de la ventana
    def _restore_geometry(self) -> None:
        try:
            width, height = int(self._state["width"]), int(self._state["height"])
        except (KeyError, ValueError):
            return
        screen = QApplication.primaryScreen()
        limit = screen.availableGeometry().size() if screen else QSize(width, height)
        self.resize(max(self.minimumWidth(), min(width, limit.width())), max(self.minimumHeight(), min(height, limit.height())))

    def closeEvent(self, event) -> None:
        self.feedback.close()
        self._persist_state()
        super().closeEvent(event)

    # ------------------------------------------------------------------ ambiente
    def _apply_ambient(self) -> None:
        self.ambient.set_enabled(self._settings.ambient)
        self.ambient.set_hour(hour_of(self.clock()))
        self.dashboard.set_animated(self._settings.ambient)
        self.dashboard.update_greeting()
        self.ambient.setGeometry(self.centralWidget().rect())
        self.toast.raise_()

    def tick_clock(self) -> None:
        """Pone al dia el saludo, el astro del cielo y la luz ambiente con la hora actual."""
        self.ambient.set_hour(hour_of(self.clock()))
        self.dashboard.update_greeting()

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self._settings = replace(settings, theme=self._settings.theme)
        self._svc.settings.save(self._settings)
        self._apply_ambient()
        self.refresh()
