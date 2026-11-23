"""The Candidates item in a real Chromium (ruling 77, segment AD2C rung
9): the search finds someone on record, Add lists them, Remove takes them
off, a CSV adds its good rows and lists the rest back; none of it marks
Process unsaved, since each change is kept as it is made."""

from __future__ import annotations

from dataclasses import replace

from playwright.sync_api import Page

from applydesk import db, people, process_store, stages
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
    item.locator("[data-cand-search]").fill("zoe.cand")
    found = item.locator("[data-cand-found] li", has_text="zoe.candidate@example.edu")
    found.locator("button").click()
    row = item.locator("[data-cand-list] tr", has_text="zoe.candidate@example.edu")
    row.wait_for()
    assert item.locator("[data-cand-count]").text_content() == "1 person"
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
