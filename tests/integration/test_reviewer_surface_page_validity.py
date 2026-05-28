"""Segment 18N PR 1 — page-validity 404 alignment across the
reviewer-surface GET, the save POST, and the operator-side
preview route.

Pre-PR-1 the GET + preview routes clamped ``page_count = len(pages)
or 1`` (rendering empty content on ``/1`` for empty sessions)
while the save POST hard-failed with ``len(pages)`` (404 on
empty). PR 1 lifts a shared ``validate_page_n`` helper that all
three routes now call; ``validate_page_n`` raises 404 on every
out-of-range case (including the unreachable-in-practice empty-
pages case). These integration tests pin that all three routes
agree on every reachable in-range / out-of-range combination.
"""
from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import ReviewSession

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _make_active_session_with_one_page(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
) -> ReviewSession:
    """One reviewer, one reviewee, one instrument → one page session
    (no page break, so all instruments collapse to page 1)."""
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
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    operator_client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    return review_session


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def test_get_in_range_page_returns_200(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Sanity check: GET ``/1`` of a single-page session returns
    200 (this is the pre-PR-1 happy-path, unchanged)."""
    review_session = _make_active_session_with_one_page(
        client, db, code="pg-get-1", reviewer_email=rae.email
    )
    rae_client = make_client(rae)
    resp = rae_client.get(f"/reviewer/sessions/{review_session.id}/1")
    assert resp.status_code == 200


@pytest.mark.parametrize("bad_page_n", [2, 5, 999])
def test_get_out_of_range_page_returns_404(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
    bad_page_n: int,
) -> None:
    """GET on a page beyond the last 404s. Pre-PR-1 this matched
    the existing GET shape (clamp returned 404 too); pin to lock it
    against drift."""
    review_session = _make_active_session_with_one_page(
        client, db, code=f"pg-get-{bad_page_n}", reviewer_email=rae.email
    )
    rae_client = make_client(rae)
    resp = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/{bad_page_n}"
    )
    assert resp.status_code == 404


@pytest.mark.parametrize("bad_page_n", [2, 5, 999])
def test_save_post_out_of_range_page_returns_404(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
    bad_page_n: int,
) -> None:
    """POST save on a page beyond the last 404s. Matches the GET
    route's behaviour at the same indices — PR 1's alignment
    pinned."""
    review_session = _make_active_session_with_one_page(
        client, db, code=f"pg-post-{bad_page_n}", reviewer_email=rae.email
    )
    rae_client = make_client(rae)
    resp = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/{bad_page_n}/save",
        data={},
        follow_redirects=False,
    )
    assert resp.status_code == 404


def test_operator_preview_in_range_page_returns_200(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
) -> None:
    """Sanity check the preview route is reachable — distinguishes
    the page-validity 404 in the test below from a route-not-found
    404."""
    review_session = _make_active_session_with_one_page(
        client, db, code="pg-prev-ok", reviewer_email=rae.email
    )
    resp = client.get(
        f"/operator/sessions/{review_session.id}/preview-surface/1"
        f"?reviewer_email={rae.email}",
    )
    assert resp.status_code == 200


@pytest.mark.parametrize("bad_page_n", [2, 5, 999])
def test_operator_preview_out_of_range_page_returns_404(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    bad_page_n: int,
) -> None:
    """The operator-side preview surface uses the same helper —
    out-of-range 404s match the reviewer surface's behaviour at
    every page index. (Confirmed as a page-validity 404 by the
    ``_in_range_page_returns_200`` test above, which exercises the
    same route at the valid index.)"""
    review_session = _make_active_session_with_one_page(
        client, db, code=f"pg-prev-{bad_page_n}", reviewer_email=rae.email
    )
    # The operator preview is owner-only, so the alice-default
    # ``client`` fixture (which the seed used) is the right caller.
    resp = client.get(
        f"/operator/sessions/{review_session.id}/preview-surface/"
        f"{bad_page_n}?reviewer_email={rae.email}",
    )
    assert resp.status_code == 404
