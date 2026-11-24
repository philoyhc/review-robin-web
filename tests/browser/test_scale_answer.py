"""The scale answer (segment 20P Item 1), on rung 2's scaffold page: a
bounded number box becomes a line with a circle. It snaps with a stop per
point up to 11 points and slides past that, keeping its box; it answers to
clicks, the keys and *clear*, and a disabled one is read-only. The box
underneath keeps the value that a save would send."""

from __future__ import annotations

import re
from collections.abc import Callable

from playwright.sync_api import Page, expect

from .conftest import app_url

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
