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


def test_add_makes_as_many_dossiers_as_its_box_says(page: Page) -> None:
    """Author, 2026-11-27: Create dossiers has no Max dossiers per person;
    beside Add, *Dossiers per person* makes that many for the one picked,
    each Dossier 1, Dossier 2, listed under the folding count."""
    from applydesk.tests.test_candidates_browser import _pick

    _held()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    _open_all(_cards(page).nth(0))
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    assert item.locator('[data-rel="per-person"]').count() == 0
    _pick(item, "admin@", "admin@example.edu")
    item.locator("[data-cand-n]").fill("2")
    item.locator("[data-cand-add]").click()
    item.locator("[data-cand-fold-n]").filter(has_text="Dossiers (2)").wait_for()
    titles = item.locator("[data-cand-list] tbody tr td:nth-child(3)")
    assert [titles.nth(i).inner_text() for i in range(2)] == ["Dossier 1", "Dossier 2"]


def test_the_form_s_box_shows_only_without_create_dossiers(page: Page) -> None:
    """With Create dossiers on the timeline the Form's Max dossiers per
    person is hidden; removing Create dossiers shows it. A draft, so the
    form's box is not locked."""
    _held(DRAFT)
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{DRAFT}/process")
    _open_all(_cards(page).nth(0))
    form = page.locator('#pc-cards .pc-item[data-item="form"]')
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    assert form.locator("[data-per-person-row]").is_hidden()
    item.locator('[data-pc-act="remove-candidates"]').click()
    assert form.locator("[data-per-person-row]").is_visible()
