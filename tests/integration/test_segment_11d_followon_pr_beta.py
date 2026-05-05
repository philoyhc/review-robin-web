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
    operator_client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    operator_client.get(f"/operator/sessions/{review_session.id}?validated=1")
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


# ── Top-row layout — bottom-grid carries description + status panel ───


def test_top_row_uses_bottom_grid_layout(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The reviewer surface's top-row is a `.bottom-grid` carrying
    the description card on the left and the status panel on the
    right. Both render as `.card` instances inside the grid."""
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
    assert '<div class="bottom-grid">' in body
    assert 'class="card rs-description-card"' in body
    assert 'class="card rs-status-panel"' in body
    # Description content lives inside the card.
    assert "Some context for the reviewers." in body


def test_status_panel_renders_when_no_description(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the session has no description, the status panel still
    renders on the right. The left slot collapses to an empty `<div>`
    so the grid keeps its 2-column shape."""
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
    assert '<div class="bottom-grid">' in body
    assert 'class="card rs-status-panel"' in body
    # Description card is suppressed.
    assert 'class="card rs-description-card"' not in body


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
    assert "Page 1: not started" in body


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
    assert "Page 1: in progress" in body


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
    assert "Page 1: complete" in body


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
            "current_position": "1",
            f"response[{assignment.id}][rating]": "4",
        },
        follow_redirects=False,
    )
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    # `pill-success` is the v2 green pill.
    assert 'class="pill pill-success">' in body
    assert "Page 1: submitted" in body


# ── Operator preview suppresses per-page pills ────────────────────────


def test_operator_preview_status_panel_has_no_per_page_pills(
    client: TestClient, db: Session
) -> None:
    """Operator preview reuses the surface template but the panel
    renders without per-page pills (preview is read-only and synthetic;
    per-page state is moot)."""
    review_session_response = client.post(
        "/operator/sessions",
        data={"name": "Prev", "code": "rae-prev-pills"},
        follow_redirects=False,
    )
    assert review_session_response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "rae-prev-pills")
    ).scalar_one()
    body = client.get(
        f"/operator/sessions/{review_session.id}/preview"
    ).text
    # The panel still renders (layout-stable) but the pill list is empty.
    assert 'class="card rs-status-panel"' in body
    assert 'class="rs-page-status-pills"' not in body
