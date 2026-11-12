"""Segment 20M rung 4 — Band 3's Display fields chip.

An individual card cycles Across → Stacked → Joined; a group-scoped
card cycles Joined ↔ Stacked
and shows a stored Across as Joined. The chip rides the card's Save.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect

from ._builder import open_card, open_unlocked, save, session_pk
from .conftest import LiveServer


def test_an_individual_card_cycles_all_three_and_saves(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-display-layout-chip]")
    expect(chip).to_have_text("Across")
    chip.click()
    expect(chip).to_have_text("Stacked")
    chip.click()
    expect(chip).to_have_text("Joined")
    expect(card.locator("[data-display-layout-input]")).to_have_value("joined")
    save(page, card)
    card = open_unlocked(page, session_id)
    expect(card.locator("[data-display-layout-chip]")).to_have_text("Joined")


def _make_group_scoped(database_url: str, session_id: str) -> None:
    """Group by Tag 1, written directly as the integration tests do: the
    Unit of review pill's own cycle is Band 1's test's to pin."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            instrument = db.execute(
                select(Instrument).where(
                    Instrument.session_id == session_pk(database_url, session_id)
                )
            ).scalar_one()
            instrument.group_kind = "r1"
            db.commit()
    finally:
        engine.dispose()


def test_a_group_card_cycles_joined_and_stacked_only(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    for kind, body in (
        ("reviewers", b"ReviewerName,ReviewerEmail\nRana,rana@example.edu\n"),
        ("reviewees", b"RevieweeName,RevieweeEmail,RevieweeTag1\nCarol,carol@example.edu,Blue\n"),
    ):
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text
    _make_group_scoped(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-display-layout-chip]")
    # A stored Across reads as Joined, and stays Across until cycled.
    expect(chip).to_have_text("Joined")
    expect(card.locator("[data-display-layout-input]")).to_have_value("across")
    # Rung 5: a chip click rebuilds the group preview; the tags sit below
    # the names, never bold.
    group_cell = card.locator("[data-new-model-band2-preview] td.rs-group")
    chip.click()
    expect(chip).to_have_text("Stacked")
    expect(group_cell.locator(".rs-df-line")).to_have_text("Tag 1: Blue")
    chip.click()
    expect(chip).to_have_text("Joined")
    expect(group_cell.locator(".rs-df-line")).to_have_text("Blue")
    expect(group_cell.locator("strong")).to_have_count(0)
    expect(card.locator("[data-display-layout-input]")).to_have_value("joined")


def test_a_locked_cards_chip_does_not_cycle(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    card = open_card(page, session_id)
    chip = card.locator("[data-display-layout-chip]")
    expect(chip).to_have_text("Across")
    assert chip.evaluate("el => getComputedStyle(el).cursor") == "default"
    chip.click(force=True)
    expect(chip).to_have_text("Across")


def test_the_preview_follows_the_chip(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """Rung 5: Stacked and Joined move the tag under the sample
    reviewee's email and drop its column; Across brings it back."""
    session_id = new_session()
    for kind, body in (
        ("reviewers", b"ReviewerName,ReviewerEmail\nRana,rana@example.edu\n"),
        ("reviewees", b"RevieweeName,RevieweeEmail,RevieweeTag1\nCarol,carol@example.edu,Blue\n"),
    ):
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-display-layout-chip]")
    preview = card.locator("[data-new-model-band2-preview]")
    expect(preview.locator("th", has_text="Tag 1")).to_have_count(1)
    chip.click()  # Stacked
    expect(preview.locator("th", has_text="Tag 1")).to_have_count(0)
    expect(preview.locator("td.rs-reviewee .rs-df-line")).to_have_text("Tag 1: Blue")
    chip.click()  # Joined
    expect(preview.locator("td.rs-reviewee .rs-df-line")).to_have_text("Blue")
    chip.click()  # Across
    expect(preview.locator("th", has_text="Tag 1")).to_have_count(1)
    expect(preview.locator("td.rs-reviewee .rs-df-line")).to_have_count(0)
