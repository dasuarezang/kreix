"""Presupuestos del mes en Inicio: todos, de uno en uno, pasando solos cada pocos segundos y con flechas para pasarlos tu.

Cada presupuesto ocupa la tarjeta entera (categoria, gasto frente a tope, barra y lo que queda). Se detiene mientras el
raton esta encima y, si lo cambias a mano, espera un buen rato antes de volver a pasar solo.
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.budget import BudgetLine
from ui import fonts, theme
from ui.format import category_label, fmt_eur, fmt_pct
from ui.widgets import charts
from ui.widgets.panels import Panel
from core.i18n import N_, tr, trn

INTERVAL_MS = 5000          # entre un presupuesto y el siguiente
MANUAL_PAUSE_MS = 12000     # tras pasarlo a mano, espera mas antes de volver a pasar solo
SLIDE_MS = 380
SLIDE_HEIGHT = 128

STATE_TEXT = {"ok": N_("Dentro del tope"), "warn": N_("Cerca del tope"), "over": N_("Superado")}


def _tone(state: str, pal) -> QColor:
    return QColor({"ok": pal.green, "warn": pal.accent, "over": pal.red}[state])


def _tone_text(state: str, pal) -> QColor:
    """El mismo color como texto pequeno: variante con contraste suficiente sobre la tarjeta."""
    return QColor({"ok": pal.green_text, "warn": pal.accent_text, "over": pal.red}[state])


class SlideView(QWidget):
    """Pinta el presupuesto actual y, durante el cambio, el anterior saliendo y el nuevo entrando."""

    category_clicked = Signal(object)
    step_requested = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(fonts.scaled(SLIDE_HEIGHT))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._lines: list[BudgetLine] = []
        self._index = 0
        self._previous = 0
        self._direction = 1
        self._progress = 1.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(SLIDE_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.valueChanged.connect(self._on_progress)

    def sizeHint(self) -> QSize:
        return QSize(320, fonts.scaled(SLIDE_HEIGHT))

    @property
    def animating(self) -> bool:
        return self._anim.state() == QVariantAnimation.State.Running

    def set_lines(self, lines: list[BudgetLine], index: int) -> None:
        self._anim.stop()
        self._progress = 1.0
        self._lines = lines
        self._index = index
        self.update()

    def go_to(self, index: int, direction: int) -> None:
        if index == self._index:
            return
        self._previous, self._index, self._direction = self._index, index, direction
        self._anim.stop()
        if charts.ANIMATIONS:
            self._progress = 0.0
            self._anim.start()
        else:
            self._progress = 1.0
        self.update()

    def _on_progress(self, value) -> None:
        self._progress = float(value)
        self.update()

    # -- interaccion -------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if self._lines and event.button() == Qt.MouseButton.LeftButton:
            self.category_clicked.emit(self._lines[self._index].category)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Left:
            self.step_requested.emit(-1)
        elif event.key() == Qt.Key.Key_Right:
            self.step_requested.emit(1)
        else:
            super().keyPressEvent(event)

    # -- pintado -----------------------------------------------------------
    def paintEvent(self, _event) -> None:
        if not self._lines:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.current()
        w = self.width()
        if self._progress >= 1.0:
            self._paint_slide(p, pal, self._lines[self._index], 0.0, 1.0)
            return
        t = self._progress
        self._paint_slide(p, pal, self._lines[self._previous], -self._direction * t * w * 0.35, 1.0 - t)
        self._paint_slide(p, pal, self._lines[self._index], self._direction * (1.0 - t) * w * 0.35, t)

    def _paint_slide(self, p: QPainter, pal, line: BudgetLine, dx: float, opacity: float) -> None:
        p.save()
        p.setOpacity(max(0.0, min(1.0, opacity)))
        p.translate(dx, 0)
        w = self.width()
        tone = _tone(line.state, pal)

        p.setFont(fonts.qfont(fonts.BODY_MEDIUM, 15))
        p.setPen(QColor(pal.text))
        p.drawText(QRectF(0, 0, w * 0.6, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   category_label(line.category))
        p.setFont(fonts.qfont(fonts.BODY_MEDIUM, 12))
        p.setPen(_tone_text(line.state, pal))
        p.drawText(QRectF(w * 0.4, 0, w * 0.6, 24), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   tr(STATE_TEXT[line.state]))

        spent = fmt_eur(line.spent)
        big = fonts.qfont(fonts.LABEL, 28)
        p.setFont(big)
        p.setPen(QColor(pal.text))
        spent_w = p.fontMetrics().horizontalAdvance(spent)
        p.drawText(QRectF(0, 30, spent_w + 6, 40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, spent)
        p.setFont(fonts.qfont(fonts.BODY_MEDIUM, 14))
        p.setPen(QColor(pal.muted))
        p.drawText(QRectF(spent_w + 10, 30, w - spent_w - 10, 40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   tr("de {budget}").format(budget=fmt_eur(line.budget)))
        p.setFont(fonts.qfont(fonts.BODY, 13))
        p.drawText(QRectF(w * 0.6, 30, w * 0.4, 40), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   fmt_pct(line.ratio, 0))

        track = QRectF(0, 82, w, 5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(pal.surface_alt))
        p.drawRoundedRect(track, 2.5, 2.5)
        filled = min(float(line.ratio), 1.0)
        if filled > 0:
            p.setBrush(tone)
            p.drawRoundedRect(QRectF(0, 82, max(w * filled, 6), 5), 2.5, 2.5)

        note = (tr("Te has pasado {remaining}").format(remaining=fmt_eur(-line.remaining)) if line.state == "over"
                else tr("Te quedan {remaining} este mes").format(remaining=fmt_eur(line.remaining)))
        p.setFont(fonts.qfont(fonts.BODY_MEDIUM, 13))
        p.setPen(tone if line.state == "over" else QColor(pal.muted))
        p.drawText(QRectF(0, 94, w, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, note)
        p.restore()


class Dots(QWidget):
    """Un punto por presupuesto; el actual, alargado. Pulsar uno salta a ese presupuesto."""

    selected = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._count = 0
        self._index = 0
        self.setFixedHeight(18)

    def set_state(self, count: int, index: int) -> None:
        self._count, self._index = count, index
        self.update()

    def _slots(self) -> list[QRectF]:
        gap, small, big = 8.0, 7.0, 20.0
        total = (self._count - 1) * small + big + (self._count - 1) * gap
        x = (self.width() - total) / 2
        out = []
        for i in range(self._count):
            width = big if i == self._index else small
            out.append(QRectF(x, (self.height() - small) / 2, width, small))
            x += width + gap
        return out

    def paintEvent(self, _event) -> None:
        if self._count < 2:
            return
        pal = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        for i, rect in enumerate(self._slots()):
            p.setBrush(QColor(pal.accent) if i == self._index else QColor(pal.border))
            p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

    def mousePressEvent(self, event) -> None:
        for i, rect in enumerate(self._slots()):
            if rect.adjusted(-4, -6, 4, 6).contains(event.position()):
                self.selected.emit(i)
                return


class BudgetCarousel(Panel):
    category_clicked = Signal(object)

    def __init__(self) -> None:
        self._lines: list[BudgetLine] = []
        self._index = 0
        self._has_budgets = False
        self._hovered = False

        self.prev_button = QPushButton("‹")
        self.next_button = QPushButton("›")
        for button, tip in ((self.prev_button, tr("Presupuesto anterior")), (self.next_button, tr("Presupuesto siguiente"))):
            button.setObjectName("Arrow")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(tip)
            button.setAccessibleName(tip)
            button.setFixedWidth(38)
        self.counter = QLabel("")
        self.counter.setObjectName("Small")
        self.counter.setMinimumWidth(52)
        self.counter.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        controls = QWidget()
        row = QHBoxLayout(controls)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.counter)
        row.addWidget(self.prev_button)
        row.addWidget(self.next_button)

        self.slide = SlideView()
        self.dots = Dots()
        self._message = QLabel("")
        self._message.setObjectName("Muted")
        self._message.setWordWrap(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 6, 0, 0)
        col.setSpacing(6)
        col.addWidget(self.slide)
        col.addWidget(self.dots)
        col.addWidget(self._message)
        col.addStretch(1)
        super().__init__(tr("Presupuestos del mes"), "", body, controls, raised=True)
        self._controls = controls

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._auto_advance)
        self.prev_button.clicked.connect(self._prev_clicked)
        self.next_button.clicked.connect(self._next_clicked)
        self.dots.selected.connect(self._dot_clicked)
        self.slide.category_clicked.connect(self.category_clicked)
        self.slide.step_requested.connect(self._manual_step)
        self.setMouseTracking(True)

    # -- datos ----------------------------------------------------------------
    @property
    def lines(self) -> list[BudgetLine]:
        return self._lines

    @property
    def index(self) -> int:
        return self._index

    @property
    def current(self) -> BudgetLine | None:
        return self._lines[self._index] if self._lines else None

    @property
    def auto_running(self) -> bool:
        return self._timer.isActive()

    def set_state(self, lines: list[BudgetLine], has_budgets: bool) -> None:
        """`lines`: todos los presupuestos del mes. Si cambia la lista se sigue en el mismo presupuesto cuando se puede."""
        keep = self.current.category if self.current else None
        self._lines = list(lines)
        self._has_budgets = has_budgets
        self._index = next((i for i, line in enumerate(self._lines) if line.category == keep), 0)
        many = len(self._lines) > 1
        has = bool(self._lines)
        self.slide.setVisible(has)
        self.dots.setVisible(many)
        self._controls.setVisible(many)
        self._message.setVisible(not has)
        if has:
            over = sum(1 for line in self._lines if line.state == "over")
            near = sum(1 for line in self._lines if line.state == "warn")
            parts = [trn("{n} presupuesto", "{n} presupuestos", len(self._lines)).format(n=len(self._lines))]
            if over:
                parts.append(trn("{n} superado", "{n} superados", over).format(n=over))
            if near:
                parts.append(tr("{near} cerca del tope").format(near=near))
            self.subtitle.setText("  ·  ".join(parts))
            self.slide.set_lines(self._lines, self._index)
            self._refresh_chrome()
        else:
            self.subtitle.setText(tr("Sin presupuestos todavía") if not has_budgets else tr("Sin gasto este mes"))
            self._message.setText(
                tr("Define un tope mensual por categoría en la pestaña Cuentas y aquí los verás pasar uno a uno.")
                if not has_budgets else tr("Todavía no hay gastos este mes en las categorías con presupuesto."))
        self._rearm(INTERVAL_MS)

    # -- navegacion ---------------------------------------------------------------
    def advance(self, step: int = 1) -> None:
        """Pasa al presupuesto siguiente (o anterior con -1), dando la vuelta al llegar al final."""
        if len(self._lines) < 2:
            return
        new = (self._index + step) % len(self._lines)
        self.slide.go_to(new, 1 if step > 0 else -1)
        self._index = new
        self._refresh_chrome()

    def _refresh_chrome(self) -> None:
        self.dots.set_state(len(self._lines), self._index)
        self.counter.setText(tr("{n} de {total}").format(n=self._index + 1, total=len(self._lines)))
        line = self.current
        if line is not None:
            self.setAccessibleDescription(
                f"{category_label(line.category)}: " + tr("{spent} de {budget}").format(spent=fmt_eur(line.spent), budget=fmt_eur(line.budget)))

    def _manual_step(self, step: int) -> None:
        self.advance(step)
        self._rearm(MANUAL_PAUSE_MS)

    def _prev_clicked(self) -> None:
        self._manual_step(-1)

    def _next_clicked(self) -> None:
        self._manual_step(1)

    def _dot_clicked(self, index: int) -> None:
        if index == self._index:
            return
        self._jump(index)
        self._rearm(MANUAL_PAUSE_MS)

    def _jump(self, index: int) -> None:
        direction = 1 if index > self._index else -1
        self.slide.go_to(index, direction)
        self._index = index
        self._refresh_chrome()

    # -- paso automatico ----------------------------------------------------------
    def _auto_advance(self) -> None:
        self.advance(1)
        self._rearm(INTERVAL_MS)

    def _rearm(self, delay: int) -> None:
        """Programa el siguiente paso solo si hay varios, esta a la vista y el raton no esta encima."""
        self._timer.stop()
        if len(self._lines) > 1 and self.isVisible() and not self._hovered:
            self._timer.start(delay)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._rearm(INTERVAL_MS)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._rearm(INTERVAL_MS)
        super().leaveEvent(event)

    def refresh_theme(self) -> None:
        self.slide.update()
        self.dots.update()
