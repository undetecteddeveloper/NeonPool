import pygame as pg

from game.render import fonts


def test_font_survives_pygame_quit_and_reinit():
    pg.init()
    first = fonts.get(20, True)
    first.render("Việt", True, (255, 255, 255))
    pg.quit()
    pg.init()
    again = fonts.get(20, True)  # must not hand back the dead font
    assert again.render("Việt", True, (255, 255, 255)).get_width() > 0
    pg.quit()


def test_font_is_cached_while_alive():
    pg.init()
    assert fonts.get(14) is fonts.get(14)
    assert fonts.get(14) is not fonts.get(14, True)
    pg.quit()
