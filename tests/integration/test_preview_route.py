"""Integration tests for the legacy ``/operator/sessions/{id}/preview``
permanent-redirect (Segment 10B-3 → Segment 11F PR C → Segment 18Q
follow-on).

PR C retired the standalone preview route in favor of the iframe-
embedded surface card on the consolidated previews hub; the Segment
18Q follow-on then retired the iframe in favor of the standalone
operator-side full preview at ``/preview-surface/{page_n}``
(``_preview_surface.py``). The legacy ``/preview`` URL now 308s
straight to ``/preview-surface/1``. This file keeps the redirect
contract test, the operator-only access regression guard, the
deadline-observation D9 contract (rendering after deadline does not
mutate session state), and a regression guard that the live reviewer
surface still ships the write-path chrome.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import AuditEvent, ReviewSession
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)

from ._full_preview import get_full_preview_html


@pytest.fixture
def reviewer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="r-oid",
        email="r@example.edu",
        name="R Reviewer",
        provider="aad",
    )


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _populate_rosters(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,r@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def _generate_full_matrix(client: TestClient, db: Session, session_id: int) -> None:
    pin_full_matrix_on_all_instruments(db, session_id)
    generate_via_page_button(client, session_id)


def _activate(client: TestClient, db: Session, session_id: int) -> None:
    client.get(f"/operator/sessions/{session_id}/assignments?validated=1")
    client.post(
        f"/operator/sessions/{session_id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )


def test_preview_route_returns_308_to_full_preview(
    client: TestClient, db: Session
) -> None:
    """``/preview`` (singular) is a permanent redirect. Through
    Segment 11F PR C it pointed at the Previews hub's iframe surface
    card; the Segment 18Q follow-on retired that card and the
    redirect now points straight at the operator-side full preview
    (``/preview-surface/1``). Status 308 keeps the GET method on
    cross-client redirect handling and preserves legacy bookmarks."""
    review_session = _make_session(client, db, code="prev-308")

    response = client.get(
        f"/operator/sessions/{review_session.id}/preview",
        follow_redirects=False,
    )

    assert response.status_code == 308
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/preview-surface/1"
    )


def test_preview_route_redirects_non_operator_to_request_access(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Under the Segment 16A PR 1 operator-allowlist gate, a
    signed-in user who isn't on the workspace allowlist gets bounced
    to ``/request-access`` from the operator-router level — well
    before the per-session ``require_session_operator`` check fires.
    Either way the non-operator never sees the redirect into the
    operator hub."""
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="prev-308-403")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, db, review_session.id)

    other_client = make_client(reviewer_user)
    response = other_client.get(
        f"/operator/sessions/{review_session.id}/preview",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/request-access"


def test_preview_does_not_observe_deadline_side_effect(
    client: TestClient, db: Session
) -> None:
    """Bypassing deadline observation per D9 means an expired deadline
    does NOT trigger the lazy-close path on a preview render. The
    contract carries through the operator-side full preview route:
    rendering it after deadline must not emit a ``deadline``-reason
    ``instrument.closed`` audit event."""
    from datetime import datetime, timedelta, timezone

    review_session = _make_session(client, db, code="prev-deadline")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, db, review_session.id)
    _activate(client, db, review_session.id)
    db.refresh(review_session)

    # Set a deadline in the past after activation.
    review_session.deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    db.flush()

    body = get_full_preview_html(
        client, review_session.id, "r@example.edu"
    )
    # Surface still renders without observing the deadline.
    assert f"<h1>{review_session.name}</h1>" in body

    deadline_close = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.closed",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    for ev in deadline_close:
        assert ev.detail.get("reason") != "deadline"


def test_reviewer_side_surface_still_renders_write_path(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Regression guard for Slice 3's ``{% if not preview_mode %}``
    wrappers — the reviewer's normal /reviewer/sessions/{id} surface
    must still render Save / Submit / Discard / Clear (and no preview
    banner)."""
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="rev-regress")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, db, review_session.id)
    _activate(operator, db, review_session.id)

    reviewer_client = make_client(reviewer_user)
    body = reviewer_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text

    assert "Preview — not visible to reviewers" not in body
    assert ">Save</button>" in body
    assert (
        f'formaction="/reviewer/sessions/{review_session.id}/submit"' in body
    )
    assert ">Discard</a>" in body
    assert (
        f'action="/reviewer/sessions/{review_session.id}/1/save"' in body
    )
