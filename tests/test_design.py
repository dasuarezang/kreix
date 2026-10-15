from datetime import date
from decimal import Decimal as D

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QFontDatabase

from core.account_metrics import CategoryAmount
from core.enums import TxCategory
from core.metrics import AllocationSlice, MonthlyFlow, WealthPoint
from ui import fonts, theme
from ui.widgets import charts
from ui.widgets.cards import ElidedLabel, HeroCard, PageHeader, StatBand, StatCard
from ui.widgets.charts import axis_label, monotone_path, nice_ticks


@pytest.fixture(autouse=True)
def static_charts():
    charts.ANIMATIONS = False


# ---------------------------------------------------------------- tipografia
def test_bundled_fonts_load_and_every_weight_is_its_own_family(qapp):
    assert fonts.load_fonts() is True
    available = set(QFontDatabase.families())
    for family in (fonts.DISPLAY, fonts.DISPLAY_BOLD, fonts.LABEL, fonts.BODY, fonts.BODY_MEDIUM, fonts.BODY_BOLD):
        assert family in available and fonts.family(family) == family
    assert fonts.family("Fuente Que No Existe") == fonts.FALLBACK
    assert fonts.qfont(fonts.BODY, 13, spacing=1.2, tabular=True).pixelSize() == 13


def test_font_files_and_licenses_ship_with_the_app():
    for name in ("MontserratExtraBold", "MontserratBold", "MontserratSemiBold", "DMSans", "DMSansMedium", "DMSansBold"):
        assert (fonts.FONT_DIR / f"{name}.ttf").is_file()
    assert "SIL Open Font License" in (fonts.FONT_DIR / "LICENCIAS.txt").read_text(encoding="utf-8")


def test_stylesheet_uses_the_brand_fonts_for_hierarchy(qapp):
    qss = theme.stylesheet(theme.DARK)
    assert fonts.DISPLAY in qss and fonts.BODY_MEDIUM in qss and fonts.LABEL in qss and fonts.BODY_BOLD not in qss
    for palette in theme.PALETTES.values():
        assert palette.accent in theme.stylesheet(palette)


# ---------------------------------------------------------------- utilidades de grafico
def test_nice_ticks_cover_the_range_with_round_steps():
    ticks = nice_ticks(0, 4300)
    assert ticks[0] == 0 and ticks[-1] >= 4300 and len(ticks) <= 8
    steps = {round(b - a, 6) for a, b in zip(ticks, ticks[1:])}
    assert len(steps) == 1 and steps.pop() in (500, 1000, 2000, 1250, 2500)
    assert nice_ticks(-120, 300)[0] <= -120 and 0 in nice_ticks(-120, 300)
    assert len(nice_ticks(5, 5)) >= 2                                        # rango vacio: no revienta


def test_axis_labels_are_short_and_spanish():
    assert axis_label(0) == "0" and axis_label(250) == "250" and axis_label(1500) == "1,5k"
    assert axis_label(5000) == "5k" and axis_label(-2500) == "−2,5k" and axis_label(2_000_000) == "2M"


def test_monotone_curve_never_overshoots_the_data():
    pts = [QPointF(0, 0), QPointF(1, 10), QPointF(2, 10), QPointF(3, 0)]
    box = monotone_path(pts).boundingRect()
    assert box.top() >= -1e-6 and box.bottom() <= 10 + 1e-6                  # una curva normal pasaria de 10 o bajaria de 0
    assert monotone_path([]).isEmpty() and monotone_path([QPointF(1, 1)]).elementCount() == 1


# ---------------------------------------------------------------- los graficos se dibujan
def months(n):
    return [MonthlyFlow(date(2026, m, 1), D(900 + 40 * m), D(400 + 25 * m), D(300 if m % 2 else 0)) for m in range(1, n + 1)]


def wealth(n):
    return [WealthPoint(date(2026, m, 28), D(100), D(1000 * m), D(900 * m), D(1000 * m + 100)) for m in range(1, n + 1)]


CHART_NAMES = ["flow", "income", "wealth", "portfolio", "balance", "donut", "categories"]


def all_charts():   # se construye dentro de cada test: los widgets necesitan una QApplication
    return {
        "flow": (charts.FlowChart(), lambda c, n: c.set_data(months(n))),
        "income": (charts.IncomeExpenseChart(), lambda c, n: c.set_data(months(n))),
        "wealth": (charts.WealthChart(), lambda c, n: c.set_data(wealth(n))),
        "portfolio": (charts.PortfolioChart(), lambda c, n: c.set_data(wealth(n))),
        "balance": (charts.BalanceChart(), lambda c, n: c.set_data([(date(2026, 9, d + 1), D(100 + d * 7)) for d in range(n)])),
        "donut": (charts.DonutChart(), lambda c, n: c.set_data([AllocationSlice("Inversión", D(900), D("0.9")),
                                                                  AllocationSlice("Liquidez", D(100), D("0.1"))][:n])),
        "categories": (charts.CategoryBarsChart(), lambda c, n: c.set_data(
            [CategoryAmount(TxCategory.GROCERIES, D(300 - 30 * i), D("0.2")) for i in range(n)])),
    }


@pytest.mark.parametrize("name", CHART_NAMES)
@pytest.mark.parametrize("count", [0, 1, 2, 6, 12])
def test_every_chart_paints_with_any_amount_of_data(qapp, name, count):
    chart, load = all_charts()[name]
    chart.resize(560, 320)
    load(chart, count)
    assert not chart.grab().isNull()
    chart.resize(200, 160)                                                    # y tambien en un hueco pequeno
    assert not chart.grab().isNull()


@pytest.mark.parametrize("name", CHART_NAMES)
def test_every_chart_shows_a_hover_card_without_errors(qapp, name):
    chart, load = all_charts()[name]
    chart.resize(560, 320)
    load(chart, 6)
    for point in (QPointF(280, 150), QPointF(5, 5), QPointF(555, 315), QPointF(-10, 10)):
        chart._mouse = point
        assert not chart.grab().isNull()
    chart._mouse = None
    assert not chart.grab().isNull()


def test_empty_charts_say_so_and_follow_the_theme(qapp):
    for name, (chart, load) in all_charts().items():
        chart.resize(400, 260)
        load(chart, 0)
        assert chart.has_data is False and chart.EMPTY_TEXT
        theme.set_current(theme.LIGHT)
        chart.refresh_theme()
        assert not chart.grab().isNull()
        theme.set_current(theme.DARK)


def test_donut_hover_finds_the_slice_under_the_cursor(qapp):
    donut = charts.DonutChart()
    donut.resize(700, 320)
    donut.set_data([AllocationSlice("Inversión", D(75), D("0.75")), AllocationSlice("Liquidez", D(25), D("0.25"))])
    donut.grab()                                                              # fija la geometria
    center, radius, _ = donut._geometry
    donut._mouse = QPointF(center.x() + radius, center.y())                   # a las 3 en punto: dentro del primer trozo (0-270 grados)
    assert donut._hover_slice() == 0
    donut._mouse = QPointF(center.x() - radius, center.y() - 5)               # a las 9, algo por encima: ultimo cuarto
    assert donut._hover_slice() == 1
    donut._mouse = QPointF(center.x(), center.y())                            # en el centro: ninguno
    assert donut._hover_slice() is None


def test_donut_with_a_tiny_slice_still_draws_it(qapp):
    donut = charts.DonutChart()
    donut.resize(500, 300)
    donut.set_data([AllocationSlice("Inversión", D("5742.81"), D("0.993")), AllocationSlice("Liquidez", D("38.42"), D("0.007"))])
    assert not donut.grab().isNull() and len(donut._angles) == 2
    donut.set_data([AllocationSlice("Inversión", D(100), D(1))])               # un unico trozo: anillo completo
    assert not donut.grab().isNull()


def test_bars_hover_picks_the_month_under_the_cursor(qapp):
    chart = charts.FlowChart()
    chart.resize(600, 300)
    chart.set_data(months(6))
    chart.grab()
    plot_left, slot = 40.0, (600 - 46) / 6
    chart._mouse = QPointF(plot_left + slot * 2.5, 150)
    assert chart._hover_index(__import__("PySide6.QtCore", fromlist=["QRectF"]).QRectF(plot_left, 34, 554, 240), slot) == 2


def test_category_chart_grows_to_fit_its_rows_and_groups_the_rest(qapp):
    chart = charts.CategoryBarsChart()
    chart.set_data([CategoryAmount(TxCategory.GROCERIES, D(100 - i), D("0.1")) for i in range(11)])
    assert len(chart._items) == charts.MAX_CATEGORIES + 1 and chart._items[-1][0] == "Otras categorías"
    assert chart.minimumHeight() >= chart.ROW_H * len(chart._items)


# ---------------------------------------------------------------- piezas de tarjeta
def test_elided_label_shrinks_then_elides_without_breaking(qapp):
    label = ElidedLabel("5.742,81 €")
    label.setObjectName("CardValue")
    label.resize(60, 40)
    assert not label.grab().isNull()
    label.setText("Un texto larguisimo que no cabe de ninguna manera")
    label.resize(80, 30)
    assert not label.grab().isNull() and label.toolTip().startswith("Un texto")


def test_stat_band_hero_and_header_build_and_update(qapp):
    cells = [StatCard(t, band=True) for t in ("Uno", "Dos", "Tres")]
    band = StatBand(cells)
    band.resize(600, 120)
    cells[0].set_content("12,00 €", "contexto", positive=True)
    cells[1].set_content("—", negative=True)
    assert cells[0]._value.property("tone") == "positive" and cells[1]._value.property("tone") == "negative"
    assert band.findChildren(type(cells[0])) and not band.grab().isNull()

    hero = HeroCard("Patrimonio neto")
    hero.resize(520, 360)
    hero.set_content("5.781,23 €", "Todo lo que tienes")
    hero.set_chips([("+4,41 % rendimiento", "positive"), ("TIR 6,0 % anual", "")])
    hero.trend.set_values([1.0, 2.0, 3.0, 5.0])
    hero.split.set_parts([("Liquidez", "38,42 €", 0.007, "neutral"), ("Inversión", "5.742,81 €", 0.993, "accent")])
    assert len(hero._chip_widgets) == 2 and not hero.grab().isNull()
    hero.set_chips([])
    assert hero._chip_widgets == []

    header = PageHeader("Cuentas", eyebrow="Tus cuentas", subtitle="1 cuenta")
    assert header.title.text() == "Cuentas" and header._eyebrow.text() == "TUS CUENTAS" and header._eyebrow.isHidden()
    header.set_subtitle("")
    assert not header._subtitle.isVisibleTo(header)


# ---------------------------------------------------------------- contraste (WCAG AA: 4,5:1 el texto pequeno)
def _luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("palette", [theme.DARK, theme.LIGHT], ids=["dark", "light"])
def test_small_text_has_enough_contrast_on_every_surface_it_sits_on(palette):
    surfaces = {"fondo": palette.bg, "barra": palette.side, "tarjeta": palette.surface, "campo": palette.surface_alt}
    for name, surface in surfaces.items():
        assert contrast(palette.text, surface) >= 7, f"texto sobre {name}"
        assert contrast(palette.muted, surface) >= 4.5, f"texto de apoyo sobre {name}"
    for name, tint in (("tarjeta", palette.surface), ("aviso", palette.accent_soft)):
        assert contrast(palette.accent_text, tint) >= 4.5, f"acento (texto) sobre {name}"
    assert contrast(palette.green_text, palette.surface) >= 4.5 and contrast(palette.red, palette.surface) >= 4.5
    assert contrast(palette.on_accent, palette.accent) >= 7                                   # texto de los botones amarillos
    assert contrast(palette.accent, palette.surface) >= 1.5 or palette.name == "light"        # el amarillo claro solo es relleno, nunca texto


@pytest.mark.parametrize("palette", [theme.DARK, theme.LIGHT], ids=["dark", "light"])
def test_form_fields_have_a_visible_edge_and_the_active_nav_item_has_its_own(palette):
    assert contrast(palette.field_edge, palette.surface) >= 1.8                 # el campo se distingue de la tarjeta
    assert contrast(palette.accent_edge, palette.accent) >= 1.3                 # el filo del elemento activo se nota sobre el amarillo
    assert palette.field_edge != palette.border


def test_main_pages_use_flat_sections_with_the_brand_rule_and_keep_a_single_hero_card(window):
    from PySide6.QtWidgets import QFrame
    from ui.widgets.cards import BrandRule

    window.start_demo()
    for view in (window.dashboard, window.accounts_view, window.investment_view):
        names = [f.objectName() for f in view.findChildren(QFrame)]
        assert names.count("Section") >= 3 and view.findChildren(BrandRule)          # secciones sin caja, con el filo de marca
    raised = [f for f in window.dashboard.findChildren(QFrame) if f.objectName() in ("Card", "Hero") and f.isVisibleTo(window.dashboard)]
    assert {f.objectName() for f in raised} <= {"Hero", "Card"} and len(raised) <= 4   # la cifra principal y las dos piezas interactivas
    sheet = theme.stylesheet(theme.DARK)
    assert "QFrame#Hero {" in sheet and "border-radius: 34px" in sheet and "QFrame#Card {" in sheet   # radios jerarquicos: la estrella manda
