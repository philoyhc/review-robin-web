"""Segment AD1T: the Operator Lobby's tick panel in a real Chromium, as
Review Robin's. Ticking rows highlights them and opens the panel under the
last ticked one: one exercise's fields, or the bulk actions for several.
Without a Chromium build the tests skip, saying why;
``RRW_REQUIRE_BROWSER=1`` (set by CI) turns that skip into a failure."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from applydesk.tests.test_form_browser import page as page

LOBBY = "http://applydesk.test/applydesk/operator/exercises"


def _tick(page: Page, code: str) -> None:
    page.get_by_role("checkbox", name=f"Select {code}").check()


def _row(page: Page, code: str) -> Locator:
    return page.locator("tr[data-lb-row]", has=page.get_by_role("checkbox", name=f"Select {code}"))


def test_one_tick_opens_the_panel_with_that_exercise_s_fields(page: Page) -> None:
    page.goto(LOBBY)
    panel = page.locator("[data-lb-panel]")
    expect(panel).to_be_hidden()
    _tick(page, "RA-2027")
    expect(panel).to_be_visible()
    expect(_row(page, "RA-2027")).to_have_class("lb-on")
    # The panel sits directly under the ticked row.
    assert _row(page, "RA-2027").evaluate("r => r.nextElementSibling.hasAttribute('data-lb-panel')")
    expect(panel.locator(".lb-exp-h")).to_have_text("1 exercise selected")
    expect(panel.locator('[data-lb-f="name"]')).to_have_value(
        "Recruitment and Selection of Residential Assistants"
    )
    expect(panel.locator('[data-lb-f="code"]')).to_have_value("RA-2027")
    expect(panel.locator('[data-lb-f="tags"]')).to_have_value("Residential, 2027")
    expect(panel.get_by_role("button", name="Duplicate settings only")).to_be_visible()
    expect(panel.get_by_role("button", name="Delete all")).to_be_hidden()
    # Every action but Cancel waits for AD2B, saying so.
    expect(panel.get_by_role("button", name="Save")).to_be_disabled()
    expect(panel.get_by_role("button", name="Save")).to_have_attribute(
        "title", "Saving here is not built yet"
    )
    # The header box shows a dash while only some rows are ticked.
    assert page.locator("[data-lb-all]").evaluate("b => b.indeterminate")
    panel.get_by_role("button", name="Cancel").click()
    expect(panel).to_be_hidden()
    expect(_row(page, "RA-2027")).not_to_have_class("lb-on")


def test_more_ticks_move_the_panel_under_the_last_and_offer_bulk_actions(page: Page) -> None:
    page.goto(LOBBY)
    panel = page.locator("[data-lb-panel]")
    _tick(page, "RA-2027")
    _tick(page, "TEA-2026")
    assert _row(page, "TEA-2026").evaluate(
        "r => r.nextElementSibling.hasAttribute('data-lb-panel')"
    )
    expect(panel.locator(".lb-exp-h")).to_have_text("2 exercises selected")
    expect(panel.get_by_role("button", name="Delete all")).to_be_visible()
    expect(panel.get_by_role("button", name="Duplicate")).to_be_hidden()
    # Cancel unticks the row the panel sits under; the panel goes back
    # to the row ticked before it, as Review Robin's.
    _tick(page, "PCG-2027")
    panel.get_by_role("button", name="Cancel").click()
    assert not page.get_by_role("checkbox", name="Select PCG-2027").is_checked()
    assert _row(page, "TEA-2026").evaluate(
        "r => r.nextElementSibling.hasAttribute('data-lb-panel')"
    )
    # Unticking the last ticked row moves the panel back too, not to the
    # lowest ticked row.
    _tick(page, "PCG-2027")
    page.get_by_role("checkbox", name="Select PCG-2027").uncheck()
    assert _row(page, "TEA-2026").evaluate(
        "r => r.nextElementSibling.hasAttribute('data-lb-panel')"
    )
    # Unselect others keeps the last ticked, and the panel turns to one.
    panel.get_by_role("button", name="Unselect others").click()
    expect(panel.locator(".lb-exp-h")).to_have_text("1 exercise selected")
    expect(panel.locator('[data-lb-f="code"]')).to_have_value("TEA-2026")
    assert not page.get_by_role("checkbox", name="Select RA-2027").is_checked()
    # The header box ticks every row, then clears them and the panel.
    page.locator("[data-lb-all]").check()
    expect(page.locator("tr.lb-on")).to_have_count(page.locator("[data-lb-tick]").count())
    expect(panel).to_be_visible()
    page.locator("[data-lb-all]").uncheck()
    expect(panel).to_be_hidden()
    expect(page.locator("tr.lb-on")).to_have_count(0)
    # Unselect all clears every row at once.
    _tick(page, "RA-2027")
    _tick(page, "TEA-2026")
    panel.get_by_role("button", name="Unselect all").click()
    expect(panel).to_be_hidden()


def test_the_cards_stand_side_by_side_over_the_table(page: Page) -> None:
    page.set_viewport_size({"width": 1300, "height": 900})
    page.goto(LOBBY)
    counts, filt = page.locator(".lb-row > .card").all()
    a, b = counts.bounding_box(), filt.bounding_box()
    assert a is not None and b is not None
    assert abs(a["y"] - b["y"]) < 1 and b["x"] > a["x"] + a["width"]
    # New exercise opens the scratch form from the Filter card.
    filt.get_by_role("button", name="New exercise").click()
    expect(page.locator("[data-nx-form]")).to_be_visible()
