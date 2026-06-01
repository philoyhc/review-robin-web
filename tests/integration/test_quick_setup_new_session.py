"""Tests for the Quick Setup card on the ``/operator/sessions/new``
page.

Mirrors the Session Home scaffold (per Segment 11H PR A) but in
its always-unlocked / no-Lock-button shape. The slot inputs are
wired to the create-session form via the HTML ``form="..."``
attribute so any uploads / rule selection the operator stages
here are processed by ``POST /operator/sessions`` after the
session row is created.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, ReviewSession, Reviewer
from app.web import views


REVIEWER_CSV = b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n"
REVIEWEE_CSV = b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n"


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
    # Slots render with their stable fragment anchors. The
    # Assignments slot retired in 15D PR 7a; Relationships
    # arrives in PR 7c.
    for key in ("reviewers", "reviewees", "settings"):
        assert f'id="quick-setup-{key}"' in body
    assert 'id="quick-setup-assignments"' not in body


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


def test_new_session_quick_setup_renders_action_labels(
    client: TestClient,
) -> None:
    """Every slot heading carries the ``Upload a CSV`` action label
    post-15D PR 7a. No count copy renders here since there's no
    session row yet."""

    body = client.get("/operator/sessions/new").text

    # Three file-upload slots (Reviewers, Reviewees, Session settings).
    assert body.count(">Upload a CSV<") >= 3
    # ``Generate by rule`` label retired with the Assignments slot.
    assert ">Generate by rule<" not in body


def test_build_new_session_quick_setup_context_shape() -> None:
    """Post-15D PR 7c the new-session adapter returns a 4-slot
    context (Reviewers, Reviewees, Relationships, Settings) with
    every wire flag off, the lock toggle suppressed, and the
    customised title."""

    context = views.build_new_session_quick_setup_context()

    assert [slot.key for slot in context.slots] == [
        "reviewers",
        "reviewees",
        "relationships",
        "observers",
        "settings",
    ]
    assert all(slot.is_wired is False for slot in context.slots)
    assert all(slot.count == 0 for slot in context.slots)
    assert context.is_disabled is False
    assert context.is_locked is False
    assert context.show_lock_toggle is False
    assert context.title == "Quick setup (optional)"


def test_new_session_quick_setup_omits_confirm_replace_checkbox(
    client: TestClient,
) -> None:
    """The card-level "This will replace any existing reviewers,
    reviewees, assignments or settings ..." checkbox is suppressed
    on the new-session variant — there's nothing to replace yet."""

    body = client.get("/operator/sessions/new").text

    assert 'id="quick-setup-confirm-replace-toggle"' not in body
    assert "Yes, replace existing reviewers" not in body


def test_new_session_quick_setup_inputs_wired_to_create_session_form(
    client: TestClient,
) -> None:
    """Slot inputs use ``form="create-session-form"`` so the
    Create-session button submits both the session details and any
    staged Quick Setup uploads in one POST."""

    body = client.get("/operator/sessions/new").text

    # Create-session form id is set so HTML5 form-association works.
    assert 'id="create-session-form"' in body
    # File inputs target the create-session form, not a separate
    # submit-all form.
    assert 'name="reviewers_file"' in body
    assert 'form="create-session-form"' in body
    # Slot 4 (settings) stays inert since 12A PR 6 hasn't shipped.
    # No separate submit-all form is rendered.
    assert "/quick-setup/submit-all" not in body


def test_create_session_with_quick_setup_files_processes_uploads(
    client: TestClient, db: Session
) -> None:
    """POST /operator/sessions with reviewers + reviewees files
    creates the session and applies the imports so the operator
    lands on Session Home with a populated roster."""

    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": "qs-newsess-roster", "description": "d"},
        files={
            "reviewers_file": ("r.csv", REVIEWER_CSV, "text/csv"),
            "reviewees_file": ("e.csv", REVIEWEE_CSV, "text/csv"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "qs-newsess-roster")
    ).scalar_one()
    reviewers = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalars().all()
    reviewees = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars().all()
    assert len(reviewers) == 1
    assert len(reviewees) == 1


def test_create_session_with_no_quick_setup_files_still_works(
    client: TestClient, db: Session
) -> None:
    """The original create-session-only path still works when no
    Quick Setup uploads are staged."""

    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": "qs-newsess-bare"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "qs-newsess-bare")
    ).scalar_one()
    # No Quick Setup uploads → redirect to the Edit page so the
    # operator continues filling in session details.
    assert (
        response.headers["location"]
        == f"/operator/sessions/{review_session.id}/edit"
    )


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
