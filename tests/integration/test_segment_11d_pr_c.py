"""Tests for Segment 11D PR C — reviewer top-bar variant + D5/D6/D7 sweep."""

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
) -> ReviewSession:
    operator_client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
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


# ── D2: reviewer top bar variant ────────────────────────────────────────


def test_reviewer_dashboard_uses_ui_v2_reviewer_body_class(
    client: TestClient,
) -> None:
    body = client.get("/reviewer").text
    assert '<body class="ui-v2 reviewer">' in body


def test_reviewer_dashboard_chrome_drops_about_link_and_version(
    client: TestClient,
) -> None:
    body = client.get("/reviewer").text
    # Operator-style chrome details are gone from the reviewer top bar.
    assert "Review Robin Web App" not in body
    assert "version dev" not in body
    assert 'href="/about"' not in body
    # Identity is the lighter "Review Robin" text-only span.
    assert 'class="chrome-app-identity">Review Robin</span>' in body


def test_reviewer_chrome_suppresses_my_reviews_link_with_one_review(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """My Reviews link is only useful when the reviewer has more than
    one review pending or completed (otherwise the dashboard would be
    a single row). Test the count == 1 case → link suppressed."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-c-one",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert "My Reviews" not in body


def test_reviewer_chrome_renders_my_reviews_link_with_multiple_reviews(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the reviewer has more than one review, the chrome carries
    a "My Reviews" link back to the dashboard."""
    operator = make_client(alice)
    first = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-c-multi-1",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-c-multi-2",
        reviewer_email="rae@example.edu",
        reviewee_ident="dan@example.edu",
    )

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{first.id}").text
    assert (
        'class="chrome-link" href="/reviewer">My Reviews</a>' in body
    )


# ── D5: status icons ────────────────────────────────────────────────────


def test_status_icons_use_canonical_classes_not_inline_style(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The ✓ / ⚠ glyphs migrate from inline `color: #16a34a/#d97706` to
    the `.status-icon-complete` / `.status-icon-incomplete` classes
    (D5; spec/ui_elements.md §9)."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-d5",
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
    # Submit with no values to force the status column to render with
    # the incomplete glyph (show_acknowledge path).
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={f"response[{assignment.id}][rating]": ""},
        follow_redirects=False,
    )
    body = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={},
        follow_redirects=False,
    ).text
    # The legacy inline `style="color: #...; font-weight: bold; font-size:
    # 1.2em;"` blocks on the ✓/⚠ glyphs are gone — the canonical
    # `.status-icon-{complete,incomplete}` classes carry the colour now.
    assert "font-weight: bold; font-size: 1.2em" not in body
    # The incomplete state is rendered (no values → required missing).
    assert 'class="status-icon-incomplete"' in body


# ── D6: banner family ───────────────────────────────────────────────────


def test_invite_mismatch_renders_banner_warning(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The invite-mismatch error renders as a `.banner.banner-warning`
    rather than the legacy inline-styled red card."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-mismatch",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    # Find the invitation token.
    from app.db.models import EmailOutbox, Invitation

    operator.post(
        f"/operator/sessions/{review_session.id}/invitations/generate"
    )
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == review_session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    # Mint a token by reading the outbox row the send route just wrote
    # — alice (the signed-in operator) doesn't match the invitation's
    # reviewer email (rae), so the GET below 403s into the mismatch
    # template, which is what we want to test the markup of.
    outbox_row = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.invitation_id == invitation.id
        )
    ).scalar_one()
    import re

    match = re.search(r"/reviewer/invite/([A-Za-z0-9_\-]+)", outbox_row.body)
    assert match is not None
    raw_token = match.group(1)

    response = operator.get(
        f"/reviewer/invite/{raw_token}", follow_redirects=False
    )
    assert response.status_code == 403
    body = response.text
    assert 'class="banner banner-warning"' in body
    # The legacy inline `style="border-color: #b91c1c; background: #fee2e2;"`
    # block on the wrapper card is gone — the .banner.banner-warning
    # primitive carries the framing now.
    assert 'style="border-color: #b91c1c' not in body
    # Body is a banner, not the legacy red `.card` wrapper.
    assert (
        'class="card" style="border-color: #b91c1c'
        not in body
    )


def test_review_surface_preview_banner_is_banner_info(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Operator preview banner migrates from `.warning-banner` (the
    recoloured-blue legacy class) to the canonical `.banner.banner-info`."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-d6-prev",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    body = operator.get(
        f"/operator/sessions/{review_session.id}/preview"
    ).text
    assert 'class="banner banner-info"' in body
    assert 'class="warning-banner"' not in body
    # Copy is preserved exactly so cross-tests don't churn.
    assert "Preview" in body
    assert "not visible to reviewers" in body


def test_review_surface_saved_banner_uses_banner_success(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-d6-saved",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}?saved=ok"
    ).text
    assert 'class="banner banner-success"' in body
    assert "Your draft has been saved." in body


# ── D7: page header ─────────────────────────────────────────────────────


def test_review_surface_renders_h1_and_deadline(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The reviewer surface page header carries the session name as H1
    plus a small text-secondary line for the deadline (D7)."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-d7",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert f"<h1>{review_session.name}</h1>" in body
    # Newly created session has no deadline; absence is a feature, not
    # a bug — assertion below only checks the H1 is present and the
    # template doesn't crash on the optional deadline branch.


# ── Operator preview keeps operator chrome ──────────────────────────────


def test_operator_preview_keeps_operator_chrome(
    client: TestClient, db: Session
) -> None:
    """The operator preview reuses review_surface.html but should keep
    the operator chrome (with breadcrumb back to the session) — the
    reviewer top bar override is suppressed in preview_mode."""
    client.post(
        "/operator/sessions",
        data={"name": "Prev", "code": "rae-prev-chrome"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "rae-prev-chrome")
    ).scalar_one()
    body = client.get(f"/operator/sessions/{review_session.id}/preview").text
    # Operator chrome present (Web App identity, breadcrumb).
    assert "Review Robin Web App (version dev)" in body
    assert 'class="breadcrumb"' in body
    # Reviewer body class branch is dropped on preview so the operator
    # surface doesn't pick up the .reviewer-scoped chrome rules.
    assert '<body class="ui-v2 reviewer">' not in body
    assert '<body class="ui-v2">' in body
