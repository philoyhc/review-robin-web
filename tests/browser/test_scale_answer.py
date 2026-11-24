"""The scale answer (segment 20P Item 1), on rung 2's scaffold page: a
bounded number box becomes a line with a circle. It snaps with a stop per
point up to 11 points and slides past that, keeping its box; it answers to
clicks, the keys and *clear*, and a disabled one is read-only. The box
underneath keeps the value that a save would send."""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect

from ._builder import (
    REVIEWER_EMAIL,
    activate,
    branch_rating,
    make_rating_a_scale,
    seed_rosters,
)
from .conftest import LiveServer, app_url

_PREVIEW = "/operator/sys-admin/scale-preview"


def _open(page: Page) -> Page:
    page.set_viewport_size({"width": 1400, "height": 1000})
    page.goto(app_url(_PREVIEW))
    expect(page.locator("[data-rs-scale-widget]").first).to_be_visible()
    return page


def test_a_snap_scale_has_a_stop_per_point_and_answers_click_keys_and_clear(page: Page) -> None:
    _open(page)
    box = page.locator('input[name="p1"]')
    widget = page.locator('[data-rs-scale-widget="snap"]').first
    thumb = widget.get_by_role("slider")
    expect(widget.locator(".sc-stop")).to_have_count(5)
    expect(widget.locator(".sc-label")).to_have_text(["Poor", "Fair", "Excellent"])
    expect(thumb).to_have_attribute("aria-valuetext", "not answered")
    expect(widget.locator(".sc-said")).to_have_text("Not answered")
    # A click near the fourth stop snaps to 4.
    line = widget.locator(".sc-line")
    bounds = line.bounding_box()
    assert bounds is not None
    line.click(position={"x": bounds["width"] * 0.74, "y": bounds["height"] / 2})
    expect(box).to_have_value("4")
    expect(thumb).to_have_attribute("aria-valuetext", "4 of 1 to 5")
    thumb.press("ArrowRight")
    expect(box).to_have_value("5")
    thumb.press("ArrowRight")  # clamped at Max
    expect(box).to_have_value("5")
    thumb.press("Home")
    expect(box).to_have_value("1")
    widget.locator(".sc-clear").click()
    expect(box).to_have_value("")
    thumb.press("ArrowLeft")  # the first press on an empty scale picks Min
    expect(box).to_have_value("1")
    thumb.press("Delete")
    expect(box).to_have_value("")
    # The snapped box is out of the tab order, its value still submitted.
    expect(box).to_have_attribute("tabindex", "-1")


def test_eleven_decimal_points_snap_and_a_disabled_scale_is_read_only(page: Page) -> None:
    _open(page)
    tenths = page.locator('[data-rs-scale-widget="snap"]').nth(1)
    expect(tenths.locator(".sc-stop")).to_have_count(11)
    expect(tenths.get_by_role("slider")).to_have_attribute("aria-valuenow", "0.7")
    tenths.get_by_role("slider").press("ArrowUp")
    expect(page.locator('input[name="p2"]')).to_have_value("0.8")
    closed = page.locator('[data-rs-scale-widget="snap"]').nth(2)
    expect(closed).to_have_class(re.compile(r"\bsc-off\b"))
    expect(closed.get_by_role("slider")).to_have_attribute("aria-disabled", "true")
    expect(closed.locator(".sc-clear")).to_be_disabled()
    closed.locator(".sc-line").click(force=True)
    expect(page.locator('input[name="p3"]')).to_have_value("5")


def test_a_slide_keeps_its_box_and_each_moves_the_other(page: Page) -> None:
    _open(page)
    slide = page.locator('[data-rs-scale-widget="slide"]').nth(1)
    box = slide.locator('input[name="p5"]')
    thumb = slide.get_by_role("slider")
    expect(slide.locator(".sc-stop")).to_have_count(0)
    expect(slide.locator(".sc-num")).to_have_text(["1000", "1500", "2000"])
    expect(box).to_be_visible()
    expect(thumb).to_have_attribute("aria-valuenow", "1450")
    box.fill("1999")
    expect(thumb).to_have_attribute("aria-valuenow", "1999")
    thumb.press("PageDown")  # ten steps
    expect(box).to_have_value("1989")
    thumb.press("End")
    expect(box).to_have_value("2000")


def test_without_script_the_box_remains(page_as: Callable[..., Page]) -> None:
    page = page_as(javascript=False)
    page.goto(app_url(_PREVIEW))
    expect(page.locator('input[name="p1"]')).to_be_visible()
    expect(page.locator("[data-rs-scale-widget]")).to_have_count(0)


def test_each_scale_sits_in_a_column_that_resizes_down_to_its_minimum(page: Page) -> None:
    """The author's ask (2026-11-24): each scale in a table column, the
    columns resized as Band 2's are, never below what the scale states."""
    _open(page)
    col = page.locator('col[data-col-key="merit"]')
    minimum = int(col.get_attribute("data-min") or "0")
    widget = page.locator('[data-rs-scale-widget="snap"]').first
    assert minimum >= int(widget.get_attribute("data-rs-scale-min") or "0")
    handle = page.locator('.new-model-band2-resize-handle[data-col-key="merit"]')

    def drag(dx: float) -> None:
        box = handle.bounding_box()
        assert box is not None
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + dx, y, steps=5)
        page.mouse.up()

    def stops_span() -> float:
        first = widget.locator(".sc-stop").first.bounding_box()
        last = widget.locator(".sc-stop").last.bounding_box()
        assert first is not None and last is not None
        return last["x"] - first["x"]

    narrow = stops_span()
    drag(160)
    assert int(col.evaluate("c => parseInt(c.style.width, 10)")) >= minimum + 150
    assert stops_span() > narrow + 100  # the stops spread with the column
    drag(-1000)  # far past the minimum
    assert int(col.evaluate("c => parseInt(c.style.width, 10)")) == minimum
    # At its minimum the scale is whole: the last stop inside its cell.
    cell = widget.locator("xpath=ancestor::td[1]").bounding_box()
    last = widget.locator(".sc-stop").last.bounding_box()
    assert cell is not None and last is not None
    assert last["x"] + last["width"] <= cell["x"] + cell["width"]
    # And it still answers.
    widget.locator(".sc-stop").nth(2).click(force=True)
    expect(page.locator('input[name="p1"]')).to_have_value("3")


def test_a_scale_field_on_the_reviewer_surface_saves_what_it_shows(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """Rung 3a: a field set to a scale draws one on the reviewer surface;
    a click there marks the page unsaved, Save keeps the value, and the
    reload draws the circle where it was left."""
    session_id = new_session()
    seed_rosters(api, session_id)
    make_rating_a_scale(live_server.database_url, session_id)
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.set_viewport_size({"width": 1400, "height": 1000})
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    widget = reviewer.locator('[data-rs-scale-widget="snap"]').first
    expect(widget.locator(".sc-stop")).to_have_count(5)
    expect(widget.locator(".sc-label")).to_have_text(["Poor", "", "Excellent"])
    widget.locator(".sc-stop").nth(3).click(force=True)
    box = reviewer.locator("[name^='response['][name$='][rating]']")
    expect(box).to_have_value("4")
    with reviewer.expect_response(lambda r: r.request.method == "POST"):
        reviewer.locator("[data-rs-save]:visible").first.click()
    reviewer.wait_for_load_state()
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    widget = reviewer.locator('[data-rs-scale-widget="snap"]').first
    expect(widget.get_by_role("slider")).to_have_attribute("aria-valuenow", "4")


def test_a_governed_scale_follows_its_branch(
    page: Page,
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """A scale whose box a branch disables and enables after load (Codex
    on #4193): closed it takes no input, open it answers, and closed
    again it stops."""
    session_id = new_session()
    seed_rosters(api, session_id)
    branch_rating(page, session_id)  # "Why" opens at Rating >= 4
    make_rating_a_scale(live_server.database_url, session_id, "", label="Why")
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.set_viewport_size({"width": 1400, "height": 1000})
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    rating = reviewer.locator("[name^='response['][name$='][rating]']")
    why = reviewer.locator("[name^='response['][name$='][why]']")
    widget = reviewer.locator('[data-rs-scale-widget="snap"]').first
    thumb = widget.get_by_role("slider")
    expect(widget).to_have_class(re.compile(r"\bsc-off\b"))
    expect(thumb).to_have_attribute("aria-disabled", "true")
    widget.locator(".sc-stop").nth(1).click(force=True)
    expect(why).to_have_value("")

    rating.fill("5")
    expect(why).to_be_enabled()
    expect(widget).not_to_have_class(re.compile(r"\bsc-off\b"))
    expect(widget.locator(".sc-clear")).to_be_enabled()
    widget.locator(".sc-stop").nth(1).click(force=True)
    expect(why).to_have_value("2")

    rating.fill("2")
    expect(why).to_be_disabled()
    expect(thumb).to_have_attribute("aria-disabled", "true")
    thumb.press("ArrowRight", timeout=2000)
    expect(why).to_have_value("2")


def test_a_tiny_decimal_step_keeps_its_places(page: Page) -> None:
    """A step JavaScript writes in scientific notation (``1e-7``) still
    numbers its stops and answers to seven places (Codex on #4193)."""
    _open(page)
    page.evaluate(
        """() => {
          const box = document.createElement("input");
          box.type = "number"; box.name = "tiny"; box.min = "0"; box.max = "0.000001";
          box.dataset.rsStep = "1e-7"; box.setAttribute("data-rs-scale", "");
          const cell = document.createElement("div"); cell.id = "tiny-cell";
          cell.appendChild(box); document.body.appendChild(cell);
          window.rrwScaleEnhance(cell);
        }"""
    )
    widget = page.locator("#tiny-cell [data-rs-scale-widget='snap']")
    expect(widget.locator(".sc-num").nth(3)).to_have_text("0.0000003")
    widget.get_by_role("slider").press("End")
    expect(page.locator('input[name="tiny"]')).to_have_value("0.0000010")


def test_a_narrow_saved_column_widens_to_hold_its_scale(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """Codex on #4193: a column sized for a number box (here a saved
    60px width, which makes the table fixed-layout) widens to the
    scale's minimum rather than letting it paint over the next cell."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument, InstrumentResponseField

    from ._builder import session_pk

    session_id = new_session()
    seed_rosters(api, session_id)
    make_rating_a_scale(live_server.database_url, session_id)
    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            instrument = db.execute(
                select(Instrument).where(
                    Instrument.session_id == session_pk(live_server.database_url, session_id)
                )
            ).scalar_one()
            rating = db.execute(
                select(InstrumentResponseField).where(
                    InstrumentResponseField.instrument_id == instrument.id,
                    InstrumentResponseField.label == "Rating",
                )
            ).scalar_one()
            instrument.column_widths = {f"rf_{rating.id}": 60}
            db.commit()
    finally:
        engine.dispose()
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.set_viewport_size({"width": 1400, "height": 1000})
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    widget = reviewer.locator('[data-rs-scale-widget="snap"]').first
    expect(widget).to_be_visible()
    cell = widget.locator("xpath=ancestor::td[1]")
    next_cell = cell.locator("xpath=following-sibling::td[1]")
    w, c, n = widget.bounding_box(), cell.bounding_box(), next_cell.bounding_box()
    assert w is not None and c is not None and n is not None
    assert w["x"] + w["width"] <= c["x"] + c["width"] + 1
    assert w["x"] + w["width"] <= n["x"] + 1
