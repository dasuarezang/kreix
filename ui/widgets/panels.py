"""Paneles de la pestana Cuentas: presupuestos del periodo y pagos recurrentes."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.budget import BudgetLine
from core.recurring import Recurring, monthly_cost
from ui import fonts, theme
from ui.format import category_label, fmt_date, fmt_eur
from ui.widgets.tables import RIGHT, Column, DataTable

ROW_H = 58


class BudgetBars(QWidget):
    """Una barra por presupuesto: verde mientras sobra, amarilla cerca del tope y roja al pasarse."""

    category_clicked = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._lines: list[BudgetLine] = []
        self.setMouseTracking(True)

    def _line_at(self, pos: QPointF) -> BudgetLine | None:
        index = int(pos.y() // ROW_H)
        return self._lines[index] if 0 <= index < len(self._lines) else None

    def mouseMoveEvent(self, event) -> None:
        over = self._line_at(event.position()) is not None
        self.setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.ArrowCursor)
        self.setToolTip("Clic para ver los movimientos de esta categoría" if over else "")

    def mousePressEvent(self, event) -> None:
        line = self._line_at(event.position())
        if line is not None and event.button() == Qt.MouseButton.LeftButton:
            self.category_clicked.emit(line.category)

    def set_lines(self, lines: list[BudgetLine]) -> None:
        self._lines = lines
        self.setMinimumHeight(len(lines) * ROW_H + 4)
        self.updateGeometry()
        self.update()
        self.setAccessibleDescription("; ".join(
            f"{category_label(line.category)}: {fmt_eur(line.spent)} de {fmt_eur(line.budget)}" for line in lines))

    def sizeHint(self) -> QSize:
        return QSize(300, len(self._lines) * ROW_H + 4)

    def paintEvent(self, _event) -> None:
        pal = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        name_font, amount_font, note_font = (fonts.qfont(fonts.BODY_MEDIUM, 13), fonts.qfont(fonts.BODY_BOLD, 13),
                                             fonts.qfont(fonts.BODY, 12))
        tones = {"ok": pal.green, "warn": pal.accent, "over": pal.red}
        for i, line in enumerate(self._lines):
            top = i * ROW_H
            p.setFont(name_font)
            p.setPen(QColor(pal.text))
            p.drawText(QRectF(0, top, self.width() * 0.45, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       category_label(line.category))
            amount = f"{fmt_eur(line.spent)} de {fmt_eur(line.budget)}"
            p.setFont(amount_font)
            p.drawText(QRectF(self.width() * 0.4, top, self.width() * 0.6, 20),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, amount)
            color = QColor(tones[line.state])
            track = QRectF(0, top + 27, self.width(), 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(pal.surface_alt))
            p.drawRoundedRect(track, 4, 4)
            filled = min(float(line.ratio), 1.0)
            if filled > 0:
                p.setBrush(color)
                p.drawRoundedRect(QRectF(0, top + 27, max(self.width() * filled, 8), 8), 4, 4)
            note = (f"Te has pasado {fmt_eur(-line.remaining)}" if line.state == "over" else f"Quedan {fmt_eur(line.remaining)}")
            p.setFont(note_font)
            p.setPen(color if line.state == "over" else QColor(pal.muted))
            metrics = QFontMetricsF(note_font)
            p.drawText(QRectF(0, top + 38, self.width(), 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       metrics.elidedText(note, Qt.TextElideMode.ElideRight, self.width()))


class Panel(QFrame):
    """Tarjeta con titulo, subtitulo, un boton opcional arriba a la derecha y un cuerpo."""

    def __init__(self, title: str, subtitle: str, body: QWidget, action: QPushButton | None = None) -> None:
        super().__init__()
        self.setObjectName("Card")
        self.heading = QLabel(title)
        self.heading.setObjectName("H2")
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("Small")
        self.subtitle.setWordWrap(True)
        top = QHBoxLayout()
        top.setSpacing(10)
        column = QVBoxLayout()
        column.setSpacing(2)
        column.addWidget(self.heading)
        column.addWidget(self.subtitle)
        top.addLayout(column, 1)
        if action is not None:
            top.addWidget(action, 0, Qt.AlignmentFlag.AlignTop)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(body, 1)
        self.setAccessibleName(title)


class BudgetPanel(Panel):
    edit_requested = Signal()

    def __init__(self) -> None:
        self.bars = BudgetBars()
        self.edit_button = QPushButton("Editar")
        self.edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_button.setToolTip("Fija cuánto quieres gastar al mes en cada categoría")
        self._empty = QLabel("Fija un tope mensual por categoría y Kreix te avisa cuando te acercas a él.")
        self._empty.setObjectName("Muted")
        self._empty.setWordWrap(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 6, 0, 0)
        col.addWidget(self.bars)
        col.addWidget(self._empty)
        col.addStretch(1)
        super().__init__("Presupuestos", "", body, self.edit_button)
        self.edit_button.clicked.connect(self.edit_requested)

    def set_lines(self, lines: list[BudgetLine], monthly: bool) -> None:
        self.bars.setVisible(bool(lines))
        self._empty.setVisible(not lines)
        self.edit_button.setText("Editar" if lines else "Definir presupuestos")
        if lines:
            over = sum(1 for line in lines if line.state == "over")
            scope = "Gasto del mes frente a tu tope" if monthly else "Gasto medio mensual frente a tu tope"
            self.subtitle.setText(f"{scope}  ·  {over} superado{'s' if over != 1 else ''}" if over else scope)
            self.bars.set_lines(lines)
        else:
            self.subtitle.setText("Sin presupuestos todavía")


class AlertsPanel(Panel):
    """Resumen: los presupuestos del mes que estan cerca del tope o superados."""

    def __init__(self) -> None:
        self.bars = BudgetBars()
        self._message = QLabel("")
        self._message.setObjectName("Muted")
        self._message.setWordWrap(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 6, 0, 0)
        col.addWidget(self.bars)
        col.addWidget(self._message)
        col.addStretch(1)
        super().__init__("Presupuestos del mes", "", body)

    def set_state(self, alerts: list[BudgetLine], has_budgets: bool) -> None:
        self.bars.setVisible(bool(alerts))
        self._message.setVisible(not alerts)
        if alerts:
            self.subtitle.setText("Lo que está cerca del tope o se ha pasado")
            self.bars.set_lines(alerts)
        elif has_budgets:
            self.subtitle.setText("Todo en orden")
            self._message.setText("Vas dentro de todos tus presupuestos este mes.")
        else:
            self.subtitle.setText("Sin presupuestos todavía")
            self._message.setText("Define un tope mensual por categoría en la pestaña Cuentas y aquí verás cuándo te acercas.")


class UpcomingPanel(Panel):
    """Resumen: los pagos recurrentes que se esperan en las proximas semanas."""

    def __init__(self) -> None:
        columns = [
            Column("PAGO", lambda r: r.name, lambda r: r.name.lower(), stretch=True),
            Column("IMPORTE", lambda r: fmt_eur(r.amount), lambda r: r.amount, RIGHT),
            Column("FECHA", lambda r: fmt_date(r.next_date), lambda r: r.next_date, RIGHT, tone=lambda r: "accent"),
        ]
        self.table = DataTable(columns, min_height=120)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self._message = QLabel("Cuando Kreix detecte suscripciones o recibos mensuales, verás aquí cuándo toca el siguiente.")
        self._message.setObjectName("Muted")
        self._message.setWordWrap(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self.table)
        col.addWidget(self._message)
        col.addStretch(1)
        super().__init__("Próximos pagos", "", body)

    def set_items(self, items: list[Recurring]) -> None:
        self.table.setVisible(bool(items))
        self._message.setVisible(not items)
        self.table.set_rows(items)
        if items:
            self.table.fit_height(6)
            self.subtitle.setText(f"{fmt_eur(monthly_cost(items))} en los próximos pagos (fechas estimadas)")
        else:
            self.subtitle.setText("Sin pagos recurrentes a la vista")

    def refresh_theme(self) -> None:
        self.table.refresh_theme()


class RecurringPanel(Panel):
    def __init__(self) -> None:
        columns = [
            Column("PAGO", lambda r: r.name, lambda r: r.name.lower(), stretch=True),
            Column("IMPORTE", lambda r: fmt_eur(r.amount), lambda r: r.amount, RIGHT),
            Column("PRÓXIMO", lambda r: fmt_date(r.next_date), lambda r: r.next_date, RIGHT, tone=lambda r: "accent"),
        ]
        self.table = DataTable(columns, min_height=120)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self._empty = QLabel("Aún no hay pagos que se repitan cada mes. Aparecerán cuando haya al menos tres cargos "
                             "seguidos por un importe parecido.")
        self._empty.setObjectName("Muted")
        self._empty.setWordWrap(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self.table)
        col.addWidget(self._empty)
        col.addStretch(1)
        super().__init__("Pagos recurrentes", "", body)

    def set_items(self, items: list[Recurring]) -> None:
        self.table.setVisible(bool(items))
        self._empty.setVisible(not items)
        self.table.set_rows(items)
        if items:
            self.table.fit_height(6)
            total = monthly_cost(items)
            n = len(items)
            self.subtitle.setText(f"{n} pago{'s' if n != 1 else ''}  ·  {fmt_eur(total)} al mes, {fmt_eur(total * 12)} al año")
        else:
            self.subtitle.setText("Suscripciones y recibos que se repiten")

    def refresh_theme(self) -> None:
        self.table.refresh_theme()
