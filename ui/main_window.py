"""Ventana principal: barra lateral, paginas y cambio de tema en caliente."""
from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from services.accounts_service import AccountsService
from services.dashboard_service import DashboardService
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
from ui.widgets.switch import ThemeToggle


@dataclass(frozen=True, slots=True)
class Services:
    importer: ImportService
    dashboard: DashboardService
    settings: SettingsService
    data: DataService
    accounts: AccountsService
    investment: InvestmentService
    transfer: TransferService


class MainWindow(QMainWindow):
    # El orden es el de los atajos Ctrl+1..7: arriba las tres vistas de datos, abajo las pildoras.
    PAGES = ("Resumen", "Cuentas", "Inversiones", "Ajustes", "Ayuda", "Importar", "Exportar")
    SUMMARY, ACCOUNTS, INVESTMENT, SETTINGS, HELP, IMPORT, EXPORT = range(7)
    PILLS = ((SETTINGS, "gear"), (HELP, "help"), (IMPORT, "upload"), (EXPORT, "download"))

    def __init__(self, services: Services, db_path: str) -> None:
        super().__init__()
        self._svc = services
        self._settings = services.settings.load()
        self.setWindowTitle("Kreix")
        self.setWindowIcon(assets.app_icon())
        self.resize(1280, 820)
        self.setMinimumSize(1040, 700)

        self.dashboard = DashboardView()
        self.accounts_view = AccountsView(services.accounts, lambda: self._settings.flow_options)
        self.investment_view = InvestmentView(services.investment)
        self.settings_view = SettingsView(self._settings, db_path)
        self.help_view = HelpView()
        self.import_view = ImportView(services.importer)
        self.export_view = ExportView(services.transfer)
        self.stack = QStackedWidget()
        for page in (self.dashboard, self.accounts_view, self.investment_view, self.settings_view,
                     self.help_view, self.import_view, self.export_view):
            self.stack.addWidget(page)

        for view in (self.dashboard, self.accounts_view, self.investment_view):
            view.go_import.connect(lambda: self.navigate(self.IMPORT))
        self.accounts_view.accounts_changed.connect(self.refresh)
        self.import_view.imported.connect(self.refresh)
        self.import_view.restore_requested.connect(self.restore_from)
        self.settings_view.settings_changed.connect(self._on_settings_changed)
        self.settings_view.reset_requested.connect(self.confirm_reset)

        root = QWidget()
        root.setObjectName("Root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        QShortcut(QKeySequence("Ctrl+T"), self, activated=lambda: self.theme_switch.toggle())
        for i in range(len(self.PAGES)):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda i=i: self.navigate(i))

        self.apply_theme(self._settings.theme)
        self.refresh()

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
        self.stack.setCurrentIndex(index)
        button = self._nav.button(index)
        button.setChecked(True)
        button.setFocus(Qt.FocusReason.OtherFocusReason)   # el aro de foco acompana a la pestana activa
        if index == self.HELP:
            self.help_view.ensure_built()
        elif index == self.EXPORT:
            self.export_view.refresh()

    def refresh(self) -> None:
        self.dashboard.set_data(self._svc.dashboard.load(self._settings.flow_options))
        self.accounts_view.reload()
        self.investment_view.reload()
        self.import_view.set_accounts(self._svc.accounts.accounts())
        self.export_view.refresh()

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
        self._logo.setPixmap(assets.wordmark(palette, 46))
        for pill, icon_name in self._pill_buttons.values():
            pill.setIcon(icons.button_icon(icon_name, palette))
        if self.theme_switch.isChecked() != (name == "dark"):
            self.theme_switch.setChecked(name == "dark")
        self.theme_switch.update()
        self.dashboard.refresh_theme()
        self.accounts_view.refresh_theme()
        self.investment_view.refresh_theme()
        self._settings = replace(self._settings, theme=name)
        self.settings_view.set_theme(name)
        if persist:
            self._svc.settings.save(self._settings)

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self._settings = replace(settings, theme=self._settings.theme)
        self._svc.settings.save(self._settings)
        self.refresh()
