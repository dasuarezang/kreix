"""Pantalla de importacion de extractos."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core.entities import FileKind
from etl.common import ParseError
from services.accounts_service import AccountInfo
from services.import_service import FilePreview, FileReport, ImportReport, ImportService
from services.transfer_service import EXTENSION
from ui.popups import Combo
from ui.feedback import Feedback, snapshot_of, tell
from ui.format import fmt_date
from ui.mapping_dialog import MappingDialog
from ui.widgets.cards import PageHeader, repolish
from ui.widgets.dropzone import DropZone
from ui.widgets.section_card import GroupCard
from core.i18n import tr, N_


def _clear(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


class ResultRow(QFrame):
    def __init__(self, report: FileReport) -> None:
        super().__init__()
        self.setObjectName("ListRow")
        if not report.ok:
            state, label = "error", tr("Error")
        elif report.warnings:
            state, label = "warn", tr("Con avisos")
        else:
            state, label = "ok", tr("Importado")
        pill = QLabel(label)
        pill.setObjectName("Pill")
        pill.setProperty("state", state)
        repolish(pill)

        name = QLabel(report.file_name)
        name.setObjectName("H2")
        if report.ok:
            detail = tr("{kind_label}  ·  {inserted} nuevos").format(kind_label=report.kind_label, inserted=report.inserted)
            if report.updated:
                detail += tr("  ·  {updated} actualizados").format(updated=report.updated)
            if report.skipped:
                detail += tr("  ·  {skipped} ya existían").format(skipped=report.skipped)
        else:
            detail = report.explanation
        sub = QLabel(detail)
        sub.setObjectName("Muted")
        sub.setWordWrap(True)

        top = QHBoxLayout()
        top.addWidget(name)
        top.addStretch(1)
        top.addWidget(pill)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 18, 0, 18)
        col.setSpacing(6)
        col.addLayout(top)
        col.addWidget(sub)
        for warning in report.warnings:
            w = QLabel(f"• {warning}")
            w.setObjectName("Small")
            w.setWordWrap(True)
            col.addWidget(w)


ROW_NAMES = {
    FileKind.IMAGIN_STATEMENT: (N_("movimiento"), N_("movimientos")),
    FileKind.BANK_STATEMENT: (N_("movimiento"), N_("movimientos")),
    FileKind.MYINVESTOR_OPERATIONS: (N_("operación"), N_("operaciones")),
    FileKind.MYINVESTOR_PORTFOLIO: (N_("posición"), N_("posiciones")),
}


def plural(n: int, kind: FileKind | None) -> str:
    one, many = ROW_NAMES.get(kind, (N_("fila"), N_("filas")))
    return f"{n} {tr(one) if n == 1 else tr(many)}"


class PreviewRow(QFrame):
    """Un archivo leido y lo que pasara al importarlo: cuantas filas, de cuando a cuando, nuevas y repetidas."""

    map_requested = Signal(str)        # el usuario quiere asignar las columnas de este archivo (ruta)

    def __init__(self, preview: FilePreview) -> None:
        super().__init__()
        self.setObjectName("ListRow")
        self.map_button: QPushButton | None = None
        if not preview.ok:
            state, label = "error", tr("No se puede importar")
        elif not preview.changes_data:
            state, label = "warn", tr("Nada nuevo")
        else:
            state, label = "ok", tr("Listo para importar")
        pill = QLabel(label)
        pill.setObjectName("Pill")
        pill.setProperty("state", state)
        repolish(pill)
        name = QLabel(preview.file_name)
        name.setObjectName("H2")
        lines: list[str] = []
        if preview.ok:
            read = f"{preview.kind_label}  ·  {plural(preview.rows, preview.kind)}"
            if preview.first and preview.last:
                read += (tr("  ·  del {first} al {last}").format(first=fmt_date(preview.first), last=fmt_date(preview.last))
                         if preview.first != preview.last else f"  ·  {fmt_date(preview.first)}")
            lines.append(read)
            parts = [tr("{new} nuevos").format(new=preview.new)]
            if preview.updated:
                parts.append(tr("{updated} se actualizarán").format(updated=preview.updated))
            if preview.existing:
                parts.append(tr("{existing} ya estaban importados y se ignoran").format(existing=preview.existing))
            lines.append("  ·  ".join(parts))
        else:
            lines.append(preview.explanation)
        top = QHBoxLayout()
        top.addWidget(name)
        top.addStretch(1)
        top.addWidget(pill)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 18, 0, 18)
        col.setSpacing(6)
        col.addLayout(top)
        for i, text in enumerate(lines):
            label_ = QLabel(text)
            label_.setObjectName("Muted" if i == 0 or not preview.ok else "Small")
            label_.setWordWrap(True)
            col.addWidget(label_)
        for warning in preview.warnings:
            w = QLabel(f"• {warning}")
            w.setObjectName("Small")
            w.setWordWrap(True)
            col.addWidget(w)
        if preview.unknown_format and preview.path:
            self.map_button = QPushButton(tr("Asignar las columnas…"))
            self.map_button.setObjectName("Primary")
            self.map_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.map_button.setAccessibleName(tr("Asignar las columnas de {name}").format(name=preview.file_name))
            self.map_button.clicked.connect(lambda _=False, path=preview.path: self.map_requested.emit(path))
            row = QHBoxLayout()
            row.addWidget(self.map_button)
            row.addStretch(1)
            col.addSpacing(4)
            col.addLayout(row)


class FormatRow(QWidget):
    """Un banco que Kreix ya sabe leer (formato definido por el usuario) y el boton para olvidarlo."""

    remove_requested = Signal(str)

    def __init__(self, name: str, detail: str) -> None:
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        title = QLabel(name)
        title.setObjectName("H2")
        info = QLabel(detail)
        info.setObjectName("Muted")
        info.setWordWrap(True)
        self.remove = QPushButton(tr("Olvidar"))
        self.remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove.setAccessibleName(tr("Olvidar el formato {name}").format(name=name))
        self.remove.clicked.connect(lambda _=False, n=name: self.remove_requested.emit(n))
        lay.addWidget(title)
        lay.addWidget(info, 1)
        lay.addWidget(self.remove)


class ImportView(QWidget):
    imported = Signal()
    restore_requested = Signal(str)     # se ha soltado un archivo .kreix exportado desde otro Kreix
    feedback: Feedback | None = None    # lo asigna la ventana: avisos y "Deshacer"

    def __init__(self, service: ImportService, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._service = service
        self.before_import: Callable[[], None] | None = None   # la ventana lo usa para quitar los datos de ejemplo
        self._pending: list[str] = []
        self._last_paths: list[str] = []

        header = PageHeader(tr("Importar extractos"), eyebrow=tr("Entrada de datos"),
                            subtitle=tr("Los archivos se procesan en tu equipo. Reimportar un extracto no duplica movimientos."))

        self.dropzone = DropZone()
        self.dropzone.files_dropped.connect(self.preview_paths)

        self.as_of = QDateEdit(QDate.currentDate())
        self.as_of.setCalendarPopup(True)
        self.as_of.setMinimumWidth(150)
        self.as_of.setDisplayFormat("dd/MM/yyyy")
        self.as_of.setAccessibleName(tr("Fecha de la cartera"))
        as_of_label = QLabel(tr("Fecha de la cartera"))
        as_of_label.setObjectName("H2")
        as_of_hint = QLabel(tr("El extracto de cartera de MyInvestor no incluye fecha: indica a qué día corresponde."))
        as_of_hint.setObjectName("Small")
        as_of_row = QHBoxLayout()
        as_of_row.setContentsMargins(0, 0, 0, 0)
        as_of_col = QVBoxLayout()
        as_of_col.setSpacing(2)
        as_of_col.addWidget(as_of_label)
        as_of_col.addWidget(as_of_hint)
        as_of_row.addLayout(as_of_col, 1)
        as_of_row.addWidget(self.as_of)

        self.account_combo = Combo()
        self.account_combo.setMinimumWidth(230)
        self.account_combo.setAccessibleName(tr("Cuenta de destino"))
        self.account_combo.addItem(tr("Cuenta nueva (se creará al importar)"), None)
        account_label = QLabel(tr("Cuenta de destino"))
        account_label.setObjectName("H2")
        account_hint = QLabel(tr("A qué cuenta bancaria pertenecen los extractos que importes (Imagin u otro banco)."))
        account_hint.setObjectName("Small")
        account_row = QHBoxLayout()
        account_row.setContentsMargins(0, 0, 0, 0)
        account_col = QVBoxLayout()
        account_col.setSpacing(2)
        account_col.addWidget(account_label)
        account_col.addWidget(account_hint)
        account_row.addLayout(account_col, 1)
        account_row.addWidget(self.account_combo)

        self.fund_combo = Combo()
        self.fund_combo.setMinimumWidth(230)
        self.fund_combo.setAccessibleName(tr("Fondo del histórico"))
        self.fund_combo.addItem(tr("Detectarlo por el archivo"), None)
        fund_label = QLabel(tr("Fondo del histórico"))
        fund_label.setObjectName("H2")
        fund_hint = QLabel(tr("Si importas el histórico de precios de un fondo y el archivo no lleva su ISIN, indica a qué fondo pertenece."))
        fund_hint.setObjectName("Small")
        fund_hint.setWordWrap(True)
        fund_col = QVBoxLayout()
        fund_col.setSpacing(2)
        fund_col.addWidget(fund_label)
        fund_col.addWidget(fund_hint)
        fund_row = QHBoxLayout()
        fund_row.addLayout(fund_col, 1)
        fund_row.addWidget(self.fund_combo)
        fund_row.setContentsMargins(0, 0, 0, 0)
        settings = GroupCard()                  # los tres ajustes de destino, en una sola tarjeta con filas
        for row in (account_row, as_of_row):
            holder = QWidget()
            holder.setLayout(row)
            settings.add_setting(holder)
        fund_holder = QWidget()
        fund_holder.setLayout(fund_row)
        self._fund_box = settings.add_setting(fund_holder)
        self._fund_box.hide()                 # solo cuando Kreix ya conoce algun fondo (set_funds)

        self._results = QVBoxLayout()
        self._results.setSpacing(10)
        self._preview = QVBoxLayout()
        self._preview.setSpacing(10)
        self._preview_title = QLabel(tr("Revisa antes de importar"))
        self._preview_title.setObjectName("H2")
        self._preview_hint = QLabel(tr("Esto es lo que Kreix ha leído. Todavía no se ha guardado nada."))
        self._preview_hint.setObjectName("Small")
        self.cancel_button = QPushButton(tr("Cancelar"))
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self.cancel_preview)
        self.confirm_button = QPushButton(tr("Importar"))
        self.confirm_button.setObjectName("Primary")
        self.confirm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_button.clicked.connect(self.confirm_import)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.confirm_button)
        self._preview_box = QWidget()
        box = QVBoxLayout(self._preview_box)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        box.addWidget(self._preview_title)
        box.addWidget(self._preview_hint)
        box.addLayout(self._preview)
        box.addLayout(actions)
        self._preview_box.hide()
        self._formats_title = QLabel(tr("Bancos que ya conozco"))
        self._formats_title.setObjectName("H2")
        self._formats_hint = QLabel(tr("Formatos que definiste tú: los archivos con esas columnas se leen solos."))
        self._formats_hint.setObjectName("Small")
        self._formats = QVBoxLayout()
        self._formats.setSpacing(2)
        self._formats_box = QWidget()
        formats_col = QVBoxLayout(self._formats_box)
        formats_col.setContentsMargins(0, 0, 0, 0)
        formats_col.setSpacing(6)
        formats_col.addWidget(self._formats_title)
        formats_col.addWidget(self._formats_hint)
        formats_col.addLayout(self._formats)
        self._formats_box.hide()
        results_title = QLabel(tr("Resultado"))
        results_title.setObjectName("H2")
        self._results_title = results_title
        results_title.hide()

        body = QWidget()
        body.setObjectName("Page")
        col = QVBoxLayout(body)
        col.setContentsMargins(48, 40, 48, 48)
        col.setSpacing(26)
        col.addWidget(header)
        col.addWidget(self.dropzone)
        col.addWidget(settings)
        col.addSpacing(6)
        col.addWidget(self._preview_box)
        col.addWidget(results_title)
        col.addLayout(self._results)
        col.addWidget(self._formats_box)
        col.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh_formats()

    # ------------------------------------------------------------------ bancos definidos por el usuario
    def refresh_formats(self) -> None:
        """La lista de formatos guardados (se oculta si no hay ninguno)."""
        _clear(self._formats)
        formats = self._service.formats()
        for mapping in formats:
            if mapping.uses_two_columns:
                money = tr("ingresos «{income}» y gastos «{expense}»").format(income=mapping.income, expense=mapping.expense)
            else:
                money = tr("importe «{amount}»").format(amount=mapping.amount)
            detail = tr("fecha «{date}», concepto «{description}», {money}").format(
                date=mapping.date, description=mapping.description, money=money)
            row = FormatRow(mapping.name, detail)
            row.remove_requested.connect(self.forget_format)
            self._formats.addWidget(row)
        self._formats_box.setVisible(bool(formats))

    def forget_format(self, name: str) -> None:
        snapshot = snapshot_of(self.feedback)
        if self._service.delete_format(name):
            self.refresh_formats()
            tell(self.feedback, tr("Formato «{name}» olvidado. Los movimientos ya importados no cambian.").format(name=name), snapshot)
        elif snapshot is not None:
            self.feedback.remove(snapshot)

    def open_mapping(self, path: str) -> bool:
        """Abre el asistente para asignar las columnas de un archivo desconocido; si se guarda, vuelve a leer lo pendiente."""
        try:
            dialog = MappingDialog(self._service, path, self)
        except (ParseError, OSError) as exc:
            QMessageBox.warning(self, tr("No se puede leer el archivo"), str(exc))
            return False
        snapshot = snapshot_of(self.feedback)
        accepted = dialog.exec() == MappingDialog.DialogCode.Accepted
        dialog.deleteLater()
        if not accepted:
            if snapshot is not None:
                self.feedback.remove(snapshot)
            return False
        self.refresh_formats()
        tell(self.feedback, tr("Formato guardado: Kreix ya sabe leer este banco."), snapshot)
        if self._last_paths:
            self.preview_paths(list(self._last_paths))
        return True

    def set_accounts(self, accounts: list[AccountInfo]) -> None:
        keep = self.account_combo.currentData()
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        if accounts:
            for a in accounts:
                self.account_combo.addItem(a.name, a.id)
            index = self.account_combo.findData(keep)
            self.account_combo.setCurrentIndex(max(index, 0))
        else:
            self.account_combo.addItem(tr("Cuenta nueva (se creará al importar)"), None)
        self.account_combo.blockSignals(False)

    def set_funds(self, funds: list[tuple[str, str]]) -> None:
        """Los fondos conocidos, para decir a cual pertenece un historico de precios que no trae el ISIN."""
        keep = self.fund_combo.currentData()
        self.fund_combo.blockSignals(True)
        self.fund_combo.clear()
        self.fund_combo.addItem(tr("Detectarlo por el archivo"), None)
        for isin, name in funds:
            self.fund_combo.addItem(name, isin)
        index = self.fund_combo.findData(keep) if keep is not None else 0
        self.fund_combo.setCurrentIndex(max(index, 0))
        self.fund_combo.blockSignals(False)
        self._fund_box.setVisible(bool(funds))

    def portfolio_date(self) -> date:
        qd = self.as_of.date()
        return date(qd.year(), qd.month(), qd.day())

    def preview_paths(self, paths: list[str]) -> None:
        """Lo que se suelta o se elige: se lee y se ensena que pasaria; se guarda al pulsar Importar."""
        backups = [p for p in paths if p.lower().endswith(EXTENSION)]
        paths = [p for p in paths if p not in backups]
        if backups:
            self.restore_requested.emit(backups[0])
            if not paths:
                return
        self._last_paths = list(paths)
        previews = self._service.preview(paths, self.portfolio_date(), self.account_combo.currentData(),
                                         self.fund_combo.currentData())
        _clear(self._preview)
        for preview in previews:
            row = PreviewRow(preview)
            row.map_requested.connect(self.open_mapping)
            self._preview.addWidget(row)
        self._pending = [p for p, preview in zip(paths, previews) if preview.ok]
        ready = [pr for pr in previews if pr.changes_data]
        self.confirm_button.setEnabled(bool(ready))
        if ready:
            total = sum(pr.new + pr.updated for pr in ready)
            self.confirm_button.setText(tr("Importar {total} filas nuevas").format(total=total) if total != 1 else tr("Importar 1 fila nueva"))
        else:
            self.confirm_button.setText(tr("No hay nada nuevo que importar"))
        self._preview_box.show()
        self._results_title.hide()
        _clear(self._results)

    def cancel_preview(self) -> None:
        self._pending = []
        self._preview_box.hide()
        _clear(self._preview)

    def confirm_import(self) -> ImportReport | None:
        paths, self._pending = self._pending, []
        self._preview_box.hide()
        _clear(self._preview)
        return self.import_paths(paths) if paths else None

    def import_paths(self, paths: list[str]) -> ImportReport | None:
        backups = [p for p in paths if p.lower().endswith(EXTENSION)]
        paths = [p for p in paths if p not in backups]
        if backups:
            self.restore_requested.emit(backups[0])
            if not paths:
                return None
        if self.before_import is not None:
            self.before_import()
        snapshot = snapshot_of(self.feedback)
        report = self._service.import_files(paths, self.portfolio_date(), self.account_combo.currentData(),
                                            self.fund_combo.currentData())
        self.show_report(report)
        if report.total_changed:
            self.imported.emit()
            added = sum(f.inserted for f in report.files)
            changed = sum(f.updated for f in report.files)
            text = tr("Importado: {added} nuevos").format(added=added) + (tr(" y {changed} actualizados").format(changed=changed) if changed else "") + "."
            tell(self.feedback, text, snapshot)
        else:
            tell(self.feedback, tr("No había nada nuevo que importar.") if any(f.ok for f in report.files)
                 else tr("No se ha podido importar ningún archivo."))
            if snapshot is not None:
                self.feedback.remove(snapshot)       # no cambio nada: no hay nada que deshacer
        return report

    def show_report(self, report: ImportReport) -> None:
        _clear(self._results)
        self._results_title.show()
        for file_report in report.files:
            self._results.addWidget(ResultRow(file_report))
        if report.reconciliation_warnings:
            box = QFrame()
            box.setObjectName("Banner")
            lay = QVBoxLayout(box)
            lay.setContentsMargins(16, 12, 16, 12)
            head = QLabel(tr("<b>La cartera no cuadra con las operaciones importadas</b>"))
            head.setTextFormat(Qt.TextFormat.RichText)
            lay.addWidget(head)
            for warning in report.reconciliation_warnings:
                w = QLabel(f"• {warning}")
                w.setWordWrap(True)
                lay.addWidget(w)
            tip = QLabel(tr("Exporta desde MyInvestor el historial completo de operaciones y vuelve a importarlo."))
            tip.setObjectName("Small")
            tip.setWordWrap(True)
            lay.addWidget(tip)
            self._results.addWidget(box)
