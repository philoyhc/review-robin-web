"""Session Home's details card: leaving with unsaved edits asks first.

``guide/operator_pages_enhancements.md`` Item 1, PR 1. Another card's
form, a link, a reload or closing the tab would drop the card's edits
without a word; a ``beforeunload`` guard now asks. The card's own Save,
and Cancel or Lock, leave without asking.

Chromium shows a ``beforeunload`` prompt only to a page the user has
interacted with, so the edits are typed (``press_sequentially``) rather
than ``fill``-ed.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Dialog, Page, expect


def _record_dialogs(page: Page, *, accept: bool = False) -> list[str]:
    seen: list[str] = []

    def handle(dialog: Dialog) -> None:
        seen.append(dialog.type)
        if accept:
            dialog.accept()
        else:
            dialog.dismiss()

    page.on("dialog", handle)
    return seen


def _edit_description(page: Page, session_id: int, text: str) -> None:
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    expect(page.locator("#session-config")).to_have_attribute("data-config-mode", "edit")
    field = page.locator("#mock-description")
    field.click()
    field.press_sequentially(text)
    expect(page.locator("#session-config")).to_have_attribute("data-config-dirty", "true")


def _reviewers_tab(page: Page):
    return page.locator("a.nav-tab", has_text="Reviewers")


def test_a_dirty_card_asks_before_a_link_leaves_home(
    page: Page, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _edit_description(page, session_id, "Unsaved")
    seen = _record_dialogs(page)

    _reviewers_tab(page).click()

    # Declined: still on Home, the edit still there.
    expect(page.locator("#mock-description")).to_have_value("Unsaved")
    assert seen == ["beforeunload"]
    assert page.url.endswith(f"/operator/sessions/{session_id}?editing=1")


def test_accepting_the_prompt_leaves_and_drops_the_edit(
    page: Page, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _edit_description(page, session_id, "Dropped")
    seen = _record_dialogs(page, accept=True)

    with page.expect_navigation():
        _reviewers_tab(page).click()

    assert seen == ["beforeunload"]
    assert f"/operator/sessions/{session_id}/" in page.url
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    expect(page.locator("#mock-description")).not_to_have_value("Dropped")


def test_save_leaves_without_asking(
    page: Page, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _edit_description(page, session_id, "Saved")
    seen = _record_dialogs(page)

    with page.expect_navigation():
        page.locator("[data-config-save]").click()
    page.wait_for_load_state("load")
    expect(page.locator("#mock-description")).to_have_value("Saved")

    # The card came back clean, so a link leaves without asking too.
    with page.expect_navigation():
        _reviewers_tab(page).click()
    assert seen == []


def test_cancel_and_lock_leave_without_asking(
    page: Page, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    seen = _record_dialogs(page)

    _edit_description(page, session_id, "Cancelled")
    page.locator("[data-config-cancel]").click()
    expect(page.locator("#session-config")).to_have_attribute("data-config-mode", "display")
    with page.expect_navigation():
        page.reload()

    _edit_description(page, session_id, "Locked")
    page.locator("[data-config-lock-toggle]").click()
    expect(page.locator("#session-config")).to_have_attribute("data-config-mode", "display")
    with page.expect_navigation():
        _reviewers_tab(page).click()

    assert seen == []
