"""Shared steps for the Instruments-builder browser tests."""

from __future__ import annotations

import httpx
from playwright.sync_api import Locator, Page, expect

REVIEWERS_CSV = b"ReviewerName,ReviewerEmail\nRana,rana@example.edu\n"
REVIEWEES_CSV = b"RevieweeName,RevieweeEmail,Tag1\nCarol,carol@example.edu,Blue\n"


def seed_rosters(api: httpx.Client, session_id: int) -> None:
    """One reviewer and one reviewee, so Band 3 has display fields."""
    for kind, body in (("reviewers", REVIEWERS_CSV), ("reviewees", REVIEWEES_CSV)):
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text


def add_instrument(api: httpx.Client, session_id: int) -> None:
    response = api.post(
        f"/operator/sessions/{session_id}/instruments/add-new-model",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def open_card(page: Page, session_id: int, index: int = 0) -> Locator:
    """Load the Instruments page and expand one card, still locked."""
    page.goto(f"/operator/sessions/{session_id}/instruments")
    card = page.locator("[data-instrument-card]").nth(index)
    # A card opens collapsed, as it does for a person; its summary expands it.
    card.locator("summary.instrument-card-summary").click()
    return card


def unlock(card: Locator) -> None:
    card.locator("[data-instrument-unlock-toggle]:visible").first.click()
    expect(card).to_have_attribute("data-instrument-locked", "false")


def open_unlocked(page: Page, session_id: int, index: int = 0) -> Locator:
    card = open_card(page, session_id, index)
    unlock(card)
    return card


def rows(card: Locator) -> Locator:
    return card.locator("[data-new-model-rf-row]")


def names(card: Locator) -> list[str]:
    return [
        field.input_value()
        for field in rows(card).locator("[data-new-model-rf-name]").all()
    ]


def preview_headers(card: Locator) -> list[str]:
    """The Band 2 preview's response-field column labels, in order."""
    return card.evaluate(
        """card => [...card.querySelectorAll('th[scope=col]:not(.rs-reviewee)')]
            .map(th => th.textContent.replace(/[*↕]/g, '').trim())"""
    )


def save_button(card: Locator) -> Locator:
    return card.locator("[data-new-model-save]:visible").first


def save(page: Page, card: Locator) -> None:
    button = save_button(card)
    expect(button).to_be_enabled()
    with page.expect_response(
        lambda r: r.request.method == "POST" and r.url.endswith("/save")
    ) as saved:
        button.click()
    assert saved.value.ok, saved.value.text()
