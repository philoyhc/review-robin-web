"""Form's and Process's one Save (ruling 23, segment AD1F rung 7b): an
Unsaved changes marker once anything is changed, and a question on
leaving with it showing; opening a card, a preview or a panel box is not
a change. Skips without a Chromium build, as `test_form_browser.py`'s."""

from __future__ import annotations

from playwright.sync_api import Page

from applydesk.tests.test_form_browser import FORM
from applydesk.tests.test_form_browser import page as page  # the fixture, re-exported
from applydesk.tests.test_process_browser import PAGE as PROCESS

LEAVES = (
    "() => { const e = new Event('beforeunload', {cancelable: true});"
    " window.dispatchEvent(e); return e.defaultPrevented; }"
)


def test_form_marks_a_change_and_asks_before_leaving(page: Page) -> None:
    page.goto(FORM)
    mark = page.locator("[data-unsaved]")
    assert not mark.is_visible() and not page.evaluate(LEAVES)
    # Opening a card and the preview change nothing.
    page.locator("#fb-cards .fc [data-fc-toggle]").first.click()
    page.locator("[data-fb-preview]").click()
    page.locator("[data-fb-preview]").click()
    assert not mark.is_visible()
    card = page.locator("#fb-cards .fc[data-open]").first
    card.locator('[data-f="label"]').fill("A new label")
    assert mark.is_visible() and mark.inner_text() == "Unsaved changes"
    assert page.evaluate(LEAVES)


def test_process_marks_a_change_and_asks_before_leaving(page: Page) -> None:
    page.goto(PROCESS)
    mark = page.locator("[data-unsaved]")
    assert not mark.is_visible() and not page.evaluate(LEAVES)
    page.locator("#pc-cards > .pc [data-fc-toggle]").first.click()
    assert not mark.is_visible()
    page.locator('#pc-cards > .pc [data-fc-act="new"]').first.click()
    assert mark.is_visible()
    assert page.evaluate(LEAVES)


def test_a_move_a_toggle_and_a_rule_button_are_changes(page: Page) -> None:
    """Cold read on rung 7b: none of these fires an input or a change."""
    page.goto(FORM)
    mark = page.locator("[data-unsaved]")
    page.locator("#fb-cards [data-fc-grip]").first.press("ArrowDown")
    assert mark.is_visible()
    page.goto(FORM)
    card = page.locator(
        ".fc", has=page.locator('[data-sum="label"]:text-is("Matriculation number")')
    )
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-f="required"]').click()
    assert mark.is_visible()
    page.goto(PROCESS)
    page.locator("#pc-cards [data-fc-grip]").first.press("ArrowDown")
    assert mark.is_visible()


def test_what_is_not_a_change_leaves_no_mark(page: Page) -> None:
    """Typing in the preview, opening a rule editor, and picking + New
    panel… then cancelling change nothing."""
    page.goto(FORM)
    mark = page.locator("[data-unsaved]")
    page.locator("[data-fb-preview]").click()
    page.locator("#fb-preview input[type=text], #fb-preview textarea").first.fill("an answer")
    page.locator("[data-fb-preview]").click()
    assert not mark.is_visible()
    page.goto(PROCESS.replace("wa9juxbc2t", "c4xh2ndv6s"))  # a draft: its gate unsent
    stage = page.locator("#pc-cards > .pc").nth(1)
    stage.locator("[data-fc-toggle]").first.click()
    gate = stage.locator('.pc-item[data-item="gate"]').first
    if gate.get_attribute("data-open") is None:
        gate.locator("[data-pi-toggle]").click()
    gate.locator("[data-pc-panel]").select_option("__new")
    gate.get_by_role("button", name="Cancel").click()
    assert not mark.is_visible()
    rule = page.locator('[data-pc-act="rule"]:visible').first
    rule.click()
    assert not mark.is_visible()
