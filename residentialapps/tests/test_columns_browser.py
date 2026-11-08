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
