"""The Band 2 preview's long-text response box takes no resize handle,
while the reviewer surface's keeps one (segment 19Y Item 4): a drag in
the preview would persist nowhere.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect

from ._builder import REVIEWER_EMAIL, activate, open_card, open_unlocked, seed_rosters
from .conftest import LiveServer, app_url

_PREVIEW_BOX = "[data-new-model-band2] textarea[disabled][aria-hidden='true']"


def _resize(box) -> str:
    return box.evaluate("el => getComputedStyle(el).resize")


def test_the_preview_box_has_no_handle_locked_or_unlocked(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    card = open_card(page, session_id)
    box = card.locator(_PREVIEW_BOX).first
    expect(box).to_be_visible()
    assert _resize(box) == "none"

    card = open_unlocked(page, session_id)
    box = card.locator(_PREVIEW_BOX).first
    expect(box).to_be_visible()
    assert _resize(box) == "none"


def test_the_reviewer_box_keeps_its_handle(
    page: Page,
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    session_id = new_session()
    seed_rosters(api, session_id)
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.goto(app_url(f"/me/sessions/{session_id}"))
    box = reviewer.locator("table textarea").first
    expect(box).to_be_visible()
    assert _resize(box) == "vertical"
