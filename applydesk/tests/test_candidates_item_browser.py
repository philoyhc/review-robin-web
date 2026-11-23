"""The Candidates item in a real Chromium, as the page's script draws it
(ruling 77, segment AD2C rung 8; Codex on #4158): it keeps its own name and
kicker, and is counted as no outcome."""

from __future__ import annotations

from playwright.sync_api import Page

from applydesk.tests.test_process_browser import ORIGIN
from applydesk.tests.test_process_browser import page as page  # the fixture, re-exported

INVITED = "k7mfr3pq8z"  # Invitation only: Candidates drawn with the form


def test_candidates_is_drawn_as_itself_not_an_outcome(page: Page) -> None:
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{INVITED}/process")
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    assert item.locator("[data-pc-kicker]").text_content() == "Candidates"
    assert item.locator("[data-pi-name]").text_content() == "Candidates"
    outcomes = page.locator('#pc-cards .pc-item[data-item="outcome"]').count()
    counts = page.locator("[data-pc-counts]").text_content() or ""
    assert f"{outcomes} outcome" in counts, counts
    assert "Candidates" in (page.locator("[data-pc-outline]").text_content() or "")
