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
    beside Add, *Dossiers per person* makes that many for each one picked,
    each Dossier 1, Dossier 2, rows of the Dossiers page's one table."""
    from applydesk.tests.test_candidates_browser import _pick

    _held()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    _open_all(_cards(page).nth(0))
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    assert item.locator('[data-rel="per-person"]').count() == 0
    _pick(item, "admin@", "admin@example.edu")
    item.locator("[data-cand-n]").fill("2")
    item.locator("[data-cand-add-all]").click()
    item.locator("[data-cand-sum]").filter(has_text="2 dossiers for 1 person").wait_for()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/dossiers")
    mine = page.locator("tr[data-entry]")
    assert [mine.nth(i).locator(".ap-app").inner_text() for i in range(2)] == [
        "Created by hand · Dossier 1",
        "Created by hand · Dossier 2",
    ]


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


def test_the_dossiers_page_holds_create_dossiers_entries(page: Page) -> None:
    """Author, 2026-11-27: one table. With Create dossiers in the process,
    its entries are rows of the Dossiers grid, added above it (the page
    drawn again) and removed by ticking them, Remove ticked."""
    from applydesk.tests.test_candidates_browser import _pick

    _held()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/dossiers")
    strip = page.locator('.ap-hand-add [data-cand-live][data-cand-kind="candidates"]')
    _pick(strip, "admin@", "admin@example.edu")
    with page.expect_navigation():
        strip.locator("[data-cand-add-all]").click()
    row = page.locator("tr[data-entry]", has_text="admin@example.edu")
    row.wait_for()
    assert "Created by hand · Dossier 1" in row.inner_text()
    assert row.locator(".ap-stat .chip").text_content() == "By hand"
    page.locator("[data-ap-status]").select_option("hand")
    assert (
        page.locator("[data-row]:not([hidden])").count() == page.locator("tr[data-entry]").count()
    )
    row.locator("[data-ap-tick]").check()
    page.once("dialog", lambda d: d.accept())
    with page.expect_navigation():
        page.locator("[data-ap-remove]").click()
    assert page.locator("tr[data-entry]", has_text="admin@example.edu").count() == 0


def test_the_dossiers_page_has_no_add_row_without_create_dossiers(page: Page) -> None:
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{DRAFT}/dossiers")
    page.locator("[data-applications]").wait_for()
    assert page.locator(".ap-hand-add").count() == 0
    assert page.locator("[data-ap-remove]").count() == 0
