"""The Assignments page's per-instrument status chips (guide/ux_refinements.md
Item 7): the instrument's name filters the preview table, and "Include N
self reviews" is dark with every self review in, light with none, amber
with some.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Locator, Page, expect

from ._builder import pin_full_matrix
from .conftest import LiveServer

#: Rana and Carol on both sides: four pairs, two of them self reviews.
ROSTERS = {
    "reviewers": b"ReviewerName,ReviewerEmail\nRana,rana@example.edu\nCarol,carol@example.edu\n",
    "reviewees": b"RevieweeName,RevieweeEmail\nRana,rana@example.edu\nCarol,carol@example.edu\n",
}


def _generated(api: httpx.Client, live_server: LiveServer, session_id: int) -> None:
    for kind, body in ROSTERS.items():
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text
    pin_full_matrix(live_server.database_url, session_id)
    generated = api.post(
        f"/operator/sessions/{session_id}/assignments/generate", follow_redirects=False
    )
    assert generated.status_code == 303, generated.text


def _exclude_one_self_review(database_url: str, session_id: int) -> None:
    """Leave the instrument mixed: Rana's self review out, Carol's in. The
    page's row expander can do this too; the database is the short way."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Assignment, Reviewer

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            rana = db.execute(
                select(Reviewer).where(
                    Reviewer.session_id == session_id, Reviewer.name == "Rana"
                )
            ).scalar_one()
            row = db.execute(
                select(Assignment).where(
                    Assignment.session_id == session_id,
                    Assignment.reviewer_id == rana.id,
                    Assignment.is_self_review.is_(True),
                )
            ).scalar_one()
            row.include = False
            db.commit()
    finally:
        engine.dispose()


def _bg(locator: Locator) -> str:
    return locator.evaluate("el => getComputedStyle(el).backgroundColor")


def test_the_self_review_chip_is_dark_light_or_amber(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _generated(api, live_server, session_id)
    page.goto(f"/operator/sessions/{session_id}/assignments")
    name_chip = page.locator("label.tag-chip:has([data-filter-instrument])")
    chip = page.locator("[data-self-review-chip]")
    expect(chip).to_have_text("Include 2 self reviews")
    dark = _bg(name_chip)
    assert _bg(chip) == dark

    chip.click()
    page.wait_for_load_state()
    expect(chip).to_have_text("Include 0 self reviews")
    light = _bg(chip)
    assert light != dark

    chip.click()
    page.wait_for_load_state()
    expect(chip).to_have_text("Include 2 self reviews")

    _exclude_one_self_review(live_server.database_url, session_id)
    page.reload()
    expect(chip).to_have_text("Include 1 self review")
    assert "pill-empty" in (chip.get_attribute("class") or "")
    assert _bg(chip) not in (dark, light)
    # A click from the mixed state includes them all.
    chip.click()
    page.wait_for_load_state()
    expect(chip).to_have_text("Include 2 self reviews")
    assert _bg(chip) == dark


def test_the_instrument_name_chip_filters_the_preview_table(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _generated(api, live_server, session_id)
    page.goto(f"/operator/sessions/{session_id}/assignments")
    rows = page.locator("tr[data-row-instrument]")
    expect(rows.first).to_be_visible()
    name_chip = page.locator("label.tag-chip:has([data-filter-instrument])")
    on = _bg(name_chip)

    name_chip.click()
    expect(rows.first).to_be_hidden()
    assert _bg(name_chip) != on

    name_chip.click()
    expect(rows.first).to_be_visible()
    assert _bg(name_chip) == on
