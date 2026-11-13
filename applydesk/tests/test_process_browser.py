"""The Process page in a real Chromium (segment AD1E rung 3): stage cards
that open and close, take a name and dates, are added, replicated,
deleted and moved, and hold the form within ruling 15, the Outline
following. Without a Chromium build the test skips, saying why;
``RRW_REQUIRE_BROWSER=1`` (set by CI) turns that skip into a failure."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error, Locator, Page, Route, sync_playwright

from applydesk.tests._host import host_with

ORIGIN = "http://applydesk.test"
PAGE = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/process"
BLANK = f"{ORIGIN}/applydesk/operator/exercises/n5wg8tjr3e/process"


@pytest.fixture
def page() -> Iterator[Page]:
    client = TestClient(host_with(("applydesk",))[0])

    def serve(route: Route) -> None:
        response = client.get(route.request.url.removeprefix(ORIGIN))
        route.fulfill(
            status=response.status_code,
            body=response.content,
            headers={"content-type": response.headers.get("content-type", "text/html")},
        )

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as exc:
            reason = f"Chromium could not launch: {exc.message.splitlines()[0]}"
            if os.environ.get("RRW_REQUIRE_BROWSER") == "1":
                pytest.fail(f"{reason}, and RRW_REQUIRE_BROWSER=1", pytrace=False)
            pytest.skip(reason)
        tab = browser.new_page(viewport={"width": 1280, "height": 900})
        errors: list[str] = []
        tab.on("pageerror", lambda exc: errors.append(str(exc)))
        tab.context.route(f"{ORIGIN}/**", serve)
        yield tab
        browser.close()
        assert errors == [], f"page errors: {errors}"


def _cards(page: Page) -> Locator:
    return page.locator("#pc-cards > .pc")


def _names(page: Page) -> list[str]:
    return _cards(page).locator('[data-sum="name"]').all_inner_texts()


def _counts(page: Page) -> str:
    return page.locator("[data-pc-counts]").inner_text()


def _open(card: Locator) -> None:
    if card.get_attribute("data-open") is None:
        card.locator("[data-fc-toggle]").click()


def test_a_card_opens_and_its_name_and_dates_follow(page: Page) -> None:
    page.goto(PAGE)
    review = _cards(page).nth(1)
    assert review.get_attribute("data-open") is None
    _open(review)
    assert review.get_attribute("data-open") == ""
    review.locator('[data-pc="name"]').fill("Peer and panel review")
    review.locator('[data-pc="to"]').fill("12 Nov")
    assert review.locator('[data-sum="name"]').inner_text() == "Peer and panel review"
    assert review.locator('[data-sum="dates"]').inner_text() == "16 Oct – 12 Nov"
    outline = page.locator("[data-pc-outline]").inner_text()
    assert "Peer and panel review 16 Oct – 12 Nov" in outline
    review.locator('[data-pc="name"]').fill("")
    assert review.locator('[data-sum="name"]').inner_text() == "Stage 2"


def test_stages_are_added_replicated_and_deleted(page: Page) -> None:
    page.goto(PAGE)
    assert _counts(page) == "4 stages · 3 gates · 3 outcomes"
    review = _cards(page).nth(1)
    _open(review)
    review.locator('[data-fc-act="new"]').click()
    assert _names(page)[2] == "Stage 3"
    assert _counts(page) == "5 stages · 3 gates · 3 outcomes"
    # A replica keeps the gates and outcome, as new columns; not the form.
    first = _cards(page).nth(0)
    _open(first)
    first.locator('[data-fc-act="replicate"]').click()
    copy = _cards(page).nth(1)
    assert copy.locator('.pc-item[data-item="form"]').count() == 0
    review = _cards(page).nth(2)
    review.locator('[data-fc-act="replicate"]').click()
    assert _counts(page) == "7 stages · 5 gates · 4 outcomes"
    keys = (
        _cards(page)
        .locator(".pc-item[data-key]")
        .evaluate_all("els => els.map(e => e.dataset.key)")
    )
    assert len(keys) == len(set(keys))
    # Deleting, down to the last stage, which stays.
    while _cards(page).count() > 1:
        card = _cards(page).nth(0)
        _open(card)
        card.locator('[data-fc-act="delete"]').click()
    last = _cards(page).nth(0)
    _open(last)
    delete = last.locator('[data-fc-act="delete"]')
    assert (
        delete.is_disabled() and delete.get_attribute("title") == "The last stage cannot be deleted"
    )


def test_moving_a_stage_renumbers_its_gates_and_outcome(page: Page) -> None:
    page.goto(PAGE)
    interview = _cards(page).nth(2)
    interview.locator("[data-fc-grip]").focus()
    page.keyboard.press("ArrowUp")
    assert _names(page) == ["Call for applications", "Interview", "Review", "Decision"]
    moved = _cards(page).nth(1)
    _open(moved)
    kickers = moved.locator("[data-pc-kicker]").all_inner_texts()
    assert [k.upper() for k in kickers] == ["GATE 1", "OUTCOME 1"]
    assert "Gate 1: Interview" in page.locator("[data-pc-outline]").inner_text()
    assert "Moved Interview to 2 of 4." in page.locator("[data-pc-live]").inner_text()


def test_the_form_sits_in_one_stage_never_beside_a_gate(page: Page) -> None:
    page.goto(PAGE)
    first, review, decision = _cards(page).nth(0), _cards(page).nth(1), _cards(page).nth(3)
    for card in (review, decision):
        _open(card)
    assert review.locator('[data-pc-act="form"]').get_attribute("title") == (
        "A stage holding gates holds no form"
    )
    assert decision.locator('[data-pc-act="form"]').get_attribute("title") == (
        "Another stage holds the form"
    )
    _open(first)
    first.locator('[data-pc-act="remove-form"]').click()
    assert first.locator('[data-sum="holds"]').inner_text().upper() == "NO GATES"
    assert decision.locator('[data-pc-act="form"]').is_enabled()
    decision.locator('[data-pc-act="form"]').click()
    assert decision.locator('.pc-item[data-item="form"]').count() == 1
    assert first.locator('[data-pc-act="form"]').get_attribute("title") == (
        "Another stage holds the form"
    )
    outline = page.locator("[data-pc-outline]").inner_text()
    assert outline.index("Form") > outline.index("Decision")


def test_a_blank_exercise_starts_with_one_open_stage(page: Page) -> None:
    page.goto(BLANK)
    assert _cards(page).count() == 1
    card = _cards(page).nth(0)
    assert card.get_attribute("data-open") == ""
    assert card.locator('[data-sum="name"]').inner_text() == "Stage 1"
    assert card.locator('[data-fc-act="delete"]').is_disabled()


# --- Rung 4: gates and the outcome, added and removed ---
def test_gates_and_an_outcome_are_added_and_removed(page: Page) -> None:
    page.goto(PAGE)
    review = _cards(page).nth(1)
    _open(review)
    review.locator('[data-pc-act="gate"]').click()
    items = review.locator(".pc-item").evaluate_all("els => els.map(e => e.dataset.item)")
    assert items == ["gate", "gate", "gate", "outcome"]  # before the outcome
    new = review.locator('.pc-item[data-item="gate"]').nth(2)
    assert new.locator('[data-pc="item-name"]').evaluate("e => e === document.activeElement")
    new.locator('[data-pc="item-name"]').fill("Community panel")
    assert new.locator("[data-pc-kicker]").text_content() == "Gate 3"
    outline = page.locator("[data-pc-outline]").inner_text()
    assert "Gate 3: Community panel" in outline and "Gate 4: Interview" in outline
    assert _counts(page) == "4 stages · 4 gates · 3 outcomes"
    # One outcome per stage: its button refuses until it is removed.
    add_out = review.locator('[data-pc-act="outcome"]')
    assert add_out.is_disabled()
    review.locator('[data-pc-act="remove-outcome"]').click()
    assert add_out.is_enabled()
    assert review.locator('[data-sum="holds"]').text_content() == "3 gates"
    add_out.click()
    assert review.locator('.pc-item[data-item="outcome"]').count() == 1
    assert _counts(page) == "4 stages · 4 gates · 3 outcomes"
    # Removing every gate lets the stage take the form, were it free.
    for _ in range(3):
        review.locator('[data-pc-act="remove-gate"]').first.click()
    assert review.locator('[data-pc-act="form"]').get_attribute("title") == (
        "Another stage holds the form"
    )


def test_a_stage_holding_the_form_takes_no_gate(page: Page) -> None:
    page.goto(PAGE)
    first = _cards(page).nth(0)
    _open(first)
    gate = first.locator('[data-pc-act="gate"]')
    assert gate.is_disabled()
    assert gate.get_attribute("title") == "A stage holding the form holds no gate"
    first.locator('[data-pc-act="outcome"]').click()  # an outcome beside the form is fine
    assert first.locator('[data-sum="holds"]').text_content() == "Form · Outcome: Untitled outcome"
    first.locator('[data-pc-act="remove-form"]').click()
    assert gate.is_enabled()
