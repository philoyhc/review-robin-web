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

from ._builder import session_pk
from .conftest import LiveServer, app_url

PAGES = {
    "lobby": ("/operator/sessions", "sessions"),
    "archived": ("/operator/sessions/archived", "archived"),
}


def _make(
    api: httpx.Client, database_url: str, *, archived: bool, word: str = ""
) -> tuple[int, str]:
    """Make a session; return its key (the lobby checkbox's value) and code."""
    code = f"o1{uuid.uuid4().hex[:8]}"
    response = api.post(
        "/operator/sessions",
        data={"name": f"Select {word} {code}".replace("  ", " "), "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    session_id = response.headers["location"].split("?")[0].rsplit("/", 1)[1]
    if archived:
        response = api.post(
            f"/operator/sessions/{session_id}/workflow/archive", follow_redirects=False
        )
        assert response.status_code == 303, response.text
    return session_pk(database_url, session_id), code


@pytest.mark.parametrize("kind", sorted(PAGES))
def test_select_all_ticks_only_the_rows_the_filter_shows(
    page: Page, api: httpx.Client, live_server: LiveServer, kind: str
) -> None:
    url, prefix = PAGES[kind]
    shown_id, shown_code = _make(api, live_server.database_url, archived=kind == "archived")
    hidden_id, _ = _make(api, live_server.database_url, archived=kind == "archived")
    page.goto(app_url(url))
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


def test_the_bulk_panel_follows_the_filter_and_keeps_an_unsaved_edit(
    page: Page, api: httpx.Client, live_server: LiveServer
) -> None:
    """The panel rebuilds when the filter unticks a row, and only then:
    it is editable, so a keystroke that hides nothing ticked must not
    re-seed it (diff read on #3095)."""
    word = f"w{uuid.uuid4().hex[:6]}"
    first, _ = _make(api, live_server.database_url, archived=False, word=word)
    second, _ = _make(api, live_server.database_url, archived=False, word=word)
    other, _ = _make(api, live_server.database_url, archived=False)
    page.goto(app_url("/operator/sessions"))
    box = lambda session_id: page.locator(  # noqa: E731
        f'.sessions-list-select-row[value="{session_id}"]'
    )
    search = page.locator(".sessions-search-input")

    for session_id in (first, second, other):
        box(session_id).check()
    count = page.locator(".session-expander [data-expander-count]")
    expect(count).to_have_text("3")
    search.fill(word)
    expect(box(other)).not_to_be_checked()
    expect(count).to_have_text("2")

    # One row left ticked: the single panel, with an edit not yet saved.
    box(second).uncheck()
    name = page.locator('.session-expander [data-expander-field="name"]')
    name.fill("Renamed, not saved")
    search.press("End")
    search.type(" ")  # still matches the ticked row once trimmed
    expect(box(first)).to_be_visible()
    expect(name).to_have_value("Renamed, not saved")
