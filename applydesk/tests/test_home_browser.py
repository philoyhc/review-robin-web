"""Exercise Home's timeline in a real Chromium (segment AD1I, rung 3):
the Horizontal / Vertical switch, kept per viewer in the browser, and the
starting rule (Vertical on a phone or past four stages). Without a
Chromium build the tests skip, saying why; ``RRW_REQUIRE_BROWSER=1`` (set
by CI) turns that skip into a failure."""

from __future__ import annotations

from playwright.sync_api import Page

from applydesk.tests.test_form_browser import page as page

ORIGIN = "http://applydesk.test"
HOME = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t"


def _layout(page: Page) -> str | None:
    return page.locator("[data-timeline]").get_attribute("data-layout")


def test_the_timeline_flips_and_the_choice_is_kept(page: Page) -> None:
    page.goto(HOME)
    switch = page.get_by_role("group", name="Timeline layout")
    assert switch.is_visible() and _layout(page) == "h"
    assert switch.get_by_role("button", name="Horizontal").get_attribute("aria-pressed") == "true"
    # Equal widths: every stage's bar as wide as the next (Decision amended).
    widths = page.locator(".tl-bar").evaluate_all(
        "els => els.map(e => Math.round(e.closest('.tl-stage').getBoundingClientRect().width))"
    )
    assert len(set(widths)) == 1
    # Today sits inside the stage under way, at its place in that stage.
    bar = page.locator(".tl-now .tl-bar").bounding_box()
    today = page.locator(".tl-now .tl-today").bounding_box()
    assert bar and today and bar["x"] < today["x"] < bar["x"] + bar["width"]
    switch.get_by_role("button", name="Vertical").click()
    assert _layout(page) == "v"
    assert switch.get_by_role("button", name="Vertical").get_attribute("aria-pressed") == "true"
    page.reload()
    assert _layout(page) == "v"  # kept in this browser
    page.get_by_role("button", name="Horizontal").click()
    page.reload()
    assert _layout(page) == "h"


def test_a_phone_starts_vertical_unless_the_viewer_chose(page: Page) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(HOME)
    assert _layout(page) == "v"
    # The vertical spine runs through each stage's dot.
    dot = page.locator(".tl-now .tl-dot").bounding_box()
    bar = page.locator(".tl-now .tl-bar").bounding_box()
    assert dot and bar and abs((dot["x"] + dot["width"] / 2) - (bar["x"] + bar["width"] / 2)) < 3
    page.get_by_role("button", name="Horizontal").click()
    page.reload()
    assert _layout(page) == "h"  # the viewer's own choice holds


def test_without_storage_the_starting_rule_holds(page: Page) -> None:
    page.add_init_script(
        "Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } })"
    )
    page.goto(HOME)
    assert _layout(page) == "h"
    page.get_by_role("button", name="Vertical").click()
    assert _layout(page) == "v"  # still flips on this page
