from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import AuditEvent, Reviewer, ReviewSession
from ._full_matrix import full_matrix_seed_id


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
    assert response.headers["location"] == f"/operator/sessions/{review_session.id}/reviewers"
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
    assert event.detail["counts"] == {
        "new": 1,
        "replaced": 0,
        "cascaded_assignments": 0,
    }
    assert event.detail["context"] == {"filename": "reviewers.csv"}
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
    assert events[0].detail["counts"] == {
        "new": 1,
        "replaced": 1,
        "cascaded_assignments": 0,
    }
    assert events[0].detail["context"] == {"filename": "reviewers.csv"}


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


def _reviewee_csv(*rows: tuple[str, str]) -> bytes:
    body = "RevieweeName,RevieweeEmail\n" + "".join(f"{n},{e}\n" for n, e in rows)
    return body.encode("utf-8")


def _post_reviewers(client: TestClient, sid: int, *rows: tuple[str, str]):
    return client.post(
        f"/operator/sessions/{sid}/reviewers/import",
        files={"file": ("reviewers.csv", _reviewer_csv(*rows), "text/csv")},
        follow_redirects=False,
    )


def _post_reviewees(client: TestClient, sid: int, *rows: tuple[str, str]):
    return client.post(
        f"/operator/sessions/{sid}/reviewees/import",
        files={"file": ("reviewees.csv", _reviewee_csv(*rows), "text/csv")},
        follow_redirects=False,
    )


def test_cross_table_reviewer_matches_reviewee_same_name_is_allowed(
    client: TestClient, db: Session
) -> None:
    """Person who is both reviewer + reviewee imports cleanly when names match."""
    review_session = _make_session(client, db)
    assert _post_reviewees(client, review_session.id, ("Alice", "alice@example.edu")).status_code == 303

    response = _post_reviewers(client, review_session.id, ("Alice", "alice@example.edu"))

    assert response.status_code == 303
    reviewers = list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).scalars()
    )
    assert {r.email for r in reviewers} == {"alice@example.edu"}


def test_cross_table_reviewer_matches_reviewee_different_name_blocks(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    assert _post_reviewees(client, review_session.id, ("Alice", "alice@example.edu")).status_code == 303

    response = _post_reviewers(client, review_session.id, ("Alex", "alice@example.edu"))

    assert response.status_code == 400
    body = response.text
    assert "names must match" in body
    reviewers = list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).scalars()
    )
    assert reviewers == []


def test_cross_table_reviewee_matches_reviewer_different_name_blocks(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    assert _post_reviewers(client, review_session.id, ("Alice", "alice@example.edu")).status_code == 303

    response = _post_reviewees(client, review_session.id, ("Alex", "alice@example.edu"))

    assert response.status_code == 400
    assert "names must match" in response.text


def test_cross_table_reviewee_non_email_identifier_never_collides(
    client: TestClient, db: Session
) -> None:
    """Reviewees without @ in identifier can't collide with reviewer emails."""
    review_session = _make_session(client, db)
    assert _post_reviewers(client, review_session.id, ("Alice", "alice@example.edu")).status_code == 303

    response = _post_reviewees(client, review_session.id, ("Different Person", "alice"))

    assert response.status_code == 303


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
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "true"},
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
    assert events[0].detail["counts"]["cascaded_assignments"] == 1
    assert events[0].detail["counts"]["replaced"] == 1


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
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "true"},
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
    assert events[0].detail["counts"]["cascaded_assignments"] == 2


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
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "true"},
        follow_redirects=False,
    )

    page = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    )

    assert page.status_code == 200
    # The cascade warning now lives inline in the confirm-replace
    # label: "Yes, replace the existing N reviewer and delete the M
    # assignment." (with N/M wrapped as pills).
    assert "1 reviewer" in page.text
    assert "1 assignment" in page.text
    assert "delete the" in page.text


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


def test_reviewers_page_renders_tag_columns_with_visibility_toggles(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="r-tags")
    csv_body = (
        b"ReviewerName,ReviewerEmail,ReviewerTag1,ReviewerTag2\n"
        b"Alice,alice@example.edu,senior,cohort-a\n"
        b"Bob,bob@example.edu,,\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("r.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )

    body = client.get(f"/operator/sessions/{review_session.id}/reviewers").text

    # New per-tag columns replace the combined "Tags" cell.
    assert '<th class="tag-col tag-col-1">Tag1</th>' in body
    assert '<th class="tag-col tag-col-2">Tag2</th>' in body
    assert '<th class="tag-col tag-col-3">Tag3</th>' in body
    assert "<th>Tags</th>" not in body

    # Toggle row above the table — Tag1 / Tag2 ticked (have data),
    # Tag3 disabled because the column has no data anywhere.
    assert 'data-tag-toggle="1"\n                 checked' in body
    assert 'data-tag-toggle="2"\n                 checked' in body
    assert 'data-tag-toggle="3"\n                 checked' not in body
    assert (
        'data-tag-toggle="3"\n                 disabled aria-disabled="true" '
        'title="No data in this column"'
    ) in body
    # Tag1 / Tag2 are NOT disabled (they have data).
    assert (
        'data-tag-toggle="1"\n                 disabled' not in body
    )

    # Tag values render in their own cells (no "1: " prefix).
    assert "1: senior" not in body
    assert ">senior</td>" in body


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
