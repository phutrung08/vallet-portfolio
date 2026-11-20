"""Multi-device journey: invite link join, bank setup, VietQR settlement, and link rotation."""

from __future__ import annotations

from collections.abc import Callable

from flows import INVITE_LINK, TRIP_PAGE, add_expense, create_trip, open_balances, open_invite_link
from pages import DIALOG, Screen, button, field, row, text_node

TRIP_NAME = "Phu Quoc E2E"
BANK_ME_STATUS = "Your receiving account"


def standing(screen: Screen, label: str) -> str:
    """Return the amount shown on the current user standing card under `label`."""
    return screen.text(f"{text_node(label, 'p')}/following-sibling::p[1]")


def test_join_by_link_pay_back_and_rotate_link(browser: Callable[[], Screen]) -> None:
    device_a = browser()
    create_trip(device_a, TRIP_NAME, "Alex", ["Ben"])
    add_expense(device_a, "Dinner", "600000")
    old_link = open_invite_link(device_a)
    assert old_link.startswith("http://127.0.0.1:5174/join#")

    # Device B joins via invite fragment; fragment is immediately stripped from the URL bar.
    device_b = browser()
    device_b.open(old_link)
    device_b.wait_until(lambda driver: "#" not in driver.current_url)
    assert device_b.driver.current_url.endswith("/join")
    device_b.visible(text_node("You're invited to the trip", "p"))
    device_b.visible(text_node(TRIP_NAME, "h1"))
    device_b.click(button("Ben", "//*[@role='group']"))
    device_b.click(button("Join the trip"))
    device_b.wait_url(TRIP_PAGE)
    device_b.visible(text_node(TRIP_NAME, "h1"))
    assert "600,000" in device_b.text(row("Dinner"))

    # Ben owes half of the dinner to Alex.
    open_balances(device_b)
    assert "300,000" in standing(device_b, "You owe")
    transfer = device_b.text("//li[contains(., 'Ben') and contains(., '300,000')]")
    assert transfer.index("Ben") < transfer.index("Alex")

    # Alex configures receiving bank account; Ben refreshes and settles via VietQR sheet.
    open_balances(device_a)
    device_a.click(button(BANK_ME_STATUS))
    device_a.type(field("Search banks", DIALOG), "Vietcombank")
    device_a.click(button("Vietcombank", DIALOG))
    device_a.type(field("Account number", DIALOG), "0123456789")
    device_a.type(field("Account holder name", DIALOG), "Alex Nguyen")
    device_a.visible(text_node("Will be printed as: ALEX NGUYEN", "p", DIALOG))
    device_a.click(button("Save", DIALOG))
    device_a.gone(DIALOG)
    device_a.wait_text(button(BANK_ME_STATUS), "•••• 6789")

    device_b.driver.refresh()
    device_b.click(button("QR code: Ben pays Alex"))
    device_b.visible(f"{DIALOG}//*[local-name()='svg' and @aria-label='Transfer QR code']")
    device_b.wait_text(DIALOG, "•••• 6789")
    device_b.wait_text(DIALOG, "ALEX NGUYEN")
    device_b.click(button("I've paid", DIALOG))
    device_b.gone(DIALOG)
    device_b.visible(text_node("Everyone is square", "p"))
    assert standing(device_b, "You're all square")

    # Reloading on device A reflects the recorded settlement.
    device_a.driver.refresh()
    device_a.visible(text_node("You're all square", "p"))

    # Rotating the invite link invalidates the previous token for new devices.
    device_a.click(button("Members", "//nav"))
    device_a.visible(INVITE_LINK)
    device_a.click(button("Change invite link"))
    device_a.click(button("Change link", DIALOG))
    device_a.gone(DIALOG)
    device_a.wait_until(lambda _: device_a.text(INVITE_LINK).strip() != old_link)
    device_c = browser()
    device_c.open(old_link)
    device_c.visible(text_node("This link no longer works", "h1"))
