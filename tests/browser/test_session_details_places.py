"""Session details keeps each field in its place when a linked application
hides some (author, 2026-11-16): with the release fields gone, the two
prompts stay in the right-hand column, Invites above Reminders, rather
than flowing under End. No profile hides the release fields and keeps the
prompts (Utilities takes the email lock too from rung 7j), so the test
takes the release cells off a native page: it checks the grid's
placement, and `tests/integration/test_linked_sessions.py` the template's
branching."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page

from .conftest import app_url


def _box(page: Page, label_for: str) -> dict[str, float]:
    return page.locator(f'label[for="{label_for}"]').evaluate(
        "el => { const r = el.parentElement.getBoundingClientRect();"
        " return {left: r.left, top: r.top}; }"
    )


def test_the_prompts_keep_their_column_without_the_release_fields(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.set_viewport_size({"width": 1700, "height": 1000})
    page.goto(app_url(f"/operator/sessions/{session_id}"))
    page.evaluate(
        """() => ['mock-release-from', 'mock-release-until'].forEach(id =>
            document.querySelector(`label[for="${id}"]`).parentElement.remove())"""
    )
    start, end = _box(page, "mock-start"), _box(page, "mock-end")
    invites, reminders = _box(page, "mock-invite-offsets"), _box(page, "mock-reminder-offsets")
    assert invites["left"] > start["left"] and invites["top"] == start["top"]
    assert reminders["left"] == invites["left"] and reminders["top"] == end["top"]
