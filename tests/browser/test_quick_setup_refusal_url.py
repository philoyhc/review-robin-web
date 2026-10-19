"""A refused Quick Setup upload re-renders Session Home at 422 under the
POST's URL (findings O7); the page names Home's own path at once, so the
in-place Unlock and a reload address Home, never the POST-only route
(the read of the S4 / O7 PR)."""

from __future__ import annotations

from collections.abc import Callable

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
