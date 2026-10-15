"""Piezas visuales de las paginas: cifras (KPI), tarjeta principal, bandas, cabecera de pagina y chips."""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPalette
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui import fonts, theme
from ui.widgets.charts import Sparkline
from core.i18n import tr


def repolish(widget: QWidget) -> None:
    """Reaplica la hoja de estilos tras cambiar una propiedad dinamica."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def track(label: QLabel, spacing: float) -> QLabel:
    """Separacion entre letras (tracking) para las etiquetas en mayusculas."""
    font = QFont(label.font())
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    label.setFont(font)
    return label


class ElidedLabel(QLabel):
    """Etiqueta de una linea para cifras: si no cabe, primero reduce el cuerpo (hasta un 60 %) y,
    si aun asi no cabe, acaba en puntos suspensivos. No impone su ancho a la tarjeta."""

    MIN_SCALE = 0.6

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:  # noqa: N802 (API de Qt)
        super().setText(text)
        self.setToolTip(text)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        font = QFont(self.font())
        base = font.pixelSize() if font.pixelSize() > 0 else max(int(font.pointSizeF() * 96 / 72), 12)
        px, floor = base, max(int(base * self.MIN_SCALE), 12)
        font.setPixelSize(px)
        while px > floor and QFontMetricsF(font).horizontalAdvance(self.text()) > self.width():
            px -= 1
            font.setPixelSize(px)
        painter.setFont(font)
        text = QFontMetricsF(font).elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        self.style().drawItemText(
            painter, self.rect(), int(self.alignment()) | Qt.TextFlag.TextSingleLine, self.palette(),
            self.isEnabled(), text, QPalette.ColorRole.WindowText,
        )


# ============================================================================ motivo de marca
class StripeMark(QWidget):
    """Las cuatro franjas inclinadas de la K del logotipo (las de la senyera), como firma discreta de la cabecera."""

    def __init__(self, width: int = 64, height: int = 34, centered: bool = False) -> None:
        super().__init__()
        self._centered = centered
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, _event) -> None:
        pal = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        h = self.height()
        slant, bar, gap = h * 0.50, h * 0.185, h * 0.165
        block = slant + 4 * bar + 3 * gap
        left = (self.width() - block) / 2 if self._centered else self.width() - block
        yellow, red = QColor(pal.accent), QColor(pal.red)
        for i, alpha in enumerate((255, 190, 120, 60)):
            t = i / 3                                       # de amarillo (la primera barra) a rojo (la ultima)
            c = QColor(round(yellow.red() + (red.red() - yellow.red()) * t),
                       round(yellow.green() + (red.green() - yellow.green()) * t),
                       round(yellow.blue() + (red.blue() - yellow.blue()) * t))
            c.setAlpha(alpha)
            painter.setBrush(c)
            x = left + i * (bar + gap)
            path = QPainterPath()
            path.moveTo(x + slant, 2)
            path.lineTo(x + slant + bar, 2)
            path.lineTo(x + bar, h - 2)
            path.lineTo(x, h - 2)
            path.closeSubpath()
            painter.drawPath(path)


ACCESSORY_GAP = 36          # espacio entre el titulo y el dibujo que lo acompana


class PageHeader(QWidget):
    """Cabecera comun: etiqueta de contexto en amarillo, titulo grande, subtitulo y las franjas de marca."""

    def __init__(self, title: str, eyebrow: str = "", subtitle: str = "") -> None:
        super().__init__()
        self._eyebrow = QLabel(eyebrow.upper())
        self._eyebrow.setObjectName("Eyebrow")
        track(self._eyebrow, 1.6)
        if not eyebrow:
            self._eyebrow.hide()   # no setVisible(True) sin padre: abriria una ventana suelta
        self.title = QLabel(title)
        self.title.setObjectName("H1")
        self._subtitle = QLabel(subtitle)
        self._subtitle.setObjectName("Muted")
        if not subtitle:
            self._subtitle.hide()   # no setVisible(True) sin padre: abriria una ventana suelta
        column = QVBoxLayout()
        self._column = column
        column.setSpacing(2)
        self._head_left = QVBoxLayout()                  # la etiqueta de contexto y el titulo, juntos
        self._head_left.setSpacing(2)
        self._head_left.addWidget(self._eyebrow)
        self._head_left.addWidget(self.title)
        self._title_row = QHBoxLayout()
        self._title_row.setSpacing(14)
        self._title_row.addLayout(self._head_left)
        self._title_row.addStretch(1)
        column.addLayout(self._title_row)
        column.addWidget(self._subtitle)
        self._right = QHBoxLayout()
        self._right.setSpacing(12)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addLayout(column, 1)
        row.addLayout(self._right)
        row.addWidget(StripeMark(), 0, Qt.AlignmentFlag.AlignTop)

    def add_line(self, widget: QWidget) -> None:
        """Una linea extra entre el titulo y el subtitulo (p. ej. la fecha y la hora)."""
        self._column.insertWidget(self._column.indexOf(self._subtitle), widget)

    def add_title_accessory(self, widget: QWidget) -> None:
        """Coloca un elemento (p. ej. un dibujo animado) a la derecha del titulo, con holgura, alineado con su base. Como
        ocupa la misma altura que la etiqueta y el titulo juntos, no separa las lineas de texto de debajo."""
        self._title_row.setSpacing(ACCESSORY_GAP)
        self._title_row.insertWidget(1, widget, 0, Qt.AlignmentFlag.AlignBottom)

    def set_subtitle(self, text: str) -> None:
        self._subtitle.setText(text)
        self._subtitle.setVisible(bool(text))

    def add_right(self, widget: QWidget) -> None:
        self._right.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)


class Chip(QLabel):
    """Etiqueta redondeada para una variacion o un dato corto (+4,4 %)."""

    def __init__(self, text: str = "", tone: str = "") -> None:
        super().__init__(text)
        self.setObjectName("Chip")
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        self.setProperty("tone", tone)
        repolish(self)


# ============================================================================ cifras
class StatCard(QFrame):
    """Una cifra: etiqueta en mayusculas, valor grande y una linea de contexto.

    `band=True` la deja sin caja propia, para colocarla dentro de una StatBand."""

    def __init__(self, title: str, accent: str = "yellow", compact: bool = False, band: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BandCell" if band else "Card")
        self._title = track(QLabel(title.upper()), 1.2)
        self._title.setObjectName("CardTitle")
        self._value = ElidedLabel("—")
        self._value.setObjectName("MiniValue" if compact else "CardValue")
        self._sub = QLabel("")
        self._sub.setObjectName("CardSub")
        self._sub.setWordWrap(True)

        col = QVBoxLayout(self)
        pad = (30, 20, 30, 20) if compact else (30, 26, 30, 26)
        col.setContentsMargins(*pad)
        col.setSpacing(8)
        for w in (self._title, self._value, self._sub):
            col.addWidget(w)
        col.addStretch(1)                       # el contenido se alinea arriba aunque falte la linea de contexto
        self.setAccessibleName(title)

    def set_title(self, title: str) -> None:
        self._title.setText(title.upper())
        self.setAccessibleName(title)

    def set_content(self, value: str, subtitle: str = "", negative: bool = False, positive: bool = False) -> None:
        self._value.setText(value)
        self._value.setProperty("tone", "negative" if negative else "positive" if positive else "normal")
        repolish(self._value)
        self._sub.setText(subtitle)
        self._sub.setVisible(bool(subtitle))
        self.setAccessibleDescription(f"{value}. {subtitle}")


class StatBand(QFrame):
    """Varias cifras en una sola superficie, separadas por finas lineas: menos cajas, mas jerarquia."""

    def __init__(self, cells: Sequence[StatCard]) -> None:
        super().__init__()
        self.setObjectName("Band")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        for i, cell in enumerate(cells):
            if i:
                divider = QFrame()
                divider.setObjectName("BandDivider")
                divider.setFixedWidth(1)
                row.addWidget(divider)
            row.addWidget(cell, 1)


class SplitBar(QWidget):
    """Barra partida (p. ej. liquidez e inversion) con el importe de cada parte debajo."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[tuple[str, str, float, str]] = []     # (nombre, importe, fraccion, color)
        self.setMinimumHeight(58)

    def sizeHint(self) -> QSize:
        return QSize(200, 58)

    def set_parts(self, parts: list[tuple[str, str, float, str]]) -> None:
        self._parts = parts
        self.update()

    def paintEvent(self, _event) -> None:
        if not self._parts:
            return
        pal = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(pal.surface_alt))
        p.drawRoundedRect(QRectF(0, 4, self.width(), 10), 5, 5)
        x = 0.0
        total = sum(f for _, _, f, _ in self._parts) or 1.0
        for i, (_, _, fraction, key) in enumerate(self._parts):
            w = max(self.width() * fraction / total - (3 if i < len(self._parts) - 1 else 0), 6)
            p.setBrush(QColor(getattr(pal, key)))
            p.drawRoundedRect(QRectF(x, 4, w, 10), 5, 5)
            x += w + 3
        cursor = 0.0
        name_font, amount_font = fonts.qfont(fonts.BODY, 12), fonts.qfont(fonts.BODY_MEDIUM, 12)
        for name, amount, _, key in self._parts:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(getattr(pal, key)))
            p.drawEllipse(QRectF(cursor, 27, 8, 8))
            name_w = QFontMetricsF(name_font).horizontalAdvance(name)
            amount_w = QFontMetricsF(amount_font).horizontalAdvance(amount)
            p.setFont(name_font)
            p.setPen(QColor(pal.muted))
            p.drawText(QRectF(cursor + 14, 22, name_w + 4, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
            p.setFont(amount_font)
            p.setPen(QColor(pal.text))
            p.drawText(QRectF(cursor + 14 + name_w + 8, 22, amount_w + 4, 18),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, amount)
            cursor += 14 + name_w + 8 + amount_w + 26


class HeroCard(StatCard):
    """La cifra que manda en la pagina: valor enorme, chips de contexto, curva de evolucion y reparto."""

    def __init__(self, title: str) -> None:
        super().__init__(title)
        self.setObjectName("Hero")
        self._value.setObjectName("HeroValue")
        layout = self.layout()
        layout.setContentsMargins(40, 36, 40, 30)
        layout.setSpacing(12)
        self._chips = QHBoxLayout()
        self._chips.setSpacing(8)
        self._chips.addStretch(1)
        self.split = SplitBar()
        self.trend = Sparkline()
        self.trend.setMinimumHeight(70)
        layout.insertLayout(2, self._chips)
        layout.addSpacing(6)
        layout.addWidget(self.trend, 1)
        layout.addWidget(self.split)
        self._chip_widgets: list[Chip] = []

    def set_chips(self, chips: list[tuple[str, str]]) -> None:
        for chip in self._chip_widgets:
            chip.deleteLater()
        self._chip_widgets = []
        for text, tone in chips:
            chip = Chip(text, tone)
            self._chips.insertWidget(self._chips.count() - 1, chip)
            self._chip_widgets.append(chip)

    def refresh_theme(self) -> None:
        self.trend.refresh_theme()
        self.split.update()


class ChartCard(QFrame):
    """Tarjeta con titulo, subtitulo y un grafico dentro."""

    def __init__(self, title: str, subtitle: str, content: QWidget, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        heading = QLabel(title)
        heading.setObjectName("H2")
        sub = QLabel(subtitle)
        sub.setObjectName("Small")
        sub.setWordWrap(True)
        self._headline = QLabel("")
        self._headline.setObjectName("Headline")
        self._headline.setWordWrap(True)
        self._headline.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 26)
        layout.setSpacing(4)
        layout.addWidget(heading)
        layout.addWidget(sub)
        layout.addSpacing(6)
        layout.addWidget(self._headline)
        layout.addSpacing(6)
        layout.addWidget(content, 1)
        self.setAccessibleName(title)

    def set_headline(self, text: str) -> None:
        """La idea del grafico en una frase, para quien no quiera interpretarlo."""
        self._headline.setText(text)
        self._headline.setVisible(bool(text))
