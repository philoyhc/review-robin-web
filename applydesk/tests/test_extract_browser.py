"""Extract data's chips in a real Chromium (segment AD1J, rung 3): each
card's chips shape its download links and are kept per viewer in the
browser. Without a Chromium build the tests skip, saying why;
``RRW_REQUIRE_BROWSER=1`` (set by CI) turns that skip into a failure."""

from __future__ import annotations

from playwright.sync_api import Page

from applydesk.tests.test_form_browser import page as page

ORIGIN = "http://applydesk.test"
PAGE = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/extract"


def _href(page: Page, card: str, file: str) -> str:
    link = page.locator(f'[data-xd-card="{card}"] a[data-xd-dl="{file}"]')
    return link.get_attribute("href") or ""


def test_chips_shape_the_links_and_are_kept(page: Page) -> None:
    page.goto(PAGE)
    assert _href(page, "applications", "applications.csv").endswith("?rows=last")
    apps = page.locator('[data-xd-card="applications"]')
    apps.get_by_role("button", name="All applications").click()
    apps.get_by_role("button", name="Included").click()
    assert _href(page, "applications", "applications.csv").endswith("?rows=all&drafts=1")
    gates = page.locator('[data-xd-card="gates"]')
    gates.get_by_role("button", name="A row per application").click()
    assert "shape=application" in _href(page, "gates", "gate_1.csv")
    assert "shape=application" in _href(page, "gates", "gates.zip")
    every = page.locator('[data-xd-card="all"]')
    every.get_by_role("button", name="Applications").click()
    assert "carries=gates%2Coutcomes" in _href(page, "all", "all.zip")
    page.reload()  # kept in this browser
    assert apps.get_by_role("button", name="All applications").get_attribute("aria-pressed") == (
        "true"
    )
    assert _href(page, "applications", "applications.csv").endswith("?rows=all&drafts=1")
    assert "carries=gates%2Coutcomes" in _href(page, "all", "all.zip")
    # The link downloads what it says.
    with page.expect_download() as d:
        apps.get_by_role("link", name="Download CSV").click()
    assert d.value.suggested_filename == "applications.csv"


def test_without_storage_the_chips_still_shape_the_links(page: Page) -> None:
    page.add_init_script(
        "Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } })"
    )
    page.goto(PAGE)
    out = page.locator('[data-xd-card="outcomes"]')
    out.get_by_role("button", name="All applications").click()
    assert _href(page, "outcomes", "outcomes.csv").endswith("?rows=all")
