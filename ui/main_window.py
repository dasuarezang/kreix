"""Ventana principal: barra lateral, paginas y cambio de tema en caliente."""
from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from services.dashboard_service import DashboardService
from services.import_service import ImportService
from services.settings_service import AppSettings, SettingsService
from ui import assets, theme
from ui.views.dashboard_view import DashboardView
from ui.views.import_view import ImportView
from ui.views.settings_view import VERSION, SettingsView
from ui.widgets.switch import SwitchToggle


@dataclass(frozen=True, slots=True)
class Services:
    importer: ImportService
    dashboard: DashboardService
    settings: SettingsService


class MainWindow(QMainWindow):
    PAGES = ("Resumen", "Importar", "Ajustes")

    def __init__(self, services: Services, db_path: str) -> None:
        super().__init__()
        self._svc = services
        self._settings = services.settings.load()
        self.setWindowTitle("Kreix")
        self.setWindowIcon(assets.app_icon())
        self.resize(1280, 820)
        self.setMinimumSize(1040, 700)

        self.dashboard = DashboardView()
        self.import_view = ImportView(services.importer)
        self.settings_view = SettingsView(self._settings, db_path)
        self.stack = QStackedWidget()
        for page in (self.dashboard, self.import_view, self.settings_view):
            self.stack.addWidget(page)

        self.dashboard.go_import.connect(lambda: self.navigate(1))
        self.import_view.imported.connect(self.refresh)
        self.settings_view.settings_changed.connect(self._on_settings_changed)

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
        for i, name in enumerate(self.PAGES):
            btn = QPushButton(name)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{name} (Ctrl+{i + 1})")
            btn.clicked.connect(lambda _=False, i=i: self.navigate(i))
            self._nav.addButton(btn, i)
            col.addWidget(btn)
        self._nav.button(0).setChecked(True)
        col.addStretch(1)

        self.theme_switch = SwitchToggle(self._settings.theme == "dark")
        self.theme_switch.setAccessibleName("Modo oscuro")
        self.theme_switch.setToolTip("Cambiar entre modo oscuro y claro (Ctrl+T)")
        self.theme_switch.toggled.connect(lambda on: self.apply_theme("dark" if on else "light", persist=True))
        self._theme_label = QLabel("Modo oscuro")
        self._theme_label.setObjectName("H2")
        row = QHBoxLayout()
        row.addWidget(self._theme_label, 1)
        row.addWidget(self.theme_switch)
        col.addLayout(row)
        col.addSpacing(10)
        foot = QLabel(f"Kreix {VERSION}  ·  datos solo en tu equipo")
        foot.setObjectName("SidebarFoot")
        foot.setWordWrap(True)
        col.addWidget(foot)
        return bar

    # ------------------------------------------------------------------ comportamiento
    def navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self._nav.button(index).setChecked(True)

    def refresh(self) -> None:
        self.dashboard.set_data(self._svc.dashboard.load(self._settings.flow_options))

    def apply_theme(self, name: str, persist: bool = False) -> None:
        palette = theme.PALETTES[name]
        theme.set_current(palette)
        QApplication.instance().setStyleSheet(theme.stylesheet(palette))
        self._logo.setPixmap(assets.wordmark(palette, 46))
        self._theme_label.setText("Modo oscuro" if name == "dark" else "Modo claro")
        if self.theme_switch.isChecked() != (name == "dark"):
            self.theme_switch.setChecked(name == "dark")
        self.theme_switch.update()
        self.dashboard.refresh_theme()
        self._settings = replace(self._settings, theme=name)
        self.settings_view.set_theme(name)
        if persist:
            self._svc.settings.save(self._settings)

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self._settings = replace(settings, theme=self._settings.theme)
        self._svc.settings.save(self._settings)
        self.refresh()
