"""A refused Quick Setup upload re-renders Session Home at 422 under the
POST's URL (findings O7); the page names Home's own path at once, so the
in-place Unlock and a reload address Home, never the POST-only route
(the read of the S4 / O7 PR)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page, expect


def test_a_refused_upload_lands_on_homes_own_path(
    page: Page, new_session: Callable[[], str], tmp_path
) -> None:
    session_id = new_session()
    bad = tmp_path / "reviewers.csv"
    bad.write_text("not,a,roster\n1,2,3\n")
    page.goto(f"/operator/sessions/{session_id}")
    page.locator('input[name="reviewers_file"]').set_input_files(str(bad))
    page.locator("#quick-setup-confirm-replace-toggle").check()
    with page.expect_navigation():
        page.locator("#quick-setup-submit-all").click()
    page.wait_for_load_state("load")

    expect(page.locator("[data-quick-setup-reason]").first).to_be_visible()
    assert page.evaluate("window.location.pathname") == f"/operator/sessions/{session_id}"

    response = page.reload()
    assert response is not None and response.status == 200


def test_dismiss_clears_the_banner_on_homes_own_path(
    page: Page, new_session: Callable[[], str], tmp_path
) -> None:
    """Home renamed the address to its own path, so Dismiss's link
    differs only by fragment: following it would leave the banner up
    (browser run 2026-10-19, steps 52 and 56)."""
    session_id = new_session()
    bad = tmp_path / "reviewers.csv"
    bad.write_text("not,a,roster\n1,2,3\n")
    page.goto(f"/operator/sessions/{session_id}")
    page.locator('input[name="reviewers_file"]').set_input_files(str(bad))
    page.locator("#quick-setup-confirm-replace-toggle").check()
    with page.expect_navigation():
        page.locator("#quick-setup-submit-all").click()
    page.wait_for_load_state("load")

    banner = page.locator("#quick-setup-reviewers-error-banner")
    expect(banner).to_be_visible()
    banner.get_by_role("link", name="Dismiss").click()

    expect(banner).to_be_hidden()
    expect(page.locator("[data-quick-setup-reason]")).to_have_count(0)
    assert page.evaluate("window.location.pathname") == f"/operator/sessions/{session_id}"


_CHECKLIST = Path(__file__).resolve().parents[2] / "guide/browser_check_files/checklist"


def _submit_settings(page: Page, path: Path) -> None:
    page.locator('input[name="settings_file"]').set_input_files(str(path))
    page.locator("#quick-setup-confirm-replace-toggle").check()
    with page.expect_navigation():
        page.locator("#quick-setup-submit-all").click()
    page.wait_for_load_state("load")


def test_dismiss_drops_the_deletion_tick(
    page: Page, new_session: Callable[[], str]
) -> None:
    """The S4 ask's tick rides the submit-all form through ``form=``;
    Dismiss takes it out of the page with the banner, so a later Submit
    cannot carry it."""
    session_id = new_session()
    page.goto(f"/operator/sessions/{session_id}")
    _submit_settings(page, _CHECKLIST / "05_settings.csv")
    _submit_settings(page, _CHECKLIST / "09_settings_one_instrument.csv")

    banner = page.locator("#quick-setup-settings-error-banner")
    tick = page.locator('input[name="acknowledge_instrument_deletion"]')
    expect(tick).to_have_count(1)
    tick.check()
    banner.get_by_role("link", name="Dismiss").click()

    expect(banner).to_be_hidden()
    expect(tick).to_have_count(0)


def test_dismiss_still_navigates_when_the_query_differs(
    page: Page, new_session: Callable[[], str]
) -> None:
    """The Create page's refusal lands on Home with its codes in the
    query; Dismiss's link differs by more than the fragment there, so it
    loads Home rather than hiding the banner in place."""
    session_id = new_session()
    page.goto(
        f"/operator/sessions/{session_id}"
        "?quick_setup_error=reviewers&quick_setup_reason=refused"
    )
    banner = page.locator("#quick-setup-reviewers-error-banner")
    expect(banner).to_be_visible()
    with page.expect_navigation():
        banner.get_by_role("link", name="Dismiss").click()
    page.wait_for_load_state("load")

    assert page.evaluate("window.location.search") == ""
    expect(page.locator("[data-quick-setup-reason]")).to_have_count(0)
