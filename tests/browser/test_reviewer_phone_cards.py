"""Segment 20Q rung 3 — on a phone the reviewer surface's response table
is a list of cards: a row is a card, each answer a label over its box,
the header row hidden, and nothing scrolls sideways. At desktop width
the table is untouched."""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Page, ViewportSize, expect

from ._builder import REVIEWER_EMAIL, activate, seed_rosters, session_pk
from .conftest import LiveServer, app_url

_PHONE: ViewportSize = {"width": 390, "height": 844}


def _set_instrument(database_url: str, session_id: str, **attrs: object) -> None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            instrument = db.execute(
                select(Instrument).where(
                    Instrument.session_id == session_pk(database_url, session_id)
                )
            ).scalar_one()
            for name, value in attrs.items():
                setattr(instrument, name, value)
            db.commit()
    finally:
        engine.dispose()


def _surface(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
    size: ViewportSize = _PHONE,
    **instrument: object,
) -> Page:
    session_id = new_session()
    seed_rosters(api, session_id)
    if instrument:
        _set_instrument(live_server.database_url, session_id, **instrument)
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.set_viewport_size(size)
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    expect(reviewer.locator("table.rs-table")).to_be_visible()
    return reviewer


def _no_sideways_scroll(page: Page) -> None:
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0, f"the page scrolls {overflow}px sideways"
    # The response table's own wrapper; the visibility grid's is rung 4's.
    for scroller in page.locator(".table-scroll:has(> table.rs-table)").all():
        spill = scroller.evaluate("el => el.scrollWidth - el.clientWidth")
        assert spill <= 0, f"the response table scrolls {spill}px sideways"


def _label(page: Page, selector: str) -> str:
    return page.locator(selector).first.evaluate(
        "td => getComputedStyle(td, '::before').content.replace(/^\"|\"$/g, '')"
    )


def test_a_row_is_a_card_with_a_label_over_each_answer(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    reviewer = _surface(page_as, api, live_server, new_session)
    expect(reviewer.locator("table.rs-table > thead")).to_be_hidden()
    row = reviewer.locator("table.rs-table > tbody > tr").first
    assert row.evaluate("tr => getComputedStyle(tr).display") == "block"
    assert _label(reviewer, "table.rs-table td[data-label^='Rating']").startswith("Rating")
    # The label sits over its box, and the box spans the card.
    cell = reviewer.locator("table.rs-table td[data-label^='Comments']").first
    box = cell.locator("textarea, input").first
    cell_box, input_box = cell.bounding_box(), box.bounding_box()
    assert cell_box and input_box
    assert input_box["y"] > cell_box["y"] + 8
    assert input_box["width"] > cell_box["width"] - 2
    _no_sideways_scroll(reviewer)


def test_stacked_and_group_tables_are_cards_too(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    stacked = _surface(page_as, api, live_server, new_session, response_layout="stacked")
    field = stacked.locator(".rs-stack-field").first
    label = field.locator(".rs-stack-label").bounding_box()
    box = field.locator(".rs-stack-input").bounding_box()
    assert label and box and box["y"] >= label["y"] + label["height"] - 1  # under it
    _no_sideways_scroll(stacked)

    group = _surface(page_as, api, live_server, new_session, group_kind="r1")
    row = group.locator("table.rs-group-table > tbody > tr").first
    assert row.evaluate("tr => getComputedStyle(tr).display") == "block"
    _no_sideways_scroll(group)


def test_a_wide_column_width_does_not_force_a_scroll(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """An operator's saved pixel width (here the identity column's) has
    no column to act on in a card."""
    reviewer = _surface(page_as, api, live_server, new_session, column_widths={"identity": 600})
    _no_sideways_scroll(reviewer)


def test_the_desktop_table_is_untouched(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    reviewer = _surface(
        page_as, api, live_server, new_session, size={"width": 1400, "height": 1000}
    )
    expect(reviewer.locator("table.rs-table > thead")).to_be_visible()
    row = reviewer.locator("table.rs-table > tbody > tr").first
    assert row.evaluate("tr => getComputedStyle(tr).display") == "table-row"
    assert _label(reviewer, "table.rs-table td[data-label]") == "none"
