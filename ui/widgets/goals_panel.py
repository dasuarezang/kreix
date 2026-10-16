"""Inicio: las metas de ahorro, una barra de progreso por meta."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from core.goals import Goal, monthly_needed
from ui import fonts, theme
from ui.format import fmt_date, fmt_eur
from ui.widgets.panels import Panel
from core.i18n import tr, trn

ROW_H = 66


class GoalBars(QWidget):
    """Una barra por meta: nombre y cifras arriba, la barra, y una linea de ayuda (cuanto falta y cuanto apartar al mes)."""

    def __init__(self) -> None:
        super().__init__()
        self._goals: list[Goal] = []
        self._today = date.today()

    def set_goals(self, goals: list[Goal], today: date | None = None) -> None:
        self._goals = goals
        self._today = today or date.today()
        self.setMinimumHeight(len(goals) * fonts.scaled(ROW_H) + 4)
        self.updateGeometry()
        self.update()
        self.setAccessibleDescription("; ".join(
            f"{g.name}: " + tr("{spent} de {budget}").format(spent=fmt_eur(g.saved), budget=fmt_eur(g.target)) for g in goals))

    def sizeHint(self) -> QSize:
        return QSize(300, len(self._goals) * fonts.scaled(ROW_H) + 4)

    def note(self, goal: Goal) -> str:
        """La linea de ayuda de una meta (publica para poder probarla)."""
        if goal.reached:
            return tr("Meta alcanzada")
        parts = [tr("Faltan {amount}").format(amount=fmt_eur(goal.remaining))]
        if goal.deadline is not None:
            need = monthly_needed(goal, self._today)
            if goal.deadline < self._today:
                parts.append(tr("Venció el {date}").format(date=fmt_date(goal.deadline)))
            else:
                parts.append(tr("Para el {date}").format(date=fmt_date(goal.deadline)))
                if need is not None:
                    parts.append(tr("{amount} al mes").format(amount=fmt_eur(need)))
        return "  ·  ".join(parts)

    def paintEvent(self, _event) -> None:
        pal = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        name_font = fonts.qfont(fonts.BODY_MEDIUM, 13)
        note_font = fonts.qfont(fonts.BODY, 12)
        for i, goal in enumerate(self._goals):
            top = i * fonts.scaled(ROW_H)
            tone = QColor(pal.green if goal.reached else pal.accent)
            p.setFont(name_font)
            p.setPen(QColor(pal.text))
            p.drawText(QRectF(0, top, self.width() * 0.6, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, goal.name)
            p.setPen(QColor(pal.muted))
            p.drawText(QRectF(self.width() * 0.4, top, self.width() * 0.6, 22), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       tr("{spent} de {budget}").format(spent=fmt_eur(goal.saved), budget=fmt_eur(goal.target)))
            track = QRectF(0, top + 29, self.width(), 5)
            p.setPen(Qt.PenStyle.NoPen)
            track_c = QColor(pal.border)
            p.setBrush(track_c)
            p.drawRoundedRect(track, 2.5, 2.5)
            if goal.fraction > 0:
                p.setBrush(tone)
                p.drawRoundedRect(QRectF(0, top + 29, max(self.width() * goal.fraction, 6), 5), 2.5, 2.5)
            p.setFont(note_font)
            p.setPen(QColor(pal.green_text if goal.reached else pal.muted))
            p.drawText(QRectF(0, top + 38, self.width(), 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"{round(goal.fraction * 100)} %  ·  {self.note(goal)}")


class GoalsPanel(Panel):
    manage_requested = Signal()

    def __init__(self) -> None:
        self.bars = GoalBars()
        self.manage_button = QPushButton(tr("Gestionar metas"))
        self.manage_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manage_button.setToolTip(tr("Crea metas de ahorro y apunta lo que vas guardando"))
        self._empty = QLabel(tr("Ponte un objetivo, por ejemplo «1.000 € para vacaciones», y ve cómo avanzas."))
        self._empty.setObjectName("Muted")
        self._empty.setWordWrap(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 6, 0, 0)
        col.addWidget(self.bars)
        col.addWidget(self._empty)
        col.addStretch(1)
        super().__init__(tr("Metas de ahorro"), "", body, self.manage_button)
        self.manage_button.clicked.connect(self.manage_requested)

    def set_goals(self, goals: list[Goal], today: date | None = None) -> None:
        self.bars.setVisible(bool(goals))
        self._empty.setVisible(not goals)
        self.manage_button.setText(tr("Gestionar metas") if goals else tr("Crear una meta"))
        if goals:
            done = sum(1 for g in goals if g.reached)
            self.subtitle.setText(trn("{n} meta", "{n} metas", len(goals)).format(n=len(goals))
                                  + (f"  ·  " + trn("{n} alcanzada", "{n} alcanzadas", done).format(n=done) if done else ""))
            self.bars.set_goals(goals, today)
        else:
            self.subtitle.setText(tr("Sin metas todavía"))
            self.bars.set_goals([], today)
