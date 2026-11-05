"""On a phone every control is at least 44 px tall (author, 2026-10-29),
measured in a real Chromium at phone width, on RA Leave's mobile-critical
pages (`residentialapps/spec/applications.md`). A link inside a sentence
keeps its line, as WCAG's inline exception allows; the typeahead counts by
its 44 px box, and a tick box by its label. The browser fixture is the sort test's; it skips
without Chromium, or fails under ``RRW_REQUIRE_BROWSER=1``.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from residentialapps.tests.test_sort_persistence_browser import (  # noqa: F401  (the fixture)
    ORIGIN,
    page,
)

# Easy Auth's headers for a signed-in viewer: the account menu needs one.
SIGNED_IN = {
    "X-MS-CLIENT-PRINCIPAL-NAME": "chloe.lim@example.edu",
    "X-MS-CLIENT-PRINCIPAL-ID": "chloe-oid",
}

PHONE_PAGES = (
    "/",
    "/ra-leave/",
    "/ra-leave/apply",
    "/ra-leave/appeal",
    "/ra-leave/applications/L-0101",
    "/ra-leave/cover",
    "/ra-leave/staff/",
    "/ra-leave/staff/decide",
    "/ra-leave/staff/decide/L-0101",
)

SMALL = """() => [...document.querySelectorAll('a[href], button, input, select, textarea')]
  .filter(e => e.offsetParent !== null)
  .filter(e => !(e.tagName === 'A' && getComputedStyle(e).display === 'inline'
                 && e.parentElement.textContent.trim() !== e.textContent.trim()))
  .map(e => [e.matches('.token-input') ? e.closest('.tokens')
             : e.matches('[type=checkbox], [type=radio]') && e.closest('label') ? e.closest('label') : e, e])
  .map(([box, e]) => [e.outerHTML.slice(0, 80), Math.round(box.getBoundingClientRect().height)])
  .filter(([, h]) => h < 44)"""


@pytest.mark.parametrize("path", PHONE_PAGES)
def test_every_control_is_a_thumb_s_width_on_a_phone(page: Page, path: str) -> None:  # noqa: F811
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(ORIGIN + path)
    assert page.evaluate(SMALL) == []


def test_a_token_s_remove_button_is_a_thumb_s_width(page: Page) -> None:  # noqa: F811
    """No phone page shows a chosen person yet; Assignments' cells do, and
    the rule is the shared stylesheet's."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(ORIGIN + "/rosters/assignments")
    sizes = page.eval_on_selector_all(
        ".token-x",
        "xs => xs.map(x => [Math.round(x.getBoundingClientRect().height), Math.round(x.getBoundingClientRect().width)])",
    )
    assert sizes and all(h >= 44 and w >= 44 for h, w in sizes)


def test_the_account_menu_holds_the_toggle_on_a_phone_and_closes_on_escape(page: Page) -> None:  # noqa: F811
    """`docs/header_chrome.md` §2, §7 (RRW segment 20D): under 640 px the
    toggle leaves the bar for the account menu; Escape closes the menu."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.set_extra_http_headers(SIGNED_IN)
    page.goto(ORIGIN + "/ra-leave/")
    assert not page.locator(".right > .theme-toggle").is_visible()
    menu = page.locator("details.acct-menu")
    box = menu.locator("summary").bounding_box()
    assert box and box["height"] >= 44 and box["width"] >= 44  # SMALL skips a summary
    menu.locator("summary").click()
    assert menu.locator(".narrow-only .theme-toggle").is_visible()
    assert menu.get_by_role("link", name="Sign out").is_visible()
    assert page.evaluate(SMALL) == []
    page.keyboard.press("Escape")
    assert menu.get_attribute("open") is None
