"""Exercise Home's timeline in a real Chromium (segment AD1I, rung 3):
the Horizontal / Vertical switch, kept per viewer in the browser, and the
starting rule (Vertical on a phone or past four stages). Without a
Chromium build the tests skip, saying why; ``RRW_REQUIRE_BROWSER=1`` (set
by CI) turns that skip into a failure."""

from __future__ import annotations

from playwright.sync_api import Dialog, Page, expect

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
        "els => els.map(e => Math.round(e.getBoundingClientRect().width))"
    )
    assert len(set(widths)) == 1, widths  # the last one too (cold read)
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


# --- Rung 4: Details unlocked ---
DRAFT_HOME = f"{ORIGIN}/applydesk/operator/exercises/c4xh2ndv6s"


def test_details_unlock_edit_and_lock(page: Page) -> None:
    page.goto(HOME)
    card = page.locator("[data-details]")
    assert not card.locator("[data-dt-form]").is_visible()
    card.get_by_role("button", name="Unlock").click()
    assert card.get_attribute("data-unlocked") is not None
    assert not card.get_by_role("button", name="Unlock").is_visible()  # its place taken by Lock
    assert card.locator('[data-dt="name"]').evaluate("e => e === document.activeElement")
    # A published exercise's code and who may apply are fixed (G2).
    assert card.get_by_label("Exercise Code").is_disabled()
    assert card.get_by_label("Who may apply").is_disabled()
    card.get_by_label("Description").fill("Look after a house of residents.")
    card.get_by_label("Help contact").fill("")
    card.get_by_label("Timezone").select_option("Europe/London")
    card.get_by_role("checkbox", name="Blind review").check()
    assert card.locator("[data-unsaved]").is_visible()
    card.get_by_role("button", name="Lock", exact=True).click()
    assert card.get_attribute("data-unlocked") is None
    view = card.locator("[data-dt-view]")
    assert view.locator('[data-dt-show="description"]').inner_text() == (
        "Look after a house of residents."
    )
    # Emptied, the help contact is the operator settings' default again.
    assert view.locator('[data-dt-show="contact"]').inner_text() == (
        "applydesk-help@example.edu · the default"
    )
    assert view.locator('[data-dt-show="timezone"]').inner_text() == "Europe/London"
    assert view.locator('[data-dt-show="blind"]').inner_text() == "On"
    assert card.locator("[data-dt-said]").inner_text().startswith("Locked: changed on this page")
    assert card.locator("[data-unsaved]").is_visible()  # kept, but not saved
    assert card.get_by_role("button", name="Unlock").evaluate("e => e === document.activeElement")
    # Discard puts back what was last kept, not what was loaded.
    card.get_by_role("button", name="Unlock").click()
    card.get_by_label("Description").fill("Something else.")
    card.get_by_role("button", name="Discard changes").click()
    assert view.locator('[data-dt-show="description"]').inner_text() == (
        "Look after a house of residents."
    )


def test_details_refuse_what_cannot_hold(page: Page) -> None:
    page.goto(DRAFT_HOME)
    card = page.locator("[data-details]")
    card.get_by_role("button", name="Unlock").click()
    why = card.locator("[data-dt-why]")
    card.locator('[data-dt="name"]').fill("  ")
    card.get_by_role("button", name="Lock", exact=True).click()
    expect(why).to_have_text("A name is needed.")
    assert card.locator('[data-dt="name"]').get_attribute("aria-invalid") == "true"
    assert card.locator('[data-dt="name"]').evaluate("e => e === document.activeElement")
    card.locator('[data-dt="name"]').fill("Summer Internship Scheme 2027")
    # A draft's code may change, but never to another exercise's, any case.
    card.get_by_label("Exercise Code").fill("ra-2027")
    card.get_by_role("button", name="Lock", exact=True).click()
    expect(why).to_have_text(
        "ra-2027 is already Recruitment and Selection of Residential Assistants's code."
    )
    card.get_by_label("Exercise Code").fill("SIS-2028")
    card.get_by_label("Help contact").fill("not an address")
    card.get_by_role("button", name="Lock", exact=True).click()
    expect(why).to_have_text("A help contact is an email address.")
    card.get_by_label("Help contact").fill("interns@example.edu")
    card.get_by_role("button", name="Lock", exact=True).click()
    assert card.locator('[data-dt-show="code"]').inner_text() == "SIS-2028"
    assert card.locator('[data-dt-show="contact"]').inner_text() == "interns@example.edu"
    assert card.locator("[aria-invalid]").count() == 0


def test_leaving_with_changes_asks_first(page: Page) -> None:
    page.goto(HOME)
    card = page.locator("[data-details]")
    card.get_by_role("button", name="Unlock").click()
    card.locator('[data-dt="name"]').fill("Recruitment of RAs")
    asked: list[str] = []

    def answer(d: Dialog) -> None:
        asked.append(d.type)
        d.accept()

    page.once("dialog", answer)
    page.reload()
    assert asked == ["beforeunload"]


def test_enter_on_blind_review_does_not_lock(page: Page) -> None:
    page.goto(HOME)
    card = page.locator("[data-details]")
    card.get_by_role("button", name="Unlock").click()
    card.get_by_role("checkbox", name="Blind review").focus()
    page.keyboard.press("Enter")
    assert card.get_attribute("data-unlocked") is not None


# --- Rung 5a: cards side by side share a height only when theirs are close ---


def test_cards_share_a_height_only_when_theirs_are_close(page: Page) -> None:
    page.goto(HOME)  # three stages and their operator rows: far taller than Details
    grid = page.locator(".hm-grid")
    assert "is-equal-height" not in (grid.get_attribute("class") or "")
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/r6tm4kq9wz")  # one stage: close
    assert "is-equal-height" in (grid.get_attribute("class") or "")
    heights = page.locator(".hm-grid > .card").evaluate_all(
        "els => els.map(e => Math.round(e.getBoundingClientRect().height))"
    )
    assert len(set(heights)) == 1, heights
    # Stacked on a phone, each keeps its own height.
    page.set_viewport_size({"width": 390, "height": 844})
    page.reload()
    assert "is-equal-height" not in (grid.get_attribute("class") or "")


def test_the_operator_part_lines_up_across_stages(page: Page) -> None:
    page.goto(HOME)
    tops = page.locator(".tl-op").evaluate_all(
        "els => els.map(e => Math.round(e.getBoundingClientRect().top))"
    )
    assert len(tops) == 3 and len(set(tops)) == 1, tops
