"""Session details keeps each field in its place when a linked application
hides some (author, 2026-11-16): with the release fields hidden, the two
prompts stay in the right-hand column, Invites above Reminders, rather
than flowing under End."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page

from .conftest import LiveServer, app_url


def _box(page: Page, label_for: str) -> dict[str, float]:
    return page.locator(f'label[for="{label_for}"]').evaluate(
        "el => { const r = el.parentElement.getBoundingClientRect();"
        " return {left: r.left, top: r.top}; }"
    )


def _relink(database_url: str, session_id: str, app: str) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.models import ReviewSession

    from ._builder import session_pk

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            review_session = db.get(ReviewSession, session_pk(database_url, session_id))
            assert review_session is not None
            review_session.linked_app = app
            db.commit()
    finally:
        engine.dispose()


def test_the_prompts_keep_their_column_without_the_release_fields(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    _relink(live_server.database_url, session_id, "utilities")  # release off, email on
    page.set_viewport_size({"width": 1700, "height": 1000})
    page.goto(app_url(f"/operator/sessions/{session_id}"))
    assert page.locator('label[for="mock-release-from"]').count() == 0
    start, end = _box(page, "mock-start"), _box(page, "mock-end")
    invites, reminders = _box(page, "mock-invite-offsets"), _box(page, "mock-reminder-offsets")
    assert invites["left"] > start["left"] and invites["top"] == start["top"]
    assert reminders["left"] == invites["left"] and reminders["top"] == end["top"]
