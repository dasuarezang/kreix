"""Zona de importacion: arrastrar y soltar archivos, o hacer clic para elegirlos."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog, QFrame, QLabel, QPushButton, QVBoxLayout

from ui.widgets.cards import StripeMark
from ui.widgets.cards import repolish
from core.i18n import tr, N_

# Primero "todos": los extractos de algunos bancos no llevan extension (p. ej. "extractImagin").
FILE_FILTER = N_("Todos los archivos (*);;Extractos bancarios (*.csv *.txt *.xlsx *.xlsm *.xls)")


def local_files(mime_data) -> list[str]:
    """Rutas de archivos (no carpetas) incluidas en un arrastre."""
    paths = [Path(u.toLocalFile()) for u in mime_data.urls() if u.isLocalFile()]
    return [str(p) for p in paths if p.is_file()]


class DropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(230)
        self.setProperty("dragging", False)

        logo = StripeMark(112, 58, centered=True)
        self._title = QLabel(tr("Arrastra aquí tus extractos"))
        self._title.setObjectName("H1")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel(tr("CSV o Excel de Imagin y MyInvestor, con o sin extensión; también el histórico de precios de un fondo. Y un archivo .kreix exportado desde otro Kreix."))
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button = QPushButton(tr("Seleccionar archivos"))
        button.setObjectName("Primary")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(self.browse)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)
        layout.addWidget(hint)
        layout.addSpacing(6)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName(tr("Zona de importación"))
        self.setAccessibleDescription(tr("Arrastra archivos CSV o Excel, o usa el botón Seleccionar archivos"))

    def browse(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, tr("Seleccionar extractos"), "", tr(FILE_FILTER))
        if paths:
            self.files_dropped.emit(paths)

    def _set_dragging(self, value: bool) -> None:
        self.setProperty("dragging", value)
        self._title.setText(tr("Suelta los archivos para importarlos") if value else tr("Arrastra aquí tus extractos"))
        repolish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if local_files(event.mimeData()):
            event.acceptProposedAction()
            self._set_dragging(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_dragging(False)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_dragging(False)
        files = local_files(event.mimeData())
        if files:
            event.acceptProposedAction()
            self.files_dropped.emit(files)
