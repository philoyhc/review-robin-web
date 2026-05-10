"""Integration tests for ``GET
/operator/sessions/{id}/export/{reviewers,reviewees,relationships}.csv``
— Segment 12A-1 PR 2 + Segment 12A-3 PR 1.

Covers route surface (auth, response shape, filename + audit
emission). Per-row content shape is unit-tested in
``tests/unit/test_reviewers_extract.py`` /
``tests/unit/test_reviewees_extract.py`` /
``tests/unit/test_relationships_extract.py``.
"""

from __future__ import annotations

import csv
import io
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str = "ext-r"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Roster", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_roster(client: TestClient, review_session: ReviewSession) -> None:
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                (
                    "ReviewerName,ReviewerEmail,ReviewerTag1\n"
                    "Alex,alex@example.edu,cohort-a\n"
                    "Bob,bob@example.edu,\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                (
                    "RevieweeName,RevieweeEmail,RevieweeTag1,PhotoLink\n"
                    "Carol,carol@example.edu,design,https://example.edu/c.jpg\n"
                    "Dan,dan@example.edu,,\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
        follow_redirects=False,
    )


# --------------------------------------------------------------------------- #
# Reviewers route
# --------------------------------------------------------------------------- #


def test_reviewers_route_streams_csv_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="r-fname")
    _seed_roster(client, review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/reviewers.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="r-fname_reviewers.csv"'
    )

    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == [
        "ReviewerName",
        "ReviewerEmail",
        "ReviewerTag1",
        "ReviewerTag2",
        "ReviewerTag3",
    ]
    body = rows[1:]
    assert {r[1] for r in body} == {"alex@example.edu", "bob@example.edu"}


def test_reviewers_route_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="r-audit")
    _seed_roster(client, review_session)
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/reviewers.csv"
    )
    assert response.status_code == 200
    response.read()

    db.expire_all()
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.reviewers_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    assert len(events) == 1
    detail = cast(dict, events[0].detail)
    assert detail["session_code"] == "r-audit"
    assert detail["counts"]["rows"] == 2


def test_reviewers_route_empty_session_emits_header_only(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="r-empty")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/reviewers.csv"
    )
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.text)))
    assert len(rows) == 1
    assert rows[0][0] == "ReviewerName"

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.reviewers_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = cast(dict, event.detail)
    assert detail["counts"]["rows"] == 0


# --------------------------------------------------------------------------- #
# Reviewees route
# --------------------------------------------------------------------------- #


def test_reviewees_route_streams_csv_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="e-fname")
    _seed_roster(client, review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/reviewees.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="e-fname_reviewees.csv"'
    )
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == [
        "RevieweeName",
        "RevieweeEmail",
        "RevieweeTag1",
        "RevieweeTag2",
        "RevieweeTag3",
        "PhotoLink",
    ]


def test_reviewees_route_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="e-audit")
    _seed_roster(client, review_session)
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/reviewees.csv"
    )
    assert response.status_code == 200
    response.read()

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.reviewees_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = cast(dict, event.detail)
    assert detail["counts"]["rows"] == 2


def _seed_relationships(
    client: TestClient, review_session: ReviewSession
) -> None:
    client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "p.csv",
                (
                    "ReviewerEmail,RevieweeEmail,PairContextTag1\n"
                    "alex@example.edu,carol@example.edu,advisor\n"
                    "bob@example.edu,dan@example.edu,\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
        follow_redirects=False,
    )


# --------------------------------------------------------------------------- #
# Relationships route
# --------------------------------------------------------------------------- #


def test_relationships_route_streams_csv_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="p-fname")
    _seed_roster(client, review_session)
    _seed_relationships(client, review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/relationships.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="p-fname_relationships.csv"'
    )
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == [
        "ReviewerEmail",
        "RevieweeEmail",
        "PairContextTag1",
        "PairContextTag2",
        "PairContextTag3",
        "Status",
    ]


def test_relationships_route_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="p-audit")
    _seed_roster(client, review_session)
    _seed_relationships(client, review_session)
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/relationships.csv"
    )
    assert response.status_code == 200
    response.read()

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.relationships_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = cast(dict, event.detail)
    assert detail["counts"]["rows"] == 2


def test_routes_reject_non_operator(
    db: Session,
    alice: object,
    bob: object,
    make_client: object,
) -> None:
    alice_client = make_client(alice)  # type: ignore[operator]
    review_session = _make_session(alice_client, db, code="permgate")

    bob_client = make_client(bob)  # type: ignore[operator]
    for kind in ("reviewers", "reviewees", "relationships"):
        response = bob_client.get(
            f"/operator/sessions/{review_session.id}/export/{kind}.csv"
        )
        assert response.status_code in (403, 404)
