"""Pagina Exportar: un unico archivo .kreix con todos los datos, para guardarlos o llevarlos a otro equipo."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from services.transfer_service import EXTENSION, DataSummary, TransferError, TransferService
from ui.widgets.cards import PageHeader, repolish
from core.i18n import tr, N_


NO_DATA = N_("Todavía no hay datos que exportar.")


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


class ExportView(QWidget):
    exported = Signal(str)

    def __init__(self, service: TransferService, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._service = service
        self._seal = None                  # funcion de cifrado del almacen; None = sin cifrado disponible

        header = PageHeader(tr("Exportar"), eyebrow=tr("Copia de seguridad"),
                            subtitle=tr("Guarda todos tus datos en un único archivo para hacer una copia o llevarlos a otro ordenador."))

        self._contents = QLabel("")
        self._contents.setWordWrap(True)
        self._contents.setTextFormat(Qt.TextFormat.RichText)
        self.button = QPushButton(tr("Exportar datos…"))
        self.button.setObjectName("Primary")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.choose_and_export)
        self._status = QLabel("")
        self._status.setObjectName("Small")
        self._status.setWordWrap(True)
        self._status.setProperty("state", "")

        action_row = QHBoxLayout()
        action_row.addWidget(self.button)
        action_row.addWidget(self._status, 1)

        self.encrypt = QCheckBox(tr("Cifrar el archivo con mi contraseña maestra"))
        self.encrypt.setChecked(True)
        self.encrypt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.encrypt.toggled.connect(self._update_warning)
        self.encrypt_note = self._note(
            tr("Para abrirlo, en este u otro ordenador, hará falta la contraseña maestra que tienes ahora."))
        self.encrypt.hide()                # solo se ofrece cuando hay almacen cifrado (set_sealer)
        self.encrypt_note.hide()

        what = self._card(tr("Qué se exporta"), self._contents, self._note(
            tr("Cuentas, movimientos, categorías, operaciones, cartera y ajustes. Todo tal cual está ahora.")),
            self.encrypt, self.encrypt_note, action_row)

        self.warning = warning = QFrame()
        warning.setObjectName("Banner")
        warn_lay = QVBoxLayout(warning)
        warn_lay.setContentsMargins(18, 14, 18, 14)
        warn_head = QLabel(tr("<b>El archivo no está cifrado</b>"))
        warn_head.setTextFormat(Qt.TextFormat.RichText)
        warn_text = QLabel(tr("Contiene tu información financiera. Guárdalo en un sitio seguro y no lo compartas."))
        warn_text.setWordWrap(True)
        warn_lay.addWidget(warn_head)
        warn_lay.addWidget(warn_text)

        steps = self._card(
            tr("Cómo llevarlo a otro ordenador"),
            self._step("1", tr("Instala Kreix en el otro ordenador y ábrelo.")),
            self._step("2", tr("Ve a Importar y arrastra el archivo {EXTENSION} a la zona de importación.").format(EXTENSION=EXTENSION)),
            self._step("3", tr("Confirma. Verás exactamente los mismos datos que aquí.")),
            self._note(tr("Importar un archivo .kreix reemplaza los datos que hubiera en ese ordenador.")),
        )

        body = QWidget()
        body.setObjectName("Page")
        col = QVBoxLayout(body)
        col.setContentsMargins(48, 40, 48, 48)
        col.setSpacing(26)
        for w in (header, what, warning, steps):
            col.addWidget(w)
        col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh()

    # ------------------------------------------------------------------ cifrado
    def set_sealer(self, seal) -> None:
        """`seal` cifra los bytes con la contrasena maestra; None si los datos no estan en un almacen cifrado."""
        self._seal = seal
        self.encrypt.setVisible(seal is not None)
        self.encrypt_note.setVisible(seal is not None)
        self._update_warning()

    def encrypting(self) -> bool:
        return self._seal is not None and self.encrypt.isChecked()

    def _update_warning(self) -> None:
        self.warning.setVisible(not self.encrypting())     # el aviso de "no cifrado" solo cuando de verdad no lo esta

    # ------------------------------------------------------------------ piezas
    @staticmethod
    def _note(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Small")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _step(number: str, text: str) -> QWidget:
        badge = QLabel(number)
        badge.setObjectName("StepBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(26, 26)
        label = QLabel(text)
        label.setWordWrap(True)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(label, 1)
        holder = QWidget()
        holder.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        return holder

    @staticmethod
    def _card(title: str, *items) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)
        heading = QLabel(title.upper())
        heading.setObjectName("CardTitle")
        lay.addWidget(heading)
        for item in items:
            if isinstance(item, QWidget):
                lay.addWidget(item)
            else:
                lay.addLayout(item)
        return card

    # ------------------------------------------------------------------ datos
    def refresh(self) -> None:
        s = self._service.summary()
        self._show_summary(s)
        self.button.setEnabled(not s.is_empty)
        if s.is_empty:
            self._set_status(tr(NO_DATA), "")
        elif self._status.text() == tr(NO_DATA):        # ya hay datos: se quita el aviso viejo
            self._set_status("", "")

    def _show_summary(self, s: DataSummary) -> None:
        if s.is_empty:
            self._contents.setText(tr("Todavía no hay nada guardado."))
            return
        lines = [
            _plural(s.accounts, tr("cuenta"), tr("cuentas")),
            _plural(s.transactions, tr("movimiento bancario"), tr("movimientos bancarios")),
            _plural(s.operations, tr("operación de inversión"), tr("operaciones de inversión")),
            _plural(s.investments, tr("fondo"), tr("fondos")),
        ]
        self._contents.setText("<br>".join(f"• {line}" for line in lines))

    def _set_status(self, text: str, state: str) -> None:
        self._status.setText(text)
        self._status.setProperty("state", state)
        repolish(self._status)

    def suggested_name(self) -> str:
        return f"kreix-datos-{date.today().isoformat()}{EXTENSION}"

    def choose_and_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, tr("Exportar datos"), self.suggested_name(),
                                              tr("Datos de Kreix (*{EXTENSION})").format(EXTENSION=EXTENSION))
        if path:
            self.export_to(path)

    def export_to(self, path: str) -> bool:
        try:
            self._service.export_to(path, self._seal if self.encrypting() else None)
        except (TransferError, OSError) as exc:
            self._set_status(tr("No se pudo exportar: {exc}").format(exc=exc), "error")
            return False
        final = Path(path if path.lower().endswith(EXTENSION) else path + EXTENSION)
        size_kb = max(final.stat().st_size // 1024, 1) if final.exists() else 0
        self._set_status(tr("Exportado en {final} ({size_kb} KB).").format(final=final, size_kb=size_kb), "ok")
        self.exported.emit(str(final))
        return True
