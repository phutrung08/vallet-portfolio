"""Automated WCAG 2.1 Level A & AA audits in real headless Chrome via axe-core."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from typing import Any

from flows import add_expense, add_fund_contribution, create_trip, open_balances, open_row
from pages import DIALOG, Screen, button, text_node
from selenium.webdriver.common.keys import Keys
from servers import ROOT

AXE_PATH = ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"


@cache
def _axe_source() -> str:
    if not AXE_PATH.exists():
        raise RuntimeError(f"axe-core bundle missing at {AXE_PATH}; run `npm ci` in frontend/.")
    return AXE_PATH.read_text(encoding="utf-8")


def _audit(screen: Screen, label: str, failures: list[str]) -> None:
    if not screen.driver.execute_script("return Boolean(window.axe)"):
        screen.driver.execute_script(_axe_source())
    violations: list[dict[str, Any]] = screen.driver.execute_async_script(
        "const done = arguments[arguments.length - 1];"
        "axe.run(document, { runOnly: { type: 'tag', "
        "values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } })"
        ".then((result) => done(result.violations))"
        ".catch((err) => done([{ id: 'axe-error', impact: 'critical', "
        "description: String(err), nodes: [] }]));"
    )
    if violations:
        formatted = []
        for item in violations:
            targets = [", ".join(node.get("target", [])) for node in item.get("nodes", [])]
            formatted.append(
                f"- [{item.get('impact')}] {item.get('id')}: {item.get('description')} -> {targets}"
            )
        failures.append(f"WCAG violations on {label}:\n" + "\n".join(formatted))


def test_wcag_compliance_across_all_screens(browser: Callable[[], Screen]) -> None:
    screen = browser()
    failures: list[str] = []

    # Empty home screen and trip creation flow.
    screen.open("/")
    screen.visible(text_node("Wander together, split fair", "h1"))
    _audit(screen, "Home empty state", failures)

    screen.click(button("Create a trip"))
    screen.visible(text_node("Create a trip", "h1"))
    _audit(screen, "Create Trip", failures)

    # Populated trip with shared fund, contribution, expense list, and expanded split row.
    trip_path = create_trip(screen, "Axe Audit Trip", "Alex", ["Ben"], uses_fund=True)
    screen.click(button("Group fund"))
    screen.visible(text_node("Shared fund", "h1"))
    add_fund_contribution(screen, None, "2000000")
    _audit(screen, "Shared Fund", failures)

    screen.click(button("Back"))
    screen.visible(text_node("Axe Audit Trip", "h1"))
    add_expense(screen, "Street food", "300000", payer="Alex (you)")
    open_row(screen, "Street food")
    _audit(screen, "Trip View (expanded row)", failures)

    # Standalone expense form.
    screen.click(button("Add expense", "//nav"))
    screen.visible(text_node("Add expense", "h1"))
    _audit(screen, "Expense Form", failures)

    # Balances view plus open Transfer modal dialog sheet.
    screen.open(trip_path)
    open_balances(screen)
    _audit(screen, "Balances", failures)

    screen.click(button("QR code: Ben pays Alex"))
    screen.visible(DIALOG)
    _audit(screen, "Transfer Sheet dialog", failures)
    screen.driver.switch_to.active_element.send_keys(Keys.ESCAPE)
    screen.gone(DIALOG)

    # Members and Activity screens.
    screen.click(button("Members", "//nav"))
    screen.visible(text_node("Members", "h1"))
    _audit(screen, "Members", failures)

    screen.click(button("Activity"))
    screen.visible(text_node("Activity", "h1"))
    _audit(screen, "Activity", failures)

    # Settings in both light and dark modes.
    screen.open("/settings")
    screen.visible(text_node("Settings", "h1"))
    _audit(screen, "Settings (light mode)", failures)

    screen.click(button("Dark"))
    screen.wait_until(
        lambda d: d.execute_script("return document.documentElement.dataset.theme") == "dark"
    )
    _audit(screen, "Settings (dark mode)", failures)

    # Reset theme back to system and check standalone sample trip screens.
    screen.click(button("System"))
    screen.open("/demo")
    screen.visible(text_node("Phu Quoc 3D2N", "h1"))
    _audit(screen, "Demo Trip", failures)

    screen.open("/demo/balances")
    screen.visible(text_node("Balances", "h1"))
    _audit(screen, "Demo Balances", failures)

    assert not failures, "\n\n".join(failures)
