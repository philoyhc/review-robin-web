"""The Instruments card's Band 1 link chips (Links 1-3): back on "Not set"
a chip is amber whichever state it rendered in, Enter and Space cycle it
as a click does, and on a locked card it drops the edge and pointer (the
author, 2026-10-10; ``spec/ui_elements.md`` §9).
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Locator, Page, expect

from ._builder import open_card, open_unlocked, pin_full_matrix
from .conftest import LiveServer

REVIEWERS_CSV = b"ReviewerName,ReviewerEmail,ReviewerTag1\nRana,rana@example.edu,Red\n"
REVIEWEES_CSV = b"RevieweeName,RevieweeEmail,RevieweeTag1\nCarol,carol@example.edu,Blue\n"

LINK_CHIPS = (
    "[data-new-model-rule-mode][role=button], [data-new-model-unit-mode][role=button]"
)


def _seed(api: httpx.Client, session_id: int) -> None:
    for kind, body in (("reviewers", REVIEWERS_CSV), ("reviewees", REVIEWEES_CSV)):
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text


def _fill(chip: Locator) -> str:
    return chip.evaluate("el => getComputedStyle(el).backgroundColor")


def _probe(card: Locator, classes: str) -> tuple[str, str]:
    """The fill and text color a span with these classes wears in the card."""
    return tuple(
        card.evaluate(
            """(card, classes) => {
                const probe = document.createElement('span');
                probe.className = classes;
                card.appendChild(probe);
                const style = getComputedStyle(probe);
                const out = [style.backgroundColor, style.color];
                probe.remove();
                return out;
            }""",
            classes,
        )
    )


def _amber(card: Locator) -> str:
    """The fill a chip rendered on "Not set" wears."""
    return _probe(card, "pill pill-empty tag-chip is-unset")[0]


def test_a_set_link_chip_cycled_back_to_not_set_is_amber(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    pin_full_matrix(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    chips = card.locator(LINK_CHIPS)
    assert chips.count() == 3
    amber = _amber(card)
    for i in range(3):
        chip = chips.nth(i)
        # Rendered set: the first state of the pinned matrix ("All" /
        # "Individual"), two clicks from "Not set".
        expect(chip).not_to_have_text("Not set")
        solid = _fill(chip)
        assert solid != amber
        chip.click()
        chip.click()
        expect(chip).to_have_text("Not set")
        expect(chip).to_have_attribute("aria-pressed", "mixed")
        assert _fill(chip) == amber, i
        chip.click()
        assert _fill(chip) == solid, i


def test_enter_and_space_cycle_a_link_chip(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    card = open_unlocked(page, session_id)
    chip = card.locator(LINK_CHIPS).first
    expect(chip).to_have_text("Not set")
    chip.focus()
    page.keyboard.press("Enter")
    expect(chip).to_have_text("All")
    page.keyboard.press("Space")
    expect(chip).not_to_have_text("All")
    expect(chip).not_to_have_text("Not set")
    page.keyboard.press("Enter")
    expect(chip).to_have_text("Not set")


def _style(chip: Locator, prop: str) -> str:
    return chip.evaluate("(el, p) => getComputedStyle(el)[p]", prop)


def test_a_locked_cards_link_chips_read_as_plain_pills(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    """Set links read as the plain pill; no edge or pointer either way."""
    session_id = new_session()
    _seed(api, session_id)
    pin_full_matrix(live_server.database_url, session_id)
    card = open_card(page, session_id)
    expect(card).to_have_attribute("data-instrument-locked", "true")
    chips = card.locator(LINK_CHIPS)
    assert chips.count() == 3
    plain_fill, plain_text = _probe(card, "pill pill-count")
    for i in range(3):
        chip = chips.nth(i)
        assert _fill(chip) == plain_fill, i
        assert _style(chip, "color") == plain_text, i
        assert _style(chip, "cursor") == "default", i
        assert _style(chip, "boxShadow") == "none", i


def test_a_locked_cards_unset_link_chip_stays_amber(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    card = open_card(page, session_id)
    expect(card).to_have_attribute("data-instrument-locked", "true")
    chip = card.locator(LINK_CHIPS).first
    expect(chip).to_have_text("Not set")
    assert _fill(chip) == _amber(card)
    assert _style(chip, "cursor") == "default"
    assert _style(chip, "boxShadow") == "none"
