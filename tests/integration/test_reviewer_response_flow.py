from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, AuditEvent, Instrument, Reviewer, ReviewSession


def _operator_creates_session_with_pair(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
    reviewee_ident: str,
    activate: bool = True,
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
    if activate:
        _activate(operator_client, db, review_session)
    return review_session


def _activate(
    operator_client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    operator_client.get(f"/operator/sessions/{review_session.id}?validated=1")
    response = operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(review_session)
    assert review_session.status == "ready"


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def test_dashboard_lists_only_sessions_where_user_is_active_reviewer(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    matched = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-session",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    _operator_creates_session_with_pair(
        operator,
        db,
        code="other-session",
        reviewer_email="someone@example.edu",
        reviewee_ident="dan@example.edu",
    )

    rae_client = make_client(rae)
    response = rae_client.get("/reviewer")

    assert response.status_code == 200
    assert "Rae-Session" in response.text or matched.name in response.text
    assert "Other-Session" not in response.text


def test_dashboard_skips_inactive_reviewer_rows(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-inactive",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    reviewer.status = "inactive"
    db.commit()

    rae_client = make_client(rae)
    response = rae_client.get("/reviewer")

    assert response.status_code == 200
    assert "Rae-Inactive" not in response.text


def test_surface_renders_pair_context_and_default_fields(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-ctx",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "m.csv",
                (
                    b"ReviewerEmail,RevieweeEmail,PairContext1,AssignmentContext1\n"
                    b"rae@example.edu,carol@example.edu,morning,panel-1\n"
                ),
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")

    assert response.status_code == 200
    assert "Carol" in response.text
    assert "Pair context 1" in response.text
    assert "morning" in response.text
    assert "P1:" not in response.text  # 10B-1 moved pair context out of identity cell
    assert "panel-1" not in response.text  # assignment_context hidden
    assert "Rating" in response.text
    assert "Comments" in response.text


def test_surface_heading_uses_position_not_system_name(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Reviewer-surface heading is position-based when description is empty.

    Regression: Instrument.name is a stable system handle (used for Manual
    CSV cross-references per item #28). After earlier instruments are
    deleted, a survivor named e.g. "instrument_4" can sit at position 1.
    The reviewer-surface heading must show "Instrument #1" (matching the
    operator surface's loop-index render), not the historical name.
    """
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-heading",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,
    )
    only_instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    only_instrument.name = "instrument_4"
    only_instrument.description = None
    db.commit()
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")

    assert response.status_code == 200
    assert "Instrument #1" in response.text
    assert "instrument_4" not in response.text


def test_surface_filters_out_excluded_assignments(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-excl",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "m.csv",
                (
                    b"ReviewerEmail,RevieweeEmail,IncludeAssignment\n"
                    b"rae@example.edu,carol@example.edu,false\n"
                ),
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")

    assert response.status_code == 200
    assert "Carol" not in response.text
    assert "No assignments are visible" in response.text


def test_save_draft_persists_and_reload_shows_values(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-save",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()

    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/save",
        data={
            f"response[{assignment.id}][rating]": "4",
            f"response[{assignment.id}][comments]": "good work",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "saved=ok" in response.headers["location"]

    page = rae_client.get(f"/reviewer/sessions/{review_session.id}")
    assert 'value="4"' in page.text
    assert "good work" in page.text


def test_submit_with_all_required_filled_succeeds_and_writes_audit(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-submit",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()

    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={f"response[{assignment.id}][rating]": "5"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "submitted=ok" in response.headers["location"]
    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).scalar_one()
    assert audit.detail["count"] >= 1
    assert audit.detail["acknowledged_missing"] is False


def test_submit_with_missing_required_warns_without_audit(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-warn",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Required fields missing" in response.text
    assert "acknowledge_missing" in response.text
    # Per-row amber icon shows on the warn re-render (so reviewer can find
    # which rows are incomplete without scrolling back to the top card).
    assert "⚠" in response.text
    submitted = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).first()
    assert submitted is None


def test_submit_with_acknowledge_missing_succeeds(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-ack",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={"acknowledge_missing": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).scalar_one()
    assert audit.detail["acknowledged_missing"] is True
    assert audit.detail["missing_required_count"] >= 1


def test_clear_all_with_confirm_deletes_responses(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-clear",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/save",
        data={f"response[{assignment.id}][rating]": "5"},
        follow_redirects=False,
    )

    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/clear",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.cleared")
    ).scalar_one()
    assert audit.detail["deleted_count"] >= 1


def test_clear_all_without_confirm_400s(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-noclear",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/clear",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_resubmit_after_edit_refreshes_submitted_at(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-resub",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={f"response[{assignment.id}][rating]": "3"},
        follow_redirects=False,
    )
    first_events = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).scalars().all()
    assert len(first_events) == 1

    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={f"response[{assignment.id}][rating]": "5"},
        follow_redirects=False,
    )
    later_events = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).scalars().all()
    assert len(later_events) == 2


def test_cancel_link_renders_last_saved_values(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-cancel",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/save",
        data={
            f"response[{assignment.id}][rating]": "4",
            f"response[{assignment.id}][comments]": "saved comment",
        },
        follow_redirects=False,
    )

    page = rae_client.get(f"/reviewer/sessions/{review_session.id}")
    assert "saved comment" in page.text
    assert 'value="4"' in page.text


def test_other_session_url_returns_403(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    op_alice = make_client(alice)
    rae_session = _operator_creates_session_with_pair(
        op_alice,
        db,
        code="rae-only",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    op_bob = make_client(bob)
    other_session = _operator_creates_session_with_pair(
        op_bob,
        db,
        code="bob-only",
        reviewer_email="someone@example.edu",
        reviewee_ident="dan@example.edu",
    )

    rae_client = make_client(rae)
    own = rae_client.get(f"/reviewer/sessions/{rae_session.id}")
    other = rae_client.get(f"/reviewer/sessions/{other_session.id}")
    assert own.status_code == 200
    assert other.status_code == 403


def test_inactive_reviewer_row_403s_on_surface(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-403",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    reviewer.status = "inactive"
    db.commit()

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")
    assert response.status_code == 403
