"""Inicio vivo: cielo animado junto al nombre, luz ambiente segun la hora y carrusel de presupuestos."""
from datetime import datetime
from decimal import Decimal as D

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from core.budget import BudgetLine
from core.enums import TxCategory
from tests.test_ui_features import loaded  # noqa: F401  (fixture: Netflix y Mercadona ya importados)
from ui.widgets import charts
from ui.widgets.ambient import KEYFRAMES, MAX_ALPHA, AmbientLight, ambient_tint, hour_of
from ui.widgets.budget_carousel import INTERVAL_MS, MANUAL_PAUSE_MS, BudgetCarousel
from ui.widgets.sky import SkyWidget, sky_state


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 15, hour, minute)


def line(category, spent, budget):
    return BudgetLine(category, D(budget), D(spent))


THREE = [line(TxCategory.DINING, 70, 60), line(TxCategory.GROCERIES, 130, 150), line(TxCategory.LEISURE, 5, 100)]


# ---------------------------------------------------------------- que astro se ve y donde
def test_sun_by_day_moon_by_night_and_the_arc_follows_the_hour():
    assert sky_state(6).kind == "sun" and sky_state(6).progress == 0
    assert sky_state(13.5).kind == "sun" and sky_state(20.9).kind == "sun"
    assert sky_state(21).kind == "moon" and sky_state(0).kind == "moon" and sky_state(5.99).kind == "moon"
    assert 0.48 < sky_state(13.5).progress < 0.52                         # a mediodia, en lo alto del arco
    day = [sky_state(h).progress for h in (6, 9, 12, 15, 18, 20.9)]
    assert day == sorted(day) and day[-1] > 0.95                          # sube y baja por el mismo recorrido: avanza siempre
    night = [sky_state(h).progress for h in (21, 23, 1, 3, 5.9)]
    assert night == sorted(night) and night[0] == 0
    assert sky_state(27).kind == sky_state(3).kind                        # las horas se envuelven


def test_the_sky_widget_switches_between_sun_and_moon(qapp):
    sky = SkyWidget()
    for hour, kind in ((7, "sun"), (12, "sun"), (17, "sun"), (22, "moon"), (3, "moon")):
        sky.set_hour(hour)
        assert sky.kind == kind
    assert "noche" in sky.accessibleDescription() and sky.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    sky.set_hour(12)
    assert "día" in sky.accessibleDescription()


def test_each_moment_of_the_day_draws_something_different(qapp):
    sky = SkyWidget()
    images = {}
    for hour in (7, 12, 17, 23):
        sky.set_hour(hour)
        images[hour] = sky.grab().toImage()
        assert not images[hour].isNull() and images[hour].width() == sky.width() > SkyWidget.W
    assert len({image.constBits().tobytes() for image in images.values()}) == 4     # sol bajo, sol alto, sol poniente y luna


def test_the_sky_only_animates_while_visible_and_when_allowed(qapp, monkeypatch):
    monkeypatch.setattr(charts, "ANIMATIONS", True)
    sky = SkyWidget()
    assert not sky.running                                                # oculto: no gasta nada
    sky.show()
    assert sky.running
    first = sky.grab().toImage()
    sky._phase = 3.7                                                      # un instante despues: el dibujo ha cambiado
    assert sky.grab().toImage().constBits().tobytes() != first.constBits().tobytes()
    sky.hide()
    assert not sky.running
    sky.show()
    sky.set_animated(False)
    assert not sky.running and sky.isVisible()                            # sin animacion sigue dibujado, quieto
    sky.set_animated(True)
    assert sky.running
    sky.deleteLater()


# ---------------------------------------------------------------- junto al nombre
def test_the_sky_sits_next_to_the_name_with_room_to_spare(window):
    from ui.widgets.cards import ACCESSORY_GAP

    window.show()
    window.dashboard.set_user_name("Ana")
    head = window.dashboard.header
    window.start_demo()
    window.navigate(window.SUMMARY)
    sky = window.dashboard.sky
    assert head._row.indexOf(sky) == 2                                    # a la derecha de todo el bloque de texto
    dash = window.dashboard
    right_of_text = max(w.mapTo(window, w.rect().topRight()).x() for w in (head.title, dash.date_line, head._subtitle))
    gap = sky.mapTo(window, sky.rect().topLeft()).x() - right_of_text
    assert ACCESSORY_GAP - 4 <= gap <= ACCESSORY_GAP + 400                # pegado al texto pero con holgura (el bloque puede ser mas ancho que sus lineas)
    assert sky.y() >= 0 and sky.geometry().bottom() <= head.rect().bottom() + 2          # dentro de la cabecera


def test_the_lines_of_text_in_the_header_are_evenly_spaced_and_the_sky_does_not_stretch_them(window):
    window.show()
    window.dashboard.set_user_name("Ana")
    window.start_demo()
    window.navigate(window.SUMMARY)
    head, dash = window.dashboard.header, window.dashboard

    def top(widget) -> int:
        return widget.mapTo(window, widget.rect().topLeft()).y()

    def bottom(widget) -> int:
        return widget.mapTo(window, widget.rect().bottomLeft()).y()

    # el dibujo no es mas alto que las lineas de texto juntas (saludo, fecha y actualizacion) y va a su derecha: no abre huecos entre ellas
    assert dash.sky.height() <= 160                                      # alto, pero sin descolocar la pagina: la cabecera crece lo justo
    right_of_text = max(w.mapTo(window, w.rect().topRight()).x() for w in (head.title, dash.date_line, head._subtitle))
    assert dash.sky.mapTo(window, dash.sky.rect().topLeft()).x() > right_of_text
    gaps = [top(dash.date_line) - bottom(head.title), top(head._subtitle) - bottom(dash.date_line)]
    assert max(gaps) <= 6 and abs(gaps[0] - gaps[1]) <= 4                 # saltos de linea casi iguales (el hueco que se veia era de ~14 px)
    assert head.sizePolicy() is not None


def test_the_greeting_drives_the_sky_in_home_and_in_the_welcome_screen(window):
    dash = window.dashboard
    for hour, kind in ((8, "sun"), (16, "sun"), (23, "moon")):
        dash.clock = lambda h=hour: at(h)
        dash.update_greeting()
        assert dash.sky.kind == dash.onboarding.sky.kind == kind
    dash.clock = lambda: at(16, 30)
    dash.update_greeting()
    assert dash.sky.state.progress > 0.6                                  # por la tarde el sol ya esta bajando


# ---------------------------------------------------------------- luz ambiente
def test_ambient_light_is_subtle_zero_by_day_and_never_above_seven_percent():
    assert all(ambient_tint(h)[3] == 0 for h in (7.5, 9, 11, 13))
    assert 0 < ambient_tint(16.5)[3] < ambient_tint(19)[3] <= MAX_ALPHA
    assert max(ambient_tint(h / 4)[3] for h in range(96)) == MAX_ALPHA and MAX_ALPHA <= 18   # 18/255 = 7 %
    assert ambient_tint(23)[3] > ambient_tint(17)[3] > ambient_tint(10)[3]       # cuanto mas tarde, menos luz
    assert all(a <= MAX_ALPHA for _, (_, _, _, a) in KEYFRAMES)


def test_ambient_light_changes_gradually_and_wraps_around_midnight():
    steps = [ambient_tint(h / 60)[3] for h in range(24 * 60)]
    assert max(abs(a - b) for a, b in zip(steps, steps[1:])) <= 1               # nunca da un salto brusco
    assert ambient_tint(24)[3] == ambient_tint(0)[3] and ambient_tint(23.99)[3] - ambient_tint(0)[3] in (0, 1)
    assert hour_of(at(14, 30)) == 14.5


def test_ambient_layer_covers_the_window_lets_clicks_through_and_can_be_switched_off(window):
    ambient = window.ambient
    assert ambient.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    window.resize(1100, 760)
    assert ambient.geometry() == window.centralWidget().rect()
    root = window.centralWidget()
    kids = root.children()
    assert kids.index(window.toast) > kids.index(ambient)                       # los avisos quedan por encima de la luz
    window.clock = lambda: at(23)
    window.tick_clock()
    assert ambient.tint[3] > 0
    window.settings_view.ambient.switch.setChecked(False)
    assert ambient.tint == (0, 0, 0, 0) and not ambient.enabled
    window.settings_view.ambient.switch.setChecked(True)
    assert ambient.tint[3] > 0


def test_it_only_dims_a_little_and_does_not_touch_the_theme(window):
    window.show()
    window.clock = lambda: at(12)
    window.tick_clock()
    noon = window.grab().toImage()
    window.clock = lambda: at(23)
    window.tick_clock()
    night = window.grab().toImage()
    assert window.settings_view._settings.theme == window._settings.theme == "dark"

    sky = window.dashboard.sky
    sky_rect = sky.rect().translated(sky.mapTo(window, sky.rect().topLeft())).adjusted(-30, -30, 30, 30)

    def brightness(image: QImage) -> float:
        total = 0
        for x in range(240, image.width(), 53):
            for y in range(sky_rect.bottom() + 10, image.height(), 41):      # por debajo de la cabecera: se mide la luz de la pantalla, no el saludo ni el propio cielo
                if sky_rect.contains(x, y):
                    continue
                c = image.pixelColor(x, y)
                total += c.red() + c.green() + c.blue()
        return total

    assert 0.88 < brightness(night) / brightness(noon) < 1.0                   # se nota un poco, no mas de un ~7 %


def test_ambient_setting_is_saved_and_the_clock_tick_updates_everything(window):
    window.settings_view.ambient.switch.setChecked(False)
    assert window._svc.settings.load().ambient is False and not window.dashboard.sky.running
    window.clock = lambda: at(22)
    window.tick_clock()
    assert window.dashboard.header.title.text() == "Buenas noches." and window.dashboard.sky.kind == "moon"
    window.clock = lambda: at(9)
    window.tick_clock()
    assert window.dashboard.header.title.text() == "Buenos días." and window.dashboard.sky.kind == "sun"


# ---------------------------------------------------------------- carrusel de presupuestos
def test_carousel_shows_every_budget_one_at_a_time(qapp):
    c = BudgetCarousel()
    c.set_state(THREE, True)
    assert c.index == 0 and c.current.category == TxCategory.DINING and c.counter.text() == "1 de 3"
    assert not c.dots.isHidden() and not c._controls.isHidden()
    assert "3 presupuestos" in c.subtitle.text() and "1 superado" in c.subtitle.text()
    c.advance()
    assert c.index == 1 and c.counter.text() == "2 de 3" and c.current.category == TxCategory.GROCERIES
    c.advance()
    c.advance()
    assert c.index == 0                                                    # al llegar al final da la vuelta
    c.advance(-1)
    assert c.index == 2
    c.deleteLater()


def test_the_user_can_page_with_arrows_dots_and_keys(qapp):
    c = BudgetCarousel()
    c.set_state(THREE, True)
    c.next_button.click()
    assert c.index == 1
    c.prev_button.click()
    c.prev_button.click()
    assert c.index == 2
    c.dots.selected.emit(0)                                                # saltar directo desde los puntos
    assert c.index == 0
    c.slide.show()
    QTest.keyClick(c.slide, Qt.Key.Key_Right)
    assert c.index == 1
    QTest.keyClick(c.slide, Qt.Key.Key_Left)
    assert c.index == 0
    c.deleteLater()


def test_it_passes_by_itself_pauses_while_hovered_and_waits_longer_after_a_manual_change(qapp):
    c = BudgetCarousel()
    c.resize(500, 300)
    c.show()
    c.set_state(THREE, True)
    assert c.auto_running and c._timer.interval() == INTERVAL_MS
    c._auto_advance()                                                      # lo que hace el temporizador
    assert c.index == 1 and c._timer.interval() == INTERVAL_MS
    c.next_button.click()                                                  # a mano: espera mucho antes de seguir solo
    assert c.index == 2 and c._timer.interval() == MANUAL_PAUSE_MS and MANUAL_PAUSE_MS > INTERVAL_MS
    QApplication_send(c, QEvent.Type.Enter)
    assert not c.auto_running                                              # con el raton encima no pasa solo
    QApplication_send(c, QEvent.Type.Leave)
    assert c.auto_running
    c.hide()
    assert not c.auto_running
    c.deleteLater()


def QApplication_send(widget, kind):
    from PySide6.QtWidgets import QApplication
    QApplication.sendEvent(widget, QEvent(kind))


def test_a_single_budget_or_none_has_no_controls_and_no_timer(qapp):
    c = BudgetCarousel()
    c.show()
    c.set_state(THREE[:1], True)
    assert c.dots.isHidden() and c._controls.isHidden() and not c.auto_running and not c.slide.isHidden()
    c.advance()
    assert c.index == 0
    c.set_state([], False)
    assert c.slide.isHidden() and "pestaña Cuentas" in c._message.text() and "Sin presupuestos" in c.subtitle.text()
    c.set_state([], True)
    assert "Sin gasto este mes" == c.subtitle.text()
    c.deleteLater()


def test_updating_the_list_keeps_the_same_budget_in_view(qapp):
    c = BudgetCarousel()
    c.set_state(THREE, True)
    c.advance()                                                            # Supermercado
    changed = [line(TxCategory.LEISURE, 80, 100), line(TxCategory.GROCERIES, 135, 150), line(TxCategory.DINING, 70, 60)]
    c.set_state(changed, True)
    assert c.current.category == TxCategory.GROCERIES and c.index == 1
    c.set_state([line(TxCategory.HEALTH, 1, 10)], True)                    # el que miraba ya no esta: vuelve al primero
    assert c.index == 0
    c.deleteLater()


def test_clicking_the_budget_asks_to_see_its_movements_and_it_paints_every_state(qapp):
    c = BudgetCarousel()
    c.resize(520, 260)
    c.set_state(THREE, True)
    got = []
    c.category_clicked.connect(got.append)
    QTest.mouseClick(c.slide, Qt.MouseButton.LeftButton)
    assert got == [TxCategory.DINING]
    for i in range(3):                                                     # superado, cerca del tope y dentro: los tres se pintan
        c.slide.set_lines(c.lines, i)
        image = c.slide.grab().toImage()
        assert not image.isNull()
    assert [l.state for l in THREE] == ["over", "warn", "ok"]
    c.deleteLater()


def test_home_lists_all_the_budgets_of_the_month_in_the_carousel(loaded):
    v = loaded.accounts_view
    v.save_budgets({TxCategory.GROCERIES: D(24), TxCategory.SUBSCRIPTIONS: D(14), TxCategory.LEISURE: D(100)})
    carousel = loaded.dashboard.budgets
    assert [(l.category, l.state) for l in carousel.lines] == [
        (TxCategory.SUBSCRIPTIONS, "warn"), (TxCategory.GROCERIES, "warn"), (TxCategory.LEISURE, "ok")]
    assert carousel.counter.text() == "1 de 3" and "3 presupuestos" in carousel.subtitle.text()
    carousel.advance()
    assert carousel.current.category == TxCategory.GROCERIES
    carousel.category_clicked.emit(TxCategory.GROCERIES)
    assert loaded.stack.currentIndex() == loaded.ACCOUNTS
