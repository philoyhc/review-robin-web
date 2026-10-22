"""A String answer box fits its text (segment 19X Item 10): it starts
one line high at a maximum of 50 or fewer characters and two lines
otherwise, grows with what the reviewer types, shows a saved answer
whole, and takes no resize handle. A one-line box takes no line break.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Locator, Page, expect

from ._builder import REVIEWER_EMAIL, activate, seed_rosters, session_pk
from .conftest import LiveServer, app_url

_BOX = "table textarea.rs-answer"
_LONG = "They led the planning and kept the team to its deadlines. " * 10


def _set_comments(database_url: str, session_id: str, max_length: int) -> None:
    """The seeded Comments field's maximum, written directly."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument, InstrumentResponseField

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            field = db.execute(
                select(InstrumentResponseField)
                .join(Instrument, Instrument.id == InstrumentResponseField.instrument_id)
                .where(
                    Instrument.session_id == session_pk(database_url, session_id),
                    InstrumentResponseField.label == "Comments",
                )
            ).scalar_one()
            field.validation = {**(field.validation or {}), "max_length": max_length}
            db.commit()
    finally:
        engine.dispose()


def _box(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
    max_length: int | None = None,
) -> tuple[Page, Locator]:
    session_id = new_session()
    seed_rosters(api, session_id)
    if max_length is not None:
        _set_comments(live_server.database_url, session_id, max_length)
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.set_viewport_size({"width": 1400, "height": 1000})
    reviewer.goto(app_url(f"/me/sessions/{session_id}"))
    box = reviewer.locator(_BOX).first
    expect(box).to_be_visible()
    return reviewer, box


def _fit(box: Locator) -> dict:
    """The box's height, its hidden overflow, its resize handle, and its
    height in lines: measured against an empty one-row copy beside it,
    since a computed ``line-height`` of ``normal`` has no number."""
    return box.evaluate(
        """el => {
             const one = el.cloneNode(false);
             one.rows = 1; one.value = ""; one.style.height = "auto";
             one.removeAttribute("data-fit-on");
             el.parentNode.appendChild(one);
             const pad = h => h - parseFloat(getComputedStyle(el).paddingTop)
                                - parseFloat(getComputedStyle(el).paddingBottom);
             const line = pad(one.clientHeight);
             one.remove();
             return {height: el.getBoundingClientRect().height,
                     hidden: el.scrollHeight - el.clientHeight,
                     resize: getComputedStyle(el).resize,
                     lines: Math.round(pad(el.clientHeight) / line)};
           }"""
    )


def test_a_long_answer_box_starts_two_lines_high_and_grows(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    reviewer, box = _box(page_as, api, live_server, new_session)
    start = _fit(box)
    assert start["lines"] == 2 and start["resize"] == "none", start

    box.fill(_LONG)
    grown = _fit(box)
    assert grown["height"] > start["height"] * 2 and grown["hidden"] <= 1, grown

    box.fill("Short again.")
    assert abs(_fit(box)["height"] - start["height"]) < 1


def test_a_saved_long_answer_shows_whole_on_load(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    reviewer, box = _box(page_as, api, live_server, new_session)
    box.fill(_LONG)
    with reviewer.expect_navigation():
        reviewer.locator("[data-rs-save]").first.click()
    box = reviewer.locator(_BOX).first
    expect(box).to_have_value(_LONG.strip())
    fit = _fit(box)
    assert fit["lines"] > 2 and fit["hidden"] <= 1, fit


def test_a_short_answer_box_is_one_line_and_takes_no_line_break(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    reviewer, box = _box(page_as, api, live_server, new_session, max_length=50)
    assert box.get_attribute("data-fit-box") == "one-line"
    assert _fit(box)["lines"] == 1

    box.click()
    box.press_sequentially("one")
    box.press("Enter")
    box.press_sequentially("two")
    expect(box).to_have_value("onetwo")

    # A paste lands as one inserted text with its breaks in it.
    box.fill("")
    reviewer.keyboard.insert_text("first\nsecond\r\nthird")
    expect(box).to_have_value("first second third")


def test_a_long_answer_box_keeps_its_line_breaks(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    reviewer, box = _box(page_as, api, live_server, new_session)
    box.click()
    box.press_sequentially("one")
    box.press("Enter")
    box.press_sequentially("two")
    expect(box).to_have_value("one\ntwo")


def test_a_one_line_box_sits_level_with_the_number_input(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    reviewer, box = _box(page_as, api, live_server, new_session, max_length=50)
    number = reviewer.locator('table input[type="number"]').first
    height = number.evaluate("el => el.getBoundingClientRect().height")
    assert abs(_fit(box)["height"] - height) <= 2, (_fit(box), height)
