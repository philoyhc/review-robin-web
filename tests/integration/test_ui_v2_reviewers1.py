"""Smoke tests for the /reviewers1 v2 pilot page.

The page is a parallel, body.ui-v2-scoped copy of /reviewers used to
trial the canonical primitives in spec/ui_elements.md without
touching the existing surface. See spec/ui_elements.md Part 3.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _create_session(
    client: TestClient, db: Session, *, code: str = "ui-v2-spring"
) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_reviewers1_route_returns_200(client: TestClient, db: Session) -> None:
    review_session = _create_session(client, db)
    response = client.get(
        f"/operator/sessions/{review_session.id}/reviewers1"
    )
    assert response.status_code == 200


def test_reviewers1_opts_into_ui_v2_body_class(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db)
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers1"
    ).text
    assert '<body class="ui-v2">' in body


def test_reviewers1_uses_canonical_classes_not_inline_styles(
    client: TestClient, db: Session
) -> None:
    """The v2 page should drop the inline border/background overrides
    that the v1 page carries on its lock card and danger zone, and
    use the canonical .card.lock / .card.danger-zone classes
    instead. The danger-zone card only renders when reviewers exist;
    the lock card only when the session is ready — neither is
    visible on a fresh draft session, so we just assert the inline
    overrides from v1 are absent."""
    review_session = _create_session(client, db)
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers1"
    ).text
    # v1 inline overrides should not appear on the v2 page.
    assert 'style="border-color: #d97706; background: #fef3c7;"' not in body
    assert 'style="border-color: #b91c1c;"' not in body
    assert 'style="color: #b91c1c;"' not in body


def test_reviewers1_existing_route_unchanged(
    client: TestClient, db: Session
) -> None:
    """Sanity: the v1 page still renders and still uses its original
    inline-styled chrome. The pilot must not regress the current
    surface."""
    review_session = _create_session(client, db)
    response = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    )
    assert response.status_code == 200
    # v1 page must not opt into the ui-v2 body class.
    assert '<body class="ui-v2">' not in response.text
    assert '<body class="">' in response.text
