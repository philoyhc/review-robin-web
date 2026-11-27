"""The Candidates item in a real Chromium, as the page's script draws it
(ruling 77, segment AD2C rung 8; Codex on #4158): it keeps its own name and
kicker, and is counted as no outcome."""

from __future__ import annotations

from dataclasses import replace

from playwright.sync_api import Page

from applydesk import db, process_store, stages
from applydesk.tests.test_process_browser import ORIGIN, _cards, _open_all
from applydesk.tests.test_process_browser import page as page  # the fixture, re-exported

MODEL = "wa9juxbc2t"
DRAFT = "c4xh2ndv6s"


def _held(exercise_id: str = MODEL) -> None:
    """The first stage holds Candidates (rung 9: a stage's own flag)."""
    built = stages.plan_of(exercise_id).stages
    session = db.new_session()
    try:
        process_store.save(
            session, exercise_id, (replace(built[0], candidates=True), *built[1:]), 0, None
        )
        session.commit()
    finally:
        session.close()


def test_candidates_is_drawn_as_itself_not_an_outcome(page: Page) -> None:
    _held()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    assert item.locator("[data-pc-kicker]").text_content() == "Create dossiers"
    assert item.locator("[data-pi-name]").text_content() == "Create dossiers"
    outcomes = page.locator('#pc-cards .pc-item[data-item="outcome"]').count()
    counts = page.locator("[data-pc-counts]").text_content() or ""
    assert f"{outcomes} outcome" in counts, counts
    assert "Create dossiers" in (page.locator("[data-pc-outline]").text_content() or "")


def test_dossiers_per_person_saves_with_process(page: Page) -> None:
    """Segment AD2K: the populating item's *Dossiers per person*, saved by
    Process's Save and read back after its reload."""
    _held()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    _open_all(_cards(page).nth(0))
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    item.locator('[data-rel="per-person"]').fill("3")
    assert page.locator("[data-unsaved]").is_visible()
    page.locator("[data-fb-save]").click()
    page.locator("[data-unsaved]").wait_for(state="hidden")
    page.reload()
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    assert item.locator('[data-rel="per-person"]').input_value() == "3"


def test_dossiers_per_person_shows_on_the_item_that_creates_the_dossiers(page: Page) -> None:
    """Author, 2026-11-27: the Form follows the number set on Create
    dossiers, so with both on a stage only Create dossiers shows the box;
    its edit is the one saved. Removing Create dossiers shows the Form's.
    A draft, so the form's box is not locked."""
    _held(DRAFT)
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{DRAFT}/process")
    _open_all(_cards(page).nth(0))
    form = page.locator('#pc-cards .pc-item[data-item="form"]')
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    assert form.locator("[data-per-person-row]").is_hidden()
    item.locator('[data-rel="per-person"]').fill("4")
    page.locator("[data-fb-save]").click()
    page.locator("[data-unsaved]").wait_for(state="hidden")
    page.reload()
    _open_all(_cards(page).nth(0))
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    assert item.locator('[data-rel="per-person"]').input_value() == "4"
    item.locator('[data-pc-act="remove-candidates"]').click()
    form = page.locator('#pc-cards .pc-item[data-item="form"]')
    assert form.locator("[data-per-person-row]").is_visible()
    assert form.locator('[data-rel="per-person"]').input_value() == "4"
