"""Blitzen y Black en el cielo de Inicio: dibujan en cualquier hora y tema, solo con el cielo animado, y no se salen del widget."""
import pytest
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget

from ui import theme
from ui.widgets import charts, dogs
from ui.widgets.sky import SkyWidget, sky_state


def test_smooth_curves_are_closed_and_pass_through_their_points():
    path = dogs.smooth([(0, 0), (10, 0), (10, 10), (0, 10)])
    assert path.contains(path.boundingRect().center()) and path.boundingRect().width() >= 10
    open_path = dogs.smooth([(0, 0), (5, 3), (10, 0)], closed=False)
    assert open_path.elementCount() > 3 and open_path.currentPosition().x() == 10


def test_every_pose_draws_something_at_any_moment_in_both_themes(qapp):
    for dark in (True, False):
        for kind in ("day", "night"):
            for t in (0.0, 0.7, 1.9, 4.2, 13.3):
                image = QImage(400, 300, QImage.Format.Format_ARGB32)
                image.fill(0)
                p = QPainter(image)
                p.scale(8, 8)
                (dogs.paint_day(p, dark, t, 40, 30) if kind == "day" else dogs.paint_night(p, dark, t, 40, 30))
                p.end()
                assert any(image.pixelColor(x, y).alpha() > 200 for x in range(0, 400, 7) for y in range(0, 300, 7)), (dark, kind, t)


@pytest.mark.parametrize("name", ["blitzen", "blitzen-dormido", "blitzen-oreja-izq", "blitzen-oreja-der",
                                  "blitzen-lengua", "black", "black-dormido", "black-oreja-izq",
                                  "black-oreja-der", "durmiendo"])
def test_every_layer_of_the_illustration_ships_with_a_transparent_background(qapp, name):
    image = dogs._layer(name, dogs.STORE)
    assert not image.isNull() and image.hasAlphaChannel()
    assert image.pixelColor(2, 2).alpha() == 0                              # recortado: la esquina es transparente


def test_sleeping_closes_the_eyes_and_leaves_the_rest_of_the_dog_as_it_is(qapp):
    for dog, eye in (("blitzen", (617, 438)), ("black", (1652, 870))):
        awake, asleep = dogs._layer(dog, dogs.STORE), dogs._layer(dog + "-dormido", dogs.STORE)
        origin = (dogs.BLITZEN if dog == "blitzen" else dogs.BLACK).origin
        x, y = round((eye[0] - origin[0]) * dogs.STORE), round((eye[1] - origin[1]) * dogs.STORE)
        assert awake.pixelColor(x, y) != asleep.pixelColor(x, y)
        assert awake.pixelColor(x, awake.height() - 30) == asleep.pixelColor(x, asleep.height() - 30)


def test_tilting_the_head_moves_the_head_and_never_the_paws(qapp):
    def frame(tilt: float) -> QImage:
        image = QImage(700, 600, QImage.Format.Format_ARGB32)
        image.fill(0)
        p = QPainter(image)
        p.scale(0.4, 0.4)
        p.translate(-100, -100)
        dogs._paint_bent(p, dogs.BLITZEN, dogs._layer("blitzen", 0.4), 0.4, tilt)
        p.end()
        return image
    still, tilted = frame(0.0), frame(7.0)
    head_row, paw_row = round((500 - 100) * 0.4), round((1700 - 100) * 0.4)
    row = lambda image, y: [image.pixelColor(x, y).rgba() for x in range(image.width())]   # noqa: E731
    assert row(still, head_row) != row(tilted, head_row) and row(still, paw_row) == row(tilted, paw_row)


def test_blinks_are_brief_and_the_still_sky_keeps_the_eyes_open():
    assert dogs._blink(0.0, 0.0) == 0.0
    assert [dogs._blink(t / 10, 0.0) for t in range(0, 44)].count(1.0) <= 2


def sky_image(sky: SkyWidget) -> QImage:
    image = QImage(sky.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    sky.render(image, renderFlags=QWidget.RenderFlag.DrawChildren)
    return image


def test_the_sky_shows_the_dogs_only_while_it_is_animated(qapp):
    sky = SkyWidget()
    sky.set_hour(12.0)
    with_dogs = sky_image(sky)
    sky.set_animated(False)
    without = sky_image(sky)
    assert with_dogs.constBits().tobytes() != without.constBits().tobytes()
    sky.set_animated(True)
    assert sky_image(sky).constBits().tobytes() == with_dogs.constBits().tobytes()
    sky.deleteLater()


def test_day_and_night_have_different_dogs_and_they_move_with_time(qapp, monkeypatch):
    monkeypatch.setattr(charts, "ANIMATIONS", True)
    sky = SkyWidget()
    sky.set_hour(13.0)
    day = sky_image(sky).constBits().tobytes()
    sky._phase = 2.4
    assert sky_image(sky).constBits().tobytes() != day                    # menean la cola, respiran...
    sky.set_hour(23.0)
    night = sky_image(sky).constBits().tobytes()
    assert night != day
    sky._phase = 5.1
    assert sky_image(sky).constBits().tobytes() != night                  # respiran y suben las z
    assert "Blitzen" in sky.accessibleDescription() and "durmiendo" in sky.accessibleDescription()
    sky.deleteLater()


@pytest.mark.parametrize("name", ["dark", "light"])
def test_the_dogs_never_touch_the_edge_of_the_sky_widget(qapp, monkeypatch, name):
    monkeypatch.setattr(charts, "ANIMATIONS", True)
    theme.set_current(theme.PALETTES[name])
    sky = SkyWidget()
    for hour in (7.0, 13.0, 20.5, 23.0, 4.0):
        for phase in (0.0, 1.1, 2.7):
            sky.set_hour(hour)
            sky._phase = phase
            image = sky_image(sky)
            edge = [image.pixelColor(x, 0).alpha() for x in range(image.width())] + \
                   [image.pixelColor(image.width() - 1, y).alpha() for y in range(image.height())] + \
                   [image.pixelColor(0, y).alpha() for y in range(image.height())]
            assert max(edge) <= 3, (name, hour, phase)
    theme.set_current(theme.DARK)
    sky.deleteLater()


def test_the_sun_and_the_moon_never_cross_the_dogs_at_any_hour(qapp):
    """El astro recorre solo la parte izquierda; el dibujo de los perros empieza mas a la derecha (con sus rayos incluidos)."""
    sky = SkyWidget()
    left_of_dogs = 77.0 - 28.0                                   # donde empieza el dibujo de Blitzen y Black
    for hour in [h / 4 for h in range(0, 96)]:
        state = sky_state(hour)
        span = 15.0 if state.kind == "sun" else 9.0
        x = sky._arc_point(state.progress, span).x()
        assert x + 8.5 + 3.5 + 6.1 <= left_of_dogs + 4, (hour, x)       # disco + separacion de los rayos + su alcance
    sky.deleteLater()


def test_blitzen_pants_now_and_then_and_licks_every_seven_seconds():
    assert dogs._tongue(0.0) == (1.0, 0.0)                                   # el cielo quieto: la lengua en su sitio
    stretch, turn = dogs._tongue(7.0 + 0.45)
    assert stretch > 1.6 and abs(turn) > 1.0                                 # en pleno relamido: sale y barre
    assert all(dogs._tongue(7.0 + 0.95 + k * 0.1)[1] == 0.0 for k in range(40))   # entre relamidos solo jadea
