"""Paletas de marca (claro/oscuro) y hoja de estilos de la aplicacion.

Los colores de acento salen del logo: amarillo dorado y rojo. El resto de grises
parte del color del recuadro del logo (#1F2429) y del crema del fondo claro.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Palette:
    name: str
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    muted: str
    accent: str          # amarillo de marca
    accent_hover: str
    on_accent: str       # texto sobre el amarillo
    red: str             # rojo de marca
    neutral: str         # tercera serie de los graficos
    hover: str           # fondo de elementos al pasar el raton
    series: tuple[str, ...]  # colores para graficos con muchas series (fondos)


DARK = Palette(
    name="dark", bg="#15191D", surface="#1F2429", surface_alt="#282F36", border="#323A43",
    text="#F6F2EA", muted="#9AA5B1", accent="#FFD43B", accent_hover="#FFE066", on_accent="#1F2429",
    red="#E5484D", neutral="#7F8C99", hover="#2A3139",
    series=("#FFD43B", "#E5484D", "#7F8C99", "#F2A900", "#FF8787", "#B0BAC5"),
)
LIGHT = Palette(
    name="light", bg="#F6F2EA", surface="#FFFFFF", surface_alt="#EFE9DD", border="#E2DBCD",
    text="#1F2429", muted="#667085", accent="#F2B400", accent_hover="#FFC21A", on_accent="#1F2429",
    red="#C92A2A", neutral="#6B7885", hover="#F1ECE1",
    series=("#F2B400", "#C92A2A", "#6B7885", "#B07F00", "#E8590C", "#9AA5B1"),
)
PALETTES = {"dark": DARK, "light": LIGHT}

_current = DARK


def current() -> Palette:
    return _current


def set_current(palette: Palette) -> None:
    global _current
    _current = palette


def stylesheet(p: Palette) -> str:
    return f"""
* {{ font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif; font-size: 13px; }}
QMainWindow, QWidget#Root, QWidget#Page, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: {p.bg}; color: {p.text};
}}
QScrollArea {{ border: none; }}
QLabel {{ background: transparent; color: {p.text}; }}
QToolTip {{ background: {p.surface_alt}; color: {p.text}; border: 1px solid {p.border}; padding: 6px 8px; }}

/* ---- barra lateral ---- */
QFrame#Sidebar {{ background: {p.surface}; border-right: 1px solid {p.border}; }}
QPushButton#NavButton {{
    text-align: left; padding: 11px 16px; border: none; border-radius: 10px;
    color: {p.muted}; background: transparent; font-weight: 600; font-size: 14px;
}}
QPushButton#NavButton:hover {{ background: {p.hover}; color: {p.text}; }}
QPushButton#NavButton:checked {{ background: {p.accent}; color: {p.on_accent}; }}
QPushButton#NavButton:focus {{ border: 2px solid {p.accent}; padding: 9px 14px; }}
QPushButton#PillButton {{
    text-align: left; padding: 0 18px 0 14px; min-height: 40px; max-height: 40px;
    border: 1px solid {p.border}; border-radius: 20px; background: {p.surface_alt};
    color: {p.text}; font-weight: 600; font-size: 13px;
}}
QPushButton#PillButton:hover {{ background: {p.hover}; border-color: {p.muted}; }}
QPushButton#PillButton:checked {{ background: {p.accent}; border-color: {p.accent}; color: {p.on_accent}; }}
QPushButton#PillButton:focus {{ border: 2px solid {p.accent}; padding: 0 17px 0 13px; }}
/* ---- menu de ayuda ---- */
QPushButton#HubCard {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: 16px; text-align: left; padding: 0;
}}
QPushButton#HubCard:hover {{ background: {p.hover}; border-color: {p.accent}; }}
QPushButton#HubCard:focus {{ border: 2px solid {p.accent}; }}
QLabel#HubTitle {{ font-size: 15px; font-weight: 700; }}
QLabel#IconChip {{ background: {p.accent}; border-radius: 30px; }}
QPushButton#BackButton {{
    background: transparent; border: none; color: {p.muted}; font-weight: 700;
    padding: 6px 14px 6px 8px; border-radius: 10px;
}}
QPushButton#BackButton:hover {{ background: {p.hover}; color: {p.text}; }}
QPushButton#BackButton:focus {{ border: 2px solid {p.accent}; }}
QLabel#SidebarFoot {{ color: {p.muted}; font-size: 11px; }}

/* ---- tipografia ---- */
QLabel#SectionTitle {{ color: {p.muted}; font-size: 11px; font-weight: 800; letter-spacing: 1px; }}
QFrame#Card QLabel#StepBadge, QLabel#StepBadge {{ background: {p.accent}; color: {p.on_accent}; border-radius: 13px; font-weight: 800; }}
QLabel#Small[state="ok"] {{ color: {p.text}; }}
QLabel#Small[state="error"] {{ color: {p.red}; font-weight: 700; }}
QLabel#H1 {{ font-size: 26px; font-weight: 800; }}
QLabel#H2 {{ font-size: 15px; font-weight: 700; }}
QLabel#Muted {{ color: {p.muted}; }}
QLabel#Small {{ color: {p.muted}; font-size: 12px; }}

/* ---- tarjetas ---- */
QFrame#Card {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 14px; }}
QFrame#Card QLabel {{ background: transparent; }}
QLabel#CardTitle {{ color: {p.muted}; font-size: 12px; font-weight: 700; letter-spacing: 0.5px; }}
QLabel#CardValue {{ font-size: 30px; font-weight: 800; }}
QLabel#CardValue[tone="negative"] {{ color: {p.red}; }}
QLabel#CardSub {{ color: {p.muted}; font-size: 12px; }}
QFrame#AccentBar {{ background: {p.accent}; border-radius: 2px; border: none; }}
QFrame#AccentBar[tone="red"] {{ background: {p.red}; }}
QFrame#AccentBar[tone="neutral"] {{ background: {p.neutral}; }}

/* ---- avisos ---- */
QFrame#Banner {{ background: {p.surface_alt}; border: 1px solid {p.accent}; border-radius: 12px; }}
QFrame#Banner QLabel {{ background: transparent; }}
QLabel#Pill {{ border-radius: 9px; padding: 2px 10px; font-size: 11px; font-weight: 700;
    background: {p.surface_alt}; color: {p.text}; }}
QLabel#Pill[state="ok"] {{ background: {p.accent}; color: {p.on_accent}; }}
QLabel#Pill[state="warn"] {{ background: {p.surface_alt}; color: {p.accent}; border: 1px solid {p.accent}; }}
QLabel#Pill[state="error"] {{ background: {p.red}; color: #FFFFFF; }}

/* ---- botones ---- */
QPushButton {{
    background: {p.surface_alt}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 10px; padding: 9px 18px; font-weight: 600;
}}
QPushButton:hover {{ background: {p.hover}; border-color: {p.muted}; }}
QPushButton:focus {{ border: 2px solid {p.accent}; }}
QPushButton#Primary {{ background: {p.accent}; color: {p.on_accent}; border: none; font-weight: 700; }}
QPushButton#Primary:hover {{ background: {p.accent_hover}; }}

/* ---- zona de importacion ---- */
QFrame#DropZone {{ background: {p.surface}; border: 2px dashed {p.border}; border-radius: 18px; }}
QFrame#DropZone[dragging="true"] {{ background: {p.surface_alt}; border: 2px dashed {p.accent}; }}
QFrame#DropZone QLabel {{ background: transparent; }}

/* ---- entradas ---- */
QDateEdit {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 8px; padding: 6px 10px; min-width: 110px;
}}
QDateEdit:focus {{ border: 2px solid {p.accent}; }}
QDateEdit::drop-down {{ border: none; width: 24px; }}
QCalendarWidget QWidget {{ background: {p.surface}; color: {p.text}; }}
QCalendarWidget QAbstractItemView {{ selection-background-color: {p.accent}; selection-color: {p.on_accent}; }}

/* ---- tablas ---- */
QTableView {{
    background: {p.surface}; alternate-background-color: {p.hover}; color: {p.text};
    border: none; outline: none; gridline-color: transparent;
    selection-background-color: {p.accent}; selection-color: {p.on_accent};
}}
QTableView::item {{ padding: 0 12px; border: none; }}
QHeaderView {{ background: {p.surface}; }}
QHeaderView::section {{
    background: {p.surface}; color: {p.muted}; font-size: 11px; font-weight: 700;
    padding: 8px 12px; border: none; border-bottom: 1px solid {p.border};
}}
QHeaderView::section:hover {{ color: {p.text}; }}
QTableCornerButton::section {{ background: {p.surface}; border: none; }}

/* ---- combos, busqueda y menus ---- */
QComboBox, QLineEdit {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 8px; padding: 7px 12px; min-height: 18px;
}}
QComboBox:hover, QLineEdit:hover {{ border-color: {p.muted}; }}
QComboBox:focus, QLineEdit:focus {{ border: 2px solid {p.accent}; padding: 6px 11px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    selection-background-color: {p.accent}; selection-color: {p.on_accent}; outline: none; padding: 4px;
}}
QPushButton#Arrow {{ padding: 6px 12px; font-size: 16px; font-weight: 700; }}
QMenu {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.border}; border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 8px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p.accent}; color: {p.on_accent}; }}
QMenu::item:disabled {{ color: {p.muted}; }}
QDialog, QMessageBox, QInputDialog {{ background: {p.surface}; color: {p.text}; }}
QLabel#MiniValue {{ font-size: 20px; font-weight: 800; }}
QLabel#MiniValue[tone="negative"] {{ color: {p.red}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.muted}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 4px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {p.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
"""
