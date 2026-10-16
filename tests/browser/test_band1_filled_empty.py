"""Band 1's IS FILLED / IS EMPTY leave the value box inactive, and a new
rule cell starts from the offered tags only (author, 2026-10-16;
``guide/assignment_rule_clarify.md``, stage 1).
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Locator, Page, expect

from ._builder import open_unlocked, pin_full_matrix
from .conftest import LiveServer

REVIEWERS_CSV = b"ReviewerName,ReviewerEmail,ReviewerTag1\nRana,rana@example.edu,Red\n"
REVIEWEES_CSV = b"RevieweeName,RevieweeEmail,RevieweeTag1\nCarol,carol@example.edu,Blue\n"


def _seed(api: httpx.Client, session_id: int) -> None:
    for kind, body in (("reviewers", REVIEWERS_CSV), ("reviewees", REVIEWEES_CSV)):
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text


def _filter_on(card: Locator, link: str) -> Locator:
    """Click the Link's pill on to Filter (the pinned matrix renders it on
    All, one click short); return its first cell."""
    wrapper = card.locator("[data-new-model-link-wrapper]").filter(
        has=card.page.locator(f'select[name="{link}_field"]')
    )
    pill = wrapper.locator("[data-new-model-rule-mode]")
    expect(pill).to_have_attribute("data-new-model-rule-mode", "all")
    pill.click()
    expect(pill).to_have_attribute("data-new-model-rule-mode", "filter")
    return wrapper.locator("[data-new-model-rule-cell]").first


def test_filled_and_empty_make_the_value_box_inactive(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    pin_full_matrix(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    cell = _filter_on(card, "link1")
    operator = cell.locator("[data-new-model-operator-cycle]")
    value = cell.locator("[data-new-model-operand-value]")
    value.fill("Red")

    seen = []
    for _ in range(4):
        seen.append((operator.inner_text(), value.evaluate("i => i.readOnly")))
        operator.click()

    assert seen == [
        ("IS", False),
        ("IS NOT", False),
        ("IS FILLED", True),
        ("IS EMPTY", True),
    ]
    # Back round to IS: the box is live again and kept what was typed.
    expect(operator).to_have_text("IS")
    expect(value).to_be_editable()
    expect(value).to_have_value("Red")
    assert cell.locator("[data-new-model-op-input]").input_value() == "IS"


def test_link2_filled_shows_the_inactive_value_box(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    pin_full_matrix(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    cell = _filter_on(card, "link2")
    operator = cell.locator("[data-new-model-operator-cycle]")

    for _ in range(4):  # IS THE SAME AS → … → IS FILLED
        operator.click()

    expect(operator).to_have_text("IS FILLED")
    expect(cell.locator("[data-new-model-operand-tag]")).to_be_hidden()
    value = cell.locator("[data-new-model-operand-value]")
    expect(value).to_be_visible()
    expect(value).not_to_be_editable()

    # A new cell starts on IS THE SAME AS, with its value box live.
    card.locator("[data-new-model-rule-builder]").nth(1).locator(
        "[data-new-model-rule-add]"
    ).click()
    added = card.locator('select[name="link2_field"]').nth(1).locator(
        "xpath=ancestor::*[@data-new-model-rule-cell]"
    )
    expect(added.locator("[data-new-model-operator-cycle]")).to_have_text("IS THE SAME AS")
    assert added.locator("[data-new-model-operand-value]").evaluate("i => i.readOnly") is False
