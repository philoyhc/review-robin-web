"""Select all on the lobby and on Archived covers the rows the filter
shows, and a row the filter hides leaves the selection (findings O1,
2026-10-16; ``spec/ui_elements.md`` §10). Before, Select all ticked
hidden rows too, so a bulk Delete, Purge, Unarchive or tag edit reached
sessions the operator could not see.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from playwright.sync_api import Page, expect

from .conftest import LiveServer

PAGES = {
    "lobby": ("/operator/sessions", "sessions"),
    "archived": ("/operator/sessions/archived", "archived"),
}


def _make(api: httpx.Client, *, archived: bool) -> tuple[int, str]:
    code = f"o1{uuid.uuid4().hex[:8]}"
    response = api.post(
        "/operator/sessions",
        data={"name": f"Select {code}", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    session_id = int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])
    if archived:
        response = api.post(
            f"/operator/sessions/{session_id}/workflow/archive", follow_redirects=False
        )
        assert response.status_code == 303, response.text
    return session_id, code


@pytest.mark.parametrize("kind", sorted(PAGES))
def test_select_all_ticks_only_the_rows_the_filter_shows(
    page: Page, api: httpx.Client, live_server: LiveServer, kind: str
) -> None:
    url, prefix = PAGES[kind]
    shown_id, shown_code = _make(api, archived=kind == "archived")
    hidden_id, _ = _make(api, archived=kind == "archived")
    page.goto(live_server.base_url + url)
    box = lambda session_id: page.locator(  # noqa: E731
        f'.{prefix}-list-select-row[value="{session_id}"]'
    )

    # A hidden row that was ticked leaves the selection.
    box(hidden_id).check()
    page.locator(f".{prefix}-search-input").fill(shown_code)
    expect(box(hidden_id)).to_be_hidden()
    expect(box(hidden_id)).not_to_be_checked()

    # Select all reaches only the row still shown, and reads as all of it.
    select_all = page.locator(f".{prefix}-list-select-all")
    select_all.check()
    expect(box(shown_id)).to_be_checked()
    expect(box(hidden_id)).not_to_be_checked()
    assert page.locator(f".{prefix}-list-select-row:checked").count() == 1
    expect(select_all).to_be_checked()

    # Clearing the filter shows the other row unticked, so the header is
    # partial rather than all.
    page.locator(f".{prefix}-search-input").fill("")
    expect(box(hidden_id)).to_be_visible()
    assert select_all.evaluate("b => b.indeterminate") is True
