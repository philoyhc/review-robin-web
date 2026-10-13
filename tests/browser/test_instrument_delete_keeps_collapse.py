"""Deleting an instrument leaves every other card as it was.

The delete redirects to ``#instrument-<id>`` for the next instrument
(the previous when the last is deleted;
``views.instrument_delete_landing_id``), and the page opens whichever
card a ``#instrument-`` hash names, so that card popped open (author,
2026-10-13: "everything that was collapsed stays collapsed"). Delete now
captures every card's open state before it submits, as +Page break and
a drag already do, and the restore puts each back.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from playwright.sync_api import Page, expect

from ._builder import add_instrument, unlock


def _card(page: Page, index: int):
    return page.locator("[data-instrument-card]").nth(index)


def _details(page: Page, index: int):
    return _card(page, index).locator("details.instrument-card-collapsible")


def _expand(page: Page, index: int):
    card = _card(page, index)
    card.locator("summary.instrument-card-summary").click()
    return card


@pytest.mark.parametrize(
    ("deleted", "landing"),
    [
        # A middle card: the redirect names the next one.
        (1, 1),
        # The last card: the redirect names the one above it.
        (2, 1),
    ],
)
def test_delete_leaves_the_landing_card_collapsed(
    page: Page,
    api: httpx.Client,
    new_session: Callable[[], int],
    deleted: int,
    landing: int,
) -> None:
    session_id = new_session()
    add_instrument(api, session_id)
    add_instrument(api, session_id)
    page.goto(f"/operator/sessions/{session_id}/instruments")
    expect(page.locator("[data-instrument-card]")).to_have_count(3)

    # The first card open, the rest collapsed until one is deleted.
    _expand(page, 0)
    card = _expand(page, deleted)
    unlock(card)
    card.locator("[data-delete-confirm]").check()
    card.locator("[data-delete-btn]").click()

    page.wait_for_url(f"**/operator/sessions/{session_id}/instruments#instrument-*")
    expect(page.locator("[data-instrument-card]")).to_have_count(2)
    expect(_details(page, landing)).not_to_have_attribute("open", "")
    expect(_details(page, 0)).to_have_attribute("open", "")
