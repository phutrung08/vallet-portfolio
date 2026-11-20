"""Reusable end-to-end user journeys built on top of `pages.Screen`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pages import DIALOG, Screen, button, field, row, text_node, toggle_button

# Future trip dates ensure "today" is before the range so expenses default to Day 1.
STARTS_ON = "2030-11-05"
ENDS_ON = "2030-11-08"
TRIP_PAGE = r"/trips/[0-9a-f-]{36}(\?day=[\d-]+)?$"


def add_member_chip(screen: Screen, name: str) -> None:
    screen.type(field("Other members"), name)
    screen.click(button("Add"))


def create_trip(
    screen: Screen,
    name: str,
    creator: str,
    members: Sequence[str] = (),
    *,
    uses_fund: bool = False,
    starts_on: str = STARTS_ON,
    ends_on: str = ENDS_ON,
) -> str:
    """Create a trip from the empty home screen and return its path (`/trips/<id>`)."""
    screen.open("/")
    screen.click(button("Create a trip"))
    screen.visible(text_node("Create a trip", "h1"))
    screen.type(field("Trip name"), name)
    screen.set_date(field("Start date"), starts_on)
    screen.set_date(field("End date"), ends_on)
    if uses_fund:
        screen.click("//button[@role='switch' and @aria-checked='false']")
        screen.visible("//button[@role='switch' and @aria-checked='true']")
    screen.type(field("Your name"), creator)
    for member in members:
        add_member_chip(screen, member)
        screen.visible(f"//li[.//span[normalize-space(.)='{member}']]")
    screen.click("//form//button[@type='submit']")
    screen.wait_url(TRIP_PAGE)
    screen.visible(text_node(name, "h1"))
    return screen.current_path().split("?")[0]


def add_fund_contribution(screen: Screen, who: str | None, digits: str) -> None:
    """Record a contribution on the fund screen; `who=None` keeps the creator selected."""
    screen.click(button("Record a contribution"))
    screen.visible(DIALOG)
    if who is not None:
        screen.click(button(who, DIALOG))
    screen.type(field("Amount paid in", DIALOG), digits)
    screen.click(button("Save", DIALOG))
    screen.gone(DIALOG)


def add_expense(
    screen: Screen,
    title: str,
    digits: str,
    *,
    payer: str | None = None,
    excluded: Sequence[str] = (),
    exact: Mapping[str, str] | None = None,
) -> None:
    """Submit a new expense from the bottom nav and wait until it appears in the day list."""
    screen.click(button("Add expense", "//nav"))
    screen.visible(text_node("Add expense", "h1"))
    screen.type(field("Amount"), digits)
    screen.type(field("What for"), title)
    if payer is not None:
        screen.click("//button[@aria-haspopup='dialog']")
        screen.click(button(payer, DIALOG))
        screen.gone(DIALOG)
    for name in excluded:
        screen.click(toggle_button(name))
        screen.visible(f"{toggle_button(name)}[@aria-pressed='false']")
    if exact is not None:
        screen.click("//label[.//span[normalize-space(.)='Amount']]")
        for name, amount in exact.items():
            screen.type(field(f"{name}'s amount"), amount)
    screen.click(button("Save expense"))
    screen.wait_url(TRIP_PAGE)
    screen.visible(row(title))


def _fund_remaining_xpath() -> str:
    return f"{text_node('Fund left', 'p')}/parent::div/following-sibling::p[1]"


def fund_remaining(screen: Screen) -> str:
    """Return the headline remaining fund balance under 'Fund left'."""
    return screen.text(_fund_remaining_xpath())


def wait_fund_remaining(screen: Screen, amount: str) -> None:
    screen.wait_text(_fund_remaining_xpath(), amount)


def open_row(screen: Screen, title: str) -> str:
    """Expand an expense accordion row and return its base XPath."""
    screen.click(f"{row(title)}//button[@aria-expanded]")
    screen.visible(f"{row(title)}//button[@aria-expanded='true']")
    return row(title)


INVITE_LINK = "//p[contains(normalize-space(.), '/join#')]"


def open_invite_link(screen: Screen) -> str:
    """Navigate to Members via bottom nav and return the invite link shown."""
    screen.click(button("Members", "//nav"))
    return screen.text(INVITE_LINK).strip()


def open_balances(screen: Screen) -> None:
    screen.click(button("Balances", "//nav"))
    screen.visible(text_node("Balances", "h1"))
