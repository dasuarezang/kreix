"""Paneles de la pestana Cuentas: presupuestos del periodo y pagos recurrentes."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.budget import BudgetLine
from core.recurring import Recurring, monthly_cost
from ui import fonts, theme
from ui.format import category_label, fmt_date, fmt_eur
from ui.widgets.cards import BrandRule
from ui.popups import Menu
from ui.widgets.tables import RIGHT, Column, DataTable
from core.i18n import tr, trn

ROW_H = 66


class BudgetBars(QWidget):
    """Una barra por presupuesto: verde mientras sobra, amarilla cerca del tope y roja al pasarse."""

    category_clicked = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._lines: list[BudgetLine] = []
        self.setMouseTracking(True)

    def _line_at(self, pos: QPointF) -> BudgetLine | None:
        index = int(pos.y() // fonts.scaled(ROW_H))
        return self._lines[index] if 0 <= index < len(self._lines) else None

    def mouseMoveEvent(self, event) -> None:
        over = self._line_at(event.position()) is not None
        self.setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.ArrowCursor)
        self.setToolTip(tr("Clic para ver los movimientos de esta categoría") if over else "")

    def mousePressEvent(self, event) -> None:
        line = self._line_at(event.position())
        if line is not None and event.button() == Qt.MouseButton.LeftButton:
            self.category_clicked.emit(line.category)

    def set_lines(self, lines: list[BudgetLine]) -> None:
        self._lines = lines
        self.setMinimumHeight(len(lines) * fonts.scaled(ROW_H) + 4)
        self.updateGeometry()
        self.update()
        self.setAccessibleDescription("; ".join(
            f"{category_label(line.category)}: " + tr("{spent} de {budget}").format(spent=fmt_eur(line.spent), budget=fmt_eur(line.budget)) for line in lines))

    def sizeHint(self) -> QSize:
        return QSize(300, len(self._lines) * fonts.scaled(ROW_H) + 4)

    def paintEvent(self, _event) -> None:
        pal = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        name_font, amount_font, note_font = (fonts.qfont(fonts.BODY_MEDIUM, 13), fonts.qfont(fonts.BODY_MEDIUM, 13),
                                             fonts.qfont(fonts.BODY, 12))
        tones = {"ok": pal.green, "warn": pal.accent, "over": pal.red}
        for i, line in enumerate(self._lines):
            top = i * fonts.scaled(ROW_H)
            p.setFont(name_font)
            p.setPen(QColor(pal.text))
            p.drawText(QRectF(0, top, self.width() * 0.45, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       category_label(line.category))
            amount = tr("{spent} de {budget}").format(spent=fmt_eur(line.spent), budget=fmt_eur(line.budget))
            p.setFont(amount_font)
            p.drawText(QRectF(self.width() * 0.4, top, self.width() * 0.6, 20),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, amount)
            color = QColor(tones[line.state])
            track = QRectF(0, top + 29, self.width(), 5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(pal.surface_alt))
            p.drawRoundedRect(track, 1.5, 1.5)
            filled = min(float(line.ratio), 1.0)
            if filled > 0:
                p.setBrush(color)
                p.drawRoundedRect(QRectF(0, top + 29, max(self.width() * filled, 6), 5), 1.5, 1.5)
            note = (tr("Te has pasado {remaining}").format(remaining=fmt_eur(-line.remaining)) if line.state == "over" else tr("Quedan {remaining}").format(remaining=fmt_eur(line.remaining)))
            p.setFont(note_font)
            p.setPen(color if line.state == "over" else QColor(pal.muted))
            metrics = QFontMetricsF(note_font)
            p.drawText(QRectF(0, top + 38, self.width(), 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       metrics.elidedText(note, Qt.TextElideMode.ElideRight, self.width()))


class Panel(QFrame):
    """Tarjeta con titulo, subtitulo, un boton opcional arriba a la derecha y un cuerpo."""

    def __init__(self, title: str, subtitle: str, body: QWidget, action: QWidget | None = None, raised: bool = False) -> None:
        super().__init__()
        self.setObjectName("Card" if raised else "Section")
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
        layout.setSpacing(14)
        if raised:                                          # el carrusel y los primeros pasos se tocan: siguen siendo tarjetas
            layout.setContentsMargins(34, 30, 34, 26)
        else:
            layout.setContentsMargins(0, 0, 0, 6)
            layout.addWidget(BrandRule())
        layout.addLayout(top)
        layout.addWidget(body, 1)
        self.setAccessibleName(title)


class BudgetPanel(Panel):
    edit_requested = Signal()

    def __init__(self) -> None:
        self.bars = BudgetBars()
        self.edit_button = QPushButton(tr("Editar"))
        self.edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_button.setToolTip(tr("Fija cuánto quieres gastar al mes en cada categoría"))
        self._empty = QLabel(tr("Fija un tope mensual por categoría y Kreix te avisa cuando te acercas a él."))
        self._empty.setObjectName("Muted")
        self._empty.setWordWrap(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 6, 0, 0)
        col.addWidget(self.bars)
        col.addWidget(self._empty)
        col.addStretch(1)
        super().__init__(tr("Presupuestos"), "", body, self.edit_button)
        self.edit_button.clicked.connect(self.edit_requested)

    def set_lines(self, lines: list[BudgetLine], monthly: bool) -> None:
        self.bars.setVisible(bool(lines))
        self._empty.setVisible(not lines)
        self.edit_button.setText(tr("Editar") if lines else tr("Definir presupuestos"))
        if lines:
            over = sum(1 for line in lines if line.state == "over")
            scope = tr("Gasto del mes frente a tu tope") if monthly else tr("Gasto medio mensual frente a tu tope")
            self.subtitle.setText(f"{scope}  ·  " + trn("{n} superado", "{n} superados", over).format(n=over) if over else scope)
            self.bars.set_lines(lines)
        else:
            self.subtitle.setText(tr("Sin presupuestos todavía"))


def _payment_name(r: Recurring) -> str:
    """El concepto del pago, venga de lo que Kreix ha detectado o de lo que el usuario ha marcado: da igual."""
    return r.name


class _RemovableMixin:
    """Cualquier pago recurrente se puede quitar (por ejemplo porque se ha dado de baja), lo haya detectado Kreix o lo haya marcado el usuario."""

    remove_requested = Signal(object)           # el Recurring que se quita

    def _wire_remove(self, table: DataTable) -> None:
        table.context_requested.connect(self._show_remove_menu)
        table.setToolTip(tr("Clic derecho sobre un pago para quitarlo si ya no se cobra"))

    def _show_remove_menu(self, item, pos) -> None:
        menu = Menu(self)
        action = menu.addAction(tr("Quitar de pagos recurrentes"))
        action.triggered.connect(lambda _=False: self.remove_requested.emit(item))
        menu.exec(pos)


class UpcomingPanel(_RemovableMixin, Panel):
    """Inicio: los pagos recurrentes que se esperan en las proximas semanas (los mismos que ve Cuentas en Pagos recurrentes,
    pero solo los que tocan pronto: ordenados por fecha)."""

    def __init__(self) -> None:
        columns = [
            Column(tr("PAGO"), _payment_name, lambda r: r.name.lower(), stretch=True),
            Column(tr("IMPORTE"), lambda r: fmt_eur(r.amount), lambda r: r.amount, RIGHT),
            Column(tr("FECHA"), lambda r: fmt_date(r.next_date), lambda r: r.next_date, RIGHT, tone=lambda r: "accent"),
        ]
        self.table = DataTable(columns, min_height=120)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self._message = QLabel(tr("Cuando Kreix detecte suscripciones o recibos mensuales, verás aquí cuándo toca el siguiente."))
        self._message.setObjectName("Muted")
        self._message.setWordWrap(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self.table)
        col.addWidget(self._message)
        col.addStretch(1)
        super().__init__(tr("Próximos pagos"), "", body)
        self._wire_remove(self.table)

    def set_items(self, items: list[Recurring]) -> None:
        self.table.setVisible(bool(items))
        self._message.setVisible(not items)
        self.table.set_rows(items)
        if items:
            self.table.fit_height(6)
            self.subtitle.setText(tr("{items} en los próximos pagos (fechas estimadas)").format(items=fmt_eur(sum((r.amount for r in items), Decimal(0)))))
        else:
            self.subtitle.setText(tr("Sin pagos recurrentes a la vista"))

    def refresh_theme(self) -> None:
        self.table.refresh_theme()


class RecurringPanel(_RemovableMixin, Panel):
    def __init__(self) -> None:
        columns = [
            Column(tr("PAGO"), _payment_name, lambda r: r.name.lower(), stretch=True),
            Column(tr("IMPORTE"), lambda r: fmt_eur(r.amount), lambda r: r.amount, RIGHT),
            Column(tr("PRÓXIMO"), lambda r: fmt_date(r.next_date), lambda r: r.next_date, RIGHT, tone=lambda r: "accent"),
        ]
        self.table = DataTable(columns, min_height=120)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self._empty = QLabel(tr("Aún no hay pagos que se repitan cada mes. Aparecerán cuando haya al menos tres cargos "
                             "seguidos por un importe parecido."))
        self._empty.setObjectName("Muted")
        self._empty.setWordWrap(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self.table)
        col.addWidget(self._empty)
        col.addStretch(1)
        super().__init__(tr("Pagos recurrentes"), "", body)
        self._wire_remove(self.table)

    def set_items(self, items: list[Recurring]) -> None:
        self.table.setVisible(bool(items))
        self._empty.setVisible(not items)
        self.table.set_rows(items)
        if items:
            self.table.fit_height(6)
            total = monthly_cost(items)
            n = len(items)
            self.subtitle.setText(trn("{n} pago  ·  {month} al mes, {year} al año", "{n} pagos  ·  {month} al mes, {year} al año",
                                      n).format(n=n, month=fmt_eur(total), year=fmt_eur(total * 12)))
        else:
            self.subtitle.setText(tr("Suscripciones y recibos que se repiten"))

    def refresh_theme(self) -> None:
        self.table.refresh_theme()
