"""The Process page in a real Chromium (segment AD1E rungs 3–5): stage
cards that open and close, take a name and dates, are added, replicated,
deleted and moved, and hold the form within ruling 15; gates and an
outcome added and removed; their rules and weights edited, the Outline
following. Without a Chromium build the test skips, saying why;
``RRW_REQUIRE_BROWSER=1`` (set by CI) turns that skip into a failure.

The editor's tests run on the fellowship's process, installed on the
conference grant (`applydesk/tests/_fellowship.py`, segment AD1H); the
model exercise's own, the RA recruitment's, at the end (``MODEL``)."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Dialog, Error, Locator, Page, Route, sync_playwright

from applydesk import sample_data, stages
from applydesk.tests import _fellowship
from applydesk.tests._host import host_with

ORIGIN = "http://applydesk.test"
PAGE = f"{ORIGIN}/applydesk/operator/exercises/{_fellowship.EX}/process"
MODEL = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/process"
BLANK = f"{ORIGIN}/applydesk/operator/exercises/n5wg8tjr3e/process"


@pytest.fixture
def page(monkeypatch: pytest.MonkeyPatch) -> Iterator[Page]:
    _fellowship.install(monkeypatch)
    client = TestClient(host_with(("applydesk",))[0])

    def serve(route: Route) -> None:
        # Any method: the page asks the server for its rules' problems
        # (ruling 78).
        request = route.request
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() in ("content-type", "sec-fetch-site")
        }
        response = client.request(
            request.method,
            request.url.removeprefix(ORIGIN),
            content=request.post_data_buffer,
            headers=headers,
        )
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


def _checked(page: Page) -> None:
    """The rules' problems are the server's to say (ruling 78): wait for
    the page's last check to come back before reading them."""
    page.wait_for_function("!('pcAsking' in document.querySelector('[data-process]').dataset)")


def test_a_card_opens_and_its_name_and_dates_follow(page: Page) -> None:
    page.goto(PAGE)
    review = _cards(page).nth(1)
    assert review.get_attribute("data-open") is None
    _open(review)
    assert review.get_attribute("data-open") == ""
    review.locator('[data-pc="name"]').fill("Peer and panel review")
    review.locator('[data-pc="to"]').fill("2026-11-12T23:59")
    assert review.locator('[data-sum="name"]').inner_text() == "Peer and panel review"
    assert review.locator('[data-sum="dates"]').inner_text() == "16 Oct – 12 Nov 2026"
    outline = page.locator("[data-pc-outline]").inner_text()
    assert "Peer and panel review 16 Oct – 12 Nov 2026" in outline
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
    # A replica's gates are new: no link to the original's Review Robin
    # card (ruling 61), the original's kept.
    rr = review.locator("[data-pc-rr]").first
    assert rr.locator("a").count() == 1
    copied = _cards(page).nth(3).locator("[data-pc-rr]").first
    assert copied.locator("a").count() == 0
    assert "once this gate is saved" in (copied.text_content() or "")
    # Nor Template → links: the copy's ticks are not saved (ruling 65).
    assert review.locator(".pc-tpl").count() > 0
    assert _cards(page).nth(3).locator(".pc-tpl").count() == 0
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
    assert "Gate 1 · Interview" in page.locator("[data-pc-outline]").inner_text()
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
    _open_all(review)
    review.locator('[data-pc-act="gate"]').click()
    items = review.locator(".pc-item").evaluate_all("els => els.map(e => e.dataset.item)")
    assert items == ["gate", "gate", "gate", "outcome"]  # before the outcome
    new = review.locator('.pc-item[data-item="gate"]').nth(2)
    assert new.locator('[data-pc="item-name"]').evaluate("e => e === document.activeElement")
    new.locator('[data-pc="item-name"]').fill("Community panel")
    assert new.locator("[data-pc-kicker]").text_content() == "Gate 3"
    outline = page.locator("[data-pc-outline]").inner_text()
    assert "Gate 3 · Community panel" in outline and "Gate 4 · Interview" in outline
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
    # An opened gate keeps its place (AD-01, ruling 29); the new one goes.
    removes = review.locator('[data-pc-act="remove-gate"]')
    assert removes.nth(0).is_disabled() and removes.nth(1).is_disabled()
    # Its fieldset carries the reason, which its controls' tooltips inherit.
    why = removes.nth(0).evaluate("b => b.closest('[data-pc-lock]').title")
    assert why.startswith("Its Review Robin session has opened")
    removes.nth(2).click()
    assert review.locator('.pc-item[data-item="gate"]').count() == 2
    # Removing every gate lets a stage take the form, were it free.
    interview = _cards(page).nth(2)
    _open_all(interview)
    interview.locator('[data-pc-act="remove-gate"]').click()
    assert interview.locator('[data-pc-act="form"]').get_attribute("title") == (
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


# --- Rung 5: rules, edited on the item ---
def _item(page: Page, key: str) -> Locator:
    item = page.locator(f'.pc-item[data-key="{key}"]')
    _open(item.locator("xpath=ancestor::article[1]"))
    _open_item(item)
    return item


def _set_values(item: Locator, values: list[str]) -> None:
    """Replace an outcome's values: each row removed, then each value
    added as a new row (a rename would carry its rules along, AD-57)."""
    while item.locator('[data-pc-act="remove-value"]').count():
        item.locator('[data-pc-act="remove-value"]').first.click()
    for v in values:
        item.locator('[data-pc-act="add-value"]').click()
        item.locator('[data-pc="value"]').last.fill(v)


def _rule(item: Locator) -> object:
    return json.loads(item.get_attribute("data-rule") or "null")


def _values(item: Locator) -> list[str]:
    rows = item.locator('[data-pc="value"]')
    return [rows.nth(i).input_value() for i in range(rows.count())]


def _open_item(item: Locator) -> None:
    if item.get_attribute("data-open") is None:
        item.locator("[data-pi-toggle]").click()
    _open_cards(item)


def _open_cards(item: Locator) -> None:
    """A gate's Gate and Evaluators cards, open: shut on load (ruling 28)."""
    cards = item.locator("details.gsec:not([open]) > summary")
    while cards.count():
        cards.first.click()


def _revert(card: Locator) -> None:
    """A published stage reverted to draft on the page, with a reason;
    the published stages after it first, as the page asks."""
    later = card.locator(
        "xpath=following-sibling::article[@data-kind='stage'][@data-status!='Draft']"
    )
    for i in reversed(range(later.count())):
        _revert(later.nth(i))
    _open(card)
    card.locator('[data-pc-st="revert"]').click()
    card.locator("[data-pc-reason]").fill("To fix a rule")
    card.locator('[data-pc-st="confirm"]').click()


def _open_all(card: Locator) -> None:
    """A stage card and every item in it, open (ruling 20)."""
    _open(card)
    for i in range(card.locator(".pc-item").count()):
        _open_item(card.locator(".pc-item").nth(i))


def _line(item: Locator) -> str:
    return item.locator("[data-rule-line]").inner_text()


def test_rule_lines_read_as_applications_headers(page: Page) -> None:
    page.goto(PAGE)
    assert _line(_item(page, "g1")) == (
        "Status is Submitted and the applicant's last submitted → Entered, else Not entered"
    )
    assert _line(_item(page, "o1")) == "Combined ≥ 4.2 → Shortlisted, else Not shortlisted"
    assert _line(_item(page, "g3")) == (
        "Shortlist for interview is Shortlisted → Entered, else Not entered"
    )
    assert _line(_item(page, "o3")) == "Decided by hand"


def test_a_rule_is_edited_extended_and_cleared(page: Page) -> None:
    page.goto(PAGE)
    o1 = _item(page, "o1")
    o1.locator('[data-pc-act="rule"]').click()
    o1.locator(".pc-cond input").fill("4.5")
    assert _line(o1) == "Combined ≥ 4.5 → Shortlisted, else Not shortlisted"
    g3 = _item(page, "g3")
    g3.locator('[data-pc-act="rule"]').click()
    g3.locator('[data-rule-part="add"]').click()
    assert _line(g3) == (
        "Shortlist for interview is Shortlisted and Status is Submitted → Entered, else Not entered"
    )
    g3.locator(".pc-cond").nth(1).locator("select").first.select_option("last")
    assert _line(g3).endswith("and the applicant's last submitted → Entered, else Not entered")
    g3.locator('[data-rule-part="clear"]').click()
    assert _line(g3) == "Decided by hand"
    o2 = _item(page, "o2")
    o2.locator('[data-pc-act="rule"]').click()
    o2.locator(".pc-cond select").first.select_option("comb")
    assert _line(o2) == "Combined ≥ 4.0 → Finalist, else Not a finalist"


def test_a_rule_branches_reads_a_form_answer_and_takes_the_best_n(page: Page) -> None:
    """Ruling 30 (segment AD1H rung 3): *+ Else if* adds a branch, tried
    after the first; a form answer and the best N are conditions; a
    branch removed leaves the rule as it was."""
    page.goto(PAGE)
    o1 = _item(page, "o1")
    o1.locator('[data-pc-act="rule"]').click()
    o1.locator('[data-rule-part="add-branch"]').click()
    assert _line(o1) == (
        "Combined ≥ 4.2 → Shortlisted; else if Rating at Peer Review ≥ 4.0 → Shortlisted,"
        " else Not shortlisted"
    )
    second = o1.locator('.pc-branch[data-branch="1"]')
    second.locator(".pc-cond select").first.select_option("form")
    answer = second.locator('select[aria-label="Answer, branch 2"]')
    assert answer.evaluate("e => [...e.options].map(o => o.value)") == [
        "Life Sciences",
        "Engineering",
        "Humanities",
    ]
    answer.select_option("Engineering")
    second.locator('[data-rule-part="add"]').click()
    second.locator(".pc-cond").nth(1).locator("select").first.select_option("top")
    count = second.locator('.pc-cond input[aria-label="How many, branch 2"]')
    count.fill("x")
    _checked(page)
    assert "takes the best “x”, not a whole number" in o1.locator("[data-rule-warn]").inner_text()
    count.fill("5")
    second.locator('[data-rule-part="then"]').select_option("Not shortlisted")
    assert _line(o1) == (
        "Combined ≥ 4.2 → Shortlisted; else if Field of study is Engineering and the best 5"
        " by Rating at Peer Review → Not shortlisted, else Not shortlisted"
    )
    _checked(page)
    assert not o1.locator("[data-rule-warn]").is_visible()
    # The question is named by its key (segment AD2D), shown by its label.
    field = next(
        k
        for k, q in sample_data.list_questions(_fellowship.EX).items()
        if q.label == "Field of study"
    )
    assert json.loads(o1.get_attribute("data-rule") or "null")["more"] == [
        {
            "when": [
                ["form", field, "is", "Engineering"],
                ["top", "g1.r1", "le", "5"],
            ],
            "then": "Not shortlisted",
        }
    ]
    # A branch removed, focus goes to the branch before it.
    o1.locator('[data-rule-part="add-branch"]').click()
    assert o1.locator(".pc-branch").count() == 3
    o1.locator('[aria-label="Remove branch 3"]').click()
    assert o1.locator(".pc-branch").count() == 2
    assert o1.locator('.pc-branch[data-branch="1"] [data-rule-part="add"]').evaluate(
        "e => e === document.activeElement"
    )
    # Its last condition removed, a branch goes with it.
    second.locator('[data-rule-part="remove"]').nth(1).click()
    second.locator('[data-rule-part="remove"]').first.click()
    assert _line(o1) == "Combined ≥ 4.2 → Shortlisted, else Not shortlisted"
    assert o1.locator(".pc-branch").count() == 1
    # A gate reads a form answer, never a ranking: it reads no results.
    g3 = _item(page, "g3")
    g3.locator('[data-pc-act="rule"]').click()
    kinds = g3.locator(".pc-cond select").first.evaluate("e => [...e.options].map(o => o.value)")
    assert "form" in kinds and "top" not in kinds


def test_a_form_answer_the_form_no_longer_asks_is_named(page: Page) -> None:
    page.goto(PAGE)
    o1 = _item(page, "o1")
    rule = {
        "when": [["form", "Year of study", "is", "2"]],
        "then": "Shortlisted",
        "otherwise": "Not shortlisted",
    }
    o1.evaluate("(e, r) => { e.dataset.rule = JSON.stringify(r); }", rule)
    _set_values(o1, ["Shortlisted", "Not shortlisted"])  # redraws
    _checked(page)
    assert "reads “Year of study”, not a List question on the form" in (
        o1.locator("[data-rule-warn]").inner_text()
    )


def test_a_rule_left_reading_a_later_outcome_is_named(page: Page) -> None:
    page.goto(PAGE)
    interview = _cards(page).nth(2)
    interview.locator("[data-fc-grip]").focus()
    page.keyboard.press("ArrowUp")
    g3 = _item(page, "g3")
    _checked(page)
    warn = g3.locator("[data-rule-warn]")
    assert warn.is_visible()
    assert warn.inner_text() == "This rule reads Shortlist for interview, which comes later."
    _checked(page)
    issues = page.locator("[data-pc-issues]").inner_text()
    assert "· Interview reads Shortlist for interview, which comes later." in issues
    _cards(page).nth(1).locator("[data-fc-grip]").focus()
    page.keyboard.press("ArrowDown")
    _checked(page)
    assert not warn.is_visible() and not page.locator("[data-pc-issues]").is_visible()


def test_an_outcome_s_weights_follow_the_gates_before_it(page: Page) -> None:
    page.goto(PAGE)
    o1 = _item(page, "o1")
    weights = o1.locator("[data-pc-weights]")
    # Every numeric result of its gates (ruling 21); the recommendation's
    # share is not weighed.
    assert weights.locator("[data-w-key]").evaluate_all("els => els.map(e => e.value)") == [
        "30",
        "70",
        "0",
    ]
    review = _cards(page).nth(1)
    _open_all(review)
    review.locator('[data-pc-act="gate"]').click()
    review.locator('.pc-item[data-item="gate"]').nth(2).locator('[data-pc="item-name"]').fill(
        "Extra"
    )
    names = weights.locator("[data-w-name]").all_inner_texts()
    assert names == [
        "Rating at Peer Review",
        "Score at Faculty Panel review",
        "Recommendation at Faculty Panel review",
        "Untitled result at Extra",
    ]
    assert weights.locator("[data-w-key]").evaluate_all("els => els.map(e => e.value)")[:2] == [
        "30",
        "70",
    ]
    review.locator('[data-pc-act="remove-gate"]').nth(2).click()
    assert weights.locator("[data-w-name]").all_inner_texts() == names[:3]


# --- Rung 5, after the item's cold read ---
def test_then_and_otherwise_are_chosen_with_the_mouse(page: Page) -> None:
    page.goto(PAGE)
    o1 = _item(page, "o1")
    o1.locator('[data-pc-act="rule"]').click()
    then = o1.locator('[data-rule-part="then"]')
    then.click()  # a click on the select must not redraw it away
    assert then.evaluate("e => e.isConnected && document.activeElement === e")
    then.select_option("Not shortlisted")
    assert _line(o1) == "Combined ≥ 4.2 → Not shortlisted, else Not shortlisted"


def test_a_flagged_rule_keeps_its_column_while_edited(page: Page) -> None:
    page.goto(PAGE)
    interview = _cards(page).nth(2)
    _open_all(interview)
    interview.locator('[data-pc-act="remove-gate"]').click()  # g3 goes
    interview.locator('[data-pc-act="gate"]').click()
    o2 = _item(page, "o2")
    _checked(page)
    warn = o2.locator("[data-rule-warn]")
    assert "no longer in the process" in (warn.text_content() or "")
    o2.locator('[data-pc-act="rule"]').click()
    o2.locator(".pc-cond input").fill("4.5")
    assert _line(o2) == "Result at (removed) ≥ 4.5 → Finalist, else Not a finalist"
    assert "no longer in the process" in (warn.text_content() or "")


def test_focus_stays_in_the_editor(page: Page) -> None:
    page.goto(PAGE)
    o1 = _item(page, "o1")
    o1.locator('[data-pc-act="rule"]').click()
    o1.locator(".pc-cond input").focus()
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.getAttribute('aria-label')") == (
        "Remove condition 1"
    )
    o1.locator('[data-rule-part="add"]').click()
    assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "Condition 2"
    o1.locator('[aria-label="Remove condition 2"]').click()
    assert page.evaluate("document.activeElement.dataset.rulePart") == "add"
    o1.locator(".pc-cond select").first.select_option("res")
    assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "Condition 1"
    assert _line(o1) == "Rating at Peer Review ≥ 4.0 → Shortlisted, else Not shortlisted"


def test_a_replica_s_rules_and_weights_read_its_own_gates(page: Page) -> None:
    page.goto(PAGE)
    review = _cards(page).nth(1)
    _open(review)
    review.locator('[data-fc-act="replicate"]').click()
    copy = _cards(page).nth(2)
    out = copy.locator('.pc-item[data-item="outcome"]')
    assert out.locator("[data-w-key]").evaluate_all("els => els.map(e => e.value)") == [
        "30",
        "70",
        "0",
    ]
    g = copy.locator('.pc-item[data-item="gate"]').evaluate_all(
        "els => els.map(e => e.dataset.key)"
    )
    assert out.locator("[data-w-key]").evaluate_all("els => els.map(e => e.dataset.wKey)") == [
        f"{g[0]}.r1",
        f"{g[1]}.r1",
        f"{g[1]}.r2",
    ]
    _checked(page)
    assert not out.locator("[data-rule-warn]").is_visible()


def test_a_replica_s_branched_rule_reads_its_own_gates(page: Page) -> None:
    """The cold read on rungs 2-3: a replica's rule renames the gate keys
    in every branch, a best N's included, and leaves a form answer's
    question as it is."""
    page.goto(PAGE)
    o1 = _item(page, "o1")
    rule = {
        "when": [["res", "g1.r1", "ge", "4"]],
        "then": "Shortlisted",
        "otherwise": "Not shortlisted",
        "more": [
            {
                "when": [
                    ["form", "Field of study", "is", "Engineering"],
                    ["top", "g2.r1", "le", "5"],
                ],
                "then": "Shortlisted",
            }
        ],
    }
    o1.evaluate("(e, r) => { e.dataset.rule = JSON.stringify(r); }", rule)
    review = _cards(page).nth(1)
    review.locator('[data-fc-act="replicate"]').click()
    copy = _cards(page).nth(2)
    g = copy.locator('.pc-item[data-item="gate"]').evaluate_all(
        "els => els.map(e => e.dataset.key)"
    )
    got = json.loads(copy.locator('.pc-item[data-item="outcome"]').get_attribute("data-rule") or "")
    assert got["when"] == [["res", f"{g[0]}.r1", "ge", "4"]]
    assert got["more"][0]["when"] == [
        ["form", "Field of study", "is", "Engineering"],
        ["top", f"{g[1]}.r1", "le", "5"],
    ]


def test_weights_say_when_their_gates_change_and_check_the_total(page: Page) -> None:
    page.goto(PAGE)
    o1 = _item(page, "o1")
    review = _cards(page).nth(1)
    review.locator('[data-pc-act="gate"]').click()
    weights = o1.locator("[data-pc-weights]")
    assert weights.locator("[data-w-key]").evaluate_all("els => els.map(e => e.value)") == [
        "30",
        "70",
        "0",
        "0",
    ]
    assert weights.locator("[data-w-note]").inner_text() == (
        "The results before it changed: check these weights."
    )
    weights.locator("[data-w-key]").first.fill("20")
    assert weights.locator("[data-w-note]").inner_text() == ""
    _checked(page)
    assert o1.locator("[data-rule-warn]").inner_text() == (
        "This outcome has weights adding up to 90, not 100."
    )
    _checked(page)
    assert "· Shortlist for interview has weights adding up to 90, not 100." in (
        page.locator("[data-pc-issues]").inner_text()
    )


def test_a_decision_outside_the_values_is_named(page: Page) -> None:
    page.goto(PAGE)
    o1 = _item(page, "o1")
    o1.locator('[data-pc-act="rule"]').click()
    _set_values(o1, ["Yes", "No"])
    assert o1.locator('[data-rule-part="then"]').input_value() == "Shortlisted"
    _checked(page)
    assert "decides “Shortlisted”, not among its values" in (
        o1.locator("[data-rule-warn]").inner_text()
    )


def test_a_stage_is_dragged_by_its_handle(page: Page) -> None:
    page.goto(PAGE)
    grip = _cards(page).nth(2).locator("[data-fc-grip]")
    target = _cards(page).nth(0).bounding_box()
    box = grip.bounding_box()
    assert target and box
    page.mouse.move(box["x"] + 4, box["y"] + 4)
    page.mouse.down()
    page.mouse.move(target["x"] + 20, target["y"] + 4, steps=8)
    page.mouse.up()
    assert _names(page)[0] == "Interview"


def test_every_rule_line_reads_as_the_server_wrote_it(page: Page) -> None:
    """The script rewrites each line on load; it must agree with
    `stages.rule_text` on every item, not just a sample."""
    page.goto(PAGE)
    served = page.evaluate(
        """async () => {
          const html = await (await fetch(location.href)).text();
          const doc = new DOMParser().parseFromString(html, "text/html");
          return [...doc.querySelectorAll("#pc-cards [data-rule-line]")].map(e => e.textContent);
        }"""
    )
    shown = page.locator("#pc-cards [data-rule-line]").all_text_contents()
    assert shown == served and len(shown) > 4


def test_a_later_rule_s_editor_follows_an_outcome_s_values(page: Page) -> None:
    page.goto(PAGE)
    g3 = _item(page, "g3")
    g3.locator('[data-pc-act="rule"]').click()
    o1 = _item(page, "o1")
    _set_values(o1, ["Yes", "No"])
    value = g3.locator('.pc-cond select[aria-label="Value"]')
    assert value.evaluate_all("els => [...els[0].options].map(o => o.value)") == [
        "Shortlisted",
        "Yes",
        "No",
    ]
    _checked(page)
    assert "reads “Shortlisted”, not among the values of Shortlist for interview" in (
        g3.locator("[data-rule-warn]").inner_text()
    )
    value.select_option("Yes")
    assert _line(g3) == "Shortlist for interview is Yes → Entered, else Not entered"
    _checked(page)
    assert not g3.locator("[data-rule-warn]").is_visible()


def test_an_open_editor_follows_gates_added_and_renamed(page: Page) -> None:
    page.goto(PAGE)
    o1 = _item(page, "o1")
    o1.locator('[data-pc-act="rule"]').click()
    o1.locator(".pc-cond select").first.select_option("res")
    review = _cards(page).nth(1)
    review.locator('[data-pc-act="gate"]').click()
    review.locator('.pc-item[data-item="gate"]').nth(2).locator('[data-pc="item-name"]').fill(
        "Extra"
    )
    result = o1.locator('.pc-cond select[aria-label="Result"]')
    # A gate's results a rule can read (ruling 21): not its comments.
    assert result.evaluate("e => [...e.options].map(o => o.text)") == [
        "Rating at Peer Review",
        "Score at Faculty Panel review",
        "Recommendation at Faculty Panel review",
        "Untitled result at Extra",
    ]
    assert result.input_value() == "g1.r1"  # its rule still reads the result it read


def test_the_outline_opens_and_goes_to_a_stage_or_its_item(page: Page) -> None:
    """As Form's Outline goes to a question (author, 2026-11-13)."""
    page.goto(PAGE)
    interview = _cards(page).nth(2)
    assert interview.get_attribute("data-open") is None
    page.locator("[data-pc-outline] .pc-o-stage").nth(2).click()
    assert interview.get_attribute("data-open") == ""
    assert interview.locator("[data-fc-toggle]").evaluate("e => e === document.activeElement")
    page.locator("[data-pc-outline] .fb-o-item", has_text="Outcome 1").click()
    review = _cards(page).nth(1)
    assert review.get_attribute("data-open") == ""
    assert page.evaluate("document.activeElement.value") == "Shortlist for interview"


def test_the_outline_s_form_row_opens_the_form_s_stage(page: Page) -> None:
    page.goto(PAGE)
    page.locator("[data-pc-outline] .fb-o-item", has_text="Form").click()
    first = _cards(page).nth(0)
    assert first.get_attribute("data-open") == ""
    # The form item opens too, its own toggle taking focus (it has no name).
    form = first.locator('.pc-item[data-item="form"]')
    assert form.get_attribute("data-open") == ""
    assert form.locator("[data-pi-toggle]").evaluate("e => e === document.activeElement")


def _checks(item: Locator) -> list[bool]:
    return item.locator("input[type=checkbox]").evaluate_all("els => els.map(e => e.checked)")


def test_an_outcome_s_release_is_set_per_audience(page: Page) -> None:
    """When released: applicants and panel evaluators each get the
    timeline updated, an email, or both (author, 2026-11-13); an email
    ticked is a template owed on Emails, none picked here (ruling 16)."""
    page.goto(PAGE)
    o1 = _item(page, "o1")
    groups = o1.locator(".pc-aud")
    assert groups.locator(".pc-aud-h").all_inner_texts() == ["Applicants", "Evaluators"]
    assert _checks(o1) == [True, True, False, False]
    assert _checks(_item(page, "o2")) == [True, True, False, True]
    assert o1.locator("select[data-rel-template]").count() == 0
    assert o1.locator(".pc-hint a").get_attribute("href") == (
        f"/applydesk/operator/exercises/{_fellowship.EX}/emails"
    )


def test_a_new_outcome_and_form_send_what_is_usual(page: Page) -> None:
    page.goto(PAGE)
    interview = _cards(page).nth(2)
    _open_all(interview)
    interview.locator('[data-pc-act="remove-outcome"]').click()
    interview.locator('[data-pc-act="outcome"]').click()
    assert _checks(interview.locator('.pc-item[data-item="outcome"]')) == [
        True,
        False,
        False,
        False,
    ]
    first = _cards(page).nth(0)
    _open_all(first)
    form = first.locator('.pc-item[data-item="form"]')
    assert _checks(form) == [True, True]  # the sample's receipt and reminder
    form.locator('[data-pc-act="remove-form"]').click()
    first.locator('[data-pc-act="form"]').click()
    assert _checks(first.locator('.pc-item[data-item="form"]')) == [True, False]


def test_a_replica_keeps_its_outcome_s_release(page: Page) -> None:
    page.goto(PAGE)
    review = _cards(page).nth(1)
    _open_all(review)
    review.locator('[data-rel="evaluators-timeline"]').check()
    review.locator('[data-rel="applicants-email"]').uncheck()
    review.locator('[data-fc-act="replicate"]').click()
    copy = _cards(page).nth(2).locator('.pc-item[data-item="outcome"]')
    assert _checks(copy) == [True, False, True, False]


# --- Segment AD1F rung 4b: items collapse inside their stage (ruling 20) ---
def test_items_open_and_shut_their_heads_always_named(page: Page) -> None:
    page.goto(PAGE)
    review = _cards(page).nth(1)
    _open(review)
    items = review.locator(".pc-item")
    # Three items in the stage: each shows its head, shut.
    assert items.evaluate_all("els => els.map(e => e.hasAttribute('data-open'))") == [
        False,
        False,
        False,
    ]
    heads = review.locator("[data-pi-name]").all_inner_texts()
    assert heads == ["Peer Review", "Faculty Panel review", "Shortlist for interview"]
    g1 = review.locator('.pc-item[data-key="g1"]')
    assert g1.locator(".chip").first.text_content() == "Results in"
    assert not g1.locator('[data-pc="item-name"]').is_visible()
    toggle = g1.locator("[data-pi-toggle]")
    toggle.click()
    assert g1.get_attribute("data-open") == ""
    assert toggle.get_attribute("aria-label") == "Collapse Gate 1"
    _open_cards(g1)
    assert g1.locator('[data-pc="item-name"]').is_disabled()  # opened: fixed (AD-01)
    toggle.click()
    assert g1.get_attribute("data-open") is None
    # The outcome's email chip follows its boxes.
    o1 = review.locator('.pc-item[data-key="o1"]')
    assert o1.locator("[data-pi-emails]").text_content() == "1 email"
    _open_item(o1)
    o1.locator('[data-rel="evaluators-email"]').check()
    assert o1.locator("[data-pi-emails]").text_content() == "2 emails"


def test_a_lone_or_new_item_opens_and_the_outline_opens_an_item(page: Page) -> None:
    page.goto(PAGE)
    decision = _cards(page).nth(3)  # holds only its outcome
    assert decision.locator(".pc-item").get_attribute("data-open") == ""
    review = _cards(page).nth(1)
    _open(review)
    review.locator('[data-pc-act="gate"]').click()
    assert review.locator('.pc-item[data-item="gate"]').nth(2).get_attribute("data-open") == ""
    page.locator("[data-pc-outline] .fb-o-item", has_text="Gate 4 · Interview").click()
    g3 = page.locator('.pc-item[data-key="g3"]')
    assert g3.get_attribute("data-open") == ""
    assert g3.locator('[data-pc="item-name"]').evaluate("e => e === document.activeElement")


# --- Segment AD1F rung 4c: a gate's Evaluators on Process (ruling 20) ---
DRAFT = f"{ORIGIN}/applydesk/operator/exercises/c4xh2ndv6s/process"


def test_a_gate_item_makes_and_picks_its_panel(page: Page) -> None:
    page.goto(DRAFT)
    selection = _cards(page).nth(1)
    _open(selection)
    gate = selection.locator('.pc-item[data-item="gate"]')
    assert gate.get_attribute("data-open") == ""  # alone in its stage
    _open_cards(gate)
    _checked(page)
    issues = page.locator("[data-pc-issues]")
    assert "Gate 1 · Placement interview has no evaluators." in issues.inner_text()
    assert page.locator("[data-o-panel]").text_content() == "No evaluators"
    assert not page.locator("[data-unsaved]").is_visible()
    gate.locator('[data-ps-act="add"]').click()
    assert page.locator("[data-unsaved]").is_visible()  # a source's buttons are changes
    assert "Gate 1 · Placement interview has no panel chosen for source 1." in issues.inner_text()
    gate.locator('[data-ps="total-min"]').fill("1")
    gate.locator('[data-ps="total-max"]').fill("1")
    menu = gate.locator("[data-pc-panel]")
    menu.select_option("__new")
    box = gate.locator("[data-newpanel]")
    box.locator('[data-np="name"]').fill("Interview panel")
    box.locator('[data-np="members"]').fill("Daniel Koh, priya.raman@example.edu")
    box.get_by_role("button", name="+Panel").click()
    assert gate.locator("[data-pi-panel]").text_content() == "Interview panel 1 · Total 1"
    # Its members are on Panels, not listed here (author, 2026-11-17).
    assert gate.locator("[data-pc-members]").count() == 0
    assert page.locator("[data-o-panel]").text_content() == "Interview panel"
    assert "Gate 1" not in issues.inner_text()
    # A replica keeps the sources its gate was given.
    selection.locator('[data-fc-act="replicate"]').click()
    copy = _cards(page).nth(2).locator('.pc-item[data-item="gate"]')
    assert copy.locator("[data-pi-panel]").text_content() == "Interview panel 1 · Total 1"
    # Back to none: the head and the Outline say so again.
    menu.select_option("")
    assert gate.locator("[data-pi-panel]").text_content() == "No panel 1 · Total 1"
    assert "Gate 1 · Placement interview has no panel chosen for source 1." in issues.inner_text()


def test_a_sent_gate_keeps_its_panel(page: Page) -> None:
    page.goto(PAGE)
    g1 = _item(page, "g1")
    assert g1.locator("[data-pc-panel]").first.is_disabled()
    # An opened gate says so once, at its top; its progress is Evaluations'.
    note = g1.locator("[data-pc-sent]")
    assert note.count() == 1 and note.inner_text() == (
        "Its Review Robin session has opened: its settings are fixed here."
    )
    # Mid-stage (ruling 29): the Interview gate is ready, not sent, so it
    # carries no note and its panel can still change.
    g3 = _item(page, "g3")
    assert g3.locator("[data-pc-sent]").count() == 0
    assert not g3.locator("[data-pc-panel]").is_disabled()
    assert page.locator("[data-o-panel]").all_inner_texts() == [
        "Nominated, Panel A",
        "Panel B",
        "Interviewers",
    ]
    # Drawing the ranks leaves a sent gate's arrows fixed.
    assert g1.locator('[data-ps-act="down"]').first.is_disabled()


def test_a_replica_of_a_sent_stage_is_not_sent(page: Page) -> None:
    """The cold read on 4b-4c: a copy's gates and outcome are new, so
    their sources can be changed and nothing reads sent or released."""
    page.goto(PAGE)
    review = _cards(page).nth(1)
    _open(review)
    review.locator('[data-fc-act="replicate"]').click()
    copy = _cards(page).nth(2)
    states = copy.locator("[data-pi-state]").all_text_contents()
    assert states == ["Not ready", "Not ready", "Not released"]
    menus = copy.locator("[data-pc-panel]")
    # Peer Review's two (its nominated row's hidden) and Panel B's one.
    assert menus.count() == 3
    assert all(menus.nth(i).is_enabled() for i in range(3))
    assert copy.locator("[data-pc-sent]").count() == 0
    assert (
        copy.locator("[data-pi-panel]").first.text_content()
        == "Nominated 0–1 · Panel A 1–2 · Total 2"
    )


# --- Segment AD1G rung 4: a gate's evaluator sources wired (ruling 27) ---


def _peer_copy(page: Page) -> Locator:
    """An unsent copy of the Peer Review gate: Nominated 0–1, Panel A 1–2,
    Total 2."""
    page.goto(PAGE)
    review = _cards(page).nth(1)
    _open(review)
    review.locator('[data-fc-act="replicate"]').click()
    gate = _cards(page).nth(2).locator('.pc-item[data-item="gate"]').first
    _open_item(gate)
    return gate


def _kinds(gate: Locator) -> list[str | None]:
    rows = gate.locator("[data-ps-row]")
    return [rows.nth(i).get_attribute("data-kind") for i in range(rows.count())]


def test_sources_are_ranked_and_removed(page: Page) -> None:
    gate = _peer_copy(page)
    assert _kinds(gate) == ["nominated", "panel"]
    first = gate.locator("[data-ps-row]").first
    assert first.locator('[data-ps-act="up"]').is_disabled()
    first.locator('[data-ps-act="down"]').click()
    assert _kinds(gate) == ["panel", "nominated"]
    assert gate.locator("[data-ps-rank]").all_inner_texts() == ["1", "2"]
    assert gate.locator("[data-pi-panel]").text_content() == "Panel A 1–2 · Nominated 0–1 · Total 2"
    # At the bottom its down arrow is off, so focus moves to its up arrow.
    moved = gate.locator("[data-ps-row]").nth(1)
    assert moved.locator('[data-ps-act="up"]').evaluate("e => e === document.activeElement")
    assert page.locator("[data-pc-live]").text_content() == "Source moved to 2."
    assert page.locator("[data-unsaved]").is_visible()
    # Removing Panel A leaves the Total's max above what is left.
    gate.locator("[data-ps-row]").first.locator('[data-ps-act="remove"]').click()
    assert _kinds(gate) == ["nominated"]
    # Focus goes to the row that took its place.
    assert gate.locator('[data-ps-act="remove"]').evaluate("e => e === document.activeElement")
    assert gate.locator("[data-ps-bounds]").text_content() == "within 0–1"
    _checked(page)
    issues = page.locator("[data-pc-issues]")
    assert "has its Total's max above the sources' maxes together (1)." in issues.inner_text()
    assert "chip-warn" in (gate.locator("[data-pi-panel]").get_attribute("class") or "")
    gate.locator('[data-ps="total-min"]').fill("1")
    gate.locator('[data-ps="total-max"]').fill("1")
    assert "Total" not in issues.inner_text()
    gate.locator("[data-ps-row]").first.locator('[data-ps-act="remove"]').click()
    assert gate.locator('[data-ps-act="add"]').evaluate("e => e === document.activeElement")
    assert gate.locator("[data-ps-bounds]").text_content() == "No sources"
    assert not gate.locator("[data-ps-headrow]").is_visible()
    assert gate.locator("[data-pi-panel]").text_content() == "No evaluators"


def test_a_source_takes_its_kind_and_its_bounds(page: Page) -> None:
    gate = _peer_copy(page)
    assert not gate.locator('[data-ps-act="add"]').is_visible()  # a row's + adds instead
    gate.locator("[data-ps-row]").nth(1).locator('[data-ps-act="insert"]').click()
    added = gate.locator("[data-ps-row]").nth(2)
    assert added.locator('[data-ps="kind"]').evaluate("e => e === document.activeElement")
    assert added.locator("[data-ps-rank]").text_content() == "3"
    assert added.locator('[data-ps="panel"]').is_visible()
    assert not added.locator('[data-ps="question"]').is_visible()
    added.locator('[data-ps="kind"]').select_option("nominated")
    assert added.get_attribute("data-kind") == "nominated"
    assert added.locator('[data-ps="question"]').is_visible()
    assert not added.locator('[data-ps="panel"]').is_visible()
    assert gate.locator("[data-ps-bounds]").text_content() == "within 2–4"
    added.locator('[data-ps="min"]').fill("3")
    _checked(page)
    issues = page.locator("[data-pc-issues]").inner_text()
    assert "has source 3's min above its max." in issues
    assert "has its Total's min below the sources' mins together (4)." in issues
    added.locator('[data-ps="max"]').fill("x")
    _checked(page)
    assert (
        "needs a whole-number min and max for source 3."
        in page.locator("[data-pc-issues]").inner_text()
    )
    assert (
        gate.locator("[data-pi-panel]").text_content()
        == "Nominated 0–1 · Panel A 1–2 · Nominated 3–? · Total 2"
    )


def test_a_row_s_plus_adds_the_next_source_under_it(page: Page) -> None:
    """The author, 2026-11-17: + before × adds a source, no separate
    +Source while there are rows."""
    gate = _peer_copy(page)
    assert gate.locator("[data-ps-headrow]").is_visible()  # over the rows
    gate.locator("[data-ps-row]").first.locator('[data-ps-act="insert"]').click()
    assert _kinds(gate) == ["nominated", "panel", "panel"]
    assert gate.locator("[data-ps-rank]").all_inner_texts() == ["1", "2", "3"]
    added = gate.locator("[data-ps-row]").nth(1)
    assert added.locator('[data-ps="kind"]').evaluate("e => e === document.activeElement")
    assert added.locator('[data-ps="min"]').input_value() == "1"


def test_each_bound_is_named_where_the_header_row_is_not(page: Page) -> None:
    """Codex on rung 4a: the header row names the bounds over rows on a
    wide screen; without rows, the Total's own captions do; on a narrow
    screen, every bound's."""
    gate = _peer_copy(page)
    caps = gate.locator(".ps-cap")
    assert not any(caps.nth(i).is_visible() for i in range(caps.count()))
    for _ in range(2):
        gate.locator("[data-ps-row]").first.locator('[data-ps-act="remove"]').click()
    total = gate.locator("[data-ps-total] .ps-cap")
    assert total.all_inner_texts() == ["Min", "Max"] and total.first.is_visible()
    gate.locator('[data-ps-act="add"]').click()
    assert not total.first.is_visible()
    page.set_viewport_size({"width": 600, "height": 900})
    row = gate.locator("[data-ps-row]").first
    assert row.locator(".ps-cap").first.is_visible() and total.first.is_visible()


def test_the_assignment_mode_is_one_of_three(page: Page) -> None:
    """A plain menu, as the card's other settings (author, 2026-11-17)."""
    gate = _peer_copy(page)
    mode = gate.locator('[data-ps="mode"]')
    assert mode.locator("option").all_text_contents() == [
        "Automatic",
        "Suggested, then approved",
        "Assigned by the operator",
    ]
    assert mode.input_value() == "automatic"
    mode.select_option("suggested")
    assert gate.locator('[data-gsec="evaluators"] [data-gsec-sum]').text_content() == (
        "Nominated 0–1 · Panel A 1–2 · Total 2 · Suggested, then approved"
    )


def test_all_takes_the_whole_panel(page: Page) -> None:
    """Ruling 62: All on a panel source sets Min and Max to the panel's
    size and disables them; off, they are editable again; a Nominated
    source has no All."""
    gate = _peer_copy(page)
    rows = gate.locator("[data-ps-row]")
    nominated, panel = rows.nth(0), rows.nth(1)
    assert nominated.locator('[data-ps="all"]').is_hidden()
    whole = panel.locator('[data-ps="all"]')
    assert whole.get_attribute("aria-pressed") == "false"
    size = page.evaluate(
        "ref => window.applydeskPools[ref].members.length",
        panel.locator("[data-pc-panel]").input_value(),
    )
    whole.click()
    assert whole.get_attribute("aria-pressed") == "true"
    lo, hi = panel.locator('[data-ps="min"]'), panel.locator('[data-ps="max"]')
    assert lo.is_disabled() and hi.is_disabled()
    assert lo.input_value() == hi.input_value() == str(size)
    summary = gate.locator('[data-gsec="evaluators"] [data-gsec-sum]').text_content() or ""
    assert f"Panel A {size}" in summary, summary
    # Beside the Nominated source (0–1), the Total is the sources' bounds,
    # disabled (ruling 62, amended): the whole panel plus up to one.
    tlo, thi = gate.locator('[data-ps="total-min"]'), gate.locator('[data-ps="total-max"]')
    assert tlo.is_disabled() and thi.is_disabled()
    assert (tlo.input_value(), thi.input_value()) == (str(size), str(size + 1))
    whole.click()
    assert not lo.is_disabled() and not hi.is_disabled()
    assert not tlo.is_disabled() and not thi.is_disabled()


def test_a_nominated_source_shuts_the_new_panel_box(page: Page) -> None:
    """The cold read on rungs 2-4: the +New panel box is the panel
    menu's, so turning the source Nominated shuts it."""
    gate = _peer_copy(page)
    row = gate.locator("[data-ps-row]").nth(1)
    row.locator("[data-pc-panel]").select_option("__new")
    assert row.locator("[data-newpanel]").is_visible()
    row.locator('[data-ps="kind"]').select_option("nominated")
    assert not row.locator("[data-newpanel]").is_visible()


def test_an_item_left_alone_opens(page: Page) -> None:
    page.goto(PAGE)
    interview = _cards(page).nth(2)
    _open_all(interview)
    o2 = interview.locator('.pc-item[data-item="outcome"]')
    o2.locator("[data-pi-toggle]").click()  # shut it
    interview.locator('[data-pc-act="remove-gate"]').click()
    assert o2.get_attribute("data-open") == ""


# --- Segment AD1F rung 5c: a gate's results edited (ruling 21) ---
# Every gate in the model exercise is sent, so its results are fixed; the
# draft's selection gate is not.
DRAFT_PAGE = f"{ORIGIN}/applydesk/operator/exercises/c4xh2ndv6s/process"


def _draft_gate(page: Page) -> Locator:
    page.goto(DRAFT_PAGE)
    _open(_cards(page).nth(1))
    gate = page.locator('.pc-item[data-item="gate"]')
    _open_cards(gate)
    return gate


def _field(item: Locator, n: int) -> Locator:
    """A response field's row, its editor open (ruling 28)."""
    row = item.locator("[data-rf]").nth(n)
    if row.locator("[data-rf-ed]").is_hidden():
        row.locator("[data-rf-toggle]").click()
    return row


def _result(item: Locator, n: int) -> Locator:
    row = item.locator("[data-result]").nth(n)
    if row.locator("[data-pr-ed]").is_hidden():
        row.locator("[data-pr-toggle]").click()
    return row


def test_a_result_s_derivations_follow_its_field(page: Page) -> None:
    gate = _draft_gate(page)
    row = _result(gate, 0)
    fld = _field(gate, 0)
    derive = row.locator('[data-r="derive"]')
    assert derive.locator("option").all_text_contents() == [
        "Mean",
        "Median",
        "Lowest",
        "Highest",
        "Sum",
        "Count of responses",
    ]
    fld.locator('[data-q="type"]').select_option("list")
    assert derive.locator("option").all_text_contents() == [
        "Share choosing",
        "Most common",
        "Count of responses",  # any field's (author, 2026-11-14)
    ]
    fld.locator('[data-q="type"]').select_option("string")
    assert derive.locator("option").all_text_contents() == ["All, joined", "Count of responses"]
    derive.select_option("count")
    assert row.locator("[data-pr-type]").text_content() == "Integer, from 0"
    fld.locator('[data-q="type"]').select_option("list")
    assert derive.input_value() == "count"  # kept: the list allows it too
    derive.select_option("share")
    fld.locator('[data-q="options"]').fill("Yes, No")
    derive.select_option("share")
    row.locator('[data-r="value"]').select_option("Yes")
    row.locator('[data-r="at_least"]').fill("2")
    assert row.locator("[data-pr-sum]").text_content() == (
        "From Score · Share choosing Yes, from 2 or more → Decimal 0 to 100 (%)"
    )
    assert row.locator("[data-pr-type]").text_content() == "Decimal 0 to 100 (%)"
    row.locator('[data-r="name"]').fill("Recommend")
    assert row.locator("[data-pr-name]").text_content() == "Recommend"
    assert gate.locator("[data-result]").first.get_attribute("data-name") == "Recommend"
    assert gate.locator("[data-pr-rrw]").text_content() == (
        "For Review Robin, each evaluator answers: Score (List: Yes, No)."
    )


def test_a_field_is_set_as_a_scale_its_labels_and_problems_follow(page: Page) -> None:
    """Segment AD2S: Band 3's menu sets a scale, its labels show on a
    second line, a scale Review Robin would refuse is named on the
    Outline, and a List keeps neither the flag nor its labels."""
    gate = _draft_gate(page)
    fld = _field(gate, 0)
    scale_row = fld.locator('[data-q-g="scale"]')
    assert scale_row.is_hidden()
    fld.locator('[data-q="type"]').select_option("integer:scale")
    assert scale_row.is_visible() and fld.locator('[data-q-g="number"]').is_visible()
    fld.locator('[data-q="min"]').fill("1")
    fld.locator('[data-q="max"]').fill("5")
    fld.locator('[data-q="step"]').fill("1")
    fld.locator('[data-q="scale_start"]').fill("Weak")
    fld.locator('[data-q="scale_end"]').fill("Strong")
    # A "|" typed in a label is kept as "¦", as Band 3 keeps it, so the
    # labels never move along (the cumulative read).
    fld.locator('[data-q="scale_middle"]').fill("so|so")
    snap = page.evaluate("() => window.applydeskProcessSnapshot()")
    sent = next(g for s in snap["stages"] for g in s["gates"] if g["fields"])["fields"][0]
    assert sent["scale_labels"] == "Weak|so\u00a6so|Strong"
    fld.locator('[data-q="scale_middle"]').fill("")
    label = fld.locator('[data-q="label"]').input_value() or "f1"
    assert (fld.locator("[data-rf-sum]").text_content() or "").startswith(
        "Integer scale 1 to 5, step 1, labelled Weak / Strong · "
    )
    # A result reads the field as a number: its derivations are a number's.
    assert "Mean" in _result(gate, 0).locator('[data-r="derive"] option').all_text_contents()
    snap = page.evaluate("() => window.applydeskProcessSnapshot()")
    sent = next(g for s in snap["stages"] for g in s["gates"] if g["fields"])["fields"][0]
    assert (sent["type"], sent["scale"], sent["scale_labels"]) == ("integer", True, "Weak||Strong")
    fld.locator('[data-q="max"]').fill("6")
    fld.locator('[data-q="step"]').fill("2")
    _checked(page)
    issues = page.locator("[data-pc-issues]").inner_text()
    assert (
        f"field 1 ({label}) is a scale whose Max is not Min plus a whole number of Steps." in issues
    )
    fld.locator('[data-q="type"]').select_option("list")
    assert scale_row.is_hidden()
    snap = page.evaluate("() => window.applydeskProcessSnapshot()")
    sent = next(g for s in snap["stages"] for g in s["gates"] if g["fields"])["fields"][0]
    assert (sent["scale"], sent["scale_labels"]) == (False, "")
    _checked(page)
    assert "is a scale" not in page.locator("[data-pc-issues]").inner_text()


def test_results_are_added_to_three_and_removed(page: Page) -> None:
    gate = _draft_gate(page)
    add = gate.locator('[data-pr-act="add"]')
    add.click()
    new = gate.locator("[data-result]").nth(1)
    assert new.get_attribute("data-result") == "r2"
    assert new.locator('[data-r="name"]').evaluate("e => e === document.activeElement")
    assert new.locator("[data-pr-n]").text_content() == "2"
    add.click()
    assert gate.locator("[data-pi-results]").text_content() == "3 results"
    assert add.is_disabled() and add.get_attribute("title") == "A gate yields three results at most"
    _result(gate, 0).locator('[data-pr-act="remove"]').click()
    assert gate.locator("[data-pr-n]").all_text_contents() == ["1", "2"]
    assert add.is_enabled()


def test_every_gate_derives_its_results_in_review_robin(page: Page) -> None:
    """Ruling 28 retires Runs as and Entered here: a gate's results are
    derived, at least one response each, and Review Robin asks for them."""
    gate = _draft_gate(page)
    assert gate.locator('[data-pc="via"]').count() == 0
    row = _result(gate, 0)
    options = row.locator('[data-r="derive"] option').all_text_contents()
    assert "Entered here" not in options and options[0] == "Mean"
    assert row.locator('[data-r-g="atleast"]').is_visible()
    assert row.locator("[data-pr-sum]").text_content() == ("From Score · Mean → Decimal 0 to 10")
    assert gate.locator("[data-pr-rrw]").is_visible()


def test_a_sent_gate_keeps_its_results(page: Page) -> None:
    page.goto(PAGE)
    g1 = _item(page, "g1")
    assert g1.locator('[data-pr-act="add"]').is_disabled()
    assert g1.locator("[data-pr-ed]").first.evaluate("e => e.disabled")
    assert g1.locator('[data-pc="description"]').is_disabled()
    g3 = _item(page, "g3")  # ready, not sent: still the operator's to change
    assert not g3.locator('[data-pr-act="add"]').is_disabled()
    assert not g3.locator("[data-pr-ed]").first.evaluate("e => e.disabled")
    assert not g3.locator('[data-pc="description"]').is_disabled()
    assert _line(_item(page, "o2")).startswith("Score at Interview ≥ 4.0")


def test_the_script_s_result_summaries_match_the_server_s(page: Page) -> None:
    from applydesk.tests.test_pages import RESULT_CASES

    gate = _draft_gate(page)
    row = _result(gate, 0)
    fld = _field(gate, 0)
    for r, _ in RESULT_CASES:
        f = r.field
        fld.locator('[data-q="type"]').select_option(f.type)
        if f.type in ("integer", "decimal"):
            for k in ("min", "max", "step"):
                fld.locator(f'[data-q="{k}"]').fill(getattr(f, k))
        elif f.type == "string":
            fld.locator('[data-q="maxlen"]').fill(f.max)
        else:
            fld.locator('[data-q="options"]').fill(f.options)
        row.locator('[data-r="derive"]').select_option(r.derive)
        if r.derive == "share":
            # None chosen: the menu's first option, as the server words it.
            row.locator('[data-r="value"]').select_option(
                r.value or f.options.split(",")[0].strip()
            )
        row.locator('[data-r="at_least"]').fill(str(r.at_least))
        if r.derive in stages.ZERO_DERIVATIONS:
            row.locator('[data-r="ignore_zero"]').set_checked(r.ignore_zero)
        else:  # offered only for a mean or a median (ruling 30)
            assert row.locator('[data-r-g="zero"]').is_hidden()
        # The whole line as the server draws it for a result reading this
        # field (stages.collated; Score, the draft's field, renamed by none).
        server = f"From Score · {stages.derivation_text(r)} → {stages.result_type(r)}"
        assert row.locator("[data-pr-sum]").text_content() == server, r


# --- The 5b-5c cold read ---
def test_a_replica_of_a_sent_stage_s_results_are_its_own_to_set(page: Page) -> None:
    page.goto(PAGE)
    review = _cards(page).nth(1)
    _open(review)
    review.locator('[data-fc-act="replicate"]').click()
    gate = _cards(page).nth(2).locator('.pc-item[data-item="gate"]').first
    assert gate.locator('[data-pc="description"]').is_enabled()
    assert gate.locator('[data-pc="confidential"]').is_enabled()
    assert gate.locator('[data-pr-act="add"]').is_enabled()
    assert not gate.locator("[data-pr-ed]").first.evaluate("e => e.disabled")
    assert gate.locator('[data-rf-act="add"]').is_enabled()  # its fields too (ruling 28)
    assert not gate.locator("[data-rf-ed]").first.evaluate("e => e.disabled")


def test_a_removed_result_s_key_is_not_reused(page: Page) -> None:
    gate = _draft_gate(page)
    add = gate.locator('[data-pr-act="add"]')
    add.click()
    _result(gate, 1).locator('[data-pr-act="remove"]').click()
    add.click()
    assert gate.locator("[data-result]").evaluate_all("els => els.map(e => e.dataset.result)") == [
        "r1",
        "r3",
    ]


def test_a_share_keeps_its_option_while_the_options_are_retyped(page: Page) -> None:
    gate = _draft_gate(page)
    row = _result(gate, 0)
    fld = _field(gate, 0)
    fld.locator('[data-q="type"]').select_option("list")
    fld.locator('[data-q="options"]').fill("Yes, No")
    row.locator('[data-r="derive"]').select_option("share")
    row.locator('[data-r="value"]').select_option("No")
    fld.locator('[data-q="options"]').fill("Yes, N")
    fld.locator('[data-q="options"]').fill("Yes, No")
    assert row.locator('[data-r="value"]').input_value() == "No"


def test_a_replica_keeps_three_results_at_most(page: Page) -> None:
    """Codex on #3885: a copy of a gate with three results took a fourth."""
    gate = _draft_gate(page)
    gate.locator('[data-pr-act="add"]').click()
    gate.locator('[data-pr-act="add"]').click()
    _cards(page).nth(1).locator('[data-fc-act="replicate"]').click()
    copy = _cards(page).nth(2).locator('.pc-item[data-item="gate"]')
    add = copy.locator('[data-pr-act="add"]')
    assert add.is_disabled() and add.get_attribute("title") == "A gate yields three results at most"
    assert copy.locator("[data-result]").count() == 3


# --- Segment AD1F rung 5d: rules read a named result (ruling 21) ---
def test_a_rule_matches_a_list_result_and_names_one_it_cannot_read(page: Page) -> None:
    page.goto(PAGE)
    review = _cards(page).nth(1)
    _open(review)
    review.locator('[data-pc-act="gate"]').click()
    gate = review.locator('.pc-item[data-item="gate"]').nth(2)
    gate.locator('[data-pc="item-name"]').fill("Vote")
    row = gate.locator("[data-result]").first
    if row.locator("[data-pr-ed]").is_hidden():
        row.locator("[data-pr-toggle]").click()
    fld = _field(gate, 0)
    row.locator('[data-r="name"]').fill("Verdict")
    fld.locator('[data-q="type"]').select_option("list")
    fld.locator('[data-q="options"]').fill("Yes, No")
    row.locator('[data-r="derive"]').select_option("mode")
    o1 = _item(page, "o1")
    o1.locator('[data-pc-act="rule"]').click()
    first = o1.locator(".pc-cond").first
    first.locator("select").first.select_option("res")
    first.locator('select[aria-label="Result"]').select_option(label="Verdict at Vote")
    assert first.locator('select[aria-label="Comparison"] option').all_text_contents() == ["is"]
    first.locator('select[aria-label="Value"]').select_option("No")
    assert _line(o1).startswith("Verdict at Vote is No")
    # Turned into a string, it can no longer be read: the rule says so.
    fld.locator('[data-q="type"]').select_option("string")
    _checked(page)
    assert "reads Verdict at Vote, which a rule cannot compare" in (
        o1.locator("[data-rule-warn]").inner_text()
    )


def test_a_new_gate_s_first_result_is_numbered(page: Page) -> None:
    page.goto(PAGE)
    review = _cards(page).nth(1)
    _open(review)
    review.locator('[data-pc-act="gate"]').click()
    gate = review.locator('.pc-item[data-item="gate"]').nth(2)
    assert gate.locator("[data-pr-n]").all_text_contents() == ["1"]


# --- Segment AD1G rung 4c: the gate card (ruling 28) ---


def test_a_gate_s_cards_start_shut_and_say_what_they_hold(page: Page) -> None:
    page.goto(PAGE)
    g1 = page.locator('.pc-item[data-key="g1"]')
    _open(g1.locator("xpath=ancestor::article[1]"))
    if g1.get_attribute("data-open") is None:
        g1.locator("[data-pi-toggle]").click()
    cards = g1.locator("details.gsec")
    assert cards.evaluate_all("els => els.map(e => e.open)") == [False, False]
    assert g1.locator('[data-gsec="evaluators"] [data-gsec-sum]').is_visible()
    assert not g1.locator('[data-pc="item-name"]').is_visible()
    g1.locator('[data-gsec="gate"] > summary').click()
    assert g1.locator('[data-pc="item-name"]').is_visible()
    assert not g1.locator('[data-gsec="gate"] [data-gsec-sum]').is_visible()
    # Response fields and Results stand outside the cards, always shown.
    assert g1.locator("[data-rf]").count() == 2 and g1.locator("[data-result]").count() == 2


def test_a_new_gate_and_an_outline_jump_open_the_gate_card(page: Page) -> None:
    page.goto(PAGE)
    review = _cards(page).nth(1)
    _open(review)
    review.locator('[data-pc-act="gate"]').click()
    new = review.locator('.pc-item[data-item="gate"]').nth(2)
    assert new.locator('[data-gsec="gate"]').evaluate("e => e.open")
    assert new.locator('[data-pc="item-name"]').evaluate("e => e === document.activeElement")
    page.locator("[data-pc-outline] .fb-o-item", has_text="Gate 4 · Interview").click()
    g3 = page.locator('.pc-item[data-key="g3"]')
    assert g3.locator('[data-gsec="gate"]').evaluate("e => e.open")
    assert g3.locator('[data-pc="item-name"]').evaluate("e => e === document.activeElement")


# --- Segment AD1G rung 4d: the gate card wired (ruling 28) ---


def test_response_fields_are_added_edited_and_removed(page: Page) -> None:
    gate = _draft_gate(page)
    gate.locator('[data-rf-act="add"]').click()
    new = gate.locator("[data-rf]").nth(1)
    assert new.get_attribute("data-rf") == "f2"
    assert new.locator("[data-rf-key]").input_value() == "f2"  # read-only, prescribed
    assert new.locator("[data-rf-key]").get_attribute("readonly") is not None
    assert new.locator('[data-q="label"]').evaluate("e => e === document.activeElement")
    new.locator('[data-q="label"]').fill("Fit")
    new.locator('[data-q="type"]').select_option("list")
    new.locator('[data-q="options"]').fill("Strong, Weak")
    new.locator('[data-q="required"]').check()
    new.locator('[data-q="help"]').fill("Fit to the programme")
    assert new.locator("[data-rf-sum]").text_content() == (
        "List: Strong, Weak · Required · Help: Fit to the programme"
    )
    assert gate.locator("[data-pr-rrw]").text_content() == (
        "For Review Robin, each evaluator answers: Score (Decimal 0 to 10, step 0.5);"
        " Fit (List: Strong, Weak, required; help: “Fit to the programme”)."
    )
    assert page.locator("[data-unsaved]").is_visible()
    # A result chooses the field it collates; its derivations follow it.
    row = _result(gate, 0)
    source = row.locator('[data-r="source"]')
    assert source.locator("option").all_text_contents() == ["Choose a field", "Score", "Fit"]
    source.select_option("f2")
    assert row.locator('[data-r="derive"] option').all_text_contents()[0] == "Share choosing"
    assert (row.locator("[data-pr-sum]").text_content() or "").startswith(
        "From Fit · Share choosing Strong"
    )
    # The field gone, the result has none, and the Outline says so.
    new.locator('[data-rf-act="remove"]').click()
    assert source.input_value() == ""
    assert row.locator("[data-pr-sum]").text_content() == "No field chosen"
    # With no field, nothing to derive and no type a rule could read.
    assert row.locator('[data-r="derive"] option').count() == 0
    assert row.locator("[data-pr-type]").text_content() == "None until a field is chosen"
    _checked(page)
    assert "Gate 1 · Placement interview has result 1 with no field chosen." in (
        page.locator("[data-pc-issues]").inner_text()
    )
    assert gate.locator('[data-rf-act="add"]').evaluate("e => e === document.activeElement")


def test_the_shut_cards_lines_follow_edits(page: Page) -> None:
    gate = _draft_gate(page)
    line = gate.locator('[data-gsec="gate"] [data-gsec-sum]')
    # As the server's stages.gate_summary: the draft's gate has no rule yet.
    assert line.text_content() == "Review Robin Session · Entry decided by hand"
    gate.locator('[data-pc="confidential"]').check()
    assert line.text_content() == "Review Robin Session · Confidential · Entry decided by hand"
    # Segment 23G: the type is the gate's to choose, and the line follows.
    gate.locator('[data-pc="type"]').select_option("RRW-custom")
    assert line.text_content() == (
        "Review Robin Session (custom) · Confidential · Entry decided by hand"
    )
    who = gate.locator('[data-gsec="evaluators"] [data-gsec-sum]')
    assert who.text_content() == "No evaluators · Automatic"
    gate.locator('[data-ps="mode"]').select_option("assigned")
    assert who.text_content() == "No evaluators · Assigned by the operator"


def test_the_shut_gate_line_follows_its_rule(page: Page) -> None:
    """The cold read on 4c-4d: a rule cleared shows on the shut card at
    once, not at the next unrelated edit."""
    gate = _peer_copy(page)
    line = gate.locator('[data-gsec="gate"] [data-gsec-sum]')
    kind = "Review Robin Session"  # the peer review, as copied
    assert line.text_content() == kind + " · Enters: " + _line(gate)
    gate.locator('[data-pc-act="rule"]').click()
    gate.locator('[data-rule-part="clear"]').click()
    assert _line(gate) == "Decided by hand"
    assert line.text_content() == kind + " · Entry decided by hand"


def test_a_sent_gate_keeps_its_fields(page: Page) -> None:
    page.goto(PAGE)
    g1 = _item(page, "g1")
    assert g1.locator('[data-rf-act="add"]').is_disabled()
    assert g1.locator("[data-rf-ed]").first.evaluate("e => e.disabled")
    g3 = _item(page, "g3")  # ready, not sent
    assert not g3.locator('[data-rf-act="add"]').is_disabled()
    assert not g3.locator("[data-rf-ed]").first.evaluate("e => e.disabled")


def test_a_new_gate_s_field_shows_only_its_type_s_settings(page: Page) -> None:
    """Codex on #3950: a gate added in the browser drew its results but not
    its fields, so its Integer field showed Max length and Options too."""
    page.goto(PAGE)
    review = _cards(page).nth(1)
    _open(review)
    review.locator('[data-pc-act="gate"]').click()
    new = review.locator('.pc-item[data-item="gate"]').nth(2)
    fld = _field(new, 0)
    assert fld.locator('[data-q-g="number"]').is_visible()
    assert not fld.locator('[data-q-g="string"]').is_visible()
    assert not fld.locator('[data-q-g="list"]').is_visible()
    assert fld.locator("[data-rf-n]").text_content() == "1"


def test_a_gate_s_description_grows_with_its_text(page: Page) -> None:
    """The author, 2026-11-17: no resize handle; the box fits its text,
    as Review Robin's instrument boxes do."""
    page.goto(PAGE)
    g1 = _item(page, "g1")
    box = g1.locator('[data-pc="description"]')
    assert box.evaluate("e => getComputedStyle(e).resize") == "none"
    fits = "e => Math.abs(e.clientHeight - e.scrollHeight) <= 1"
    assert box.evaluate(fits)  # fitted when its card opened
    before = box.evaluate("e => e.offsetHeight")
    gate = _peer_copy(page)
    box = gate.locator('[data-pc="description"]')
    box.fill("A line. " * 60)
    assert box.evaluate("e => e.offsetHeight") > before and box.evaluate(fits)


# --- Segment AD1H rung 6: the model exercise's own process (ruling 30) ---
def test_the_model_exercise_s_branched_rules_draw_as_the_server_does(page: Page) -> None:
    """The RA recruitment's rules branch and read a form answer and the
    best N: the script's lines are the server's, and none is a problem."""
    page.goto(MODEL)
    served = page.evaluate(
        """async () => {
          const html = await (await fetch(location.href)).text();
          const doc = new DOMParser().parseFromString(html, "text/html");
          return [...doc.querySelectorAll("#pc-cards [data-rule-line]")].map(e => e.textContent);
        }"""
    )
    shown = page.locator("#pc-cards [data-rule-line]").all_text_contents()
    assert shown == served and len(shown) == 5
    assert any("Currently an RA? is Yes" in line for line in shown)
    assert any("the best 20 by Interview score at Staff interview" in line for line in shown)
    # Weights all 0 are no combined result, which its rule does not read.
    _checked(page)
    assert not page.locator("[data-pc-issues]").is_visible()
    o1 = _item(page, "o1")
    _revert(o1.locator("xpath=ancestor::article[@data-kind='stage']"))
    _checked(page)
    assert not o1.locator("[data-rule-warn]").is_visible()
    o1.locator('[data-pc-act="rule"]').click()
    assert o1.locator(".pc-branch").count() == 2
    # A rule reading the combined result, with no weights, is named.
    o1.locator(".pc-cond select").first.select_option("comb")
    _checked(page)
    assert "This outcome has weights adding up to 0, not 100." in (
        o1.locator("[data-rule-warn]").inner_text()
    )


def test_the_model_exercise_s_review_is_fixed_and_its_interview_open(page: Page) -> None:
    page.goto(MODEL)
    g1 = _item(page, "g1")
    assert g1.locator("[data-pc-sent]").inner_text() == (
        "Its Review Robin session has opened: its settings are fixed here."
    )
    assert g1.locator('[data-r="ignore_zero"]').first.is_checked()
    assert g1.locator("[data-pr-ed]").first.evaluate("e => e.disabled")
    g3 = _item(page, "g3")
    assert g3.locator("[data-pc-sent]").count() == 0
    assert g3.locator('[data-ps="mode"]').input_value() == "suggested"
    # Not opened: fixed only by its published stage, and a revert frees it.
    assert g3.locator('[data-ps="mode"]').is_disabled()
    _revert(g3.locator("xpath=ancestor::article[@data-kind='stage']"))
    assert not g3.locator('[data-ps="mode"]').is_disabled()


# --- AD1G rungs 8-9 (carried, author 2026-11-17): what will be sent ---


def test_what_will_be_sent_follows_the_gate_and_its_stage(page: Page) -> None:
    """The line names the instrument, its stage's window in the
    exercise's timezone, the help contact and the tag, and follows the
    name, the description and the stage's dates, each on its own."""
    gate = _draft_gate(page)
    send = gate.locator("[data-pr-send]")
    assert "open when its stage's dates are set (Asia/Singapore)" in (send.text_content() or "")
    gate.locator('[data-pc="item-name"]').fill("Placement chat")
    assert (send.text_content() or "").startswith("Review Robin receives Placement chat, open")
    gate.locator('[data-pc="description"]').fill("Talk about the placement...")
    assert (send.text_content() or "").startswith(
        "Review Robin receives Placement chat: Talk about the placement, open"
    )
    stage = gate.locator("xpath=ancestor::article[@data-kind='stage']")
    stage.locator('[data-pc="from"]').fill("2027-03-01T00:00")
    stage.locator('[data-pc="to"]').fill("2027-03-15T23:59")
    assert send.text_content() == (
        "Review Robin receives Placement chat: Talk about the placement, open 1–15 Mar 2027"
        " (Asia/Singapore); help contact applydesk-help@example.edu; tagged applydesk."
    )


def test_what_was_sent_stays_once_the_session_opens(page: Page) -> None:
    """A gate whose session has opened keeps its line, though its stage's
    dates are still edited."""
    page.goto(MODEL)
    gate = page.locator('.pc-item[data-key="g1"]')
    send = gate.locator("[data-pr-send]")
    before = send.text_content()
    stage = gate.locator("xpath=ancestor::article[@data-kind='stage']")
    _open(stage)
    stage.locator('[data-pc="to"]').fill("2026-11-07T23:59")  # an extension
    assert send.text_content() == before and "open 1–31 Oct 2026" in (before or "")


def test_a_replica_of_an_opened_gate_follows_its_own_settings(page: Page) -> None:
    """Codex on #3963: the copy is unsent, so its line is not frozen."""
    page.goto(MODEL)
    stage = page.locator('.pc-item[data-key="g1"]').locator(
        "xpath=ancestor::article[@data-kind='stage']"
    )
    _open(stage)
    stage.locator('[data-fc-act="replicate"]').click()
    # A copy goes after the last published stage, so none falls behind it.
    copy = _cards(page).last
    gate = copy.locator('.pc-item[data-item="gate"]').first
    send = gate.locator("[data-pr-send]")
    assert send.get_attribute("data-fixed") is None
    _open(copy)
    _open_item(gate)
    gate.locator('[data-pc="item-from"]').fill("2026-10-02T00:00")
    assert "open 2–31 Oct 2026" in (send.text_content() or "")


def test_dates_are_date_times_and_an_item_s_window_follows(page: Page) -> None:
    """Segment AD1K (author, 2026-11-18): a stage's and its items' dates
    are date-time inputs; a gate's send line reads its own window, or its
    stage's while its own is blank."""
    page.goto(MODEL)
    stage = _cards(page).nth(2)
    _open_all(stage)
    assert stage.locator('[data-pc="from"]').input_value() == "2026-11-09T00:00"
    assert stage.locator('[data-pc="to"]').input_value() == "2026-12-04T23:59"
    gate = stage.locator('.pc-item[data-key="g3"]')
    assert gate.locator('[data-pc="item-to"]').input_value() == "2026-12-02T23:59"
    due = stage.locator('.pc-item[data-key="o2"] [data-pc="due"]')
    assert due.input_value() == "2026-12-04T17:00"
    send = gate.locator("[data-pr-send]")
    assert "open 9 Nov – 2 Dec 2026" in (send.text_content() or "")
    _revert(stage)  # its start, and its gate's, are fixed while published
    gate.locator('[data-pc="item-from"]').fill("")
    gate.locator('[data-pc="item-to"]').fill("")
    stage.locator('[data-pc="to"]').fill("2026-12-11T23:59")
    assert "open 9 Nov – 11 Dec 2026" in (send.text_content() or "")
    assert stage.locator('[data-sum="dates"]').inner_text() == "9 Nov – 11 Dec 2026"


# --- Segment AD1K rung 3b: a stage's status, publish, revert and locks ---


def test_a_published_stage_says_its_status_and_fixes_what_it_holds(page: Page) -> None:
    """Ruling 35: the model's stages are Completed, Completed, Published;
    a published stage's name, start and items are fixed, saying why, and
    its end stays editable, to extend it."""
    page.goto(MODEL)
    assert page.locator("[data-pc-status]").all_text_contents() == [
        "Completed",
        "Completed",
        "Published",
    ]
    interviews = _cards(page).nth(2)
    _open_all(interviews)
    name = interviews.locator('[data-pc="name"]')
    assert name.is_disabled()
    assert name.get_attribute("title") == (
        "Interviews is published: revert it to draft to change this"
    )
    assert interviews.locator('[data-pc="from"]').is_disabled()
    assert interviews.locator('[data-pc="shown"]').is_disabled()  # author, 2026-11-18
    assert interviews.locator('[data-pc="to"]').is_enabled()
    assert interviews.locator('[data-fc-act="delete"]').is_disabled()
    assert interviews.locator('.pc-adds [data-pc-act="gate"]').is_disabled()
    o2 = interviews.locator('.pc-item[data-key="o2"]')
    assert o2.locator('[data-pc="item-name"]').is_disabled()
    assert o2.locator('[data-pc="due"]').is_enabled()  # its end too
    assert interviews.locator("[data-pc-locked-note]").is_visible()
    assert not interviews.locator('[data-pc-st="publish"]').is_visible()


def test_a_revert_needs_a_reason_and_leaves_an_opened_gate_fixed(page: Page) -> None:
    """Author, 2026-11-18: a revert is allowed after a gate has opened;
    the gate stays fixed, and the confirm says so."""
    page.goto(MODEL)
    review = _cards(page).nth(1)
    _open_all(review)
    revert = review.locator('[data-pc-st="revert"]')
    assert revert.is_disabled()  # Interviews, after it, is published
    assert revert.get_attribute("title") == "Revert Interviews first: it comes after this stage"
    _revert(_cards(page).nth(2))
    revert.click()
    panel = review.locator("[data-pc-revert]")
    assert "Gate 1's Review Robin session has opened: it stays fixed." in panel.inner_text()
    confirm = review.locator('[data-pc-st="confirm"]')
    assert confirm.is_disabled()
    review.locator("[data-pc-reason]").fill("Shortlisting rule was wrong")
    confirm.click()
    assert review.locator("[data-pc-status]").text_content() == "Draft"
    assert review.locator('[data-pc="name"]').is_enabled()
    assert review.locator('[data-pc-st="publish"]').is_visible()
    g1 = review.locator('.pc-item[data-key="g1"]')
    assert g1.locator('[data-pc="item-name"]').is_disabled()  # opened: stays fixed
    o1 = review.locator('.pc-item[data-key="o1"]')
    assert o1.locator('[data-pc="item-name"]').is_enabled()
    assert "reverted to draft: saved, with its reason, when Process is saved" in (
        page.locator("[data-pc-live]").text_content() or ""
    )


def test_publishing_waits_on_the_stage_before_and_names_problems(page: Page) -> None:
    """AD-20: Publish lists what a stage lacks; the stage before it being
    published on the page lifts that line."""
    page.goto(PAGE)
    first, review = _cards(page).nth(0), _cards(page).nth(1)
    _open(first)
    _open(review)
    publish = review.locator('[data-pc-st="publish"]')
    assert publish.is_disabled()
    assert (
        review.locator("[data-pc-problems]")
        .inner_text()
        .endswith("Call for applications is not published yet.")
    )
    first.locator('[data-pc-st="publish"]').click()
    # Its end has passed and its form is still open: published, overdue.
    assert first.locator("[data-pc-status]").text_content() == "Overdue"
    assert (
        first.locator("[data-pc-overdue]")
        .inner_text()
        .startswith("Overdue: the form is still open.")
    )
    assert first.locator('[data-pc="name"]').is_disabled()
    assert publish.is_enabled()
    assert not review.locator("[data-pc-problems]").is_visible()
    publish.click()
    # Its end has passed with its gates' results in and its outcome
    # released: complete as soon as it is published.
    assert review.locator("[data-pc-status]").text_content() == "Completed"


def test_a_copy_of_a_published_stage_is_a_draft(page: Page) -> None:
    page.goto(MODEL)
    interviews = _cards(page).nth(2)
    _open(interviews)
    interviews.locator('[data-fc-act="replicate"]').click()
    copy = _cards(page).nth(3)
    assert copy.locator("[data-pc-status]").text_content() == "Draft"
    assert copy.locator('[data-pc="name"]').is_enabled()
    assert copy.locator('[data-pc-st="publish"]').is_disabled()  # checked once saved
    _open_all(copy)
    assert copy.locator('.pc-item[data-item="outcome"] [data-pc="item-name"]').is_enabled()


def test_a_revert_before_a_published_stage_blocks_its_republishing(page: Page) -> None:
    """Codex: revert Interviews, then Review: Interviews may not be
    published again while Review is a draft."""
    page.goto(MODEL)
    review, interviews = _cards(page).nth(1), _cards(page).nth(2)
    _revert(interviews)
    publish = interviews.locator('[data-pc-st="publish"]')
    assert publish.is_enabled()
    _revert(review)
    assert publish.is_disabled()
    assert (
        interviews.locator("[data-pc-problems]")
        .inner_text()
        .endswith("Review is not published yet.")
    )


def test_an_extension_reopens_a_completed_stage(page: Page) -> None:
    """Codex, and the author's ruling: moving a Completed stage's end past
    now makes it Published again; moving it back completes it."""
    page.goto(MODEL)
    review = _cards(page).nth(1)
    _open(review)
    chip = review.locator("[data-pc-status]")
    assert chip.text_content() == "Completed"
    end = review.locator('[data-pc="to"]')
    end.fill("2026-11-20T23:59")
    assert chip.text_content() == "Published"
    end.fill("2026-11-06T23:59")
    assert chip.text_content() == "Completed"


def test_published_stages_keep_their_order_and_start(page: Page) -> None:
    """AD1K cold read: a new stage or a copy goes after the published
    ones and cannot move above them; a published item's start is fixed,
    its end not."""
    page.goto(MODEL)
    first = _cards(page).nth(0)
    _open(first)
    first.locator('[data-fc-act="new"]').click()
    new = _cards(page).nth(3)
    assert new.get_attribute("data-status") == "Draft"
    new.locator("[data-fc-grip]").press("ArrowUp")
    assert _cards(page).nth(3).get_attribute("data-status") == "Draft"  # stayed last
    interviews = _cards(page).nth(2)
    _open_all(interviews)
    g3 = interviews.locator('.pc-item[data-key="g3"]')
    assert g3.locator('[data-pc="item-from"]').is_disabled()
    assert g3.locator('[data-pc="item-to"]').is_enabled()
    g1 = _cards(page).nth(1).locator('.pc-item[data-key="g1"]')
    assert g1.locator('[data-pc="item-from"]').is_disabled()


def test_publish_checks_the_dates_as_they_stand(page: Page) -> None:
    """AD1K cold read: a reverted stage whose end is cleared may not be
    published again until it has one."""
    page.goto(MODEL)
    interviews = _cards(page).nth(2)
    _revert(interviews)
    publish = interviews.locator('[data-pc-st="publish"]')
    assert publish.is_enabled()
    interviews.locator('[data-pc="to"]').fill("")
    assert publish.is_disabled()
    assert (
        "Interviews has no start and end." in interviews.locator("[data-pc-problems]").inner_text()
    )


def test_publish_marks_the_page_unsaved(page: Page) -> None:
    """Codex: publishing, the first change on the page, shows Unsaved
    changes and asks before leaving."""
    page.goto(PAGE)
    first = _cards(page).nth(0)
    _open(first)
    mark = page.locator("[data-unsaved]")
    assert not mark.is_visible()
    first.locator('[data-pc-st="publish"]').click()
    assert mark.is_visible()


def test_an_open_revert_shuts_when_a_later_stage_is_published(page: Page) -> None:
    """Codex: an open revert panel cannot leave a draft before a stage
    published since it opened."""
    page.goto(MODEL)
    review, interviews = _cards(page).nth(1), _cards(page).nth(2)
    _revert(interviews)
    _open(review)
    review.locator('[data-pc-st="revert"]').click()
    review.locator("[data-pc-reason]").fill("A change of mind")
    interviews.locator('[data-pc-st="publish"]').click()
    assert not review.locator("[data-pc-revert]").is_visible()
    assert review.locator('[data-pc-st="revert"]').is_disabled()
    assert review.locator("[data-pc-status]").text_content() == "Completed"


def test_an_edit_undone_before_its_check_leaves_no_stale_warning(page: Page) -> None:
    """Codex on #4156: an edit undone within the check's 250 ms is not
    checked, so its warning is never drawn on the page as restored."""
    page.goto(PAGE)
    _checked(page)
    o1 = _item(page, "o1")
    o1.locator('[data-pc-act="rule"]').click()
    first = o1.locator('[data-pc="value"]').first
    was = first.input_value()
    first.fill("")  # its rule now decides a value it no longer has
    first.fill(was)  # undone at once
    page.wait_for_timeout(600)
    _checked(page)
    assert o1.locator("[data-rule-warn]").is_hidden()


def test_a_renamed_value_carries_its_rules(page: Page) -> None:
    """AD-57: renaming a value rewrites the rules naming it, its own
    decisions and later rules reading the outcome, so nothing is flagged."""
    page.goto(PAGE)
    _checked(page)
    o1 = _item(page, "o1")
    first = o1.locator('[data-pc="value"]').first
    assert first.input_value() == "Shortlisted"
    first.fill("Invited")
    assert "Shortlisted" not in json.dumps(_rule(o1))
    assert "Invited" in json.dumps(_rule(o1))
    g3 = _item(page, "g3")
    assert "Invited" in json.dumps(_rule(g3)) and "Shortlisted" not in json.dumps(_rule(g3))
    page.wait_for_timeout(400)
    _checked(page)
    assert o1.locator("[data-rule-warn]").is_hidden()
    assert g3.locator("[data-rule-warn]").is_hidden()


def test_values_are_added_and_removed_as_rows(page: Page) -> None:
    page.goto(PAGE)
    o1 = _item(page, "o1")
    was = _values(o1)
    o1.locator('[data-pc-act="add-value"]').click()
    o1.locator('[data-pc="value"]').last.fill("Waitlisted")
    assert _values(o1) == [*was, "Waitlisted"]
    assert page.locator("[data-unsaved]").is_visible()
    snap = page.evaluate("() => window.applydeskProcessSnapshot()")
    outcome = next(s["outcome"] for s in snap["stages"] if (s["outcome"] or {}).get("key") == "o1")
    assert outcome["values"] == [*was, "Waitlisted"]
    # A sample's values carry no keys until saved; one added here has none.
    assert len(outcome["value_keys"]) == len(was) + 1 and outcome["value_keys"][-1] == ""
    o1.locator('[data-pc-act="remove-value"]').last.click()
    assert _values(o1) == was


def test_a_value_typed_through_another_s_label_keeps_both_rules(page: Page) -> None:
    """The cold read on rungs 7-10: a value renamed through a sibling's label
    (or a swap half-done) does not take the sibling's rules with it."""
    page.goto(PAGE)
    o1 = _item(page, "o1")
    first, second = _values(o1)[:2]
    before = json.dumps(_rule(o1))
    assert first in before
    row = o1.locator('[data-pc="value"]').nth(1)
    row.fill(first)  # now the same as the first value: ambiguous, not applied
    row.fill("Held")
    after = json.dumps(_rule(o1))
    assert first in after  # the first value's rules stay its own
    assert second not in after and "Held" in after


def test_swapping_two_values_swaps_their_rules(page: Page) -> None:
    """Codex on #4161: two labels swapped (each typed into the other's row)
    carry each value's rules with it, once the labels are distinct again."""
    page.goto(PAGE)
    o1 = _item(page, "o1")
    first, second = _values(o1)[:2]
    rule = {"when": [["status", "", "is", "Submitted"]], "then": first, "otherwise": second}
    o1.evaluate("(e, r) => { e.dataset.rule = JSON.stringify(r); }", rule)
    rows = o1.locator('[data-pc="value"]')
    rows.nth(0).fill(second)  # alike for now: nothing moves
    assert cast(dict[str, Any], _rule(o1))["then"] == first
    rows.nth(1).fill(first)  # distinct again: both renames apply together
    got = cast(dict[str, Any], _rule(o1))
    assert got["then"] == second and got["otherwise"] == first


def test_swapping_two_values_through_a_blank_row_swaps_their_rules(page: Page) -> None:
    """Codex on #4161: a swap made by clearing one row first waits for the
    blank row too, so the two renames apply together."""
    page.goto(PAGE)
    o1 = _item(page, "o1")
    first, second = _values(o1)[:2]
    rule = {"when": [["status", "", "is", "Submitted"]], "then": first, "otherwise": second}
    o1.evaluate("(e, r) => { e.dataset.rule = JSON.stringify(r); }", rule)
    rows = o1.locator('[data-pc="value"]')
    rows.nth(0).fill("")
    rows.nth(1).fill(first)  # the first row blank: nothing moves yet
    assert cast(dict[str, Any], _rule(o1)) == rule
    rows.nth(0).fill(second)
    got = cast(dict[str, Any], _rule(o1))
    assert got["then"] == second and got["otherwise"] == first


def test_the_type_menu_shows_its_whole_choice(page: Page) -> None:
    """Segment 23G (author, 2026-11-25): the Type menu is as wide as
    *Review Robin Session (custom)*, the Name beside it taking the rest."""
    page.goto(MODEL)
    review = _cards(page).nth(1)
    _open(review)
    gate = review.locator('.pc-item[data-item="gate"]').first
    _open_item(gate)
    menu = gate.locator('[data-pc="type"]')
    assert menu.evaluate("s => s.options[s.selectedIndex].text") == "Review Robin Session (custom)"
    # The text's own width, in the menu's font, fits inside the menu with
    # its padding and arrow.
    room, text = menu.evaluate(
        """s => {
          const probe = document.createElement("span");
          probe.style.font = getComputedStyle(s).font;
          probe.style.whiteSpace = "pre";
          probe.textContent = s.options[s.selectedIndex].text;
          document.body.append(probe);
          const w = probe.getBoundingClientRect().width;
          probe.remove();
          const cs = getComputedStyle(s);
          return [s.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight), w];
        }"""
    )
    assert room >= text, (room, text)
    name = gate.locator('[data-pc="item-name"]').bounding_box()
    box = menu.bounding_box()
    assert name and box and name["width"] > box["width"]


def test_removing_a_set_up_gate_asks_first(page: Page) -> None:
    """Segment 23J (ruling 80): a gate set up in Review Robin, its rosters
    not sent, has an empty draft there, which removing it discards: the
    page asks first, and a No keeps the gate."""
    gate = _draft_gate(page)
    key = gate.get_attribute("data-key")
    assert key
    page.evaluate(
        """key => {
          const ex = document.querySelector('[data-process]').dataset.ex;
          sessionStorage.setItem('applydesk-rr-setup:' + ex,
            JSON.stringify({[key]: {at: 'x', transfer: 't', url: 'u'}}));
        }""",
        key,
    )
    asked: list[str] = []

    def answer(dialog: Dialog) -> None:
        asked.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", answer)
    gate.locator('[data-pc-act="remove-gate"]').click()
    assert asked and "set up in Review Robin" in asked[0]
    assert page.locator(f'.pc-item[data-item="gate"][data-key="{key}"]').count() == 1


def _rr_boxes(page: Page) -> dict[str, Locator]:
    """Each saved gate's Create Review Robin session box, by gate key."""
    found: dict[str, Locator] = {}
    gates = page.locator('.pc-item[data-item="gate"]')
    for i in range(gates.count()):
        key = gates.nth(i).get_attribute("data-key") or ""
        if key:
            found[key] = gates.nth(i).locator("[data-pc-rr-box]")
    return found


def test_create_review_robin_session_sets_up_and_opens_it(page: Page) -> None:
    """Segment 23J (amended, 2026-11-25): on a published exercise, a saved
    gate not yet set up or sent offers *Create Review Robin session*; a
    click keeps the set-up in the tab, as Evaluations' *Set up* does, and
    opens the session by its code in a new tab; the card then offers *Open
    Review Robin session ↗*, after a reload too."""
    page.goto(MODEL)
    boxes = _rr_boxes(page)
    ready = [
        k
        for k, b in boxes.items()
        if b.locator("[data-pc-rr-create]").count()
        and b.locator("[data-pc-rr-create]").is_enabled()
    ]
    assert ready, "no gate to create a session for"
    key = ready[0]
    box = boxes[key]
    code = box.get_attribute("data-code") or ""
    assert code.startswith("wa9juxbc2t-g")
    gate = page.locator(f'.pc-item[data-item="gate"][data-key="{key}"]')
    _open(_cards(page).filter(has=gate))
    _open_item(gate)
    # Review Robin is not mounted here: its page stands in.
    page.context.route("**/reviewrobin/**", lambda r: r.fulfill(status=200, body="Review Robin"))
    with page.context.expect_page() as opened:
        box.locator("[data-pc-rr-create]").click()
    opened.value.wait_for_url(f"**/reviewrobin/operator/sessions/by-code/{code}")
    link = box.locator("[data-pc-rr-open]")
    assert link.inner_text() == "Open Review Robin session ↗"
    assert link.get_attribute("target") == "_blank" and link.get_attribute("rel") == "noopener"
    assert (link.get_attribute("href") or "").endswith(f"/by-code/{code}")
    assert box.locator("[data-pc-rr-said]").inner_text().startswith("Set up (simulated)")
    kept = page.evaluate(
        "k => JSON.parse(sessionStorage.getItem('applydesk-rr-setup:wa9juxbc2t'))[k]", key
    )
    assert kept["code"] == code and kept["url"].endswith(f"/by-code/{code}") and kept["transfer"]
    assert page.locator("[data-unsaved]").is_hidden()  # a set-up is not an edit
    page.reload()
    assert _rr_boxes(page)[key].locator("[data-pc-rr-open]").count() == 1


def test_a_sent_gate_offers_its_session(page: Page) -> None:
    """A gate the sample has sent has its session already: the card links
    to it by its code."""
    page.goto(MODEL)
    made = [b for b in _rr_boxes(page).values() if b.get_attribute("data-made") is not None]
    assert made
    for box in made:
        href = box.locator("[data-pc-rr-open]").get_attribute("href") or ""
        assert href.endswith(f"/by-code/{box.get_attribute('data-code')}")


def test_create_waits_for_the_save(page: Page) -> None:
    """A gate is set up as saved: with changes unsaved the button is off,
    saying so, and back on once they are saved."""
    page.goto(MODEL)
    boxes = _rr_boxes(page)
    key = next(
        k
        for k, b in boxes.items()
        if b.locator("[data-pc-rr-create]").count()
        and b.locator("[data-pc-rr-create]").is_enabled()
    )
    button = boxes[key].locator("[data-pc-rr-create]")
    page.locator("[data-unsaved]").evaluate("m => { m.hidden = false; }")
    assert button.is_disabled()
    assert button.get_attribute("title") == "Save the page first: the gate is set up as saved"
    page.locator("[data-unsaved]").evaluate("m => { m.hidden = true; }")
    assert button.is_enabled()
