"""Paletas de marca (claro/oscuro) y hoja de estilos de la aplicacion.

Identidad: el amarillo dorado y el rojo del logotipo sobre grises carbon (modo oscuro) o papel calido
(modo claro). El amarillo se reserva para lo que importa (pestana activa, accion principal, serie
destacada); el verde marca lo positivo y el rojo lo negativo. La jerarquia la da la tipografia:
Montserrat ExtraBold para titulos y cifras, DM Sans para el texto.
"""
from __future__ import annotations

from dataclasses import dataclass

from ui import fonts as F


@dataclass(frozen=True, slots=True)
class Palette:
    name: str
    bg: str              # fondo de las paginas
    side: str            # fondo de la barra lateral
    surface: str         # tarjetas
    surface_alt: str     # campos, botones secundarios, pildoras
    border: str
    text: str
    muted: str
    accent: str          # amarillo de marca
    accent_hover: str
    on_accent: str       # texto sobre el amarillo
    accent_soft: str     # amarillo muy suave (fondos de aviso, seleccion)
    red: str
    red_soft: str
    green: str
    green_soft: str
    neutral: str         # tercera serie de los graficos
    hover: str           # fondo al pasar el raton
    grid: str            # lineas de cuadricula de los graficos
    glow: str            # color del degradado de fondo (rojo en oscuro, amarillo en claro)
    glow_alpha: int      # intensidad del degradado (0-255)
    series: tuple[str, ...]   # colores para graficos con muchas series (fondos)


DARK = Palette(
    name="dark", bg="#101418", side="#0B0E11", surface="#171C22", surface_alt="#1F252D", border="#262D37",
    text="#F3EFE7", muted="#8F9AA8", accent="#FFD23F", accent_hover="#FFDE6B", on_accent="#16181B",
    accent_soft="#2A2816", red="#F0555A", red_soft="#2D1C20", green="#3FC08F", green_soft="#17291F",
    neutral="#6F7C8A", hover="#212832", grid="#232A33", glow="#E5484D", glow_alpha=70,
    series=("#FFD23F", "#F0555A", "#6F7C8A", "#F2A900", "#FF9AA0", "#A9B4C0"),
)
LIGHT = Palette(
    name="light", bg="#F5F0E6", side="#EDE6D8", surface="#FFFFFF", surface_alt="#F1EBDF", border="#E7E0D1",
    text="#1B1E22", muted="#6C7380", accent="#F5B800", accent_hover="#FFC81F", on_accent="#17191C",
    accent_soft="#FBF0CC", red="#D63B3B", red_soft="#FBE3E1", green="#1E9E6C", green_soft="#DDF3E8",
    neutral="#8B94A0", hover="#F4EFE4", grid="#ECE6D8", glow="#F5B800", glow_alpha=85,
    series=("#F5B800", "#D63B3B", "#8B94A0", "#B07F00", "#E8590C", "#B7BEC8"),
)
PALETTES = {"dark": DARK, "light": LIGHT}

_current = DARK


def current() -> Palette:
    return _current


def set_current(palette: Palette) -> None:
    global _current
    _current = palette


def stylesheet(p: Palette) -> str:
    body, medium, bold = F.stack(F.BODY), F.stack(F.BODY_MEDIUM), F.stack(F.BODY_BOLD)
    display, display_bold, label = F.stack(F.DISPLAY), F.stack(F.DISPLAY_BOLD), F.stack(F.LABEL)
    return f"""
QWidget {{ color: {p.text}; }}
QMainWindow, QWidget#Root {{ background: {p.bg}; }}
QWidget#Page, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollArea {{ border: none; }}
QLabel {{ background: transparent; }}
QToolTip {{
    background: {p.surface_alt}; color: {p.text}; border: 1px solid {p.border}; padding: 7px 10px;
    font-family: {medium}; font-size: 12px;
}}

/* ---------------------------------------------------------------- tipografia */
QLabel#H1 {{ font-family: {display}; font-size: 32px; }}
QLabel#H2 {{ font-family: {bold}; font-size: 16px; }}
QLabel#Muted {{ color: {p.muted}; }}
QLabel#Small {{ color: {p.muted}; font-size: 12px; }}
QLabel#Eyebrow {{ color: {p.accent}; font-family: {label}; font-size: 11px; }}
QLabel#SectionTitle {{ color: {p.muted}; font-family: {label}; font-size: 11px; }}
QLabel#Small[state="ok"] {{ color: {p.text}; }}
QLabel#Small[state="error"] {{ color: {p.red}; font-family: {bold}; }}

/* ---------------------------------------------------------------- barra lateral */
QFrame#Sidebar {{ background: {p.side}; border: none; }}
QPushButton#NavButton {{
    text-align: left; padding: 11px 16px; border: none; border-radius: 12px;
    color: {p.muted}; background: transparent; font-family: {bold}; font-size: 14px;
}}
QPushButton#NavButton:hover {{ background: {p.hover}; color: {p.text}; }}
QPushButton#NavButton:checked {{ background: {p.accent}; color: {p.on_accent}; }}
QPushButton#NavButton:focus {{ border: 2px solid {p.accent}; padding: 9px 14px; }}
QPushButton#PillButton {{
    text-align: left; padding: 0 18px 0 14px; min-height: 40px; max-height: 40px;
    border: none; border-radius: 20px; background: {p.surface_alt};
    color: {p.text}; font-family: {bold}; font-size: 13px;
}}
QPushButton#PillButton:hover {{ background: {p.hover}; }}
QPushButton#PillButton:checked {{ background: {p.accent}; color: {p.on_accent}; }}
QPushButton#PillButton:focus {{ border: 2px solid {p.accent}; padding: 0 16px 0 12px; }}
QLabel#SidebarFoot {{ color: {p.muted}; font-size: 11px; }}

/* ---------------------------------------------------------------- tarjetas */
QFrame#Card {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 20px; }}
QFrame#Card QLabel {{ background: transparent; }}
QFrame#Hero {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 24px; }}
QFrame#Hero QLabel {{ background: transparent; }}
QFrame#Band {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 20px; }}
QFrame#Band QLabel {{ background: transparent; }}
QFrame#BandCell {{ background: transparent; border: none; border-radius: 0; }}
QFrame#BandDivider {{ background: {p.border}; border: none; }}
QLabel#CardTitle {{ color: {p.muted}; font-family: {label}; font-size: 11px; }}
QLabel#CardValue {{ font-family: {display}; font-size: 34px; }}
QLabel#CardValue[tone="negative"], QLabel#MiniValue[tone="negative"], QLabel#HeroValue[tone="negative"] {{ color: {p.red}; }}
QLabel#CardValue[tone="positive"], QLabel#MiniValue[tone="positive"] {{ color: {p.green}; }}
QLabel#HeroValue {{ font-family: {display}; font-size: 52px; }}
QLabel#MiniValue {{ font-family: {display_bold}; font-size: 22px; }}
QLabel#CardSub {{ color: {p.muted}; font-size: 12px; }}
QFrame#AccentBar {{ background: transparent; border: none; }}

/* chips de variacion (+4,4 %) */
QLabel#Chip {{
    border-radius: 11px; padding: 3px 10px; font-family: {bold}; font-size: 12px;
    background: {p.surface_alt}; color: {p.text};
}}
QLabel#Chip[tone="positive"] {{ background: {p.green_soft}; color: {p.green}; }}
QLabel#Chip[tone="negative"] {{ background: {p.red_soft}; color: {p.red}; }}
QLabel#Chip[tone="accent"] {{ background: {p.accent_soft}; color: {p.accent}; }}

/* ---------------------------------------------------------------- avisos y estados */
QFrame#Banner {{ background: {p.accent_soft}; border: 1px solid {p.accent}; border-radius: 16px; }}
QFrame#Banner QLabel {{ background: transparent; }}
QLabel#Pill {{
    border-radius: 9px; padding: 3px 12px; font-family: {bold}; font-size: 11px;
    background: {p.surface_alt}; color: {p.text};
}}
QLabel#Pill[state="ok"] {{ background: {p.green_soft}; color: {p.green}; }}
QLabel#Pill[state="warn"] {{ background: {p.accent_soft}; color: {p.accent}; }}
QLabel#Pill[state="error"] {{ background: {p.red_soft}; color: {p.red}; }}

/* ---------------------------------------------------------------- botones */
QPushButton {{
    background: {p.surface_alt}; color: {p.text}; border: none; border-radius: 12px;
    padding: 10px 20px; font-family: {bold}; font-size: 13px;
}}
QPushButton:hover {{ background: {p.hover}; }}
QPushButton:focus {{ border: 2px solid {p.accent}; padding: 8px 18px; }}
QPushButton:disabled {{ color: {p.muted}; }}
QPushButton#Primary {{ background: {p.accent}; color: {p.on_accent}; padding: 11px 24px; }}
QPushButton#Primary:hover {{ background: {p.accent_hover}; }}
QPushButton#Primary:disabled {{ background: {p.surface_alt}; color: {p.muted}; }}
QPushButton#Arrow {{ padding: 6px 12px; font-size: 16px; }}
QPushButton#BackButton {{
    background: transparent; color: {p.muted}; padding: 6px 14px 6px 8px; border-radius: 10px;
}}
QPushButton#BackButton:hover {{ background: {p.hover}; color: {p.text}; }}

/* menu de ayuda */
QPushButton#HubCard {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: 20px; text-align: left; padding: 0;
}}
QPushButton#HubCard:hover {{ background: {p.hover}; border-color: {p.accent}; }}
QPushButton#HubCard:focus {{ border: 2px solid {p.accent}; padding: 0; }}
QLabel#HubTitle {{ font-family: {display_bold}; font-size: 16px; }}
QLabel#IconChip {{ background: {p.accent}; border-radius: 30px; }}
QLabel#StepBadge {{
    background: {p.accent}; color: {p.on_accent}; border-radius: 13px; font-family: {display_bold}; font-size: 12px;
}}
QFrame#Card QLabel#StepBadge {{ background: {p.accent}; color: {p.on_accent}; }}

/* ---------------------------------------------------------------- zona de importacion */
QFrame#DropZone {{ background: {p.surface}; border: 2px dashed {p.border}; border-radius: 24px; }}
QFrame#DropZone[dragging="true"] {{ background: {p.accent_soft}; border: 2px dashed {p.accent}; }}
QFrame#DropZone QLabel {{ background: transparent; }}

/* ---------------------------------------------------------------- entradas */
QComboBox, QLineEdit, QDateEdit {{
    background: {p.surface_alt}; color: {p.text}; border: 1px solid {p.surface_alt};
    border-radius: 12px; padding: 8px 14px; min-height: 20px; font-family: {medium};
}}
QComboBox:hover, QLineEdit:hover, QDateEdit:hover {{ border-color: {p.border}; }}
QComboBox:focus, QLineEdit:focus, QDateEdit:focus {{ border: 2px solid {p.accent}; padding: 7px 13px; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border}; border-radius: 10px;
    selection-background-color: {p.accent}; selection-color: {p.on_accent}; outline: none; padding: 4px;
}}
QCalendarWidget QWidget {{ background: {p.surface}; color: {p.text}; }}
QCalendarWidget QAbstractItemView {{ selection-background-color: {p.accent}; selection-color: {p.on_accent}; }}
QMenu, QComboBox QAbstractItemView, QMessageBox, QInputDialog, QCalendarWidget {{ font-family: {medium}; font-size: 13px; }}
QMenu {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.border}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 9px 26px; border-radius: 8px; margin: 1px 0; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 6px 8px; }}
QMenu::item:selected {{ background: {p.accent}; color: {p.on_accent}; }}
QMenu::item:disabled {{ color: {p.muted}; }}
QDialog, QMessageBox, QInputDialog {{ background: {p.surface}; color: {p.text}; }}

/* ---------------------------------------------------------------- tablas */
QTableView {{
    background: transparent; color: {p.text}; border: none; outline: none; gridline-color: transparent;
    selection-background-color: {p.accent_soft}; selection-color: {p.text};
}}
QTableView::item {{ padding: 0 8px; border: none; border-bottom: 1px solid {p.border}; }}
QTableView::item:hover {{ background: {p.hover}; }}
QTableView::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: transparent; color: {p.muted}; font-family: {label}; font-size: 10px;
    padding: 8px 8px; border: none; border-bottom: 1px solid {p.border};
}}
QHeaderView::section:hover {{ color: {p.text}; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

/* ---------------------------------------------------------------- barras de desplazamiento */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.muted}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 4px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {p.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
"""
