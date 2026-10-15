"""Inicio: fecha y hora al dia, ultima actualizacion de datos, ciclo completo del cielo y las cuatro barras de la senyera."""
import struct
import time
from datetime import date, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from core import i18n
from tests.conftest import dispose_windows
from ui import theme
from ui.widgets.cards import StripeMark
from ui.widgets.sky import RADIUS, SkyWidget, sky_state

FIX = Path(__file__).parent / "fixtures"
LOGOS = Path(__file__).resolve().parent.parent / "logo-mejorado"


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)


def at(day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2027, 1, day, hour, minute, second)


# ---------------------------------------------------------------- fecha y hora en Inicio
def test_home_shows_the_date_and_time_between_the_greeting_and_the_subtitle(window):
    dash = window.dashboard
    dash.clock = lambda: at(7, 20, 20)
    dash.update_greeting()
    assert dash.date_line.text() == "Jueves 7 de Enero del 2027 - 20:20h"
    column = dash.header._column
    order = [column.itemAt(i).widget() or column.itemAt(i).layout() for i in range(column.count())]
    title_row, date_line, subtitle = dash.header._title_row, dash.date_line, dash.header._subtitle
    assert order.index(title_row) < order.index(date_line) < order.index(subtitle)         # titulo, fecha y hora, subtitulo
    assert dash.onboarding.date_line.text() == "Jueves 7 de Enero del 2027 - 20:20h"        # tambien en la bienvenida


def test_the_date_line_is_an_intermediate_size_between_the_greeting_and_the_subtitle(window):
    sheet = theme.stylesheet(theme.DARK)
    import re

    def px(selector: str) -> int:
        return int(re.search(rf"{selector}[^}}]*?font-size: (\d+)px", sheet).group(1))

    assert px("QLabel#DateLine") == 20 and px("QLabel#H1") > px("QLabel#DateLine") > px("QLabel#Small")
    assert window.dashboard.date_line.objectName() == "DateLine"


def test_the_clock_keeps_updating_by_itself_every_second(window):
    dash = window.dashboard
    assert dash._greeting_timer.interval() == 1000
    now = [at(7, 23, 59, 30)]
    dash.clock = lambda: now[0]
    dash.update_greeting()
    assert dash.date_line.text().endswith("23:59h") and dash.header.title.text() == "Buenas noches."
    now[0] = at(8, 0, 0, 5)                                               # pasa la medianoche: cambia el dia y el saludo
    dash.update_greeting()
    assert dash.date_line.text() == "Viernes 8 de Enero del 2027 - 00:00h" and dash.header.title.text() == "Buenas noches."
    now[0] = at(8, 6, 0)
    dash.update_greeting()
    assert dash.header.title.text() == "Buenos días." and dash.date_line.text().endswith("06:00h")


def test_the_date_line_is_only_repainted_when_the_minute_changes(window):
    dash = window.dashboard
    dash.clock = lambda: at(7, 12, 0, 1)
    dash.update_greeting()
    sets = []
    original = dash.date_line.setText
    dash.date_line.setText = lambda text: (sets.append(text), original(text))
    dash.clock = lambda: at(7, 12, 0, 40)
    dash.update_greeting()
    assert sets == []                                                      # mismo minuto: no se toca la etiqueta
    dash.clock = lambda: at(7, 12, 1, 0)
    dash.update_greeting()
    assert len(sets) == 1


def test_the_date_line_follows_the_language(window):
    dash = window.dashboard
    dash.clock = lambda: at(7, 20, 20)
    i18n.set_language("ca")
    dash.date_line.setText("")
    dash.update_greeting()
    assert dash.date_line.text() == "Dijous 7 de Gener del 2027 - 20:20h"
    i18n.set_language("en")
    dash.date_line.setText("")
    dash.update_greeting()
    assert dash.date_line.text() == "Thursday 7 January 2027 - 20:20"


# ---------------------------------------------------------------- ultima actualizacion de datos
def test_subtitle_shows_the_date_of_the_last_data_update(window):
    window.import_view.import_paths([str(FIX / "imagin_sample.csv")])
    today = date.today()
    expected = f"Fecha de última actualización de datos: {today.day:02d}/{today.month:02d}/{today.year}"
    assert window.dashboard.header._subtitle.text() == expected
    assert "Datos hasta" not in window.dashboard.header._subtitle.text()


def test_last_update_falls_back_to_the_newest_data_day_when_only_a_portfolio_was_imported(window):
    from PySide6.QtCore import QDate

    window.import_view.as_of.setDate(QDate(2026, 9, 30))
    window.import_view.import_paths([str(FIX / "myinvestor_cartera.csv")])                 # sin movimientos ni operaciones
    assert window._svc.dashboard.load().last_update == date(2026, 9, 30)
    window.import_view.import_paths([str(FIX / "imagin_sample.csv")])
    assert window._svc.dashboard.load().last_update == date.today()                        # con una importacion, el dia de esa importacion


def test_last_update_follows_the_language_and_uses_the_same_date_format(window):
    window.import_view.import_paths([str(FIX / "imagin_sample.csv")])
    i18n.set_language("en")
    window.dashboard.set_data(window._svc.dashboard.load())
    assert window.dashboard.header._subtitle.text().startswith("Date of the last data update: ")
    i18n.set_language("ca")
    window.dashboard.set_data(window._svc.dashboard.load())
    assert window.dashboard.header._subtitle.text().startswith("Data de l'última actualització de dades: ")


# ---------------------------------------------------------------- ciclo completo del cielo
def test_the_sky_goes_through_a_closed_cycle_over_24_hours():
    states = [sky_state(h / 4) for h in range(96)]
    kinds = [s.kind for s in states]
    assert kinds.count("sun") == 60 and kinds.count("moon") == 36                  # sol 6-21 h, luna 21-6 h
    changes = [i for i in range(96) if kinds[i] != kinds[i - 1]]
    assert len(changes) == 2 and {changes[0], changes[1]} == {24, 84}                # al amanecer y al anochecer, solo
    for kind in ("sun", "moon"):
        run = [s.progress for s in states if s.kind == kind]
        assert min(run) == 0 and max(run) > 0.97                                   # sale y se pone: recorre todo el arco


def test_the_sun_and_the_moon_rise_and_set_half_out_so_the_cycle_has_no_blind_spot(qapp):
    sky = SkyWidget()
    start, middle, end = sky._arc_point(0.0), sky._arc_point(0.5), sky._arc_point(1.0)
    horizon = SkyWidget.BASE + 2                                                   # el horizonte: lo de debajo se recorta
    for edge in (start, end):                                                      # al salir y al ponerse: mas o menos medio disco a la vista
        assert edge.y() - RADIUS < horizon - RADIUS * 0.6 and edge.y() < horizon
    assert middle.y() < start.y() - 25 and start.x() < middle.x() < end.x()
    assert sky._arc_point(1.0 + 0.08).y() > end.y() and sky._arc_point(-0.08).y() > start.y()    # fuera del recorrido se hunden
    assert abs(middle.x() - SkyWidget.W / 2) < 1                                   # a mediodia, en lo alto y en el centro
    sky.deleteLater()


def _visible_pixels(sky: SkyWidget) -> int:
    """Pixeles dibujados por encima del horizonte (sin el fondo de la ventana)."""
    image = QImage(sky.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    sky.render(image, renderFlags=QWidget.RenderFlag.DrawChildren)
    y_limit = int((SkyWidget.BASE - 1) * SkyWidget.SCALE)
    return sum(1 for y in range(y_limit) for x in range(image.width()) if image.pixelColor(x, y).alpha() > 12)


def test_the_astro_appears_gradually_at_dawn_and_dusk(qapp):
    sky = SkyWidget()
    counts = {}
    for hour in (6.0, 6.5, 7.5, 10.0, 20.0, 20.8, 21.0, 21.5, 23.0):
        sky.set_hour(hour)
        counts[hour] = _visible_pixels(sky)
    assert counts[6.0] > 0 and counts[21.0] > 0                                    # en el relevo no hay punto ciego: se intuyen
    assert counts[6.0] < counts[7.5] < counts[10.0]                                # el sol va subiendo
    assert counts[21.0] > counts[10.0] * 0.25                                      # y en el relevo se ve bastante, aunque no completo
    assert counts[20.8] < counts[20.0] and counts[21.5] > 0 and counts[23.0] > counts[21.5]
    sky.deleteLater()


def test_the_sky_follows_the_clock_while_the_app_stays_open(window):
    dash = window.dashboard
    seen = []
    for hour, minute in ((5, 50), (6, 30), (13, 30), (20, 50), (21, 10), (23, 0)):
        dash.clock = lambda h=hour, m=minute: at(7, h, m)
        dash.update_greeting()
        seen.append((dash.sky.kind, round(dash.sky.state.progress, 2)))
    assert [k for k, _ in seen] == ["moon", "sun", "sun", "sun", "moon", "moon"]
    assert seen[1][1] < seen[2][1] < seen[3][1] and seen[4][1] < seen[5][1]        # sube y baja con la hora real


def test_the_main_window_clock_tick_moves_the_sky_light_and_greeting_together(window):
    window.clock = lambda: at(7, 22, 30)
    window.tick_clock()
    assert window.dashboard.sky.kind == "moon" and window.ambient.tint[3] > 0
    assert window.dashboard.header.title.text() == "Buenas noches." and window.dashboard.date_line.text().endswith("22:30h")


def test_the_sky_looks_right_in_both_themes_at_every_stage_of_the_day(qapp):
    sky = SkyWidget()
    for name in ("dark", "light"):
        theme.set_current(theme.PALETTES[name])
        previous = None
        for hour in (5.5, 6.25, 8, 12, 17, 20.5, 21.5, 23, 3):
            sky.set_hour(hour)
            image = sky.grab().toImage()
            assert not image.isNull()
            assert image.constBits().tobytes() != previous                          # cada momento se ve distinto del anterior
            previous = image.constBits().tobytes()
    theme.set_current(theme.DARK)
    sky.deleteLater()


# ---------------------------------------------------------------- las cuatro barras de la senyera
def test_every_logo_svg_has_the_four_senyera_bars():
    files = sorted(LOGOS.glob("*.svg"))
    assert len(files) == 9
    for path in files:
        svg = path.read_text(encoding="utf-8")
        assert svg.count("<polygon") == 5, path.name                                # la patilla de la K + cuatro barras
        assert "210,149 210,171 281,100 259,100" in svg, path.name                  # la cuarta barra, la de arriba
        for stripe in ("210,189 210,211 321,100 299,100", "210,229 210,251 361,100 339,100", "210,269 210,291 401,100 379,100"):
            assert stripe in svg


def test_the_png_and_ico_logos_are_regenerated_with_the_right_sizes():
    sizes = {"kreix-icono-claro": (1024, 1024), "kreix-icono-oscuro": (1024, 1024), "kreix-logotipo-claro": (1400, 480),
             "kreix-logotipo-transparente": (1400, 480), "kreix-monocromo-negro": (1024, 1024)}
    for name, size in sizes.items():
        image = QImage(str(LOGOS / f"{name}.png"))
        assert (image.width(), image.height()) == size, name
    for px in (16, 32, 48, 180, 256, 512):
        assert QImage(str(LOGOS / f"favicon-{px}.png")).width() == px
    data = (LOGOS / "favicon.ico").read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, 4)
    widths = [data[6 + 16 * i] or 256 for i in range(count)]
    assert widths == [16, 32, 48, 256]


def test_the_favicon_shows_the_whole_k_with_four_red_bars(qapp):
    """El favicon antiguo estaba recortado (solo un cuarto del icono); ahora se ve la K entera."""
    image = QImage(str(LOGOS / "favicon-512.png"))
    assert image.pixelColor(256, 120).name() != image.pixelColor(256, 256).name()      # fondo, tallo...
    assert image.pixelColor(2, 256).alpha() == 0 or image.pixelColor(20, 20).alpha() == 0   # esquinas redondeadas (transparentes)
    # se cuentan los tramos rojos a lo largo de una vertical que cruza las cuatro barras
    x = 240                                       # a la derecha del tallo: cruza las cuatro barras
    reds, inside = 0, False
    for y in range(512):
        c = image.pixelColor(x, y)
        is_red = c.red() > 190 and c.green() < 90 and c.blue() < 90
        reds += is_red and not inside
        inside = is_red
    assert reds == 4


@pytest.mark.parametrize("size", [(64, 34), (112, 58)])
def test_the_header_stripes_draw_four_bars(qapp, size):
    for name in ("dark", "light"):
        theme.set_current(theme.PALETTES[name])
        mark = StripeMark(*size)
        image = QImage(mark.size(), QImage.Format.Format_ARGB32)
        image.fill(0)
        mark.render(image, renderFlags=QWidget.RenderFlag.DrawChildren)
        row = int(size[1] * 0.5)
        runs, inside = 0, False
        for x in range(image.width()):
            opaque = image.pixelColor(x, row).alpha() > 20
            runs += opaque and not inside
            inside = opaque
        assert runs == 4, (name, runs)
        assert image.pixelColor(0, row).alpha() == 0                                # no se sale por la izquierda
        mark.deleteLater()
    theme.set_current(theme.DARK)


def test_stripes_fade_from_the_strongest_bar_to_the_weakest(qapp):
    mark = StripeMark(112, 58, centered=True)
    image = QImage(mark.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    mark.render(image, renderFlags=QWidget.RenderFlag.DrawChildren)
    row = 29
    peaks, inside = [], False
    for x in range(image.width()):
        a = image.pixelColor(x, row).alpha()
        if a > 20 and not inside:
            peaks.append(a)
        elif a > 20:
            peaks[-1] = max(peaks[-1], a)
        inside = a > 20
    assert len(peaks) == 4 and peaks == sorted(peaks, reverse=True) and peaks[0] == 255 and peaks[-1] < 90
    mark.deleteLater()


def test_the_day_night_loop_never_leaves_the_sky_empty(qapp):
    from ui.widgets.sky import sky_bodies

    sky = SkyWidget()
    dusk, dawn = sky_bodies(21.0), sky_bodies(6.0)
    assert [k for k, *_ in dusk] == ["moon"] and [k for k, *_ in dawn] == ["sun"]                  # uno solo: sale la luna y el sol ya no esta
    for hour in (20.99, 21.0, 21.5, 22.0, 5.99, 6.0, 6.5):                                          # y nunca conviven, a ninguna hora
        assert len(sky_bodies(hour)) == 1
    assert [k for k, *_ in sky_bodies(13.0)] == ["sun"] and [k for k, *_ in sky_bodies(2.0)] == ["moon"]
    noon = None
    least = None
    for quarter in range(96):
        sky.set_hour(quarter / 4)
        pixels = _visible_pixels(sky)
        noon = pixels if quarter == 52 else noon
        least = pixels if least is None else min(least, pixels)
    assert least > 100 and noon is not None and least > noon * 0.2                  # ni a las 21:00 ni a las 6:00 queda vacio
    sky.deleteLater()
