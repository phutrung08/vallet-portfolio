"""Smoke tests proving the full stack boots cleanly and serves both empty home and `/demo`."""

from __future__ import annotations

from collections.abc import Callable

from pages import Screen, button, text_node


def test_empty_home_screen(browser: Callable[[], Screen]) -> None:
    screen = browser()
    screen.open("/")

    assert screen.visible(text_node("Wander together, split fair", "h1")).is_displayed()
    assert screen.visible(button("Create a trip")).is_displayed()


def test_demo_trip_loads_offline_fixture(browser: Callable[[], Screen]) -> None:
    screen = browser()
    screen.open("/demo")

    assert screen.visible(text_node("This is a sample trip. Nothing is saved.", "p")).is_displayed()
    assert screen.visible(text_node("Phu Quoc 3D2N", "h1")).is_displayed()
