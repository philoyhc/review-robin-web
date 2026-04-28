from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import AuditEvent, Reviewer, ReviewSession


def _make_session(client: TestClient, db: Session, code: str = "spring-2026") -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _reviewer_csv(*rows: tuple[str, str]) -> bytes:
    body = "ReviewerName,ReviewerEmail\n" + "".join(f"{n},{e}\n" for n, e in rows)
    return body.encode("utf-8")


def test_reviewer_import_redirects_and_persists_rows(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "reviewers.csv",
                _reviewer_csv(("Alice", "alice@example.edu"), ("Bob", "bob@example.edu")),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/operator/sessions/{review_session.id}"
    reviewers = list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).scalars()
    )
    assert {r.email for r in reviewers} == {"alice@example.edu", "bob@example.edu"}


def test_reviewer_import_writes_audit_event(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "reviewers.csv",
                _reviewer_csv(("Alice", "alice@example.edu")),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewers.imported")
    ).scalar_one()
    assert event.detail == {
        "replaced_count": 0,
        "new_count": 1,
        "filename": "reviewers.csv",
        "cascaded_assignment_count": 0,
    }
    assert "Imported 1 reviewers" in event.summary


def test_reviewer_import_blocks_replace_without_confirm(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "reviewers.csv",
                _reviewer_csv(("Alice", "alice@example.edu")),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "reviewers.csv",
                _reviewer_csv(("Carol", "carol@example.edu")),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    reviewers = list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).scalars()
    )
    assert {r.email for r in reviewers} == {"alice@example.edu"}


def test_reviewer_import_replace_with_confirm_succeeds(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "reviewers.csv",
                _reviewer_csv(("Alice", "alice@example.edu")),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "reviewers.csv",
                _reviewer_csv(("Carol", "carol@example.edu")),
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    reviewers = list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).scalars()
    )
    assert {r.email for r in reviewers} == {"carol@example.edu"}

    events = list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "reviewers.imported")
            .order_by(AuditEvent.id.desc())
        ).scalars()
    )
    assert events[0].detail == {
        "replaced_count": 1,
        "new_count": 1,
        "filename": "reviewers.csv",
        "cascaded_assignment_count": 0,
    }


def test_reviewer_import_renders_issues_for_bad_csv(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("bad.csv", b"ReviewerName\nAlice\n", "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Missing required column" in response.text
    reviewers = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).all()
    assert reviewers == []


def test_non_operator_gets_403_on_reviewer_import(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="alice-only")

    bob_client = make_client(bob)
    response = bob_client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "reviewers.csv",
                _reviewer_csv(("Eve", "eve@example.edu")),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_reviewee_import_persists_with_photolink(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)

    csv_body = (
        "RevieweeName,RevieweeEmail,PhotoLink,RevieweeTag1\n"
        "Carol,carol@example.edu,https://example.edu/c.jpg,cohort-A\n"
        "Dan,dan-2026,,\n"
    ).encode("utf-8")

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={"file": ("reviewees.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    from app.db.models import Reviewee

    reviewees = list(
        db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).scalars()
    )
    by_id = {r.email_or_identifier: r for r in reviewees}
    assert by_id["carol@example.edu"].profile_link == "https://example.edu/c.jpg"
    assert by_id["carol@example.edu"].tag_1 == "cohort-A"
    assert by_id["dan-2026"].profile_link is None


def test_reviewer_replace_cascades_assignments(
    client: TestClient, db: Session
) -> None:
    from sqlalchemy import select as _select

    from app.db.models import Assignment, ReviewSession

    response = client.post(
        "/operator/sessions",
        data={"name": "Cascade", "code": "cascade-r"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    review_session = db.execute(
        _select(ReviewSession).where(ReviewSession.code == "cascade-r")
    ).scalar_one()

    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                _reviewer_csv(("Alice", "alice@example.edu")),
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
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": "true"},
        follow_redirects=False,
    )
    assignments_before = list(
        db.execute(
            _select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert len(assignments_before) == 1

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                _reviewer_csv(("Bob", "bob@example.edu")),
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assignments_after = list(
        db.execute(
            _select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert assignments_after == []

    events = list(
        db.execute(
            _select(AuditEvent)
            .where(AuditEvent.event_type == "reviewers.imported")
            .order_by(AuditEvent.id.desc())
        ).scalars()
    )
    assert events[0].detail["cascaded_assignment_count"] == 1
    assert events[0].detail["replaced_count"] == 1


def test_reviewee_replace_cascades_assignments(
    client: TestClient, db: Session
) -> None:
    from sqlalchemy import select as _select

    from app.db.models import Assignment, Reviewee, ReviewSession

    response = client.post(
        "/operator/sessions",
        data={"name": "Cascade", "code": "cascade-e"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    review_session = db.execute(
        _select(ReviewSession).where(ReviewSession.code == "cascade-e")
    ).scalar_one()

    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                _reviewer_csv(("Alice", "alice@example.edu")),
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
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\nDan,dan-2026\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": "true"},
        follow_redirects=False,
    )
    assignments_before = list(
        db.execute(
            _select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert len(assignments_before) == 2

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nEve,eve@example.edu\n",
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    reviewees = list(
        db.execute(
            _select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).scalars()
    )
    assert {r.email_or_identifier for r in reviewees} == {"eve@example.edu"}

    assignments_after = list(
        db.execute(
            _select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert assignments_after == []

    events = list(
        db.execute(
            _select(AuditEvent)
            .where(AuditEvent.event_type == "reviewees.imported")
            .order_by(AuditEvent.id.desc())
        ).scalars()
    )
    assert events[0].detail["cascaded_assignment_count"] == 2


def test_reviewer_import_form_warns_about_cascade(
    client: TestClient, db: Session
) -> None:
    from sqlalchemy import select as _select

    from app.db.models import ReviewSession

    response = client.post(
        "/operator/sessions",
        data={"name": "Warn", "code": "warn-test"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    review_session = db.execute(
        _select(ReviewSession).where(ReviewSession.code == "warn-test")
    ).scalar_one()

    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                _reviewer_csv(("Alice", "alice@example.edu")),
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
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": "true"},
        follow_redirects=False,
    )

    page = client.get(
        f"/operator/sessions/{review_session.id}/reviewers/import"
    )

    assert page.status_code == 200
    assert "1 existing assignment" in page.text
    assert "will be deleted" in page.text


def test_reviewers_page_lists_imported_rows(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, code="r-list")
    csv_body = (
        b"ReviewerName,ReviewerEmail,ReviewerTag1\n"
        b"Alice,alice@example.edu,senior\n"
        b"Bob,bob@example.edu,\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("r.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )

    response = client.get(f"/operator/sessions/{review_session.id}/reviewers")

    assert response.status_code == 200
    body = response.text
    assert "Alice" in body
    assert "alice@example.edu" in body
    assert "Bob" in body
    assert "bob@example.edu" in body
    assert "senior" in body
    assert f"/operator/sessions/{review_session.id}\"" in body  # back link


def test_reviewees_page_lists_imported_rows_with_photolink(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="e-list")
    csv_body = (
        b"RevieweeName,RevieweeEmail,PhotoLink\n"
        b"Carol,carol@example.edu,https://example.edu/c.jpg\n"
        b"Dan,dan-2026,\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={"file": ("e.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )

    response = client.get(f"/operator/sessions/{review_session.id}/reviewees")

    assert response.status_code == 200
    body = response.text
    assert "Carol" in body
    assert "carol@example.edu" in body
    assert "Dan" in body
    assert "dan-2026" in body
    assert "https://example.edu/c.jpg" in body


def test_non_operator_gets_403_on_roster_pages(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="alice-rosters")

    bob_client = make_client(bob)
    assert (
        bob_client.get(f"/operator/sessions/{review_session.id}/reviewers").status_code
        == 403
    )
    assert (
        bob_client.get(f"/operator/sessions/{review_session.id}/reviewees").status_code
        == 403
    )
