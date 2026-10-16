"""Blitzen y Black en el cielo de Inicio: dibujan en cualquier hora y tema, solo con el cielo animado, y no se salen del widget."""
import pytest
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget

from ui import theme
from ui.widgets import charts, dogs
from ui.widgets.sky import SkyWidget


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
                (dogs.paint_day(p, dark, t, 30, 30, 12) if kind == "day" else dogs.paint_night(p, dark, t, 30, 25))
                p.end()
                assert any(image.pixelColor(x, y).alpha() > 200 for x in range(0, 400, 7) for y in range(0, 300, 7)), (dark, kind, t)


def test_the_dogs_wear_the_brand_fire_and_black_and_the_dark_theme_gets_a_rim_to_stand_out():
    dark, light = dogs.colors(True), dogs.colors(False)
    assert dark.fire.red() > 200 and dark.fire.green() < 130 and dark.coat.lightness() < 25 and light.coat.lightness() < 40
    assert dark.rim.alpha() > 0 and light.rim.alpha() == 0                 # sobre fondo oscuro, un filo claro los separa del fondo


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
