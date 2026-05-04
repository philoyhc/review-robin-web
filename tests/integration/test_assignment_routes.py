from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, AuditEvent, ReviewSession


def _make_session(
    client: TestClient, db: Session, code: str = "spring-2026"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_roster(
    client: TestClient,
    session_id: int,
    *,
    reviewer_emails: list[str],
    reviewee_idents: list[str],
) -> None:
    reviewer_csv = "ReviewerName,ReviewerEmail\n" + "".join(
        f"R{i},{email}\n" for i, email in enumerate(reviewer_emails)
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={"file": ("r.csv", reviewer_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    reviewee_csv = "RevieweeName,RevieweeEmail\n" + "".join(
        f"E{i},{ident}\n" for i, ident in enumerate(reviewee_idents)
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={"file": ("e.csv", reviewee_csv.encode(), "text/csv")},
        follow_redirects=False,
    )


def test_full_matrix_save_persists_assignments_and_sets_mode(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu", "dan-2026"],
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/assignments"
    )
    rows = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert len(rows) == 2
    assert all(r.created_by_mode == "full_matrix" for r in rows)

    db.refresh(review_session)
    assert review_session.assignment_mode == "full_matrix"

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "assignments.generated")
    ).scalar_one()
    assert event.detail == {
        "mode": "full_matrix",
        "replaced_count": 0,
        "new_count": 2,
        "excluded_counts": {},
        "filename": None,
    }


def test_full_matrix_re_save_without_confirm_blocks(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": "true"},
        follow_redirects=False,
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Replace not confirmed" in response.text
    assert (
        len(
            list(
                db.execute(
                    select(Assignment).where(
                        Assignment.session_id == review_session.id
                    )
                ).scalars()
            )
        )
        == 1
    )


def test_full_matrix_re_save_with_confirm_replaces(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": "true"},
        follow_redirects=False,
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": "", "confirm_replace": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    events = list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "assignments.generated")
            .order_by(AuditEvent.id.desc())
        ).scalars()
    )
    assert events[0].detail["replaced_count"] == 1


def test_assignments_hub_renders_count_and_mode(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )

    empty = client.get(f"/operator/sessions/{review_session.id}/assignments")
    assert empty.status_code == 200
    # Empty state shows the reviewer/reviewee counts in the chrome status
    # row; the FullMatrix Generate button is rendered inline on the page.
    assert "Reviewers:" in empty.text
    assert ">Generate</button>" in empty.text

    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": "true"},
        follow_redirects=False,
    )

    populated = client.get(f"/operator/sessions/{review_session.id}/assignments")
    assert 'pill-info">1</span>' in populated.text
    assert "full_matrix" in populated.text


def test_assignments_hub_rule_based_card_uses_placeholder_macro(
    client: TestClient, db: Session
) -> None:
    """The Rule Based Assignment card on the assignments hub uses
    the canonical .card.placeholder treatment (shared with Quick
    Setup and Extract Data on Session Home) until Segment 13 ships
    the real rule builder. The card renders with id, title, body,
    and a disabled action button."""

    review_session = _make_session(client, db)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text

    assert 'class="card placeholder" id="rule-based-assignment"' in body
    assert "<h2>Rule Based Assignment</h2>" in body
    assert "matching reviewer and reviewee attributes via rules" in body
    assert "Rule Based Assignment lands in Segment 13" in body
    assert ">Build rules</button>" in body


def test_non_operator_gets_403_on_assignments_hub_and_post(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="alice-only")

    bob_client = make_client(bob)
    hub = bob_client.get(f"/operator/sessions/{review_session.id}/assignments")
    assert hub.status_code == 403

    post = bob_client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": "true"},
        follow_redirects=False,
    )
    assert post.status_code == 403


def test_assignments_hub_truncates_large_pair_list(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=[f"r{i}@example.edu" for i in range(7)],
        reviewee_idents=[f"e{i}@example.edu" for i in range(31)],
    )

    # Save 217 pairs
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )

    # The hub hosts the Current pairs preview after save
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert "Showing first 200 of 217" in body
    assert "and 17 more" in body


def test_manual_save_persists_with_include_and_context(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="m-save")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu", "bob@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )

    csv_body = (
        b"ReviewerEmail,RevieweeEmail,IncludeAssignment,"
        b"AssignmentContext1,AssignmentContext2\n"
        b"alice@example.edu,carol@example.edu,true,morning,room-A\n"
        b"bob@example.edu,carol@example.edu,false,,\n"
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={"file": ("manual.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    rows = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert len(rows) == 2
    by_reviewer = {r.reviewer.email: r for r in rows}
    assert by_reviewer["alice@example.edu"].include is True
    assert by_reviewer["alice@example.edu"].context == {
        "assignment_context_1": "morning",
        "assignment_context_2": "room-A",
    }
    assert by_reviewer["bob@example.edu"].include is False
    assert by_reviewer["bob@example.edu"].context is None
    assert all(r.created_by_mode == "manual" for r in rows)

    db.refresh(review_session)
    assert review_session.assignment_mode == "manual"

    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "assignments.generated")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event.detail["mode"] == "manual"
    assert event.detail["new_count"] == 2
    assert event.detail["filename"] == "manual.csv"


def test_manual_import_blocks_unknown_reviewer(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="m-bad")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "manual.csv",
                b"ReviewerEmail,RevieweeEmail\nghost@example.edu,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Unknown reviewer" in response.text
    assert (
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).first()
        is None
    )


def test_non_operator_gets_403_on_manual_import(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="m-403")

    bob_client = make_client(bob)
    response = bob_client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "manual.csv",
                b"ReviewerEmail,RevieweeEmail\nfoo@example.edu,bar@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_hub_renders_current_pairs_card_when_assignments_exist(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="hub-pairs")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )

    empty = client.get(f"/operator/sessions/{review_session.id}/assignments")
    assert "Current pairs" not in empty.text

    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": "true"},
        follow_redirects=False,
    )

    populated = client.get(f"/operator/sessions/{review_session.id}/assignments")
    body = populated.text
    assert "Current pairs" in body
    assert "alice@example.edu" in body
    assert "carol@example.edu" in body


def test_manual_setup_page_shows_saved_pair_after_import(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="m-names")
    reviewer_csv = (
        "ReviewerName,ReviewerEmail\n"
        "Alice Example,alice@example.edu\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("r.csv", reviewer_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    reviewee_csv = (
        "RevieweeName,RevieweeEmail\n"
        "Carol Example,carol@example.edu\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={"file": ("e.csv", reviewee_csv.encode(), "text/csv")},
        follow_redirects=False,
    )

    save = client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "manual.csv",
                b"ReviewerEmail,RevieweeEmail\nalice@example.edu,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert "Alice Example" in body
    assert "Carol Example" in body


def test_manual_save_persists_pair_and_assignment_context(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="m-context")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )

    csv_body = (
        b"ReviewerEmail,RevieweeEmail,PairContext1,AssignmentContext1\n"
        b"alice@example.edu,carol@example.edu,room-A,panel-1\n"
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={"file": ("manual.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    assert assignment.context == {
        "pair_context_1": "room-A",
        "assignment_context_1": "panel-1",
    }
