"""Sys Admin → a session's audit log: the Event type filter finds types
in the Event type list, and the list is where they are selected (20H
Item 3, author 2026-11-03). Typing narrows the list to the types
beginning with the text; a click selects or unselects one type and
keeps the rest, so a type found with one filter stays selected while
another is found with the next. The box sends nothing. The fake operator
is an admin, so the page is reachable."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect

from .conftest import app_url

LIST = "#filter-event-type"
BOX = "[data-audit-event-filter]"


def _visible(page: Page) -> list[str]:
    return page.eval_on_selector(
        LIST, "s => Array.from(s.options).filter(o => !o.hidden).map(o => o.value)"
    )


def _selected(page: Page) -> list[str]:
    return page.eval_on_selector(
        LIST, "s => Array.from(s.options).filter(o => o.selected).map(o => o.value)"
    )


def test_two_filters_build_one_selection(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.goto(app_url(f"/operator/sys-admin/sessions/{session_id}/audit-log"))
    everything = _visible(page)
    reviewer = sorted(v for v in everything if v.startswith("reviewer"))
    assert reviewer and "session.created" in everything
    expect(page.locator("[data-audit-event-hint]")).to_contain_text("None selected")

    # "reviewer" narrows to the types beginning with it, whatever case.
    page.fill(BOX, "REVIEWER")
    assert sorted(_visible(page)) == reviewer
    page.click(f"{LIST} option[value='{reviewer[0]}']")

    # A second filter finds another type; the first stays selected.
    page.fill(BOX, "session")
    assert all(v.startswith("session") for v in _visible(page))
    assert reviewer[0] not in _visible(page)
    page.click(f"{LIST} option[value='session.created']")
    assert sorted(_selected(page)) == sorted([reviewer[0], "session.created"])
    expect(page.locator("[data-audit-event-hint]")).to_contain_text("2 selected")

    # A second click unselects; a third selects again.
    page.click(f"{LIST} option[value='session.created']")
    assert _selected(page) == [reviewer[0]]
    page.click(f"{LIST} option[value='session.created']")

    # Enter in the box does not submit: it is for narrowing.
    page.press(BOX, "Enter")
    expect(page.locator(BOX)).to_have_value("session")
    # Apply sends both selections, the hidden one too, and not the text.
    with page.expect_navigation():
        page.click("text=Apply filters")
    assert f"event_type={reviewer[0]}" in page.url
    assert "event_type=session.created" in page.url
    assert sorted(_selected(page)) == sorted([reviewer[0], "session.created"])
    assert _visible(page) == everything

    # Clear, always beside Apply filters, goes back to the whole log.
    with page.expect_navigation():
        page.click("[data-audit-clear]")
    assert _selected(page) == []
