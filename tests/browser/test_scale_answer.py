"""The scale answer (segment 20P Item 1), on the reviewer surface, Band 3
and Band 2: a bounded number box becomes a line with a circle. It snaps with a stop per
point up to 11 points and slides past that, keeping its box; it answers to
clicks, the keys and *clear*, and a closed one is read-only. The box
underneath keeps the value that a save would send."""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
from playwright.sync_api import FloatRect, Locator, Page, expect

from ._builder import (
    REVIEWER_EMAIL,
    activate,
    branch_rating,
    make_rating_a_scale,
    open_unlocked,
    rows,
    save,
    seed_rosters,
)
from .conftest import LiveServer, app_url


def _surface(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
    labels: str = "Poor|Fair|Excellent",
    *,
    javascript: bool = True,
    **bounds: float | str,
) -> tuple[Page, Locator]:
    """A live session whose Rating is a scale (an Integer 1–5 unless
    ``bounds`` say otherwise), opened on the reviewer surface; returns the
    page and Rating's number box."""
    session_id = new_session()
    seed_rosters(api, session_id)
    make_rating_a_scale(live_server.database_url, session_id, labels, **bounds)  # pyright: ignore[reportArgumentType]  -- typed per keyword in the helper
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL, javascript=javascript)
    reviewer.set_viewport_size({"width": 1400, "height": 1000})
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    return reviewer, reviewer.locator("[name^='response['][name$='][rating]']")


def test_a_snap_scale_has_a_stop_per_point_and_answers_click_keys_and_clear(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    page, box = _surface(page_as, api, live_server, new_session)
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


def test_eleven_decimal_points_snap(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """0 to 1 by 0.1 is eleven points, so it snaps; a closed scale's
    read-only state is covered by ``test_a_governed_scale_follows_its_branch``."""
    page, box = _surface(
        page_as, api, live_server, new_session, "", data_type="Decimal", lo=0, hi=1, step=0.1
    )
    tenths = page.locator('[data-rs-scale-widget="snap"]').first
    expect(tenths.locator(".sc-stop")).to_have_count(11)
    expect(tenths.locator(".sc-num").nth(7)).to_have_text("0.7")
    tenths.locator(".sc-stop").nth(7).click(force=True)
    expect(box).to_have_value("0.7")
    tenths.get_by_role("slider").press("ArrowUp")
    expect(box).to_have_value("0.8")


def test_a_slide_keeps_its_box_and_each_moves_the_other(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    page, box = _surface(page_as, api, live_server, new_session, "", lo=1000, hi=2000, step=1)
    slide = page.locator('[data-rs-scale-widget="slide"]').first
    thumb = slide.get_by_role("slider")
    expect(slide.locator(".sc-stop")).to_have_count(0)
    expect(slide.locator(".sc-num")).to_have_text(["1000", "1500", "2000"])
    expect(box).to_be_visible()
    box.fill("1999")
    expect(thumb).to_have_attribute("aria-valuenow", "1999")
    # The box shows the value, so the foot doesn't repeat it.
    expect(slide.locator(".sc-said")).to_have_text("")
    thumb.press("PageDown")  # ten steps
    expect(box).to_have_value("1989")
    thumb.press("End")
    expect(box).to_have_value("2000")


def test_without_script_the_box_remains(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    page, box = _surface(page_as, api, live_server, new_session, javascript=False)
    expect(box).to_be_visible()
    expect(page.locator("[data-rs-scale-widget]")).to_have_count(0)


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
    thumb = widget.get_by_role("slider")
    expect(thumb).to_have_attribute("aria-valuenow", "4")
    # An arrow key saves as the box would.
    thumb.press("ArrowLeft")
    expect(box).to_have_value("3")
    with reviewer.expect_response(lambda r: r.request.method == "POST"):
        reviewer.locator("[data-rs-save]:visible").first.click()
    reviewer.wait_for_load_state()
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    widget = reviewer.locator('[data-rs-scale-widget="snap"]').first
    expect(widget.get_by_role("slider")).to_have_attribute("aria-valuenow", "3")
    # And *clear*, named for its field, saves the field unanswered.
    clear = widget.get_by_role("button", name=re.compile(r"^Clear Rating"))
    clear.click()
    expect(box).to_have_value("")
    with reviewer.expect_response(lambda r: r.request.method == "POST"):
        reviewer.locator("[data-rs-save]:visible").first.click()
    reviewer.wait_for_load_state()
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    expect(reviewer.locator("[name^='response['][name$='][rating]']")).to_have_value("")
    expect(
        reviewer.locator('[data-rs-scale-widget="snap"]').first.get_by_role("slider")
    ).to_have_attribute("aria-valuetext", "not answered")


def test_a_governed_scale_follows_its_branch(
    page: Page,
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """A scale whose box a branch disables and enables after load (the
    cold read of Item 1): closed it takes no input, open it answers, and
    closed again it stops."""
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


def test_a_slide_answers_a_drag_a_click_and_clear(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """The plan's rung 4: drag the circle along a slide, click its line,
    and clear it."""
    page, box = _surface(page_as, api, live_server, new_session, "", lo=0, hi=100, step=1)
    slide = page.locator('[data-rs-scale-widget="slide"]').first
    line = slide.locator(".sc-line")
    bounds = line.bounding_box()
    assert bounds is not None
    y = bounds["y"] + bounds["height"] / 2
    page.mouse.move(bounds["x"] + 2, y)
    page.mouse.down()
    page.mouse.move(bounds["x"] + bounds["width"] * 0.5, y, steps=8)
    page.mouse.up()
    assert abs(int(box.input_value()) - 50) <= 2
    line.click(position={"x": 0, "y": bounds["height"] / 2})
    expect(box).to_have_value("0")
    slide.locator(".sc-clear").click()
    expect(box).to_have_value("")


def test_band_3_chooses_a_scale_and_band_2_previews_it(
    page: Page, api: httpx.Client, new_session: Callable[[], str]
) -> None:
    """Rung 3b: Integer (scale) on Rating (1–5) shows its label line and
    "5 points · snaps", Band 2's preview draws the scale in a column no
    narrower than the scale's minimum, and Save keeps it across a reload."""
    session_id = new_session()
    seed_rosters(api, session_id)
    page.set_viewport_size({"width": 1500, "height": 1100})
    card = open_unlocked(page, session_id)
    rating = rows(card).first
    rating.locator("[data-new-model-rf-data-type]").select_option(label="Integer (scale)")
    line = rating.locator("[data-new-model-rf-scale-line]")
    expect(line).to_be_visible()
    expect(line.locator("[data-new-model-rf-scale-summary]")).to_have_text("5 points · snaps")
    rating.locator('[data-new-model-rf-scale-label="start"]').fill("Poor")
    rating.locator('[data-new-model-rf-scale-label="end"]').fill("Excellent")
    preview = card.locator("[data-new-model-band2-preview]")
    widget = preview.locator('[data-rs-scale-widget="snap"]').first
    expect(widget).to_be_visible()
    expect(widget.locator(".sc-stop")).to_have_count(5)
    expect(widget.locator(".sc-label")).to_have_text(["Poor", "", "Excellent"])
    expect(preview.locator(".rs-constraints")).to_contain_text("as a scale")
    cell = widget.locator("xpath=ancestor::td[1]").bounding_box()
    assert cell is not None
    assert cell["width"] >= int(widget.get_attribute("data-rs-scale-min") or "0")
    # A bound that breaks the scale says why, and the preview keeps the last good one.
    rating.locator('[data-new-model-rf-bound="step"]').fill("3")
    expect(line.locator("[data-new-model-rf-scale-summary]")).to_have_text(
        "Max must be Min plus a whole number of Steps."
    )
    expect(rating).to_have_attribute("data-row-pending", "true")
    rating.locator('[data-new-model-rf-bound="step"]').fill("1")
    save(page, card)
    card = open_unlocked(page, session_id)
    rating = rows(card).first
    expect(rating.locator("[data-new-model-rf-data-type] option:checked")).to_have_text(
        "Integer (scale)"
    )
    expect(rating.locator('[data-new-model-rf-scale-label="end"]')).to_have_value("Excellent")
    expect(
        card.locator('[data-new-model-band2-preview] [data-rs-scale-widget="snap"]')
    ).to_have_count(1)


def test_a_tiny_decimal_step_keeps_its_places(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """A step JavaScript writes in scientific notation (``1e-7``) still
    numbers its stops and answers to seven places (Codex on #4193). Built
    on the page, since a saved step that small renders as ``1e-07``."""
    page, _ = _surface(page_as, api, live_server, new_session)
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


def test_a_scale_governs_a_branch(
    page: Page,
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """A scale is its number box's mode, so as a parent it opens and
    closes its branch as the box does."""
    session_id = new_session()
    seed_rosters(api, session_id)
    branch_rating(page, session_id)  # "Why" opens at Rating >= 4
    make_rating_a_scale(live_server.database_url, session_id)
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.set_viewport_size({"width": 1400, "height": 1000})
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    why = reviewer.locator("[name^='response['][name$='][why]']")
    widget = reviewer.locator('[data-rs-scale-widget="snap"]').first
    expect(why).to_be_disabled()
    widget.locator(".sc-stop").nth(4).click(force=True)
    expect(why).to_be_enabled()
    widget.get_by_role("slider").press("Home")
    expect(why).to_be_disabled()


def test_stacked_scales_take_the_widest_ones_width(
    page: Page,
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """The author's ask (2026-11-24): in the stacked layout every scale
    takes the widest scale's width, so their lines line up."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument

    from ._builder import session_pk

    session_id = new_session()
    seed_rosters(api, session_id)
    branch_rating(page, session_id, op="ge", value="1")  # "Why", open from 1
    make_rating_a_scale(live_server.database_url, session_id)
    long_words = "Not convincing in the least||Convincing beyond any doubt"
    make_rating_a_scale(live_server.database_url, session_id, long_words, label="Why")
    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            instrument = db.execute(
                select(Instrument).where(
                    Instrument.session_id == session_pk(live_server.database_url, session_id)
                )
            ).scalar_one()
            instrument.response_layout = "stacked"
            db.commit()
    finally:
        engine.dispose()
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.set_viewport_size({"width": 1600, "height": 1000})
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    scales = reviewer.locator(".rs-stack-fields [data-rs-scale-widget]")
    expect(scales).to_have_count(2)
    mins = [int(scales.nth(i).get_attribute("data-rs-scale-min") or "0") for i in range(2)]
    assert mins[0] != mins[1]  # the labels make one wider than the other
    widths = [scales.nth(i).evaluate("w => w.getBoundingClientRect().width") for i in range(2)]
    assert abs(widths[0] - widths[1]) < 1
    assert abs(widths[0] - max(mins)) < 1


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


def test_a_stacked_scale_stays_inside_its_cell_with_saved_widths(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """Codex on #4193: a stacked cell with a saved 150px label track and
    a 60px input track grows the input track and the cell to hold the
    scale, rather than letting it run into the next column."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument

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
            instrument.response_layout = "stacked"
            instrument.column_widths = {"stack_label": 150, "stack_input": 60}
            db.commit()
    finally:
        engine.dispose()
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.set_viewport_size({"width": 1400, "height": 1000})
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    widget = reviewer.locator(".rs-stack-fields [data-rs-scale-widget]").first
    expect(widget).to_be_visible()
    cell = widget.locator("xpath=ancestor::td[1]")
    w, c = widget.bounding_box(), cell.bounding_box()
    assert w is not None and c is not None
    assert w["x"] + w["width"] <= c["x"] + c["width"] + 1
    assert w["width"] >= int(widget.get_attribute("data-rs-scale-min") or "0") - 1


def test_band_2_stacked_preview_holds_its_scale_with_saved_widths(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """Codex on #4194: a stacked preview whose saved response track
    (60px) is narrower than the scale grows the track and the column to
    hold it, rather than painting the scale outside its cell."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument

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
            instrument.response_layout = "stacked"
            instrument.column_widths = {"stack_label": 150, "stack_input": 60}
            db.commit()
    finally:
        engine.dispose()
    page.set_viewport_size({"width": 1500, "height": 1100})
    card = open_unlocked(page, session_id)
    widget = card.locator("[data-new-model-band2-preview] .rs-stack-fields [data-rs-scale-widget]")
    expect(widget).to_have_count(1)
    cell = widget.locator("xpath=ancestor::td[1]")
    w, c = widget.bounding_box(), cell.bounding_box()
    assert w is not None and c is not None
    assert w["x"] + w["width"] <= c["x"] + c["width"] + 1


def test_band_2_scale_column_holds_its_scale_inside_the_cell_padding(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """Codex on #4194: with a saved narrow width (a fixed-layout preview)
    a scale column's floor counts the cell's side padding, so the scale
    ends inside its cell rather than ~30px into the next."""
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
    page.set_viewport_size({"width": 1500, "height": 1100})
    card = open_unlocked(page, session_id)
    widget = card.locator("[data-new-model-band2-preview] [data-rs-scale-widget]").first
    expect(widget).to_be_visible()
    cell = widget.locator("xpath=ancestor::td[1]")
    w, c = widget.bounding_box(), cell.bounding_box()
    assert w is not None and c is not None
    assert w["x"] + w["width"] <= c["x"] + c["width"] + 1


def test_a_slides_box_sits_to_the_right_of_its_scale(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """The author's ask (2026-11-24): a slide's number box sits to the
    right of the scale, level with its line, not under it."""
    page, _ = _surface(page_as, api, live_server, new_session, "", lo=0, hi=100, step=1)
    slide = page.locator('[data-rs-scale-widget="slide"]').first
    line = slide.locator(".sc-line").bounding_box()
    numbers = slide.locator(".sc-numbers").bounding_box()
    box = slide.locator('input[type="number"]').bounding_box()
    assert line is not None and numbers is not None and box is not None
    assert box["x"] >= line["x"] + line["width"]
    assert box["y"] < numbers["y"] + numbers["height"]  # level, not below
    assert box["y"] + box["height"] > line["y"]
    # The scale's stated minimum holds the box: inside its cell.
    cell = slide.locator("xpath=ancestor::td[1]").bounding_box()
    assert cell is not None
    assert box["x"] + box["width"] <= cell["x"] + cell["width"] + 1


def test_band_3_scale_row_keeps_its_controls_on_one_line(
    page: Page, api: httpx.Client, new_session: Callable[[], str]
) -> None:
    """The author's ask (2026-11-24): a scale row's own controls stay
    level with Min, Max and Step, and the label boxes take the next
    line under them, "Labels" in front and the summary after."""
    session_id = new_session()
    seed_rosters(api, session_id)
    page.set_viewport_size({"width": 1500, "height": 1100})
    card = open_unlocked(page, session_id)
    rating = rows(card).first
    type_box = rating.locator("[data-new-model-rf-data-type]").bounding_box()
    assert type_box
    type_width = type_box["width"]
    rating.locator("[data-new-model-rf-data-type]").select_option(label="Integer (scale)")

    def box(sel: str) -> FloatRect:
        b = rating.locator(sel).first.bounding_box()
        assert b is not None
        return b

    # The scale line never squeezes the Type menu (author, 2026-11-24):
    # it keeps the width it had before the switch, with long labels and
    # at narrower windows too.
    rating.locator('[data-new-model-rf-scale-label="start"]').fill("Not familiar")
    rating.locator('[data-new-model-rf-scale-label="middle"]').fill("Some observations")
    rating.locator('[data-new-model-rf-scale-label="end"]').fill("Worked together")
    for width in (1500, 1100, 900):
        page.set_viewport_size({"width": width, "height": 1100})
        menu = rating.locator("[data-new-model-rf-data-type]").bounding_box()
        assert menu and abs(menu["width"] - type_width) <= 1, width
    page.set_viewport_size({"width": 1500, "height": 1100})
    top = box('[data-new-model-rf-bound="min"]')["y"]
    for sel in (
        "[data-new-model-rf-name]",
        "[data-new-model-rf-data-type]",
        "[data-new-model-rf-delete]",
    ):
        assert abs(box(sel)["y"] - top) <= 4, sel
    start, end = (
        box('[data-new-model-rf-scale-label="start"]'),
        box('[data-new-model-rf-scale-label="end"]'),
    )
    assert start["y"] > top + 10  # the next line
    assert abs(start["x"] - box('[data-new-model-rf-bound="min"]')["x"]) <= 1
    # The label boxes are as tall as the bounds above them.
    assert abs(start["height"] - box('[data-new-model-rf-bound="min"]')["height"]) <= 1
    caption, summary = box(".rf-scale-caption"), box("[data-new-model-rf-scale-summary]")
    assert caption["x"] + caption["width"] <= start["x"]
    assert summary["x"] >= end["x"] + end["width"]
    assert abs(caption["y"] + caption["height"] / 2 - (start["y"] + start["height"] / 2)) <= 4
    assert abs(summary["y"] + summary["height"] / 2 - (start["y"] + start["height"] / 2)) <= 4


def test_an_answered_field_switching_to_its_scale_keeps_string_off(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """Codex on #4196: switching an answered Integer to Integer (scale)
    recomputes the row's actions, which must not re-enable String."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import (
        Assignment,
        Instrument,
        InstrumentResponseField,
        Response,
        Reviewee,
        Reviewer,
    )

    from ._builder import session_pk

    session_id = new_session()
    seed_rosters(api, session_id)
    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            pk = session_pk(live_server.database_url, session_id)
            instrument = db.execute(
                select(Instrument).where(Instrument.session_id == pk)
            ).scalar_one()
            rating = db.execute(
                select(InstrumentResponseField).where(
                    InstrumentResponseField.instrument_id == instrument.id,
                    InstrumentResponseField.label == "Rating",
                )
            ).scalar_one()
            reviewer = (
                db.execute(select(Reviewer).where(Reviewer.session_id == pk)).scalars().first()
            )
            reviewee = (
                db.execute(select(Reviewee).where(Reviewee.session_id == pk)).scalars().first()
            )
            assert reviewer is not None and reviewee is not None
            assignment = Assignment(
                session_id=pk,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                instrument_id=instrument.id,
            )
            db.add(assignment)
            db.flush()
            db.add(Response(assignment_id=assignment.id, response_field_id=rating.id, value="4"))
            db.commit()
    finally:
        engine.dispose()
    page.set_viewport_size({"width": 1500, "height": 1100})
    card = open_unlocked(page, session_id)
    select_box = rows(card).first.locator("[data-new-model-rf-data-type]")
    expect(select_box).to_be_enabled()
    select_box.select_option(label="Integer (scale)")
    expect(select_box.locator('option[value="string"]')).to_be_disabled()
    expect(select_box.locator('option[value="decimal"]').first).to_be_disabled()
    select_box.select_option(label="Integer")
    expect(select_box.locator('option[value="string"]')).to_be_disabled()


def test_start_and_end_labels_reach_the_edges_and_middle_is_centered(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """The author's ask (2026-11-24): Start sits at the scale's left
    edge and End at its right, out over the side padding, and Middle is
    centered on the bar as a whole."""
    page, _ = _surface(page_as, api, live_server, new_session)
    widget = page.locator('[data-rs-scale-widget="snap"]').first  # Poor / Fair / Excellent
    w = widget.bounding_box()
    line = widget.locator(".sc-line").bounding_box()
    start = widget.locator(".sc-label-start").bounding_box()
    middle = widget.locator(".sc-label-middle").bounding_box()
    end = widget.locator(".sc-label-end").bounding_box()
    assert w and line and start and middle and end
    assert abs(start["x"] - w["x"]) <= 1
    assert abs((end["x"] + end["width"]) - (w["x"] + w["width"])) <= 1
    said = widget.locator(".sc-said").bounding_box()  # "Not answered" lines up with Start
    assert said and abs(said["x"] - start["x"]) <= 1
    # Answered, *clear* takes that place.
    widget.locator(".sc-stop").nth(2).click(force=True)
    clear = widget.locator(".sc-clear").bounding_box()
    assert clear and abs(clear["x"] - start["x"]) <= 1
    assert abs((middle["x"] + middle["width"] / 2) - (line["x"] + line["width"] / 2)) <= 1


def test_band_2_scale_column_resizes_down_to_its_scale(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """Dragging a scale column's gripper in Band 2 stops at the scale's
    minimum and the cell's padding (the scaffold's resize test, retargeted
    at Item 1's close)."""
    session_id = new_session()
    seed_rosters(api, session_id)
    make_rating_a_scale(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1500, "height": 1100})
    card = open_unlocked(page, session_id)
    preview = card.locator("[data-new-model-band2-preview]")
    widget = preview.locator("[data-rs-scale-widget]").first
    expect(widget).to_be_visible()
    handle = preview.locator('.new-model-band2-resize-handle[data-col-key^="resp_"]').first
    hb = handle.bounding_box()
    assert hb is not None
    x, y = hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x - 1000, y, steps=5)
    page.mouse.up()
    cell = widget.locator("xpath=ancestor::td[1]").bounding_box()
    w = widget.bounding_box()
    assert cell is not None and w is not None
    assert w["x"] + w["width"] <= cell["x"] + cell["width"] + 1


def test_stacked_scales_share_their_ends(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """Author, 2026-11-24: in a stacked cell a 1-5 snap and a 1-100 slide
    take one side, so the slide's line starts where the snap's does, and
    its box ends at the widget's edge, where the snap's End label ends."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument

    from ._builder import session_pk

    session_id = new_session()
    seed_rosters(api, session_id)
    make_rating_a_scale(live_server.database_url, session_id, "Unlikely||Certainly")
    make_rating_a_scale(
        live_server.database_url, session_id, "Poor||Exceptional", label="Comments", hi=100
    )
    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            instrument = db.execute(
                select(Instrument).where(
                    Instrument.session_id == session_pk(live_server.database_url, session_id)
                )
            ).scalar_one()
            instrument.response_layout = "stacked"
            db.commit()
    finally:
        engine.dispose()
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.set_viewport_size({"width": 1400, "height": 1000})
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    snap = reviewer.locator(".sc-snap .sc-line").first.bounding_box()
    end = reviewer.locator(".sc-snap .sc-label-end").first.bounding_box()
    slide = reviewer.locator(".sc-slide .sc-line").first.bounding_box()
    box = reviewer.locator(".sc-slide > input").first.bounding_box()
    assert snap and end and slide and box
    assert abs(slide["x"] - snap["x"]) < 0.5
    assert abs(box["x"] + box["width"] - (end["x"] + end["width"])) < 0.5
    assert abs(box["width"] - 88) < 0.5
    # A slide's line ends in a short bar at each end (mockup B); a snap's,
    # which has its stops, does not.
    caps = reviewer.locator(".sc-slide .sc-track").first.evaluate(
        "t => ['::before', '::after'].map(p => getComputedStyle(t, p).height)"
    )
    assert caps == ["14px", "14px"]
    assert reviewer.locator(".sc-snap .sc-track").first.evaluate(
        "t => getComputedStyle(t, '::before').content"
    ) in ("none", "normal")


def test_band_2_stacked_preview_holds_scales_with_different_sides(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """20Q cumulative read: stacked scales share the widest side, so an
    11-point 1-11 snap (a 16px side) beside a 0-0.04 by 0.01 snap (20px)
    widens 8px past its own minimum, the widest of the two; Band 2's
    track, sized to a saved 60px, grows to hold it as widened."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument

    from ._builder import session_pk

    session_id = new_session()
    seed_rosters(api, session_id)
    make_rating_a_scale(live_server.database_url, session_id, "", hi=11)
    make_rating_a_scale(
        live_server.database_url,
        session_id,
        "",
        label="Comments",
        data_type="Decimal",
        lo=0,
        hi=0.04,
        step=0.01,
    )
    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            instrument = db.execute(
                select(Instrument).where(
                    Instrument.session_id == session_pk(live_server.database_url, session_id)
                )
            ).scalar_one()
            instrument.response_layout = "stacked"
            instrument.column_widths = {"stack_label": 150, "stack_input": 60}
            db.commit()
    finally:
        engine.dispose()
    page.set_viewport_size({"width": 1500, "height": 1100})
    card = open_unlocked(page, session_id)
    widgets = card.locator("[data-new-model-band2-preview] .rs-stack-fields [data-rs-scale-widget]")
    expect(widgets).to_have_count(2)
    cell = widgets.first.locator("xpath=ancestor::td[1]").bounding_box()
    assert cell is not None
    for i in range(2):
        w = widgets.nth(i).bounding_box()
        assert w is not None and w["x"] + w["width"] <= cell["x"] + cell["width"] + 1, (i, w, cell)
