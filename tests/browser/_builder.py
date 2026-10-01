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


def preview_input(card: Locator, column: int) -> Locator:
    """The sample row's control under a response-field column."""
    return card.locator("th[scope=col]:not(.rs-reviewee)").nth(column).locator(
        "xpath=ancestor::table[1]"
    ).locator("tbody td :is(input, select, textarea)").nth(column)


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
    # The response arrives before the page's own handler has assigned ids
    # to new rows and cleared the dirty state; Save disabling is that end.
    expect(button).to_be_disabled()


REVIEWER_EMAIL = "rana@example.edu"


def sign_in(api: httpx.Client, email: str) -> None:
    """One request through the Easy Auth headers, which makes the person's
    users row (an operator, for an address in OPERATOR_EMAILS)."""
    response = api.get(
        "/operator/sessions",
        headers={
            "X-MS-CLIENT-PRINCIPAL-NAME": email,
            "X-MS-CLIENT-PRINCIPAL-ID": f"browser-{email}",
        },
    )
    assert response.status_code == 200, response.text


def activate(api: httpx.Client, database_url: str, session_id: int) -> None:
    """Pin a full matrix, generate, validate and activate, so the roster's
    reviewer has an assignment. The pin writes the database directly, as
    ``tests/integration/_full_matrix.py`` does; the rest is the app's routes.
    """
    from integration._full_matrix import pin_full_matrix_on_all_instruments
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            pin_full_matrix_on_all_instruments(db, session_id)
    finally:
        engine.dispose()
    base = f"/operator/sessions/{session_id}"
    generated = api.post(f"{base}/assignments/generate", follow_redirects=False)
    assert generated.status_code == 303, generated.text
    api.get(f"{base}/assignments?validated=1")
    activated = api.post(
        f"{base}/activate", data={"acknowledge_warnings": "true"}, follow_redirects=False
    )
    # A refused activation redirects too, with super_status=failed in the
    # query string; success lands on bare Session Home.
    assert activated.status_code == 303, activated.text
    assert activated.headers["location"] == base, activated.headers["location"]


def branch_rating(page: Page, session_id: int, *, op: str = "ge", value: str = "4") -> Locator:
    """Give "Rating" a Show branch holding one String field, "Why"; save."""
    card = open_unlocked(page, session_id)
    rows(card).first.locator("[data-new-model-rf-fork]").click()
    condition = card.locator("[data-new-model-rf-condition]").first
    condition.locator("[data-new-model-rf-condition-op]").select_option(op)
    condition.locator("[data-new-model-rf-condition-value]").fill(value)
    card.locator("[data-new-model-rf-governed] [data-new-model-rf-name]").fill("Why")
    save(page, card)
    return card
