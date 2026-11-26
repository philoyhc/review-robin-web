"""Segment 20Q rung 3 — on a phone the reviewer surface's response table
is a list of cards: a row is a card, each answer a label over its box,
the header row hidden, and nothing scrolls sideways. At desktop width
the table is untouched."""

from __future__ import annotations

import re
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
    before_activate: Callable[[str, str], None] | None = None,
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
    if before_activate is not None:
        before_activate(live_server.database_url, session_id)
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
    expect(reviewer.locator("table.vp-grid > thead").first).to_be_visible()
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


def _long_address(database_url: str, session_id: str) -> None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Reviewee

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            for reviewee in db.execute(
                select(Reviewee).where(Reviewee.session_id == session_pk(database_url, session_id))
            ).scalars():
                reviewee.email_or_identifier = (
                    "christopher.alexander.montgomery-whitfield@departmentofexamples.example.edu"
                )
            db.commit()
    finally:
        engine.dispose()


def test_the_rest_of_the_surface_fits_a_phone(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """Rung 4: the visibility grid stacks, a window's label beside its
    pill; the action row's buttons share the width; a long address
    breaks inside its card. Nothing scrolls sideways, the grid included."""
    reviewer = _surface(page_as, api, live_server, new_session, before_activate=_long_address)
    grid = reviewer.locator("table.vp-grid").first
    expect(grid.locator("thead")).to_be_hidden()
    window = grid.locator("td[data-label='Session ongoing']").first
    label = window.evaluate(
        "td => getComputedStyle(td, '::before').content.replace(/^\"|\"$/g, '')"
    )
    assert label == "Session ongoing"
    pill = window.locator(".pill").bounding_box()
    cell = window.bounding_box()
    assert pill and cell and pill["height"] < cell["height"] + 1  # one line, beside its label
    spill = reviewer.locator(".table-scroll:has(> table.vp-grid)").first.evaluate(
        "el => el.scrollWidth - el.clientWidth"
    )
    assert spill <= 0, f"the visibility grid scrolls {spill}px sideways"

    buttons = reviewer.locator(".rs-action-row-controls").first.locator(".btn")
    widths = [buttons.nth(i).bounding_box() for i in range(buttons.count())]
    assert all(widths) and len(widths) == 3
    sizes = [w["width"] for w in widths if w]
    assert max(sizes) - min(sizes) < 1  # the three share the row

    expect(reviewer.locator("table.rs-table code").first).to_contain_text("montgomery")
    _no_sideways_scroll(reviewer)


def test_the_instruments_page_grid_keeps_its_columns_in_a_narrow_window(
    page: Page, new_session: Callable[[], str]
) -> None:
    """Codex on #4206: the stacked visibility grid is the reviewer
    surface's; the Instruments page's own grids, with no labels on their
    cells, keep their header row in a window under 640 px."""
    from ._builder import open_unlocked

    session_id = new_session()
    page.set_viewport_size({"width": 600, "height": 900})
    card = open_unlocked(page, session_id)
    grids = card.locator("table.vp-grid")
    assert grids.count() > 0
    for i in range(grids.count()):
        grid = grids.nth(i)
        if grid.is_visible():
            expect(grid.locator("thead")).to_be_visible()
            assert grid.evaluate("t => getComputedStyle(t).display") == "table"


def test_a_long_unbroken_value_wraps_inside_its_card(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """Codex on #4207: a card lets its table show outside the scroll box,
    so a read-only value with no break in it (a pasted URL on the summary
    or results page) must wrap inside its cell rather than widen the
    page. Put one in a card's cell, as those pages render it."""
    reviewer = _surface(page_as, api, live_server, new_session)
    reviewer.locator("table.rs-table td[data-label]").first.evaluate(
        "td => { td.textContent = 'https://example.edu/' + 'x'.repeat(240); }"
    )
    _no_sideways_scroll(reviewer)


def test_the_bottom_action_row_floats_on_a_phone(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """Rung 6 (author, 2026-11-25): on a phone the bottom Save / Cancel /
    Submit row pins to the foot of the screen, but only once the top row
    has scrolled out of view, so the two sets never show together; on a
    desktop it stays in its place."""
    reviewer = _surface(page_as, api, live_server, new_session, size={"width": 390, "height": 420})
    row = reviewer.locator(".rs-action-row:not(.rs-action-row-top)")
    reviewer.evaluate("() => window.scrollTo(0, 0)")
    expect(reviewer.locator(".rs-action-row-top")).to_be_in_viewport()
    expect(row).not_to_have_class(re.compile(r"rs-action-row-float"))
    expect(row).not_to_be_in_viewport()  # in its place, below the fold

    top = reviewer.locator(".rs-action-row-top").bounding_box()
    assert top
    reviewer.evaluate(f"() => window.scrollTo(0, {top['y'] + top['height'] + 20})")
    expect(row).to_have_class(re.compile(r"rs-action-row-float"))
    assert row.evaluate("r => getComputedStyle(r).position") == "sticky"
    box = row.bounding_box()
    assert box and abs(box["y"] + box["height"] - 420) < 1  # at the foot of the screen
    expect(row.get_by_role("button", name="Save")).to_be_visible()

    desktop = _surface(page_as, api, live_server, new_session, size={"width": 1400, "height": 1000})
    desktop_row = desktop.locator(".rs-action-row:not(.rs-action-row-top)")
    assert desktop_row.evaluate("r => getComputedStyle(r).position") == "static"


def test_the_action_buttons_center_their_labels(page_as, api, live_server, new_session) -> None:
    """On a phone Save, Cancel and Submit share a row and its height;
    Cancel is a link, whose text sat at the top of a box stretched taller
    than it (author's phone, 2026-11-26). Each centers its label down."""
    reviewer = _surface(page_as, api, live_server, new_session)
    # A row taller than the labels, as a wrapped label makes it.
    reviewer.add_style_tag(content=".rs-action-row-controls > .btn { min-height: 60px; }")
    offsets = reviewer.evaluate(
        """() => [...document.querySelectorAll('.rs-action-row-top .rs-action-row-controls > .btn')]
             .map(b => {
               const r = document.createRange();
               r.selectNodeContents(b);
               const t = r.getBoundingClientRect(), box = b.getBoundingClientRect();
               return [b.textContent.trim(),
                       Math.abs((t.top + t.bottom) / 2 - (box.top + box.bottom) / 2)];
             })"""
    )
    assert [name for name, _ in offsets] == ["Save", "Cancel", "Submit"]
    assert all(off < 2 for _, off in offsets), offsets
