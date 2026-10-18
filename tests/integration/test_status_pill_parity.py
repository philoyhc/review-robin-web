"""Findings R7 (author's ruling 2026-10-17): the reviewer surface's
status pills and the dashboard's reviewer pill follow one answers-based
rule, so they agree on the two cases they used to split on — blank rows
of an all-optional instrument, and an answer saved after Submit.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    InstrumentResponseField,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import monitoring
from app.services import responses as responses_service
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)
from ._validated import validate_session


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def _all_optional_session(
    operator: TestClient, db: Session, *, code: str
) -> tuple[ReviewSession, Reviewer, dict[str, Assignment]]:
    """One reviewer, two reviewees, one instrument with nothing required."""
    operator.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.public_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,rae@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.public_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\n"
                b"Carol,carol@example.edu\nDan,dan@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    for field in db.execute(select(InstrumentResponseField)).scalars():
        field.required = False
    db.commit()
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    validate_session(review_session)
    operator.get(f"/operator/sessions/{review_session.public_id}/assignments")
    operator.post(
        f"/operator/sessions/{review_session.public_id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "ready"
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    by_name = {
        a.reviewee.name: a
        for a in db.execute(
            select(Assignment)
            .join(Reviewee, Reviewee.id == Assignment.reviewee_id)
            .where(Assignment.session_id == review_session.id)
        ).scalars()
    }
    return review_session, reviewer, by_name


def _dashboard(db: Session, reviewer: Reviewer, review_session: ReviewSession) -> str:
    db.expire_all()
    pill = responses_service.session_pill_for_reviewer(
        db, reviewer=reviewer, session_id=review_session.id
    ).state
    [progress] = monitoring.per_reviewer_progress(db, review_session)
    assert progress.pill_state == pill
    return pill


def test_blank_all_optional_rows_read_not_started_on_both(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, reviewer, _ = _all_optional_session(
        make_client(alice), db, code="r7-blank"
    )
    body = make_client(rae).get(f"/me/sessions/{review_session.public_id}/1").text

    # Every row is "complete" by its required fields, since none are;
    # with no answer the page is not started, as on the dashboard.
    assert "#1: not started" in body
    assert "#1: complete" not in body
    assert "Draft" in body
    assert _dashboard(db, reviewer, review_session) == "not started"


def test_submit_with_a_blank_optional_row_reads_submitted_on_both(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, reviewer, by_name = _all_optional_session(
        make_client(alice), db, code="r7-partial"
    )
    rae_client = make_client(rae)
    rae_client.post(
        f"/me/sessions/{review_session.public_id}/submit",
        data={f"response[{by_name['Carol'].id}][comments]": "good"},
        follow_redirects=False,
    )
    body = rae_client.get(f"/me/sessions/{review_session.public_id}/1").text

    # Dan's row is blank and nothing on it is required, so it does not
    # hold the page off submitted.
    assert "#1: submitted" in body
    assert "Saved but not submitted" not in body
    assert _dashboard(db, reviewer, review_session) == "submitted"


def _assert_unsubmitted_on_both(
    db: Session, reviewer: Reviewer, review_session: ReviewSession, body: str
) -> None:
    """An unsubmitted answer after Submit: the dashboard reads it as
    ``in progress``, and the surface as ``complete``, its split of
    ``in progress`` where nothing required is missing. Never
    ``submitted``, and the session pill asks for a Submit."""
    assert "#1: complete" in body
    assert "#1: submitted" not in body
    assert "Saved but not submitted" in body
    assert _dashboard(db, reviewer, review_session) == "in progress"


def test_new_answer_after_submit_is_unsubmitted_on_both(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, reviewer, by_name = _all_optional_session(
        make_client(alice), db, code="r7-new"
    )
    rae_client = make_client(rae)
    rae_client.post(
        f"/me/sessions/{review_session.public_id}/submit",
        data={f"response[{by_name['Carol'].id}][comments]": "good"},
        follow_redirects=False,
    )
    rae_client.post(
        f"/me/sessions/{review_session.public_id}/1/save",
        data={
            f"response[{by_name['Carol'].id}][comments]": "good",
            f"response[{by_name['Dan'].id}][comments]": "late thought",
        },
        follow_redirects=False,
    )
    body = rae_client.get(f"/me/sessions/{review_session.public_id}/1").text

    _assert_unsubmitted_on_both(db, reviewer, review_session, body)


def test_changed_answer_after_submit_is_unsubmitted_on_both(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Findings R1: the change clears its stamp, so both read it as
    work the reviewer has yet to submit."""
    review_session, reviewer, by_name = _all_optional_session(
        make_client(alice), db, code="r7-changed"
    )
    rae_client = make_client(rae)
    rae_client.post(
        f"/me/sessions/{review_session.public_id}/submit",
        data={f"response[{by_name['Carol'].id}][comments]": "good"},
        follow_redirects=False,
    )
    rae_client.post(
        f"/me/sessions/{review_session.public_id}/1/save",
        data={f"response[{by_name['Carol'].id}][comments]": "better"},
        follow_redirects=False,
    )
    body = rae_client.get(f"/me/sessions/{review_session.public_id}/1").text

    _assert_unsubmitted_on_both(db, reviewer, review_session, body)
