"""Kiểm môi trường: đúng Python, pygame-ce chạy được headless."""

import sys

import pygame as pg


def test_python_is_313():
    assert sys.version_info[:2] == (3, 13)


def test_pygame_ce_headless_surface():
    pg.init()
    try:
        screen = pg.display.set_mode((64, 48))
        screen.fill((10, 20, 30))
        assert screen.get_at((0, 0))[:3] == (10, 20, 30)
        assert "pygame-ce" in pg.version.ver or hasattr(pg, "IS_CE")
    finally:
        pg.quit()
