"""PR β — Reviewer surface top-row layout + per-page status pills.

Per `guide/archive/segment_11D_v2_sweep_non_session.md` "Follow-on: Reviewer
surface — multi-instrument rewrite" → PR β. Description card and
flash+status panel sit side-by-side in a `.bottom-grid`; the panel
hosts one per-page status pill per instrument the reviewer is
assigned on, plus transient flash banners.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, Reviewer, ReviewSession
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)



def _operator_creates_session_with_pair(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
    reviewee_ident: str,
    description: str | None = None,
) -> ReviewSession:
    operator_client.post(
        "/operator/sessions",
        data={
            "name": code.title(),
            "code": code,
            **({"description": description} if description else {}),
        },
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nR,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                f"RevieweeName,RevieweeEmail\nCarol,{reviewee_ident}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    operator_client.get(f"/operator/sessions/{review_session.id}/assignments?validated=1")
    operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "ready"
    return review_session


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


# ── Overview card — description + status pills rolled into one card ───


def test_overview_card_carries_description_and_pills(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The reviewer surface's overview card (`.card.rs-status-panel`)
    rolls the session description and the per-page status pills into
    one full-width card — no separate description card, no
    `.bottom-grid` 2-column row."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-toprow",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        description="Some context for the reviewers.",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert 'class="card rs-status-panel"' in body
    assert 'class="rs-session-description"' in body
    assert 'class="card rs-description-card"' not in body
    # Description content lives inside the overview card.
    assert "Some context for the reviewers." in body


def test_overview_card_renders_when_no_description(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the session has no description, the overview card still
    renders — the per-page status pills alone are enough content —
    but it carries no `.rs-session-description` paragraph."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-nodesc",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert 'class="card rs-status-panel"' in body
    # No description paragraph when the session has no description.
    assert 'class="rs-session-description"' not in body


# ── Per-page status pill — fresh "not started" session ────────────────


def test_page_status_pill_is_not_started_on_fresh_session(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A reviewer who hasn't typed anything yet sees a `not started`
    pill in the status panel for their page."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-fresh",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert 'class="rs-page-status-pills"' in body
    # `pill-empty` is the v2 alias mapped to amber for "needs-action"
    # states; matches the spec's pill-class table for not_started.
    assert 'class="pill pill-empty">' in body
    assert "#1: not started" in body


# ── Per-page status pill — Save flips to in_progress ──────────────────


def test_page_status_pill_flips_to_in_progress_after_save(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-inprog",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)
    # Save only the optional ``comments`` field, leaving the required
    # ``rating`` field empty. State should land on "in progress" (data
    # exists, but required-fields-filled doesn't apply).
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data={f"response[{assignment.id}][comments]": "first thoughts"},
        follow_redirects=False,
    )
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    # `pill-warning` is the v2 alias for "in progress" (amber).
    assert 'class="pill pill-warning">' in body
    assert "#1: in progress" in body


def test_page_status_pill_flips_to_complete_when_required_filled(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """All required fields filled → `complete` (pill-success), even
    though no Submit has fired."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-complete",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data={f"response[{assignment.id}][rating]": "4"},
        follow_redirects=False,
    )
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert 'class="pill pill-success">' in body
    assert "#1: complete" in body


# ── Per-page status pill — Submit flips to submitted ──────────────────


def test_page_status_pill_flips_to_submitted_after_submit(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-submitted",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    assignment = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.reviewer_id == reviewer.id,
        )
    ).scalar_one()
    rae_client = make_client(rae)
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            f"response[{assignment.id}][rating]": "4",
        },
        follow_redirects=False,
    )
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    # `pill-success` is the v2 green pill.
    assert 'class="pill pill-success">' in body
    assert "#1: submitted" in body


# ── Session-wide rollup pill + per-instrument completion pills ────────


def test_session_status_pill_rolls_up_draft_saved_submitted(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The session-wide pill rolls the per-page states up: Draft on a
    fresh session, Saved but not submitted once a value is saved,
    Submitted once the page is submitted."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-sess-roll",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)

    fresh = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert 'class="rs-page-status-pills"' in fresh
    assert "Draft" in fresh

    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data={f"response[{assignment.id}][comments]": "thoughts"},
        follow_redirects=False,
    )
    saved = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert "Saved but not submitted" in saved

    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            f"response[{assignment.id}][rating]": "4",
        },
        follow_redirects=False,
    )
    submitted = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text
    assert "Submitted" in submitted


def test_instrument_card_shows_completion_pills(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The instrument card carries response-cell completion pills —
    required-only and overall — that track saved values. The pair has
    one reviewee and the seeded instrument's two fields (one required
    ``rating``, one optional ``comments``)."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-pills",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)

    fresh = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert "Required items completed: 0/1" in fresh
    assert "All items completed: 0/2" in fresh

    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data={f"response[{assignment.id}][rating]": "4"},
        follow_redirects=False,
    )
    after = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert "Required items completed: 1/1" in after
    assert "All items completed: 1/2" in after


# ``test_operator_preview_omits_overview_card`` retired in the
# Segment 18Q follow-on. The old synthetic iframe preview returned an
# empty ``page_statuses`` so the overview card collapsed when the
# session had no description; the new full-preview path reuses
# ``_surface_context`` against real assignments and emits the
# per-page status pills exactly as a reviewer would see them — the
# overview card now renders even with no session description. This
# is consistent with the "operator sees exactly what the reviewer
# would see" contract that drove the retirement.
