"""Adaptive navigation bar tests across viewport breakpoints, Settings controls, and touch drag."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flows import add_expense, create_trip
from pages import Screen, button, row
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput

EXPENSES = ["Morning coffee", "Beef noodles", "Airport taxi", "Evening hotpot"]
NAV = "//nav"
PHONE_ATTR = "return document.documentElement.dataset.navPhone"
WIDE_ATTR = "return document.documentElement.dataset.navWide"
Rect = dict[str, float]


def make_trip(screen: Screen) -> str:
    path = create_trip(screen, "Nav E2E", "Alex", ["Ben", "Chloe"])
    for index, title in enumerate(EXPENSES):
        add_expense(screen, title, str(50000 + index * 10000))
    return path


def resize(screen: Screen, width: int, height: int) -> None:
    screen.driver.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {"width": width, "height": height, "deviceScaleFactor": 2, "mobile": True},
    )


def show(screen: Screen, path: str, width: int, height: int) -> None:
    """Open `path` and re-apply viewport dimensions after navigation."""
    screen.open(path)
    screen.visible(row(EXPENSES[0]))
    resize(screen, width, height)
    screen.wait_until(lambda d: d.execute_script("return innerWidth") == width)
    screen.visible(NAV)


def reset_storage(screen: Screen) -> None:
    screen.driver.execute_script("localStorage.clear()")


def rect(screen: Screen, xpath: str) -> Rect:
    element = screen.visible(xpath)
    box: Rect = screen.driver.execute_script(
        "const r = arguments[0].getBoundingClientRect();"
        "return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};",
        element,
    )
    return box


def viewport_width(screen: Screen) -> float:
    return float(screen.driver.execute_script("return document.documentElement.clientWidth"))


def assert_no_overflow(screen: Screen) -> None:
    scroll_width, inner_width = screen.driver.execute_script(
        "return [document.documentElement.scrollWidth, window.innerWidth]"
    )
    assert scroll_width <= inner_width, f"horizontal overflow: {scroll_width} > {inner_width}"


def scroll_to_end(screen: Screen) -> None:
    screen.driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight)")
    screen.wait_until(
        lambda d: d.execute_script(
            "return Math.ceil(window.scrollY + window.innerHeight) >="
            " document.documentElement.scrollHeight - 1"
        )
    )


def assert_dock_fits(screen: Screen) -> Rect:
    dock = rect(screen, NAV)
    assert dock["left"] >= 0 and dock["right"] <= viewport_width(screen)
    return dock


def open_settings(screen: Screen) -> None:
    screen.click(button("Settings", NAV))
    screen.visible("//h1[normalize-space(.)='Settings']")


def test_small_screens_dock_is_centered_clear_of_content_and_never_overflows(
    browser: Callable[[], Screen],
) -> None:
    screen = browser()
    path = make_trip(screen)

    show(screen, path, 360, 740)
    dock = assert_dock_fits(screen)
    assert abs((dock["left"] + dock["right"]) / 2 - 360 / 2) <= 1
    assert dock["bottom"] > 740 - 40
    scroll_to_end(screen)
    last = rect(screen, row(EXPENSES[-1]))
    dock = rect(screen, NAV)
    assert last["bottom"] <= dock["top"], f"last row {last} obscured by dock {dock}"

    open_settings(screen)
    screen.visible("//p[contains(normalize-space(.), 'always sits at the bottom center')]")
    assert screen.count("//*[@role='group' and @aria-label='At the bottom']") == 0
    assert screen.count("//*[@role='group' and @aria-label='Along an edge']") == 0

    for width, height in [(344, 882), (320, 640)]:
        show(screen, path, width, height)
        assert_no_overflow(screen)
        assert_dock_fits(screen)
        screen.click(button("Add expense", NAV))
        screen.visible("//h1[normalize-space(.)='Add expense']")
        assert_no_overflow(screen)


def test_large_phone_placement_is_chosen_in_settings_and_survives_reload(
    browser: Callable[[], Screen],
) -> None:
    screen = browser()
    path = make_trip(screen)
    show(screen, path, 412, 915)
    reset_storage(screen)

    open_settings(screen)
    screen.click(button("Right edge"))
    screen.wait_until(lambda d: d.execute_script(PHONE_ATTR) == "edge-right")
    show(screen, path, 412, 915)
    nav = rect(screen, NAV)
    assert abs(nav["right"] - 412) <= 16
    for title in EXPENSES:
        assert rect(screen, row(title))["right"] <= nav["left"], title
    assert_no_overflow(screen)

    open_settings(screen)
    screen.click(button("Left"))
    screen.wait_until(lambda d: d.execute_script(PHONE_ATTR) == "bottom-left")
    show(screen, path, 412, 915)
    dock = rect(screen, NAV)
    assert dock["left"] <= 16
    assert dock["bottom"] > 915 - 40
    scroll_to_end(screen)
    assert rect(screen, row(EXPENSES[-1]))["bottom"] <= rect(screen, NAV)["top"]

    show(screen, path, 412, 915)
    assert screen.driver.execute_script(PHONE_ATTR) == "bottom-left"
    assert '"phone":"bottom-left"' in screen.driver.execute_script(
        "return localStorage.getItem('vallet.nav')"
    )


def test_wide_rail_defaults_left_and_can_move_right(browser: Callable[[], Screen]) -> None:
    screen = browser()
    path = make_trip(screen)

    for width, height in [(768, 1024), (690, 830)]:
        show(screen, path, width, height)
        reset_storage(screen)
        show(screen, path, width, height)
        assert screen.driver.execute_script(WIDE_ATTR) == "rail-left"
        rail = rect(screen, NAV)
        assert rail["left"] <= 16 and rail["right"] < width / 2
        assert rail["bottom"] - rail["top"] > 830 - 40
        for title in EXPENSES:
            assert rect(screen, row(title))["left"] >= rail["right"], title
        assert_no_overflow(screen)

        open_settings(screen)
        screen.click(button("Navigation position"))
        screen.click(button("Right"))
        screen.wait_until(lambda d: d.execute_script(WIDE_ATTR) == "rail-right")
        show(screen, path, width, height)
        rail = rect(screen, NAV)
        assert rail["left"] > width / 2 and abs(rail["right"] - width) <= 16
        for title in EXPENSES:
            assert rect(screen, row(title))["right"] <= rail["left"], title
        assert_no_overflow(screen)


def touch_drag(screen: Screen, start: tuple[float, float], end: tuple[float, float]) -> None:
    """Press-and-hold past the 400ms threshold, drag smoothly across the screen, and release."""
    finger = PointerInput(interaction.POINTER_TOUCH, "finger")
    actions = ActionBuilder(screen.driver, mouse=finger)
    pointer: Any = actions.pointer_action
    pointer.move_to_location(round(start[0]), round(start[1]))
    pointer.pointer_down()
    pointer.pause(0.6)
    steps = 8
    for step in range(1, steps + 1):
        x = start[0] + (end[0] - start[0]) * step / steps
        y = start[1] + (end[1] - start[1]) * step / steps
        pointer.move_to_location(round(x), round(y))
        pointer.pause(0.03)
    pointer.release()
    actions.perform()


def test_press_hold_drag_moves_dock_to_right_edge(browser: Callable[[], Screen]) -> None:
    screen = browser()
    path = make_trip(screen)
    show(screen, path, 412, 915)
    reset_storage(screen)
    show(screen, path, 412, 915)
    assert screen.driver.execute_script(PHONE_ATTR) == "bottom-center"

    # Drag starting from padding on the dock frame so links are not clicked accidentally.
    dock = rect(screen, NAV)
    start = (dock["left"] + 4, (dock["top"] + dock["bottom"]) / 2)
    touch_drag(screen, start, (412 - 6, 915 / 2))

    screen.wait_until(lambda d: d.execute_script(PHONE_ATTR) == "edge-right")
    screen.wait_until(lambda d: d.execute_script("return localStorage.getItem('vallet.nav')"))
    nav = rect(screen, NAV)
    assert nav["left"] > 412 / 2 and abs(nav["right"] - 412) <= 16
    assert screen.current_path().startswith("/trips/")
