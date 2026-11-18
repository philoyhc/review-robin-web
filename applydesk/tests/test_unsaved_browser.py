"""Form's and Process's one Save (ruling 23, segment AD1F rung 7b): an
Unsaved changes marker once anything is changed, and a question on
leaving with it showing; opening a card, a preview or a panel box is not
a change. Skips without a Chromium build, as `test_form_browser.py`'s."""

from __future__ import annotations

import pytest
from playwright.sync_api import Dialog, Page

from applydesk import locks
from applydesk.tests.test_form_browser import FORM
from applydesk.tests.test_form_browser import page as page  # the fixture, re-exported
from applydesk.tests.test_process_browser import MODEL as PROCESS
from applydesk.tests.test_process_browser import ORIGIN


@pytest.fixture(autouse=True)
def _form_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests edit the form: its lock (segment AD1K) is opened, as a
    draft exercise's would be; the lock has tests of its own."""
    monkeypatch.setattr(locks, "form_lock", lambda e: locks.OPEN)


DRAFT_PROCESS = f"{ORIGIN}/applydesk/operator/exercises/c4xh2ndv6s/process"

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
    page.goto(DRAFT_PROCESS)  # a draft's stages move; a published one's are fixed
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
    card = page.locator(".fc", has=page.locator('[data-sum="label"]:text-is("Preferred reviewer")'))
    card.locator("[data-fc-toggle]").click()
    card.locator("select[data-panel-pick]").select_option("__new")
    card.get_by_role("button", name="Cancel").click()
    assert not mark.is_visible()
    page.goto(PROCESS.replace("wa9juxbc2t", "c4xh2ndv6s"))  # a draft: its gate unsent
    page.locator("#pc-cards > .pc").nth(1).locator("[data-fc-toggle]").first.click()
    page.locator('details[data-gsec="gate"] > summary').first.click()  # opening a card is no change
    assert not mark.is_visible()
    rule = page.locator('[data-pc-act="rule"]:visible').first
    rule.click()
    assert not mark.is_visible()


MODEL = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t"


def test_dossiers_marks_what_lock_kept_and_asks_before_leaving(page: Page) -> None:
    """AD-07: Lock keeps changes on the page only; the count stays
    marked after Lock, and leaving asks."""
    page.goto(f"{MODEL}/dossiers")
    page.locator("[data-ap-lock]").click()
    assert not page.evaluate(LEAVES)
    page.locator("[data-row] [data-ap-adm]:not([disabled])").first.click()
    page.locator("[data-ap-lock]").click()
    marker = page.locator("[data-ap-changes]")
    assert marker.is_visible()
    assert marker.inner_text() == "1 change on this page, not saved until AD2"
    assert "kept on this page" in page.locator("[data-ap-said]").inner_text()
    assert page.evaluate(LEAVES)
    # The same cell changed again over a second Lock counts once: the count
    # is of what differs from the page as loaded (cold read).
    page.locator("[data-ap-lock]").click()
    page.locator("[data-row] [data-ap-adm]:not([disabled])").first.click()
    page.locator("[data-ap-lock]").click()
    assert marker.inner_text() == "1 change on this page, not saved until AD2"


def test_panels_marks_what_is_kept_and_asks_before_leaving(page: Page) -> None:
    """AD-07: ✓ says kept on this page, the page is marked and leaving
    asks; × on a member of a panel an opened gate keeps asks first."""
    page.goto(f"{MODEL}/panels")
    assert not page.evaluate(LEAVES)
    mark = page.locator("[data-pn-kept]")
    assert not mark.is_visible()
    opened = page.locator(
        "[data-pn-row]", has=page.locator('input[data-pn-panel="current-ras"]:checked')
    )
    who = opened.first.locator('[data-pn-view="name"]').inner_text()
    opened.first.locator("[data-pn-select]").check()
    asked: list[str] = []

    def dismiss(d: Dialog) -> None:
        asked.append(d.message)
        d.dismiss()

    page.once("dialog", dismiss)
    opened.first.locator('[data-pn-act="remove"]').click()
    assert asked and "opened gate keeps" in asked[0]
    assert page.locator("[data-pn-row]", has_text=who).count() == 1  # dismissed: kept
    assert not mark.is_visible() and not page.evaluate(LEAVES)  # nothing kept yet
    opened.first.locator('[data-pn-act="save"]').click()  # untouched: nothing changed
    assert page.locator("[data-pn-said]").inner_text().endswith("nothing changed.")
    assert not mark.is_visible()
    # A new row removed was never kept.
    page.locator('[data-pn-act="add"]').click()
    page.locator("[data-pn-row]").first.locator('[data-pn-act="remove"]').click()
    assert not mark.is_visible() and not page.evaluate(LEAVES)
    # A ticked row with changes ✓ has not kept asks on leaving.
    opened.first.locator("[data-pn-select]").check()
    opened.first.locator('[data-pn="note"]').fill("Edited")
    assert page.evaluate(LEAVES) and not mark.is_visible()
    opened.first.locator('[data-pn-act="save"]').click()
    assert page.locator("[data-pn-said]").inner_text().endswith("kept on this page.")
    assert mark.is_visible() and page.evaluate(LEAVES)


def test_the_gate_page_asks_before_leaving_its_pages_with_changes(page: Page) -> None:
    """AD-07: changes kept in the tab ask before leaving the gate's
    pages; its own pager and sort do not."""
    page.goto(f"{MODEL}/evaluations/gate_3")
    assert not page.evaluate(LEAVES)
    page.locator("tbody tr").first.get_by_role("button", name="Remove").click()
    assert page.evaluate(LEAVES)
    page.evaluate(
        "() => { const a = document.querySelector('a.ev-sort-btn');"
        " a.addEventListener('click', e => e.preventDefault(), {once: true}); a.click(); }"
    )
    assert not page.evaluate(LEAVES)  # a click on its own sort: staying
    page.wait_for_timeout(1100)
    assert page.evaluate(LEAVES)  # that click led nowhere: a later leave asks (cold read)
    page.evaluate(
        "() => { const a = document.querySelector('a.ev-sort-btn');"
        " a.addEventListener('click', e => e.preventDefault(), {once: true});"
        " a.dispatchEvent(new MouseEvent('click',"
        " {bubbles: true, cancelable: true, ctrlKey: true})); }"
    )
    assert page.evaluate(LEAVES)  # a new tab is not staying
