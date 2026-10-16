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
    field_edge: str      # el borde de los campos de texto y desplegables (sin el, un campo vacio no se distingue de la tarjeta)
    accent_edge: str     # el filo del elemento activo de la barra lateral (un tono mas hondo del acento)
    accent_text: str     # el acento cuando es TEXTO pequeno (en claro, un ocre oscuro: el amarillo de marca no llega a 4,5:1 sobre blanco)
    red: str
    red_soft: str
    green: str
    green_soft: str
    green_text: str      # el verde cuando es texto pequeno (el de las cifras grandes basta con 3:1; el pequeno pide 4,5:1)
    neutral: str         # tercera serie de los graficos
    hover: str           # fondo al pasar el raton
    grid: str            # lineas de cuadricula de los graficos
    glow: str            # color del degradado de fondo (rojo en oscuro, amarillo en claro)
    glow_alpha: int      # intensidad del degradado (0-255)
    series: tuple[str, ...]   # colores para graficos con muchas series (fondos)


DARK = Palette(
    name="dark", bg="#101418", side="#0C0F12", surface="#171C22", surface_alt="#1E242B", border="#242B34",
    text="#EFEBE3", muted="#8D97A4", accent="#F5BE1E", accent_hover="#FFCC3D", on_accent="#1A1500",
    accent_soft="#2A2410", field_edge="#3C4756", accent_edge="#FFE08A", accent_text="#F5BE1E", red="#F2464A", red_soft="#34171A", green="#4DB48C", green_soft="#16261F",
    green_text="#4DB48C",
    neutral="#6B7885", hover="#1F252C", grid="#1F262E", glow="#B7584F", glow_alpha=46,
    series=("#F5BE1E", "#F2464A", "#6B7885", "#C48F00", "#F59A9C", "#A5B0BC"),
)
LIGHT = Palette(
    name="light", bg="#F6F2EA", side="#EFE9DC", surface="#FFFFFF", surface_alt="#F3EEE3", border="#ECE6D9",
    text="#22262B", muted="#626872", accent="#EDB00C", accent_hover="#F7C023", on_accent="#2A2000",
    accent_soft="#FCF1CB", field_edge="#B9B1A0", accent_edge="#B78A0B", accent_text="#80590A", red="#DC2F36", red_soft="#FCE0E0", green="#3E9C77", green_soft="#E0F1E9",
    green_text="#2F7D5E",
    neutral="#9098A3", hover="#F6F1E6", grid="#F0EADE", glow="#F5BE1E", glow_alpha=34,
    series=("#EDB00C", "#DC2F36", "#9098A3", "#B07F00", "#E8703F", "#BCC2CB"),
)
PALETTES = {"dark": DARK, "light": LIGHT}

_current = DARK


def current() -> Palette:
    return _current


def set_current(palette: Palette) -> None:
    global _current
    _current = palette


def arrow_url(color: str) -> str:
    """Ruta de un PNG con una flecha hacia abajo del color dado (la hoja de estilos solo acepta archivos). Vacio si no hay GUI."""
    import tempfile
    from pathlib import Path

    try:
        from PySide6.QtGui import QGuiApplication, QTransform

        if QGuiApplication.instance() is None:
            return ""
        from ui import icons

        folder = Path(tempfile.gettempdir()) / "kreix-ui"
        folder.mkdir(exist_ok=True)
        path = folder / f"down-{color.lstrip('#')}.png"
        if not path.exists():
            icons.pixmap("chevron", color, 24, 2.2).transformed(QTransform().rotate(90)).save(str(path))
        return path.as_posix()
    except Exception:                                        # sin flecha la app sigue funcionando
        return ""


def rgba(color: str, alpha: float) -> str:
    """'#RRGGBB' + opacidad 0-1 -> 'rgba(r, g, b, a)' para la hoja de estilos (rellenos translucidos)."""
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def stylesheet(p: Palette) -> str:
    body, medium = F.stack(F.BODY), F.stack(F.BODY_MEDIUM)
    display, display_bold, label = F.stack(F.DISPLAY), F.stack(F.DISPLAY_BOLD), F.stack(F.LABEL)
    # Jerarquia estricta: negrita y extranegrita SOLO para las cifras principales (Montserrat). Todo lo demas, DM Sans en
    # regular (etiquetas, en gris) o medium (titulos y controles).
    bold = medium
    green_soft, red_soft, accent_soft = rgba(p.green, 0.13), rgba(p.red, 0.17), rgba(p.accent, 0.16)
    arrow = arrow_url(p.muted)
    arrow_rule = f"image: url({arrow}); width: 12px; height: 12px;" if arrow else ""
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
QLabel#H1 {{ font-family: {label}; font-size: 30px; }}
QLabel#H2 {{ font-family: {medium}; font-size: 15px; }}
QLabel#Muted {{ color: {p.muted}; }}
QLabel#DateLine {{ color: {p.text}; font-family: {body}; font-size: 20px; }}
QLabel#Headline {{ color: {p.text}; font-family: {medium}; font-size: 14px; }}
QLabel#Small {{ color: {p.muted}; font-size: 13px; }}
QLabel#Eyebrow {{ color: {p.accent}; font-family: {body}; font-size: 11px; }}
QLabel#SectionTitle {{ color: {p.muted}; font-family: {medium}; font-size: 12px; }}
QLabel#Small[state="ok"] {{ color: {p.text}; }}
QLabel#Small[state="error"] {{ color: {p.red}; font-family: {bold}; }}

/* ---------------------------------------------------------------- barra lateral */
QFrame#Sidebar {{ background: {p.side}; border: none; }}
/* Un solo vocabulario para toda la navegacion (paginas, Datos, Ajustes, Ayuda y el submenu): en reposo, sin relleno; al pasar,
   un fondo suave; la pagina actual, el acento con un filo mas hondo. El aro negro queda solo para el foco de teclado. */
QPushButton#NavButton, QPushButton#PillButton {{
    text-align: left; padding: 0 16px 0 14px; min-height: 42px; max-height: 42px;
    border: 2px solid transparent; border-radius: 13px; background: transparent;
    color: {p.muted}; font-family: {medium}; font-size: 14px; outline: none;
}}
QPushButton#NavButton:hover, QPushButton#PillButton:hover {{ background: {p.hover}; color: {p.text}; }}
QPushButton#NavButton:checked, QPushButton#PillButton:checked {{
    background: {p.accent}; color: {p.on_accent}; border: 2px solid {p.accent_edge};
}}
QPushButton#NavButton[kbd="true"]:focus, QPushButton#PillButton[kbd="true"]:focus {{ border: 2px solid {p.text}; }}
QFrame#SidebarRule {{ background: {p.border}; border: none; min-height: 1px; max-height: 1px; }}
QLabel#SidebarFoot {{ color: {p.muted}; font-size: 12px; }}

/* ---------------------------------------------------------------- tarjetas */
QFrame#Card {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 22px; }}
QFrame#Card QLabel {{ background: transparent; }}
QFrame#Hero {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 34px; }}
QFrame#Hero QLabel {{ background: transparent; }}
QFrame#Band {{ background: transparent; border: none; }}
QFrame#Band QLabel {{ background: transparent; }}
QFrame#Section {{ background: transparent; border: none; }}
QFrame#Section QLabel {{ background: transparent; }}
QFrame#BandCell {{ background: transparent; border: none; border-radius: 0; }}
QFrame#BandDivider {{ background: {p.border}; border: none; }}
QLabel#CardTitle {{ color: {p.muted}; font-family: {medium}; font-size: 13px; }}
QLabel#CardValue {{ font-family: {display}; font-size: 34px; }}
QLabel#CardValue[tone="negative"], QLabel#MiniValue[tone="negative"], QLabel#HeroValue[tone="negative"] {{ color: {p.red}; }}
QLabel#CardValue[tone="positive"], QLabel#MiniValue[tone="positive"] {{ color: {p.green}; }}
QLabel#HeroValue {{ font-family: {display}; font-size: 52px; }}
QLabel#MiniValue {{ font-family: {label}; font-size: 22px; }}
QLabel#CardSub {{ color: {p.muted}; font-size: 13px; }}
QFrame#AccentBar {{ background: transparent; border: none; }}

/* chips de variacion (+4,4 %) */
QLabel#Chip {{
    border-radius: 11px; padding: 3px 10px; font-family: {bold}; font-size: 12px;
    background: {p.surface_alt}; color: {p.text};
}}
QLabel#Chip[tone="positive"] {{ background: {green_soft}; color: {p.green_text}; }}
QLabel#Chip[tone="negative"] {{ background: {red_soft}; color: {p.red}; }}
QLabel#Chip[tone="accent"] {{ background: {accent_soft}; color: {p.accent_text}; }}

/* ---------------------------------------------------------------- avisos y estados */
QFrame#Banner {{ background: {accent_soft}; border: 1px solid {rgba(p.accent, 0.45)}; border-radius: 20px; }}
QFrame#Banner QLabel {{ background: transparent; }}
QLabel#Pill {{
    border-radius: 9px; padding: 3px 12px; font-family: {bold}; font-size: 11px;
    background: {p.surface_alt}; color: {p.text};
}}
QLabel#Pill[state="ok"] {{ background: {green_soft}; color: {p.green_text}; }}
QLabel#Pill[state="warn"] {{ background: {accent_soft}; color: {p.accent_text}; }}
QLabel#Pill[state="error"] {{ background: {red_soft}; color: {p.red}; }}

/* ---------------------------------------------------------------- botones */
QPushButton {{
    background: {p.surface_alt}; color: {p.text}; border: none; border-radius: 14px;
    padding: 11px 22px; font-family: {bold}; font-size: 13px; outline: none;
}}
QPushButton:hover {{ background: {p.hover}; }}
QPushButton[kbd="true"]:focus {{ border: 2px solid {p.accent}; padding: 8px 18px; outline: none; }}
QPushButton:disabled {{ color: {p.muted}; }}
QPushButton#Primary {{ background: {p.accent}; color: {p.on_accent}; padding: 12px 26px; }}
QPushButton#Primary:hover {{ background: {p.accent_hover}; }}
QPushButton#Primary:disabled {{ background: {p.surface_alt}; color: {p.muted}; }}
QPushButton#Arrow {{ padding: 6px 12px; font-size: 16px; }}
QLabel#LockError {{ color: {p.red}; font-family: {medium}; }}
QPushButton#LinkButton {{ background: transparent; color: {p.muted}; border: none; padding: 8px 10px 8px 2px; min-width: 170px; text-decoration: underline; }}
QPushButton#LinkButton:hover {{ color: {p.red}; }}
QPushButton#BackButton {{
    background: transparent; color: {p.muted}; padding: 6px 14px 6px 8px; border-radius: 10px;
}}
QPushButton#BackButton:hover {{ background: {p.hover}; color: {p.text}; }}

/* menu de ayuda */
QPushButton#HubCard {{
    background: transparent; border: 2px solid transparent; border-radius: 22px; text-align: left; padding: 0;
}}
QPushButton#HubCard:hover {{ background: {p.hover}; }}
QPushButton#HubCard:focus {{ border: 2px solid {p.accent}; padding: 0; }}
QLabel#HubTitle {{ font-family: {medium}; font-size: 16px; }}
QLabel#IconChip {{ background: {accent_soft}; border-radius: 30px; }}
QLabel#StepBadge {{
    background: {accent_soft}; color: {p.accent_text}; border-radius: 13px; font-family: {medium}; font-size: 12px;
}}
QFrame#Card QLabel#StepBadge, QFrame#GroupCard QLabel#StepBadge, QFrame#Section QLabel#StepBadge {{ background: {accent_soft}; color: {p.accent_text}; }}

/* ---------------------------------------------------------------- tarjetas tematicas (Ajustes y Ayuda) */
QFrame#GroupCard {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 22px; }}
QFrame#GroupCard QLabel {{ background: transparent; }}
QLabel#FieldTitle {{ color: {p.text}; font-family: {medium}; font-size: 15px; }}
QFrame#SectionCard {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 22px; }}
QFrame#SectionCard[tone="alert"] {{ border: 1px solid {rgba(p.red, 0.55)}; }}
QFrame#SectionCard QLabel {{ background: transparent; }}
QFrame#SectionHead {{
    background: transparent; border: none; border-bottom: 1px solid {p.border};
    border-top-left-radius: 21px; border-top-right-radius: 21px;
}}
QFrame#SectionHead[tone="alert"] {{ background: {red_soft}; border-bottom: 1px solid {rgba(p.red, 0.35)}; }}
QFrame#SectionHead[tone="tip"] {{ background: {accent_soft}; border-bottom: 1px solid {rgba(p.accent, 0.4)}; }}
QLabel#SectionHeadTitle {{ color: {p.text}; font-family: {medium}; font-size: 15px; }}
QFrame#Divider {{ background: {p.border}; border: none; min-height: 1px; max-height: 1px; }}
QLabel#GroupTitle {{ color: {p.text}; font-family: {medium}; font-size: 14px; }}
QLabel#DetailLabel {{ color: {p.muted}; font-family: {medium}; font-size: 12px; }}
QLabel#DetailLabel[tone="alert"] {{ color: {p.red}; }}
QLabel#DetailLabel[tone="tip"] {{ color: {p.accent_text}; }}
QPushButton#Danger {{ background: transparent; color: {p.red}; border: 1px solid {rgba(p.red, 0.6)}; }}
QPushButton#Danger:hover {{ background: {red_soft}; }}

/* ---------------------------------------------------------------- submenu "Datos" */
QFrame#DataFlyout {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 20px; }}
QPushButton#FlyItem {{
    text-align: left; padding: 11px 20px 11px 14px; min-width: 150px; border: 2px solid transparent; border-radius: 13px;
    color: {p.text}; background: transparent; font-family: {medium}; font-size: 13px; outline: none;
}}
QPushButton#FlyItem:hover {{ background: {p.hover}; }}
QPushButton#FlyItem:checked {{ background: {p.accent}; color: {p.on_accent}; border: 2px solid {p.accent_edge}; }}
QPushButton#FlyItem[kbd="true"]:focus {{ border: 2px solid {p.text}; }}

/* ---------------------------------------------------------------- selector de idioma */
QPushButton#LangButton {{
    background: {p.surface_alt}; color: {p.text}; border: 2px solid transparent; border-radius: 20px;
    padding: 6px 18px 6px 10px; font-family: {bold}; font-size: 13px; text-align: left;
}}
QPushButton#LangButton:hover {{ background: {p.hover}; }}
QPushButton#LangButton:checked {{ border: 2px solid {p.accent}; background: {accent_soft}; }}
QPushButton#LangButton:focus {{ border: 2px solid {p.text}; padding: 6px 18px 6px 10px; }}
QPushButton#LangButton:checked:focus {{ border: 2px solid {p.accent}; }}

/* ---------------------------------------------------------------- buscador global (Ctrl+K) */
QFrame#PaletteCard {{ background: {p.surface}; border: 1px solid {rgba(p.accent, 0.6)}; border-radius: 26px; }}
QFrame#PaletteCard QLabel {{ background: transparent; }}
QListWidget#PaletteList {{ background: transparent; border: none; outline: none; }}
QListWidget#PaletteList::item {{ border-radius: 10px; padding: 0; margin: 1px 0; }}
QListWidget#PaletteList::item:selected {{ background: {p.accent}; }}
QLabel#PaletteRow[selected="true"] {{ color: {p.on_accent}; }}
QListWidget#PaletteList::item:hover:!selected {{ background: {p.hover}; }}
QLabel#PaletteRow {{ font-family: {medium}; font-size: 13px; }}

/* ---------------------------------------------------------------- aviso de datos de ejemplo */
QFrame#DemoBanner {{ background: {accent_soft}; border: none; border-bottom: 1px solid {p.accent}; }}
QLabel#DemoBannerText {{ color: {p.text}; font-family: {bold}; font-size: 13px; background: transparent; }}

/* ---------------------------------------------------------------- aviso flotante */
QFrame#Toast {{ background: {p.surface}; border: 1px solid {rgba(p.accent, 0.6)}; border-radius: 20px; }}
QFrame#Toast QLabel {{ background: transparent; font-family: {medium}; font-size: 13px; color: {p.text}; }}
QPushButton#ToastAction {{
    background: {p.accent}; color: {p.on_accent}; padding: 7px 16px; border-radius: 10px; font-size: 12px;
}}
QPushButton#ToastAction:hover {{ background: {p.accent_hover}; }}
QPushButton#ToastClose {{
    background: transparent; color: {p.muted}; padding: 2px 10px; font-size: 18px; border-radius: 10px;
}}
QPushButton#ToastClose:hover {{ background: {p.hover}; color: {p.text}; }}

/* ---------------------------------------------------------------- zona de importacion */
QFrame#DropZone {{ background: {p.surface}; border: 1px dashed {p.accent}; border-radius: 34px; }}
QFrame#ListRow {{ background: transparent; border: none; border-top: 1px solid {p.border}; }}
QFrame#ListRow QLabel {{ background: transparent; }}
QFrame#DropZone[dragging="true"] {{ background: {accent_soft}; border: 2px dashed {p.accent}; }}
QFrame#DropZone QLabel {{ background: transparent; }}

/* ---------------------------------------------------------------- entradas */
QLineEdit {{ lineedit-password-character: 8226; }}
QPushButton#AccountPicker {{ text-align: left; padding: 9px 40px 9px 16px; }}
QMenu QCheckBox#PickerBox {{ padding: 9px 22px 9px 14px; spacing: 12px; background: transparent; color: {p.text}; font-family: {medium}; font-size: 13px; }}
QMenu QCheckBox#PickerBox:hover {{ background: {p.hover}; border-radius: 10px; }}
QMenu QCheckBox#PickerBox::indicator {{ width: 18px; height: 18px; border-radius: 6px; border: 1px solid {p.muted}; background: {p.surface}; }}
QMenu QCheckBox#PickerBox::indicator:checked {{ background: {p.accent}; border: 1px solid {p.accent}; }}
QComboBox, QLineEdit, QDateEdit, QDoubleSpinBox {{
    background: {p.surface_alt}; color: {p.text}; border: 1px solid {p.field_edge};
    border-radius: 14px; padding: 9px 16px; min-height: 20px; font-family: {body};
}}
QComboBox:hover, QLineEdit:hover, QDateEdit:hover, QDoubleSpinBox:hover {{ border-color: {p.muted}; }}
QComboBox:focus, QLineEdit:focus, QDateEdit:focus, QDoubleSpinBox:focus {{ border: 2px solid {p.accent}; padding: 7px 13px; }}
QComboBox {{ combobox-popup: 0; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 30px; }}
QComboBox::down-arrow {{ {arrow_rule} }}
QPushButton::menu-indicator {{ {arrow_rule} subcontrol-origin: padding; subcontrol-position: right center; right: 14px; }}
QCheckBox {{ spacing: 10px; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 6px; border: 1px solid {p.muted}; background: {p.surface}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border: 1px solid {p.accent}; }}
QCheckBox::indicator:hover {{ border-color: {p.accent}; }}
QPushButton#InfoButton {{
    background: transparent; color: {p.muted}; border: 1px solid {p.muted}; border-radius: 10px; padding: 0;
    min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; font-family: {medium}; font-size: 11px;
}}
QPushButton#InfoButton:hover {{ background: {p.accent}; border-color: {p.accent}; color: {p.on_accent}; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}
QComboBoxPrivateContainer {{ background: transparent; border: none; }}
QComboBox QFrame {{ background: transparent; border: none; }}
QComboBox QAbstractItemView {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border}; border-radius: 16px;
    selection-background-color: transparent; selection-color: {p.text}; outline: none; padding: 8px;
}}
QComboBox QAbstractItemView::item {{ min-height: 26px; padding: 6px 14px; margin: 2px 0; border-radius: 10px; }}
QComboBox QAbstractItemView::item:hover {{ background: {p.hover}; color: {p.text}; }}
QComboBox QAbstractItemView::item:selected {{ background: {accent_soft}; color: {p.text}; }}
QCalendarWidget QWidget {{ background: {p.surface}; color: {p.text}; }}
QCalendarWidget QAbstractItemView {{ selection-background-color: {p.accent}; selection-color: {p.on_accent}; }}
QMenu, QComboBox QAbstractItemView, QMessageBox, QInputDialog, QCalendarWidget {{ font-family: {medium}; font-size: 13px; }}
QMenu {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.border}; border-radius: 16px; padding: 8px; }}
QMenu::item {{ padding: 9px 26px; border-radius: 8px; margin: 1px 0; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 6px 8px; }}
QMenu::item:selected {{ background: {p.accent}; color: {p.on_accent}; }}
QMenu::item:disabled {{ color: {p.muted}; }}
QDialog, QMessageBox, QInputDialog {{ background: {p.surface}; color: {p.text}; }}
QDialog QLabel {{ background: transparent; }}
QDialog QLabel#Muted {{ color: {p.muted}; }}

/* ---------------------------------------------------------------- tablas */
QTableView {{
    background: transparent; color: {p.text}; border: none; outline: none; gridline-color: transparent;
    selection-background-color: {accent_soft}; selection-color: {p.text};
}}
QTableView::item {{ padding: 0 8px; border: none; border-bottom: 1px solid {rgba(p.border, 0.65)}; }}
QTableView::item:hover {{ background: {p.hover}; }}
QTableView::item:selected {{ background: {accent_soft}; color: {p.text}; }}
/* en las secciones sin caja, el texto de la primera columna arranca justo donde el titulo (sin los 8 px de la celda) */
QFrame#Section QTableView::item {{ padding: 0 14px 0 0; }}
QFrame#Section QHeaderView::section {{ padding: 8px 14px 8px 0; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: transparent; color: {p.muted}; font-family: {medium}; font-size: 11px;
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
