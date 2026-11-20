"""End-to-end journey: create trip with shared fund, record contributions, and CRUD expenses."""

from __future__ import annotations

from collections.abc import Callable

from flows import (
    add_expense,
    add_fund_contribution,
    add_member_chip,
    create_trip,
    fund_remaining,
    open_row,
    wait_fund_remaining,
)
from pages import DIALOG, Screen, button, field, row, text_node


def test_create_trip_add_expenses_edit_and_delete(browser: Callable[[], Screen]) -> None:
    screen = browser()

    # Reject duplicate member names client-side regardless of letter casing.
    screen.open("/")
    screen.click(button("Create a trip"))
    screen.type(field("Your name"), "Alex")
    add_member_chip(screen, "Ben")
    add_member_chip(screen, "ben")
    screen.visible(text_node("Someone already has this name", "p"))
    screen.clear(field("Other members"))

    create_trip(screen, "Da Lat E2E", "Alex", ["Ben", "Chloe"], uses_fund=True)

    # Summary card shows trip date window, active member count, and remaining fund.
    screen.wait_text("//main", "11/5 – 11/8")
    screen.wait_text("//main", "3 people")
    screen.visible(text_node("Fund left", "p"))

    # Record two fund contributions and return to the trip screen.
    screen.click(button("Group fund"))
    screen.visible(text_node("Shared fund", "h1"))
    add_fund_contribution(screen, None, "3000000")
    add_fund_contribution(screen, "Ben", "3000000")
    screen.wait_text("//main", "6,000,000")
    screen.click(button("Back"))
    screen.wait_text("//main", "Fund left")
    assert "6,000,000" in fund_remaining(screen)

    add_expense(screen, "Airport taxi", "300000", payer="Group fund")
    add_expense(screen, "Late noodles", "130000", payer="Chloe", excluded=["Alex"])
    add_expense(
        screen,
        "Bistro dinner",
        "3800000",
        payer="Alex (you)",
        exact={"Alex": "1400000", "Ben": "1200000", "Chloe": "1200000"},
    )

    # Verify day tab, payer subtitles, amounts, and updated shared fund balance.
    screen.visible("//*[@role='tab' and normalize-space(.)='Day 1']")
    taxi = screen.text(row("Airport taxi"))
    assert "Group fund paid · 3/3 people" in taxi
    assert "300,000" in taxi
    noodles = screen.text(row("Late noodles"))
    assert "Chloe paid · 2/3 people" in noodles
    assert "130,000" in noodles
    dinner = screen.text(row("Bistro dinner"))
    assert "Alex paid · 3/3 people" in dinner
    assert "3,800,000" in dinner
    assert "5,700,000" in fund_remaining(screen)

    # Inspect expanded per-person split and exempt list.
    open_row(screen, "Late noodles")
    screen.wait_text(row("Late noodles"), "65,000")
    screen.wait_text(row("Late noodles"), "Exempt: Alex")

    # Edit amount with optimistic concurrency version and check recalculated split.
    screen.click(button("Edit expense", row("Late noodles")))
    screen.visible(text_node("Edit expense", "h1"))
    screen.replace(field("Amount"), "140000")
    screen.wait_value(field("Amount"), "140,000")
    screen.click(button("Save expense"))
    screen.visible(row("Late noodles"))
    open_row(screen, "Late noodles")
    screen.wait_text(row("Late noodles"), "70,000")

    # Delete fund-paid expense after confirming and verify fund balance is restored.
    open_row(screen, "Airport taxi")
    screen.click(button("Delete expense", row("Airport taxi")))
    screen.visible(text_node("Delete this expense?", "h2"))
    screen.click(button("Delete", DIALOG))
    screen.gone(row("Airport taxi"))
    wait_fund_remaining(screen, "6,000,000")
