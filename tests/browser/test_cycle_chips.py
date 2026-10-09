"""Cycle chips are always dark.

``guide/operator_pages_enhancements.md`` Item 3 (author's taxonomy,
2026-10-09; ``spec/ui_elements.md`` §9). A cycle chip's every state is a
positive choice, so it never wears the light "off" of an on/off chip.
The lobby's AND/OR and Select all / Clear all chips, and the Archived
page's Select all / Clear all, are cycle chips: their fill matches a
selected tag chip's whatever their label says.
"""

from __future__ import annotations

import re
import uuid

import httpx
from playwright.sync_api import Locator, Page, expect

from .conftest import LiveServer


def _tagged_session(api: httpx.Client, tags: str) -> int:
    code = f"c{uuid.uuid4().hex[:8]}"
    response = api.post(
        "/operator/sessions",
        data={"name": f"Chips {code}", "code": code, "tags": tags},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])


def _fill(chip: Locator) -> str:
    return chip.evaluate("el => getComputedStyle(el).backgroundColor")


def _selected_fill(strip: Locator) -> tuple[str, str]:
    """A tag chip's fill off, then selected (and put back)."""
    tag = strip.locator(".tag-chip").first
    off = _fill(tag)
    tag.click()
    expect(tag).to_have_class(re.compile(r"\bis-selected\b"))
    on = _fill(tag)
    tag.click()
    assert on != off, "a tag chip's selected fill should differ from its off fill"
    return off, on


def test_lobby_mode_and_clear_chips_stay_dark(page: Page, api: httpx.Client) -> None:
    _tagged_session(api, "chip-alpha, chip-beta")
    page.goto("/operator/sessions")
    strip = page.locator("#sessions-tag-filter")
    off, on = _selected_fill(strip)

    mode = strip.locator("[data-tag-mode]")
    clear = strip.locator("[data-tag-clear]")
    for _ in range(2):  # both labels of each
        assert _fill(mode) == on, mode.inner_text()
        assert _fill(clear) == on, clear.inner_text()
        mode.click()
        clear.click()
    assert _fill(mode) != off


def test_archived_select_all_chip_stays_dark(
    page: Page, api: httpx.Client, live_server: LiveServer
) -> None:
    session_id = _tagged_session(api, "chip-gamma")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.models import ReviewSession

    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            db.get(ReviewSession, session_id).status = "archived"
            db.commit()
    finally:
        engine.dispose()

    page.goto("/operator/sessions/archived")
    strip = page.locator("#archived-tag-filter")
    _off, on = _selected_fill(strip)
    clear = strip.locator("[data-tag-clear]")
    for _ in range(2):
        assert _fill(clear) == on, clear.inner_text()
        clear.click()
