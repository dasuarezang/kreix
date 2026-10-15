"""Aviso flotante y breve (como un "snackbar"): confirma una accion y, si se puede, ofrece deshacerla."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
from core.i18n import tr

DURATION_MS = 7000
MARGIN_BOTTOM = 28


class Toast(QFrame):
    undo_clicked = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self._text = QLabel("")
        self._text.setObjectName("ToastText")
        self._text.setWordWrap(True)
        self.undo_button = QPushButton(tr("Deshacer"))
        self.undo_button.setObjectName("ToastAction")
        self.undo_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_button.clicked.connect(self._on_undo)
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("ToastClose")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setAccessibleName(tr("Cerrar aviso"))
        self.close_button.clicked.connect(self.hide)
        row = QHBoxLayout(self)
        row.setContentsMargins(20, 12, 10, 12)
        row.setSpacing(12)
        row.addWidget(self._text, 1)
        row.addWidget(self.undo_button)
        row.addWidget(self.close_button)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DURATION_MS)
        self._timer.timeout.connect(self.hide)
        self.setAccessibleName(tr("Aviso"))
        self.hide()

    @property
    def text(self) -> str:
        return self._text.text()

    def show_message(self, text: str, undoable: bool = False) -> None:
        self._text.setText(text)
        self.undo_button.setVisible(undoable)
        self.setMaximumWidth(max(min(self.parentWidget().width() - 64, 680), 240))
        self.setMinimumWidth(min(500, self.maximumWidth()))
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start()
        self.setAccessibleDescription(text)

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.setMaximumWidth(max(min(parent.width() - 64, 680), 240))
        self.adjustSize()
        self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - MARGIN_BOTTOM)

    def _on_undo(self) -> None:
        self.hide()
        self.undo_clicked.emit()
