"""Tests for the Quick Setup placeholder card on the
``/operator/sessions/new`` page.

Mirrors the Session Home scaffold (per Segment 11H PR A) but in
its always-unlocked / no-Lock-button preview shape so the
operator sees the eventual setup workflow before creating the
session.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.web import views


def test_new_session_page_renders_quick_setup_card(
    client: TestClient,
) -> None:
    """The ``/operator/sessions/new`` page renders the Quick Setup
    card below the create-session form, sitting in the bottom-
    left of a ``.bottom-grid`` two-column layout."""

    body = client.get("/operator/sessions/new").text

    # Form card carries an in-card H2 heading matching the v2
    # convention (same font size as Quick setup (optional) below).
    assert "<h2>Session details</h2>" in body
    # Quick Setup card present with the optional title.
    assert 'id="quick-setup"' in body
    assert "<h2>Quick setup (optional)</h2>" in body
    # Half-width slot grid is the same shape as on Home.
    assert 'class="quick-setup-top-grid"' in body
    # Slots render with their stable fragment anchors.
    for key in ("reviewers", "reviewees", "assignments", "settings"):
        assert f'id="quick-setup-{key}"' in body


def test_new_session_quick_setup_has_no_lock_toggle(
    client: TestClient,
) -> None:
    """Per the user's spec the new-session variant of Quick Setup
    is always unlocked — no Lock / Unlock button. The footer
    container that holds the button on Home doesn't render here
    either."""

    body = client.get("/operator/sessions/new").text

    assert 'id="quick-setup-lock-toggle"' not in body
    assert 'class="quick-setup-card-footer"' not in body
    # Body wrapper does not carry the .locked greying class.
    assert "quick-setup-body locked" not in body


def test_new_session_quick_setup_zero_counts(
    client: TestClient,
) -> None:
    """All four slots show zero / empty counts since there's no
    session row yet."""

    body = client.get("/operator/sessions/new").text

    # Reviewers / Reviewees / Assignments slots all read "none yet".
    assert body.count("none yet") >= 3


def test_build_new_session_quick_setup_context_shape() -> None:
    """The new-session adapter returns a four-slot context with
    every wire flag off, the lock toggle suppressed, and the
    customised title."""

    context = views.build_new_session_quick_setup_context()

    assert [slot.key for slot in context.slots] == [
        "reviewers",
        "reviewees",
        "assignments",
        "settings",
    ]
    assert all(slot.is_wired is False for slot in context.slots)
    assert all(slot.count == 0 for slot in context.slots)
    assert context.is_disabled is False
    assert context.is_locked is False
    assert context.show_lock_toggle is False
    assert context.title == "Quick setup (optional)"


def test_session_home_quick_setup_keeps_default_title_and_lock_toggle(
    client: TestClient,
    db,
) -> None:
    """Regression — extending QuickSetupContext with ``title`` /
    ``show_lock_toggle`` defaults must not change Session Home's
    rendered card."""

    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": "qs-defaults", "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    from sqlalchemy import select
    from app.db.models import ReviewSession

    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "qs-defaults")
    ).scalar_one()
    body = client.get(f"/operator/sessions/{review_session.id}").text

    # Default title preserved.
    assert "<h2>Quick Setup</h2>" in body
    # Lock toggle still renders in draft.
    assert 'id="quick-setup-lock-toggle"' in body
