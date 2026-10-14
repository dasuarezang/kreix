"""Pantalla de importacion de extractos."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QDateEdit, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from services.import_service import FileReport, ImportReport, ImportService
from ui.widgets.cards import repolish
from ui.widgets.dropzone import DropZone


def _clear(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


class ResultRow(QFrame):
    def __init__(self, report: FileReport) -> None:
        super().__init__()
        self.setObjectName("Card")
        if not report.ok:
            state, label = "error", "Error"
        elif report.warnings:
            state, label = "warn", "Con avisos"
        else:
            state, label = "ok", "Importado"
        pill = QLabel(label)
        pill.setObjectName("Pill")
        pill.setProperty("state", state)
        repolish(pill)

        name = QLabel(report.file_name)
        name.setObjectName("H2")
        if report.ok:
            detail = f"{report.kind_label}  ·  {report.inserted} nuevos"
            if report.skipped:
                detail += f"  ·  {report.skipped} ya existían"
        else:
            detail = report.error or ""
        sub = QLabel(detail)
        sub.setObjectName("Muted")
        sub.setWordWrap(True)

        top = QHBoxLayout()
        top.addWidget(name)
        top.addStretch(1)
        top.addWidget(pill)
        col = QVBoxLayout(self)
        col.setContentsMargins(18, 14, 18, 14)
        col.setSpacing(4)
        col.addLayout(top)
        col.addWidget(sub)
        for warning in report.warnings:
            w = QLabel(f"• {warning}")
            w.setObjectName("Small")
            w.setWordWrap(True)
            col.addWidget(w)


class ImportView(QWidget):
    imported = Signal()

    def __init__(self, service: ImportService, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._service = service

        title = QLabel("Importar extractos")
        title.setObjectName("H1")
        intro = QLabel("Los archivos se procesan en tu equipo. Reimportar un extracto no duplica movimientos.")
        intro.setObjectName("Muted")

        self.dropzone = DropZone()
        self.dropzone.files_dropped.connect(self.import_paths)

        self.as_of = QDateEdit(QDate.currentDate())
        self.as_of.setCalendarPopup(True)
        self.as_of.setDisplayFormat("dd/MM/yyyy")
        self.as_of.setAccessibleName("Fecha de la cartera")
        as_of_label = QLabel("Fecha de la cartera")
        as_of_label.setObjectName("H2")
        as_of_hint = QLabel("El extracto de cartera de MyInvestor no incluye fecha: indica a qué día corresponde.")
        as_of_hint.setObjectName("Small")
        as_of_row = QHBoxLayout()
        as_of_col = QVBoxLayout()
        as_of_col.setSpacing(2)
        as_of_col.addWidget(as_of_label)
        as_of_col.addWidget(as_of_hint)
        as_of_row.addLayout(as_of_col, 1)
        as_of_row.addWidget(self.as_of)

        self._results = QVBoxLayout()
        self._results.setSpacing(10)
        results_title = QLabel("Resultado")
        results_title.setObjectName("H2")
        self._results_title = results_title
        results_title.hide()

        body = QWidget()
        body.setObjectName("Page")
        col = QVBoxLayout(body)
        col.setContentsMargins(32, 28, 32, 32)
        col.setSpacing(16)
        col.addWidget(title)
        col.addWidget(intro)
        col.addWidget(self.dropzone)
        col.addLayout(as_of_row)
        col.addSpacing(6)
        col.addWidget(results_title)
        col.addLayout(self._results)
        col.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def portfolio_date(self) -> date:
        qd = self.as_of.date()
        return date(qd.year(), qd.month(), qd.day())

    def import_paths(self, paths: list[str]) -> ImportReport:
        report = self._service.import_files(paths, self.portfolio_date())
        self.show_report(report)
        if report.total_inserted:
            self.imported.emit()
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
            head = QLabel("<b>La cartera no cuadra con las operaciones importadas</b>")
            head.setTextFormat(Qt.TextFormat.RichText)
            lay.addWidget(head)
            for warning in report.reconciliation_warnings:
                w = QLabel(f"• {warning}")
                w.setWordWrap(True)
                lay.addWidget(w)
            tip = QLabel("Exporta desde MyInvestor el historial completo de operaciones y vuelve a importarlo.")
            tip.setObjectName("Small")
            tip.setWordWrap(True)
            lay.addWidget(tip)
            self._results.addWidget(box)
