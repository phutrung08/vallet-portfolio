"""Responsive split-layout verification across foldables, Surface Duo, and tablets."""

from __future__ import annotations

import contextlib
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devices import DEVICES, Device, Viewport, apply_viewport
from flows import add_expense, create_trip
from pages import Screen, button, row
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver

EXPENSES = ["Morning coffee", "Beef noodles", "Airport taxi", "Evening hotpot"]
NAV = "//nav"
FACTS = """
const box = (e) => { const r = e.getBoundingClientRect();
  return {left: r.left, right: r.right, width: r.width, height: r.height}; };
const pane = (sel) => { const e = document.querySelector(sel); if (!e) return null;
  const visible = getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0;
  return {visible, text: e.innerText.trim().length, ...box(e)}; };
const nav = document.querySelector('nav');
return {scroll: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
  inner: window.innerWidth, list: pane('.split-list'), detail: pane('.split-detail'),
  nav: nav && getComputedStyle(nav).display !== 'none' ? box(nav) : null};
"""
Facts = dict[str, Any]


def _groups() -> list[tuple[Viewport, list[Device]]]:
    groups: dict[Viewport, list[Device]] = {}
    for device in DEVICES:
        groups.setdefault(device.viewport, []).append(device)
    return list(groups.items())


def _facts(screen: Screen, viewport: Viewport, needs_detail: bool) -> Facts:
    def settled(driver: WebDriver) -> bool:
        found = driver.execute_script(FACTS)
        return bool(
            found["inner"] == viewport.width
            and (not needs_detail or (found["detail"] and found["detail"]["text"] > 0))
        )

    with contextlib.suppress(TimeoutException):
        screen.wait_until(settled)
    facts: Facts = screen.driver.execute_script(FACTS)
    return facts


def _problems(facts: Facts, viewport: Viewport, *, nav: bool, single_pane: bool) -> list[str]:
    found: list[str] = []
    if facts["scroll"] > facts["inner"]:
        found.append(f"horizontal overflow {facts['scroll']} > {facts['inner']}")
    list_pane, detail = facts["list"], facts["detail"]
    shown = [pane for pane in (list_pane, detail) if pane and pane["visible"]]
    if viewport.two_panes:
        if len(shown) != 2:
            found.append(f"expected two panes, {len(shown)} visible")
        elif not list_pane["text"] or not detail["text"]:
            found.append(f"empty pane: list {list_pane['text']} chars, detail {detail['text']}")
    elif single_pane and len(shown) != 1:
        found.append(f"expected one pane, {len(shown)} visible")
    if viewport.hinge is not None and len(shown) == 2:
        x, width = viewport.hinge
        if list_pane["right"] > x + 0.5:
            found.append(f"list pane ends at {list_pane['right']}, hinge starts at {x}")
        if detail["left"] < x + width - 0.5:
            found.append(f"detail pane starts at {detail['left']}, hinge ends at {x + width}")
    if nav:
        found.extend(_nav_problems(facts, viewport))
    return found


def _nav_problems(facts: Facts, viewport: Viewport) -> list[str]:
    bar = facts["nav"]
    if bar is None:
        return ["nav missing"]
    found: list[str] = []
    if bar["left"] < -0.5 or bar["right"] > facts["inner"] + 0.5:
        found.append(f"nav {bar['left']}..{bar['right']} leaves the screen")
    if viewport.hinge is not None:
        x, width = viewport.hinge
        if bar["left"] < x < bar["right"] or bar["left"] < x + width < bar["right"]:
            found.append("nav crosses the hinge")
    if bar["height"] > bar["width"]:
        for pane in (facts["list"], facts["detail"]):
            if (
                pane
                and pane["visible"]
                and bar["left"] < pane["right"]
                and bar["right"] > pane["left"]
            ):
                found.append(f"rail {bar['left']}..{bar['right']} overlaps a pane")
    return found


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _check_viewport(screen: Screen, path: str, viewport: Viewport, shots: Path | None) -> list[str]:
    problems: list[str] = []

    def check(name: str, *, nav: bool = True, single_pane: bool = True) -> None:
        facts = _facts(screen, viewport, viewport.two_panes)
        problems.extend(
            f"{name}: {message}"
            for message in _problems(facts, viewport, nav=nav, single_pane=single_pane)
        )
        if shots and name in ("trip", "balances"):
            screen.driver.save_screenshot(str(shots / f"{name}.png"))

    dpr = 1.0 if shots else None
    screen.open(path)
    apply_viewport(screen.driver, viewport, dpr)
    screen.visible(row(EXPENSES[0]))
    check("trip")
    screen.click(button("Balances", NAV))
    screen.visible("//h1[normalize-space(.)='Balances']")
    check("balances")
    screen.click(button("Settings", NAV))
    screen.visible("//h1[normalize-space(.)='Settings']")
    check("settings", nav=False, single_pane=False)
    screen.open("/")
    apply_viewport(screen.driver, viewport, dpr)
    screen.visible("//*[normalize-space(.)='Nav E2E']")
    check("home", nav=False)
    return problems


def test_layout_holds_on_every_device(browser: Callable[[], Screen]) -> None:
    screen = browser()
    path = create_trip(screen, "Nav E2E", "Alex", ["Ben", "Chloe"])
    for index, title in enumerate(EXPENSES):
        add_expense(screen, title, str(50000 + index * 10000))

    root = os.environ.get("E2E_DEVICE_SHOTS")
    failures: list[str] = []
    for viewport, devices in _groups():
        label = " + ".join(device.name for device in devices)
        shots = None
        if root:
            shots = Path(root) / _slug(f"{devices[0].name}-{viewport.width}x{viewport.height}")
            shots.mkdir(parents=True, exist_ok=True)
        failures.extend(
            f"{label} ({viewport.width}x{viewport.height}) {problem}"
            for problem in _check_viewport(screen, path, viewport, shots)
        )
    assert not failures, "\n".join(failures)


def visit(screen: Screen, path: str) -> None:
    """Navigate through Vue Router while keeping the active CDP viewport override intact."""
    screen.driver.execute_script(
        "document.querySelector('#app').__vue_app__.config.globalProperties.$router"
        ".push(arguments[0])",
        path,
    )


def test_full_screen_expense_routes_open_the_panes_on_wide_screens(
    browser: Callable[[], Screen],
) -> None:
    screen = browser()
    path = create_trip(screen, "Redirect E2E", "Alex", ["Ben"])
    add_expense(screen, "Pho", "50000")
    tablet = Viewport(768, 1024)
    screen.open(path)
    apply_viewport(screen.driver, tablet)
    screen.visible(row("Pho"))
    expense_id = screen.driver.execute_script(
        "return new URL(location).searchParams.get('expense')"
    )

    visit(screen, f"{path}/expenses/new")
    screen.wait_url(r"[?&]pane=add")
    screen.visible("//form")

    visit(screen, f"{path}/expenses/{expense_id}/edit")
    screen.wait_url(rf"expense={expense_id}")
    screen.visible("//form//input")
    assert "edit=" not in screen.current_path()
