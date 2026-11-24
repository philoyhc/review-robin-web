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
    open_unlocked,
    rows,
    save,
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


def test_a_slide_answers_a_drag_a_click_and_clear(page: Page) -> None:
    """The plan's rung 4: drag the circle along a slide, click its line,
    and clear it (on the scaffold, retargeted at the close)."""
    _open(page)
    slide = page.locator('[data-rs-scale-widget="slide"]').first
    box = slide.locator('input[name="p4"]')
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
