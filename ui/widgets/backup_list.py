"""Lista de las copias de seguridad guardadas: fecha, tamano y un boton para restaurar cada una."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.i18n import tr
from services.backup_service import BackupFile
from ui.format import fmt_date


def human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def moment_label(moment) -> str:
    return f"{fmt_date(moment.date())}  ·  {moment.hour:02d}:{moment.minute:02d}"


class BackupList(QWidget):
    restore_requested = Signal(str)         # ruta de la copia elegida

    def __init__(self) -> None:
        super().__init__()
        self._rows = QVBoxLayout()
        self._rows.setSpacing(2)
        self._empty = QLabel(tr("Todavía no hay copias. La primera se hace sola al abrir Kreix."))
        self._empty.setObjectName("Small")
        self._empty.setWordWrap(True)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        col.addWidget(self._empty)
        col.addLayout(self._rows)
        self.buttons: list[QPushButton] = []

    def set_files(self, files: list[BackupFile]) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.buttons = []
        self._empty.setVisible(not files)
        for backup in files:
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 2, 0, 2)
            when = QLabel(moment_label(backup.moment))
            when.setObjectName("H2")
            size = QLabel(human_size(backup.size))
            size.setObjectName("Muted")
            restore = QPushButton(tr("Restaurar…"))
            restore.setCursor(Qt.CursorShape.PointingHandCursor)
            restore.setAccessibleName(tr("Restaurar la copia del {when}").format(when=moment_label(backup.moment)))
            restore.clicked.connect(lambda _=False, path=str(backup.path): self.restore_requested.emit(path))
            lay.addWidget(when)
            lay.addWidget(size, 1)
            lay.addWidget(restore)
            self._rows.addWidget(row)
            self.buttons.append(restore)
