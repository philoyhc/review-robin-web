"""Declining a leave prompt leaves no busy bar behind.

``guide/operator_pages_enhancements.md`` Item 2. ``base.html``'s
navigation busy indicator arms on a link click or a form submit and
waits for the next page to clear it. When the page's own
``beforeunload`` guard asks first and the operator stays, no page comes,
so a page with a guard tells the indicator through
``window.rrwLeaveWillPrompt``. Session Home's case is in
``test_session_home_dirty_guard.py``; these are the Instruments page's
dirty-card guard and the Observers expander's cohort guard.

Chromium shows a ``beforeunload`` prompt only to a page the user has
interacted with, so edits are typed or clicked, never set from script.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Dialog, Page, expect

from ._builder import open_unlocked, rows
from .conftest import LiveServer


def _decline_dialogs(page: Page) -> list[str]:
    seen: list[str] = []

    def handle(dialog: Dialog) -> None:
        seen.append(dialog.type)
        dialog.dismiss()

    page.on("dialog", handle)
    return seen


def _assert_no_busy_bar(page: Page) -> None:
    # Past the indicator's 200 ms arming delay.
    page.wait_for_timeout(400)
    expect(page.locator("[data-rrw-busy-bar]")).to_be_hidden()
    assert "rrw-navigating" not in (page.locator("body").get_attribute("class") or "")


def _reviewers_tab(page: Page):
    return page.locator("a.nav-tab", has_text="Reviewers")


def test_instruments_declined_leave_arms_no_bar(
    page: Page, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    card = open_unlocked(page, session_id)
    name = rows(card).first.locator("[data-new-model-rf-name]")
    name.click()
    name.press_sequentially("x")
    expect(card).to_have_attribute("data-instrument-dirty", "true")
    seen = _decline_dialogs(page)

    _reviewers_tab(page).click()

    assert seen == ["beforeunload"]
    assert page.url.endswith(f"/operator/sessions/{session_id}/instruments")
    _assert_no_busy_bar(page)


def _seed_observers(database_url: str, session_id: int) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.models import Observer, ReviewSession

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            review_session = db.get(ReviewSession, session_id)
            review_session.observers_enabled = True
            db.add(
                Observer(
                    session_id=session_id,
                    email="watcher@example.org",
                    display_name="Watcher",
                    status="active",
                )
            )
            db.commit()
    finally:
        engine.dispose()


def test_observers_declined_leave_arms_no_bar(
    page: Page, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed_observers(live_server.database_url, session_id)
    page.goto(f"/operator/sessions/{session_id}/observers")
    page.locator("input.observer-select").first.check()
    combinator = page.locator(".cohort-combinator-btn:visible").first
    combinator.click()
    seen = _decline_dialogs(page)

    _reviewers_tab(page).click()

    assert seen == ["beforeunload"]
    assert page.url.split("?")[0].endswith(f"/operator/sessions/{session_id}/observers")
    _assert_no_busy_bar(page)
