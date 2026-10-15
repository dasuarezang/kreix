"""Ventana principal: barra lateral, paginas y cambio de tema en caliente."""
from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt
from PySide6.QtGui import QColor, QKeySequence, QPainter, QRadialGradient, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from services.accounts_service import AccountsService
from services.dashboard_service import DashboardService
from services.category_service import CategoryService
from services.data_service import DataService
from services.import_service import ImportService
from services.investment_service import InvestmentService
from services.settings_service import AppSettings, SettingsService
from services.transfer_service import TransferError, TransferService
from ui import assets, icons, theme
from ui.views.accounts_view import AccountsView
from ui.views.dashboard_view import DashboardView
from ui.views.export_view import ExportView
from ui.views.help_view import HelpView
from ui.views.import_view import ImportView
from ui.views.investment_view import InvestmentView
from ui.views.settings_view import VERSION, SettingsView
from ui.widgets import charts
from ui.widgets.switch import ThemeToggle


class Backdrop(QWidget):
    """Fondo de la ventana: el color base y un resplandor en la esquina superior derecha."""

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


class MainWindow(QMainWindow):
    # El orden es el de los atajos Ctrl+1..7 y el de la barra, de arriba abajo: las tres vistas de datos
    # y despues las pildoras (Importar, Exportar, Ajustes y, la ultima de todas, Ayuda).
    PAGES = ("Resumen", "Cuentas", "Inversiones", "Importar", "Exportar", "Ajustes", "Ayuda")
    SUMMARY, ACCOUNTS, INVESTMENT, IMPORT, EXPORT, SETTINGS, HELP = range(7)
    DATA_PAGES = (SUMMARY, ACCOUNTS, INVESTMENT)
    PILLS = ((IMPORT, "upload"), (EXPORT, "download"), (SETTINGS, "gear"), (HELP, "help"))

    def __init__(self, services: Services, db_path: str) -> None:
        super().__init__()
        self._svc = services
        self._stale: set[int] = set()
        self.eager = False          # True: refresh() recarga todas las paginas (pruebas y capturas)
        self._settings = services.settings.load()
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
        self.settings_view.settings_changed.connect(self._on_settings_changed)
        self.settings_view.rules_changed.connect(self.refresh)
        self.settings_view.reset_requested.connect(self.confirm_reset)

        root = Backdrop()
        root.setObjectName("Root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        QShortcut(QKeySequence("Ctrl+T"), self, activated=lambda: self.theme_switch.toggle())
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("F5"), self, activated=self.reload_current)
        for i in range(len(self.PAGES)):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda i=i: self.navigate(i))

        self.apply_theme(self._settings.theme)
        self.refresh()
        saved = self._state.get("page", "")
        if saved.isdigit() and int(saved) in self.DATA_PAGES:      # se vuelve a la ultima vista de datos
            self.stack.setCurrentIndex(int(saved))
            self._nav.button(int(saved)).setChecked(True)
            self._load_if_stale(int(saved))

    # ------------------------------------------------------------------ construccion
    def _nav_button(self, index: int, name: str, object_name: str) -> QPushButton:
        btn = QPushButton(name)
        btn.setObjectName(object_name)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(f"{name} (Ctrl+{index + 1})")
        btn.clicked.connect(lambda _=False, i=index: self.navigate(i))
        self._nav.addButton(btn, index)
        return btn

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
        for index, icon_name in self.PILLS:                                    # abajo: pildoras con icono
            pill = self._nav_button(index, self.PAGES[index], "PillButton")
            pill.setIconSize(QSize(20, 20))
            self._pill_buttons[index] = (pill, icon_name)
            col.addWidget(pill)
        self._nav.button(self.SUMMARY).setChecked(True)

        col.addSpacing(10)
        self.theme_switch = ThemeToggle(self._settings.theme == "dark")
        self.theme_switch.setToolTip("Cambiar entre modo oscuro y claro (Ctrl+T)")
        self.theme_switch.toggled.connect(lambda on: self.apply_theme("dark" if on else "light", persist=True))
        col.addWidget(self.theme_switch, 0, Qt.AlignmentFlag.AlignHCenter)
        col.addSpacing(8)
        foot = QLabel(f"Kreix {VERSION}  ·  datos solo en tu equipo")
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
        button = self._nav.button(index)
        button.setChecked(True)
        button.setFocus(Qt.FocusReason.OtherFocusReason)   # el aro de foco acompana a la pestana activa
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

    def confirm_reset(self) -> None:
        answer = QMessageBox.question(
            self, "Borrar todos los datos",
            "Se eliminarán todos los movimientos, operaciones y la cartera importados.\n"
            "Tus ajustes se conservan. Esta acción no se puede deshacer.\n\n"
            "¿Quieres continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.reset_data()

    def reset_data(self) -> None:
        self._svc.data.reset_all()
        self.refresh()
        self.navigate(self.SUMMARY)

    # ------------------------------------------------------------------ traspaso de datos
    def restore_from(self, path: str) -> bool:
        """Restaura los datos de un archivo .kreix (reemplaza los actuales, previa confirmacion)."""
        try:
            info = self._svc.transfer.inspect(path)
        except TransferError as exc:
            QMessageBox.warning(self, "No se puede importar el archivo", str(exc))
            return False
        if not self._svc.transfer.summary().is_empty:
            s = info.summary
            answer = QMessageBox.question(
                self, "Reemplazar los datos de este ordenador",
                f"El archivo contiene {s.transactions} movimientos, {s.operations} operaciones y {s.accounts} cuentas.\n\n"
                "Al importarlo se reemplazarán TODOS los datos que hay ahora en Kreix. "
                "Esta acción no se puede deshacer.\n\n¿Quieres continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        try:
            self._svc.transfer.restore(path)
        except TransferError as exc:
            QMessageBox.warning(self, "No se pudo importar el archivo", str(exc))
            return False
        self._settings = self._svc.settings.load()                 # los ajustes viajan con los datos
        self.settings_view.set_settings(self._settings)
        self.apply_theme(self._settings.theme)
        self.refresh()
        self.navigate(self.SUMMARY)
        QMessageBox.information(self, "Datos importados", "Los datos se han importado correctamente.")
        return True

    # ------------------------------------------------------------------ tema
    def apply_theme(self, name: str, persist: bool = False) -> None:
        palette = theme.PALETTES[name]
        theme.set_current(palette)
        QApplication.instance().setStyleSheet(theme.stylesheet(palette))
        self.centralWidget().update()
        self._logo.setPixmap(assets.wordmark(palette, 46))
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
        if not self.isMaximized() and not self.isFullScreen():
            self._svc.settings.save_state(width=self.width(), height=self.height(), page=self.stack.currentIndex())
        else:
            self._svc.settings.save_state(page=self.stack.currentIndex())
        super().closeEvent(event)

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self._settings = replace(settings, theme=self._settings.theme)
        self._svc.settings.save(self._settings)
        self.refresh()
