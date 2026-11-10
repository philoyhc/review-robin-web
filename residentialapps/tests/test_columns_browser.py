"""Residential Ops in the three columns of 340 px (author, 2026-11-08):
a page's own split is two columns and one from 1116 px wide, and a
desktop-oriented page keeps its split and cards as they were. Served as
the sort tests are; without a Chromium build the test skips, saying why,
and `RRW_REQUIRE_BROWSER=1` fails it."""

from __future__ import annotations

from playwright.sync_api import Page

from residentialapps.tests.test_sort_persistence_browser import (  # noqa: F401  (the fixture)
    ORIGIN,
    page,
)

MEASURE = """() => {
  const pg = document.querySelector('main.page');
  const s = pg.querySelector(':scope > .split');
  const m = s.querySelector(':scope > .main').getBoundingClientRect();
  const d = s.querySelector(':scope > .side').getBoundingClientRect();
  return [pg.classList.contains('desktop'), Math.round(m.width), Math.round(d.width),
          m.top === d.top];
}"""


def test_a_split_is_two_and_one_and_a_desktop_page_keeps_its_own(page: Page) -> None:  # noqa: F811
    for width, path, expect in (
        (1280, "/ra-leave/", (False, 781, 379, True)),
        (736, "/ra-leave/", (False, 340, 340, True)),
        (1280, "/ra-leave/admin/", (True, 860, 300, True)),
        (736, "/ra-leave/admin/", (True, 704, 704, False)),
    ):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(ORIGIN + path)
        assert tuple(page.evaluate(MEASURE)) == expect, (width, path)


def test_an_empty_side_gives_the_main_column_the_width(page: Page) -> None:  # noqa: F811
    """RA Leave history with no drafts (author, 2026-11-08): the side has
    nothing in it, so it hides and the applications take the page's two
    columns' width, or the page below 1116 px."""
    page.set_viewport_size({"width": 1000, "height": 900})
    page.goto(ORIGIN + "/ra-leave/history?as=Hana%20Ito")
    widths = page.evaluate(
        """() => {
      const s = document.querySelector('main.page > .split');
      const side = s.querySelector(':scope > .side');
      return [side.children.length, getComputedStyle(side).display,
              Math.round(s.querySelector(':scope > .main').getBoundingClientRect().width)];
    }"""
    )
    assert widths[0] == 0 and widths[1] == "none" and widths[2] == 952, widths


def test_a_phone_sees_the_whole_month_of_leave(page: Page) -> None:  # noqa: F811
    """Author, 2026-11-10: the staff Home's calendar stays a month grid on a
    phone, all seven days across without scrolling sideways, each entry a
    tag, not a link."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(ORIGIN + "/ra-leave/staff/?as=Sam%20Lee")
    grid = page.locator(".cal-grid")
    assert grid.is_visible()
    box = grid.bounding_box()
    assert box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 390
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    assert page.locator(".cal-tag").first.is_visible()
    assert not page.locator(".cal-link").first.is_visible()
