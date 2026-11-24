"""Segment 20Q rung 3 — on a phone the reviewer surface's response table
is a list of cards: a row is a card, each answer a label over its box,
the header row hidden, and nothing scrolls sideways. At desktop width
the table is untouched."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from playwright.sync_api import Page, ViewportSize, expect

from ._builder import REVIEWER_EMAIL, activate, make_rating_a_scale, seed_rosters, session_pk
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
    scale: dict[str, float] | None = None,
    **instrument: object,
) -> Page:
    session_id = new_session()
    seed_rosters(api, session_id)
    if scale is not None:
        make_rating_a_scale(
            live_server.database_url,
            session_id,
            "Poor||Excellent",
            lo=scale["lo"],
            hi=scale["hi"],
            step=scale["step"],
        )
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


@pytest.mark.parametrize("layout", ["across", "stacked"])
@pytest.mark.parametrize(
    "bounds",
    [{"lo": 0, "hi": 10, "step": 1}, {"lo": 1, "hi": 100, "step": 1}],
    ids=["snap-11-points", "slide"],
)
def test_a_scale_fits_its_card(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
    layout: str,
    bounds: dict[str, float],
) -> None:
    """Codex on #4203: a scale states a desktop minimum width (362 px
    for 11 points) that a phone's card has not got; in a card it takes
    the card's width instead, and nothing scrolls sideways."""
    reviewer = _surface(
        page_as, api, live_server, new_session, scale=bounds, response_layout=layout
    )
    widget = reviewer.locator("table.rs-table [data-rs-scale-widget]").first
    expect(widget).to_be_visible()
    card = reviewer.locator("table.rs-table > tbody > tr").first.bounding_box()
    box = widget.bounding_box()
    assert card and box
    assert box["x"] >= card["x"] and box["x"] + box["width"] <= card["x"] + card["width"] + 0.5
    _no_sideways_scroll(reviewer)


def test_a_slide_box_sits_under_its_full_width_scale(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """Author, 2026-11-24: in a card a slide's line takes the card's
    width, and its box drops to a row of its own under the scale and its
    labels, above *Not answered*, at its desktop width."""
    reviewer = _surface(
        page_as, api, live_server, new_session, scale={"lo": 1, "hi": 100, "step": 1}
    )
    widget = reviewer.locator("table.rs-table .sc.sc-slide").first
    line = widget.locator(".sc-line").bounding_box()
    labels = widget.locator(".sc-labels").bounding_box()
    box = widget.locator("input[type='number']").bounding_box()
    foot = widget.locator(".sc-foot").bounding_box()
    whole = widget.bounding_box()
    assert line and labels and box and foot and whole
    assert line["width"] > whole["width"] * 0.8  # the line spans the card
    assert box["y"] >= labels["y"] + labels["height"] - 1  # under the labels
    assert foot["y"] >= box["y"] + box["height"] - 1  # above Not answered
    assert abs(box["width"] - 88) < 1
