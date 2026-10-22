"""Arriving on Session Home from elsewhere carries no ``#fragment``
(19X Item 7): a bare Create opens the details card for editing at
``?editing=1``, and a Create whose staged file is refused lands on the
slot's banner by Home's banner script rather than by a slot anchor."""

from __future__ import annotations

import uuid

from playwright.sync_api import Page, expect

from .conftest import app_url


def _fill_create(page: Page) -> None:
    code = f"ar{uuid.uuid4().hex[:8]}"
    page.goto(app_url("/operator/sessions/new"))
    page.locator("#name").fill(f"Arrival {code}")
    page.locator("#code").fill(code)


def test_a_bare_create_opens_the_details_card_with_no_fragment(page: Page) -> None:
    _fill_create(page)
    with page.expect_navigation():
        page.locator("#create-session-submit").click()
    page.wait_for_load_state("load")
    assert page.url.endswith("?editing=1"), page.url
    assert "#" not in page.url
    expect(page.locator("#session-config")).to_have_attribute("data-config-mode", "edit")
    # The page opens at its top: nothing scrolls it to the card.
    assert page.evaluate("window.scrollY") == 0


def test_a_refused_file_on_create_lands_on_its_banner_with_no_fragment(
    page: Page, tmp_path
) -> None:
    bad = tmp_path / "reviewers.csv"
    bad.write_text("not,a,roster\n1,2,3\n")
    page.set_viewport_size({"width": 1280, "height": 600})
    _fill_create(page)
    page.locator('input[name="reviewers_file"]').set_input_files(str(bad))
    with page.expect_navigation():
        page.locator("#create-session-submit").click()
    page.wait_for_load_state("load")
    assert "#" not in page.url
    assert "quick_setup_error=reviewers" in page.url
    expect(page.locator("#quick-setup-reviewers-error-banner")).to_be_in_viewport()
