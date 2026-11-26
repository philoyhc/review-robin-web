"""The Candidates item in a real Chromium, as the page's script draws it
(ruling 77, segment AD2C rung 8; Codex on #4158): it keeps its own name and
kicker, and is counted as no outcome."""

from __future__ import annotations

from dataclasses import replace

from playwright.sync_api import Page

from applydesk import db, process_store, stages
from applydesk.tests.test_process_browser import ORIGIN
from applydesk.tests.test_process_browser import page as page  # the fixture, re-exported

MODEL = "wa9juxbc2t"


def _held() -> None:
    """The first stage holds Candidates (rung 9: a stage's own flag)."""
    built = stages.plan_of(MODEL).stages
    session = db.new_session()
    try:
        process_store.save(
            session, MODEL, (replace(built[0], candidates=True), *built[1:]), 0, None
        )
        session.commit()
    finally:
        session.close()


def test_candidates_is_drawn_as_itself_not_an_outcome(page: Page) -> None:
    _held()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    assert item.locator("[data-pc-kicker]").text_content() == "Populate Dossiers"
    assert item.locator("[data-pi-name]").text_content() == "Populate Dossiers"
    outcomes = page.locator('#pc-cards .pc-item[data-item="outcome"]').count()
    counts = page.locator("[data-pc-counts]").text_content() or ""
    assert f"{outcomes} outcome" in counts, counts
    assert "Populate Dossiers" in (page.locator("[data-pc-outline]").text_content() or "")
