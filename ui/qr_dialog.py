"""Pasar los datos al movil: un codigo QR animado que la app movil lee con la camara (ver core/qr_transfer.py)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import segno
from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from core.i18n import tr
from core.qr_transfer import Encoder, pack
from services.transfer_service import TransferService
from ui.widgets.brand_dialog import BrandDialog

FRAME_MS = 160          # unos 6 codigos por segundo: los lee bien la camara de un movil normal
QUIET = 4               # margen blanco alrededor del codigo (en modulos), el que pide la norma para leerlo


class QrCode(QWidget):
    """Un codigo QR en negro sobre blanco (las camaras leen mejor el contraste clasico, tambien en modo oscuro)."""

    def __init__(self) -> None:
        super().__init__()
        self._matrix: list[list[bool]] = []
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        return QSize(460, 460)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return width

    def set_data(self, data: bytes) -> None:
        code = segno.make_qr(data, mode="byte", error="l", boost_error=False)
        self._matrix = [[bool(v) for v in row] for row in code.matrix]
        self.update()

    def paintEvent(self, _event) -> None:
        if not self._matrix:
            return
        painter = QPainter(self)
        modules = len(self._matrix) + 2 * QUIET
        # cada modulo, un numero entero de pixeles fisicos: con tamanos fraccionarios los modulos salen desiguales y la
        # camara no lo lee
        ratio = self.devicePixelRatioF()
        cell = max(1, int(min(self.width(), self.height()) * ratio // modules)) / ratio
        side = cell * modules
        left = round((self.width() - side) / 2 * ratio) / ratio
        top = round((self.height() - side) / 2 * ratio) / ratio
        painter.fillRect(QRectF(left, top, side, side), QColor("#FFFFFF"))
        black = QColor("#000000")
        for y, row in enumerate(self._matrix):
            for x, dark in enumerate(row):
                if dark:
                    painter.fillRect(QRectF(left + (x + QUIET) * cell, top + (y + QUIET) * cell, cell, cell), black)


class QrTransferDialog(BrandDialog):
    """Ensena la exportacion (cifrada con la contrasena maestra) como una secuencia de codigos QR que no se acaba."""

    def __init__(self, transfer: TransferService, seal=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Pasar al móvil"))
        self.resize(620, 820)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "movil.kreix"
            transfer.export_to(path, seal)
            self.encoder = Encoder(pack(path.read_bytes()))
        self.seq = 0
        self.code = QrCode()
        steps = QLabel(tr("En el móvil, abre Kreix y ve a Datos > Escanear el código QR. Apunta la cámara a este código hasta que se "
                          "complete: no importa si se salta algún fotograma."))
        steps.setObjectName("Muted")
        steps.setWordWrap(True)
        note = QLabel(tr("Al terminar, el móvil te pedirá la contraseña maestra de este ordenador.") if seal is not None
                      else tr("Los datos viajan sin cifrar: que nadie más esté mirando la pantalla."))
        note.setObjectName("Small")
        note.setWordWrap(True)
        self.counter = QLabel("")
        self.counter.setObjectName("Small")
        close = QPushButton(tr("Cerrar"))
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addWidget(self.counter, 1)
        bottom.addWidget(close)

        inner = self.frame(tr("Pasar al móvil"), tr("Copia todos tus datos a la app de Kreix del móvil sin cables ni conexión: "
                                                    "solo con la cámara."))
        inner.addWidget(steps)
        inner.addWidget(self.code, 1)
        inner.addWidget(note)
        inner.addLayout(bottom)

        self.timer = QTimer(self)
        self.timer.setInterval(FRAME_MS)
        self.timer.timeout.connect(self.advance)
        self.advance()
        self.timer.start()

    def advance(self) -> None:
        self.code.set_data(self.encoder.frame(self.seq))
        self.counter.setText(tr("{k} bloques  ·  código {n}").format(k=self.encoder.k, n=self.seq + 1))
        self.seq += 1

    def done(self, result: int) -> None:
        self.timer.stop()
        super().done(result)
