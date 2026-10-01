"""A branch as the reviewer meets it.

Each test names the row of ``guide/post_azure_todo_checklist.md`` item 6
it repeats (``guide/browser_test.md`` rung 4). Every test builds a session
whose "Rating" (Integer 1-5) governs a String field "Why" under
"Rating ≥ 4", activates it, and signs in as the roster's one reviewer.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Locator, Page, expect

from ._builder import (
    REVIEWER_EMAIL,
    activate,
    branch_rating,
    save,
    seed_rosters,
)
from .conftest import LiveServer


def _answer(reviewer: Page, field: str) -> Locator:
    # Inputs are named response[<assignment id>][<field key>]; one reviewer
    # has one assignment, so the key alone picks the cell.
    return reviewer.locator(f"[name^='response['][name$='][{field}]']")


def _save_answers(reviewer: Page) -> None:
    with reviewer.expect_response(lambda r: r.request.method == "POST"):
        reviewer.locator("[data-rs-save]:visible").first.click()
    reviewer.wait_for_load_state()


def _branched_session(
    page: Page,
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], int],
    *,
    required: bool = False,
) -> int:
    session_id = new_session()
    seed_rosters(api, session_id)
    card = branch_rating(page, session_id)
    if required:
        card.locator("[data-new-model-rf-governed] [data-new-model-rf-required]").click()
        save(page, card)
    activate(api, live_server.database_url, session_id)
    return session_id


def test_a_branch_opens_as_the_answer_meets_its_condition(
    page: Page,
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], int],
) -> None:
    """Item 6, 'The branch for a reviewer'."""
    session_id = _branched_session(page, api, live_server, new_session)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.goto(f"/me/sessions/{session_id}/1")
    rating, why = _answer(reviewer, "rating"), _answer(reviewer, "why")
    why_cell = why.locator("xpath=ancestor::td[1]")
    expect(why).to_be_disabled()
    expect(why_cell).to_have_attribute("title", "Opens when Rating ≥ 4")

    rating.fill("2")
    expect(why).to_be_disabled()
    rating.fill("5")
    expect(why).to_be_enabled()
    why.fill("Clear and specific")

    rating.fill("3")
    expect(why).to_be_disabled()
    expect(why).to_have_value("Clear and specific")  # greyed, not cleared

    _save_answers(reviewer)
    reviewer.goto(f"/me/sessions/{session_id}/1")
    expect(_answer(reviewer, "rating")).to_have_value("3")
    expect(_answer(reviewer, "why")).to_have_value("")  # Save drops a closed answer


def test_a_required_governed_field_is_required_only_while_open(
    page: Page,
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], int],
) -> None:
    """Item 6, 'Required only while open'."""
    session_id = _branched_session(page, api, live_server, new_session, required=True)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.goto(f"/me/sessions/{session_id}/1")
    submit = reviewer.get_by_role("button", name="Submit").first

    _answer(reviewer, "rating").fill("5")
    with reviewer.expect_navigation():
        submit.click()
    expect(reviewer.get_by_text("Required fields missing.")).to_be_visible()
    expect(reviewer.get_by_text("Page 1: Carol — Why")).to_be_visible()

    _answer(reviewer, "rating").fill("2")
    with reviewer.expect_navigation():
        reviewer.get_by_role("button", name="Submit").first.click()
    expect(reviewer.get_by_text("Required fields missing.")).to_have_count(0)
