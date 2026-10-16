"""Modo privacidad: las cantidades se ven difuminadas (se adivina que hay una cifra, nunca cual).

Con el modo activo, `fmt_eur` ya no devuelve el importe sino una cifra de relleno entre dos marcas invisibles (`START`/`END`): ninguna
cifra real llega nunca a un widget, asi que tampoco se escapa por el nombre accesible, el tooltip ni el portapapeles. Quien pinta texto
(`PrivacyStyle` para etiquetas, botones y tablas; `draw_text` para los graficos) reconoce las marcas y dibuja ese relleno borroso.
El borroso es barato: el texto se pinta a un tercio de tamano y se estira suavizado; cada resultado se guarda y se reutiliza.
"""
from __future__ import annotations

import math
from collections import OrderedDict

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter, QTextCharFormat, QTextLayout, QTextOption
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle, QStyledItemDelegate

START = "⁠"        # WORD JOINER: no ocupa sitio ni se ve
END = "⁣"          # INVISIBLE SEPARATOR
_MIN_SCALE, _MAX_SCALE = 3, 8       # cuanto se reduce el texto antes de estirarlo (a mas, mas borroso); crece con el tamano de la letra
_CACHE_MAX = 512
_cache: OrderedDict[tuple, QImage] = OrderedDict()


def mark(text: str) -> str:
    return f"{START}{text}{END}"


def has_mark(text: str) -> bool:
    return START in text


def split(text: str) -> tuple[str, list[tuple[int, int]]]:
    """('Gastas ⁠8.888,88 €⁣ al mes') -> (texto sin marcas, [(inicio, fin) de cada cantidad en ese texto])."""
    clean: list[str] = []
    spans: list[tuple[int, int]] = []
    begin = -1
    for ch in text:
        if ch == START:
            begin = len("".join(clean))
        elif ch == END:
            if begin >= 0:
                spans.append((begin, len("".join(clean))))
            begin = -1
        else:
            clean.append(ch)
    return "".join(clean), spans


def clean_text(text: str) -> str:
    return text.replace(START, "").replace(END, "")


def _blurred(text: str, font, color: QColor, width: float, height: float, dpr: float) -> QImage:
    scale = min(_MAX_SCALE, max(_MIN_SCALE, round(height / 5)))
    key = (text, font.key(), color.rgba(), round(width), round(height), dpr)
    image = _cache.get(key)
    if image is not None:
        _cache.move_to_end(key)
        return image
    small = QImage(max(2, math.ceil(width * dpr / scale) + 2), max(2, math.ceil(height * dpr / scale) + 2), QImage.Format.Format_ARGB32_Premultiplied)
    small.fill(Qt.GlobalColor.transparent)
    q = QPainter(small)
    q.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    q.scale(1 / scale, 1 / scale)
    q.setFont(font)
    q.setPen(color)
    q.drawText(QPointF(scale, scale + QFontMetricsF(font).ascent()), text)
    q.end()
    image = small.scaled(math.ceil(small.width() * scale), math.ceil(small.height() * scale),
                         Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    image = image.scaled(math.ceil((width + 2 * scale) * dpr), math.ceil((height + 2 * scale) * dpr),
                         Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    image.setDevicePixelRatio(dpr)
    image.setOffset(QPoint(-scale, -scale))
    _cache[key] = image
    if len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return image


def _draw_blur(p: QPainter, text: str, x: float, y: float, width: float, height: float) -> None:
    """Pinta `text` difuminado en el rectangulo (x, y, width, height), con la fuente y el color del pintor."""
    dpr = p.device().devicePixelRatioF() if p.device() is not None else 1.0
    image = _blurred(text, p.font(), p.pen().color(), width, height, dpr)
    p.save()
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.drawImage(QPointF(x, y) + QPointF(image.offset()), image)
    p.restore()


def draw_marked(p: QPainter, rect: QRectF, flags: int, text: str) -> None:
    """Como `drawText(rect, flags, text)`, con las cantidades marcadas difuminadas (admite varias lineas)."""
    clean, spans = split(text)
    layout = QTextLayout(clean, p.font())
    option = QTextOption()
    option.setAlignment(Qt.AlignmentFlag(flags & 0x000F))                     # solo la parte horizontal
    wrap = bool(flags & Qt.TextFlag.TextWordWrap)
    option.setWrapMode(QTextOption.WrapMode.WordWrap if wrap else QTextOption.WrapMode.NoWrap)
    layout.setTextOption(option)
    hidden = QTextCharFormat()
    hidden.setForeground(QColor(0, 0, 0, 0))
    ranges = []
    for a, b in spans:
        r = QTextLayout.FormatRange()
        r.start, r.length, r.format = a, b - a, hidden
        ranges.append(r)
    layout.beginLayout()
    y = 0.0
    lines = []
    while (line := layout.createLine()).isValid():
        line.setLineWidth(rect.width())
        line.setPosition(QPointF(0, y))
        y += line.height()
        lines.append(line)
    layout.endLayout()
    top = rect.top()
    if flags & Qt.AlignmentFlag.AlignVCenter:
        top += (rect.height() - y) / 2
    elif flags & Qt.AlignmentFlag.AlignBottom:
        top += rect.height() - y
    p.save()
    p.setClipRect(rect, Qt.ClipOperation.IntersectClip)
    layout.draw(p, QPointF(rect.left(), top), ranges)
    for a, b in spans:
        for line in lines:
            start, end = max(a, line.textStart()), min(b, line.textStart() + line.textLength())
            if start >= end:
                continue
            x0, x1 = line.cursorToX(start)[0], line.cursorToX(end)[0]
            _draw_blur(p, clean[start:end], rect.left() + min(x0, x1), top + line.y(), abs(x1 - x0), line.height())
    p.restore()


def draw_text(p: QPainter, *args) -> None:
    """Sustituto de `QPainter.drawText` para los graficos: (QRectF, flags, texto) o (QPointF, texto)."""
    text = args[-1]
    if not isinstance(text, str) or not has_mark(text):
        p.drawText(*args)
        return
    if len(args) == 3:
        rect, flags, _ = args
        draw_marked(p, QRectF(rect), int(flags), text)
        return
    point, _ = args                                                              # la linea base arranca en `point`
    fm = QFontMetricsF(p.font())
    width = fm.horizontalAdvance(clean_text(text)) + 2
    draw_marked(p, QRectF(point.x(), point.y() - fm.ascent(), width, fm.height()), int(Qt.AlignmentFlag.AlignLeft), text)


class PrivacyStyle(QProxyStyle):
    """Fusion, mas el difuminado de las cantidades en etiquetas y botones."""

    def __init__(self) -> None:
        super().__init__("Fusion")

    def drawItemText(self, painter, rect, flags, pal, enabled, text, textRole=None) -> None:
        if not has_mark(text):
            if textRole is None:
                return super().drawItemText(painter, rect, flags, pal, enabled, text)
            return super().drawItemText(painter, rect, flags, pal, enabled, text, textRole)
        group = pal.ColorGroup.Normal if enabled else pal.ColorGroup.Disabled
        role = pal.ColorRole.WindowText if textRole is None or textRole == pal.ColorRole.NoRole else textRole
        painter.save()
        painter.setPen(pal.color(group, role))
        draw_marked(painter, QRectF(rect), int(flags), text)
        painter.restore()


def install(app: QApplication) -> None:
    app.setStyle(PrivacyStyle())


class BlurDelegate(QStyledItemDelegate):
    """Celdas de tabla: las cantidades marcadas se pintan difuminadas (la hoja de estilos de las tablas no pasa por `PrivacyStyle`)."""

    def paint(self, painter, option, index) -> None:
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not isinstance(text, str) or not has_mark(text):
            return super().paint(painter, option, index)
        opt = type(option)(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        widget = option.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)      # fondo, seleccion e icono
        rect = QRectF(style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, widget)).adjusted(2, 0, -2, 0)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.save()
        painter.setFont(opt.font)
        painter.setPen(opt.palette.color(opt.palette.ColorGroup.Normal,
                                         opt.palette.ColorRole.HighlightedText if selected else opt.palette.ColorRole.Text))
        draw_marked(painter, rect, int(opt.displayAlignment.value), text)
        painter.restore()
