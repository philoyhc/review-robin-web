"""Segment 20M rung 4 — Band 3's Display fields chip.

An individual card cycles Across → Stacked → Joined; a group-scoped
card (Band 1's unit of review set to groups) cycles Joined ↔ Stacked
and shows a stored Across as Joined. The chip rides the card's Save.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect

from ._builder import open_card, open_unlocked, save
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
    card = open_unlocked(page, session_id)
    unit = card.locator("[data-new-model-unit-mode]")
    for _ in range(3):
        if unit.get_attribute("data-new-model-unit-mode") == "group":
            break
        unit.click()
    expect(unit).to_have_attribute("data-new-model-unit-mode", "group")
    chip = card.locator("[data-display-layout-chip]")
    # A stored Across reads as Joined, and stays Across until cycled.
    expect(chip).to_have_text("Joined")
    expect(card.locator("[data-display-layout-input]")).to_have_value("across")
    chip.click()
    expect(chip).to_have_text("Stacked")
    chip.click()
    expect(chip).to_have_text("Joined")
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
