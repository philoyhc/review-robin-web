"""Segment 19W rung 3 — a Setup upload card's ask holds the file, so in
a real browser the operator ticks and presses Upload with no file
chosen: the file input stops being ``required`` and the hidden token
carries the hold."""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect


def test_tick_and_upload_with_the_file_held(
    page: Page, new_session: Callable[[], str], api: httpx.Client, tmp_path
) -> None:
    session_id = new_session()
    url = f"/operator/sessions/{session_id}/reviewers"
    first = api.post(
        f"{url}/import",
        files={"file": ("first.csv", b"ReviewerName,ReviewerEmail\nAnn,ann@example.edu\n", "text/csv")},
        follow_redirects=False,
    )
    assert first.status_code == 303

    second = tmp_path / "second.csv"
    second.write_text("ReviewerName,ReviewerEmail\nBea,bea@example.edu\n")
    page.goto(f"{url}?unlocked=1#upload-csv")
    form = page.locator("#upload-csv-form")
    form.locator('input[name="file"]').set_input_files(str(second))
    # Force the ask: submit without the replace tick, past the browser's
    # own `required` check, as a stale tab or a direct POST would.
    form.evaluate("f => { f.noValidate = true; }")
    with page.expect_navigation():
        form.evaluate("f => f.submit()")

    expect(page.locator("[data-held-upload]")).to_contain_text("second.csv")
    form = page.locator("#upload-csv-form")
    form.locator('input[name="confirm_replace"]').check()
    with page.expect_navigation():
        form.get_by_role("button", name="Upload").click()

    expect(page.locator("[data-held-upload]")).to_have_count(0)
    expect(page.get_by_text("bea@example.edu").first).to_be_visible()
