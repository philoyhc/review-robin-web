"""Sys Admin → a session's audit log: the Event type filter narrows the
Event type list as it is typed (20H Item 3, author 2026-11-03). It sends
nothing; a selected type stays shown. The fake operator is an admin, so
the page is reachable."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect

from .conftest import app_url


def _visible(page: Page) -> list[str]:
    return page.eval_on_selector(
        "#filter-event-type",
        "s => Array.from(s.options).filter(o => !o.hidden).map(o => o.value)",
    )


def test_typing_narrows_the_list_and_keeps_a_selection(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.goto(app_url(f"/operator/sys-admin/sessions/{session_id}/audit-log"))
    everything = _visible(page)
    assert any(v.startswith("reviewer.") for v in everything)
    assert any(not v.startswith("reviewer") for v in everything)

    page.select_option("#filter-event-type", "session.created")
    page.fill("[data-audit-event-filter]", "REVIEWER")
    shown = _visible(page)
    assert all("reviewer" in v or v == "session.created" for v in shown)
    assert "session.created" in shown  # the selection is never hidden
    assert any(v.startswith("reviewer.") for v in shown)

    page.fill("[data-audit-event-filter]", "")
    assert _visible(page) == everything
    # The box has no name: Apply filters sends only the list's choice.
    with page.expect_navigation():
        page.click("text=Apply filters")
    assert "session.created" in page.url and "REVIEWER" not in page.url
    expect(page.locator("[data-audit-event-filter]")).to_have_value("")
