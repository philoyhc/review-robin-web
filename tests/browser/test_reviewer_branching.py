"""A branch as the reviewer meets it.

Each test names the row of ``guide/post_azure_todo_checklist.md`` item 6
it repeats (``guide/archive/browser_test.md`` rung 4). Every test builds a session
whose "Rating" (Integer 1-5) governs a String field "Why" under
"Rating ≥ 4", activates it, and signs in as the roster's one reviewer.
"""

from __future__ import annotations

import re
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
    opens_at: str = "4",
) -> int:
    session_id = new_session()
    seed_rosters(api, session_id)
    card = branch_rating(page, session_id, value=opens_at)
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

    # Saved while open, the answer persists ...
    rating.fill("5")
    _save_answers(reviewer)
    reviewer.goto(f"/me/sessions/{session_id}/1")
    expect(_answer(reviewer, "why")).to_have_value("Clear and specific")

    # ... and a Save with the branch closed deletes it on the server.
    _answer(reviewer, "rating").fill("3")
    _save_answers(reviewer)
    reviewer.goto(f"/me/sessions/{session_id}/1")
    expect(_answer(reviewer, "rating")).to_have_value("3")
    expect(_answer(reviewer, "why")).to_have_value("")


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
    why = _answer(reviewer, "why")
    required_pill = reviewer.get_by_text(re.compile(r"Required items completed: \d+/\d+"))

    _answer(reviewer, "rating").fill("5")
    expect(why).to_have_attribute("aria-label", re.compile(r"\(required\)$"))
    with reviewer.expect_navigation():
        reviewer.get_by_role("button", name="Submit").first.click()
    expect(reviewer.get_by_text("Required fields missing.")).to_be_visible()
    expect(reviewer.get_by_text("#1: Carol — Why")).to_be_visible()
    # The server-rendered count includes the open governed field: Rating and Why.
    expect(required_pill).to_have_text(re.compile(r"/2\s*$"))

    _answer(reviewer, "rating").fill("2")
    expect(_answer(reviewer, "why")).not_to_have_attribute(
        "aria-label", re.compile(r"\(required\)$")
    )
    reviewer.get_by_role("button", name="Submit").first.click()
    reviewer.wait_for_url(f"**/me/sessions/{session_id}/summary")


def test_a_refused_parent_keeps_the_text_without_javascript(
    page: Page,
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], int],
) -> None:
    """Item 6, 'A refused parent keeps the text'.

    With JavaScript on, the inline step check stops 2.5 in an Integer
    field before Save posts, so only a script-less page reaches the
    server's refusal. Without script the branch opens on the stored
    answer, so the parent is saved once first."""
    session_id = _branched_session(page, api, live_server, new_session, opens_at="2")
    reviewer = page_as(REVIEWER_EMAIL, javascript=False)
    url = f"/me/sessions/{session_id}/1"
    reviewer.goto(url)
    _answer(reviewer, "rating").fill("3")
    _save_answers(reviewer)
    reviewer.goto(url)
    expect(_answer(reviewer, "why")).to_be_enabled()

    _answer(reviewer, "rating").fill("2.5")
    _answer(reviewer, "why").fill("Clear and specific")
    _save_answers(reviewer)

    errors = reviewer.locator("[data-rs-errors-card]")
    expect(errors).to_contain_text("Must be a whole number.")
    expect(errors).to_contain_text("Kept until Rating is fixed.")
    expect(_answer(reviewer, "rating")).to_have_value("2.5")
    expect(_answer(reviewer, "why")).to_have_value("Clear and specific")

    # Neither was written: the stored answers are what they were.
    reviewer.goto(url)
    expect(_answer(reviewer, "rating")).to_have_value("3")
    expect(_answer(reviewer, "why")).to_have_value("")
