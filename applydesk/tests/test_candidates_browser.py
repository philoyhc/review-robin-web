"""The Candidates item in a real Chromium (ruling 77, segment AD2C rung
9): the search finds someone on record, Add lists them, Remove takes them
off, a CSV adds its good rows and lists the rest back; none of it marks
Process unsaved, since each change is kept as it is made."""

from __future__ import annotations

from dataclasses import replace

from playwright.sync_api import Locator, Page, Route

from applydesk import candidates, db, people, process_store, stages
from applydesk.tests.test_process_browser import ORIGIN
from applydesk.tests.test_process_browser import page as page  # the fixture, re-exported

MODEL = "wa9juxbc2t"


def _with_candidates() -> None:
    built = stages.plan_of(MODEL).stages
    held = (replace(built[0], candidates=True), *built[1:])
    session = db.new_session()
    try:
        process_store.save(session, MODEL, held, 0, None)
        people.pending(session, "zoe.candidate@example.edu", None)
        session.commit()
    finally:
        session.close()


def _pick(item: Locator, typed: str, email: str) -> None:
    """The typeahead (author, 2026-11-27): type, wait for the offer naming
    ``email``, then choose it as the browser's list does, putting its label
    in the box; Add is enabled only then."""
    box = item.locator("[data-cand-search]")
    box.fill(typed)
    offer = item.locator(f'[data-cand-options] option[value*="{email}"]')
    offer.wait_for(state="attached")
    assert item.locator("[data-cand-add]").is_disabled()
    box.fill(offer.get_attribute("value") or "")
    assert item.locator("[data-cand-add]").is_enabled()


def test_the_list_is_kept_as_it_is_changed(page: Page) -> None:
    _with_candidates()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    stage = page.locator("#pc-cards .pc").filter(
        has=page.locator('.pc-item[data-item="candidates"]')
    )
    if not stage.locator(".fc-body").first.is_visible():
        stage.locator("[data-fc-toggle]").first.click()
    if not item.locator("[data-cand-search]").is_visible():
        item.locator("[data-pi-toggle]").click()
    _pick(item, "zoe.cand", "zoe.candidate@example.edu")
    item.locator("[data-cand-add]").click()
    row = item.locator("[data-cand-list] tr", has_text="zoe.candidate@example.edu")
    row.wait_for()
    assert item.locator("[data-cand-count]").text_content() == "1 dossier"
    row.locator("[data-cand-remove]").click()
    item.locator("[data-cand-none]").wait_for()
    item.locator("[data-cand-file]").set_input_files(
        files=[
            {
                "name": "c.csv",
                "mimeType": "text/csv",
                "buffer": b"Email,Name\nyan@example.edu,Yan\nnope\n",
            }
        ]
    )
    item.locator("[data-cand-list] tr", has_text="yan@example.edu").wait_for()
    assert "is not an email address" in item.locator("[data-cand-bad]").inner_text()
    assert item.locator("[data-cand-said]").inner_text() == "1 added."
    # Kept as made: Process's own Save has nothing unsaved.
    assert page.locator("[data-unsaved]").is_hidden()


def test_candidates_moved_to_another_stage_shows_the_list_as_it_stands(page: Page) -> None:
    """Codex on #4161: +Populate Dossiers on another stage draws the list as it
    now is, not as the page first loaded it."""
    built = stages.plan_of(MODEL).stages
    drafts = tuple(replace(st, status="Draft", candidates=(i == 0)) for i, st in enumerate(built))
    session = db.new_session()
    try:
        process_store.save(session, MODEL, drafts, 0, None)
        people.pending(session, "zoe.candidate@example.edu", None)
        session.commit()
    finally:
        session.close()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    first, other = page.locator("#pc-cards .pc").nth(0), page.locator("#pc-cards .pc").nth(1)
    for card in (first, other):
        if not card.locator(".fc-body").first.is_visible():
            card.locator("[data-fc-toggle]").first.click()
    if not item.locator("[data-cand-search]").is_visible():
        item.locator("[data-pi-toggle]").click()
    _pick(item, "zoe.cand", "zoe.candidate@example.edu")
    item.locator("[data-cand-add]").click()
    item.locator("[data-cand-list] tr", has_text="zoe.candidate@example.edu").wait_for()
    first.locator('[data-pc-act="remove-candidates"]').click()
    other.locator('[data-pc-act="candidates"]').click()
    moved = other.locator('.pc-item[data-item="candidates"]')
    assert "zoe.candidate@example.edu" in (moved.locator("[data-cand-list]").text_content() or "")
    assert moved.locator("[data-cand-count]").text_content() == "1 dossier"


def test_changes_are_sent_one_at_a_time(page: Page) -> None:
    """Codex on #4161: two removals in quick succession are sent in turn, so
    an older answer cannot redraw over a newer list."""
    built = stages.plan_of(MODEL).stages
    session = db.new_session()
    try:
        process_store.save(
            session, MODEL, (replace(built[0], candidates=True), *built[1:]), 0, None
        )
        for address in ("one@example.edu", "two@example.edu"):
            candidates.add(session, MODEL, people.pending(session, address, None), "csv", None)
        session.commit()
    finally:
        session.close()
    seen: list[str] = []
    held: list[Route] = []

    def hold(route: Route) -> None:
        if route.request.method != "POST":
            route.fallback()  # to the fixture's server
            return
        seen.append(route.request.post_data or "")
        held.append(route)

    page.route("**/candidates", hold)
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    stage = page.locator("#pc-cards .pc").nth(0)
    if not stage.locator(".fc-body").first.is_visible():
        stage.locator("[data-fc-toggle]").first.click()
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    if not item.locator("[data-cand-search]").is_visible():
        item.locator("[data-pi-toggle]").click()
    item.locator("[data-cand-remove]").first.click()
    item.locator("[data-cand-remove]").last.click()
    page.wait_for_timeout(300)
    assert len(seen) == 1  # the second waits for the first's answer
    held.pop().fallback()
    page.wait_for_timeout(300)
    assert len(seen) == 2
    held.pop().fallback()
    item.locator("[data-cand-none]").wait_for()


def _drafts_holding_candidates() -> None:
    built = stages.plan_of(MODEL).stages
    drafts = tuple(replace(st, status="Draft", candidates=(i == 0)) for i, st in enumerate(built))
    session = db.new_session()
    try:
        process_store.save(session, MODEL, drafts, 0, None)
        people.pending(session, "zoe.candidate@example.edu", None)
        session.commit()
    finally:
        session.close()


def test_a_replicated_stage_leaves_candidates_behind(page: Page) -> None:
    """Codex on #4161: a stage's copy holds no Candidates, as it holds no
    form, so Replicate does not leave Process unsaveable."""
    _drafts_holding_candidates()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    first = page.locator("#pc-cards .pc").nth(0)
    if not first.locator(".fc-body").first.is_visible():
        first.locator("[data-fc-toggle]").first.click()
    first.locator('[data-fc-act="replicate"]').click()
    assert page.locator('#pc-cards .pc-item[data-item="candidates"]').count() == 1
    assert (
        page.locator("#pc-cards .pc").nth(1).locator('.pc-item[data-item="candidates"]').count()
        == 0
    )


def test_an_answer_after_a_move_redraws_the_item_on_the_page(page: Page) -> None:
    """Codex on #4161: a change answered after Candidates moved stage is
    drawn on the item now on the page, not the one taken off."""
    _drafts_holding_candidates()
    held: list[Route] = []

    def hold(route: Route) -> None:
        if route.request.method == "POST":
            held.append(route)
        else:
            route.fallback()

    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    first, other = page.locator("#pc-cards .pc").nth(0), page.locator("#pc-cards .pc").nth(1)
    for card in (first, other):
        if not card.locator(".fc-body").first.is_visible():
            card.locator("[data-fc-toggle]").first.click()
    if not item.locator("[data-cand-search]").is_visible():
        item.locator("[data-pi-toggle]").click()
    _pick(item, "zoe.cand", "zoe.candidate@example.edu")
    page.route("**/candidates", hold)
    item.locator("[data-cand-add]").click()
    page.wait_for_timeout(200)
    first.locator('[data-pc-act="remove-candidates"]').click()
    other.locator('[data-pc-act="candidates"]').click()
    held.pop().fallback()
    moved = other.locator('.pc-item[data-item="candidates"]')
    moved.locator("[data-cand-list] tr", has_text="zoe.candidate@example.edu").wait_for()
    assert moved.locator("[data-cand-count]").text_content() == "1 dossier"
