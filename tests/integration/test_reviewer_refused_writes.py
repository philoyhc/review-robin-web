"""A refused Save / Submit / Clear keeps what the reviewer typed
(participant audit P3, `guide/participant_surface_check.md`; author's
ruling 2026-10-15).

These used to answer the standalone error page, "No longer accepting
responses", which threw away every typed answer and used the same
words for a session that closed, one reverted to draft and a reviewer
with nothing assigned. Now the page renders again with a notice naming
the cause, and the typed answers listed as text to copy."""

from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, Response, Reviewer, ReviewSession

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)

RAE = AuthenticatedUser(
    principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
)
TYPED = "Line one\nLine two <b>bold</b>"


def _ready_session(
    operator: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """An Activated session: reviewers Rae and Sam, one reviewee."""
    operator.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\n"
                b"Rae,rae@example.edu\nSam,sam@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator.post(
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
    generate_via_page_button(operator, review_session.id)
    operator.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "ready"
    return review_session


def _assignment_of(db: Session, review_session: ReviewSession, email: str) -> Assignment:
    return db.execute(
        select(Assignment)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .where(
            Assignment.session_id == review_session.id,
            Reviewer.email == email,
        )
    ).scalar_one()


def _rae_posts(
    make_client, path: str, data: dict[str, str]
):
    resp = make_client(RAE).post(path, data=data, follow_redirects=False)
    return resp, html.unescape(resp.text)


def test_a_save_past_the_deadline_shows_the_surface_and_what_was_typed(
    client: TestClient, db: Session, make_client
) -> None:
    review_session = _ready_session(client, db, code="refused-deadline")
    review_session.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    aid = _assignment_of(db, review_session, "rae@example.edu").id

    resp, text = _rae_posts(
        make_client,
        f"/me/sessions/{review_session.id}/1/save",
        {f"response[{aid}][comments]": TYPED},
    )

    assert resp.status_code == 403
    assert "data-rs-write-refused" in resp.text
    assert "This review closed at its deadline" in text
    assert "so your last changes weren't saved." in text
    # The review page, read-only, not the standalone error page.
    assert "This session is no longer accepting responses." in text
    assert "data-rs-unsaved-answers" in resp.text
    assert "Line one\nLine two" in text
    # Escaped, never markup.
    assert "&lt;b&gt;bold&lt;/b&gt;" in resp.text
    assert db.execute(select(Response)).scalars().first() is None


def test_a_submit_after_the_operator_closed_says_so(
    client: TestClient, db: Session, make_client
) -> None:
    review_session = _ready_session(client, db, code="refused-closed")
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/close",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "expired"
    aid = _assignment_of(db, review_session, "rae@example.edu").id

    resp, text = _rae_posts(
        make_client,
        f"/me/sessions/{review_session.id}/submit?page=1",
        {f"response[{aid}][comments]": TYPED},
    )

    assert resp.status_code == 403
    assert "This review has closed, so your answers weren't submitted." in text
    assert "Line one\nLine two" in text


def test_a_save_on_a_session_reverted_to_draft_is_not_currently_open(
    client: TestClient, db: Session, make_client
) -> None:
    review_session = _ready_session(client, db, code="refused-draft")
    review_session.status = "draft"
    db.commit()
    aid = _assignment_of(db, review_session, "rae@example.edu").id

    resp, text = _rae_posts(
        make_client,
        f"/me/sessions/{review_session.id}/1/save",
        {f"response[{aid}][comments]": TYPED},
    )

    assert resp.status_code == 403
    # The pre-open page, as a GET would show it now.
    assert "opens later" in text
    assert "This review is not currently open, so your last changes weren't saved." in text
    # The old error-page detail, which said "no longer" here.
    assert "No longer accepting responses" not in text
    assert "Line one\nLine two" in text


def test_a_reviewer_with_nothing_assigned_is_not_told_no_longer(
    client: TestClient, db: Session, make_client
) -> None:
    review_session = _ready_session(client, db, code="refused-none")
    assignment = _assignment_of(db, review_session, "rae@example.edu")
    assignment.include = False
    db.commit()

    resp, text = _rae_posts(
        make_client,
        f"/me/sessions/{review_session.id}/1/save",
        {f"response[{assignment.id}][comments]": TYPED},
    )

    assert resp.status_code == 403
    assert (
        "You have nothing to review in this session right now, so your "
        "last changes weren't saved." in text
    )
    assert "No longer accepting responses" not in text
    # Typed before the operator excluded the row, so it still comes back.
    assert "Line one\nLine two" in text


def test_a_refused_clear_lists_nothing(
    client: TestClient, db: Session, make_client
) -> None:
    review_session = _ready_session(client, db, code="refused-clear")
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/close",
        follow_redirects=False,
    )

    resp, text = _rae_posts(
        make_client,
        f"/me/sessions/{review_session.id}/clear",
        {"confirm": "true"},
    )

    assert resp.status_code == 403
    assert "This review has closed, so your answers weren't cleared." in text
    assert "data-rs-unsaved-answers" not in resp.text


def test_only_the_reviewers_own_assignments_are_listed(
    client: TestClient, db: Session, make_client
) -> None:
    """A value posted against someone else's assignment, or one that
    doesn't exist, is not echoed back with that row's labels."""
    review_session = _ready_session(client, db, code="refused-own")
    review_session.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    sams = _assignment_of(db, review_session, "sam@example.edu").id

    resp, text = _rae_posts(
        make_client,
        f"/me/sessions/{review_session.id}/1/save",
        {
            f"response[{sams}][comments]": "for sam",
            "response[999999][comments]": "for nobody",
        },
    )

    assert resp.status_code == 403
    assert "data-rs-write-refused" in resp.text
    assert "data-rs-unsaved-answers" not in resp.text
    assert "for sam" not in text
    assert "for nobody" not in text


def test_an_accepted_save_shows_no_notice(
    client: TestClient, db: Session, make_client
) -> None:
    review_session = _ready_session(client, db, code="refused-not")
    aid = _assignment_of(db, review_session, "rae@example.edu").id
    rae_client = make_client(RAE)
    resp = rae_client.post(
        f"/me/sessions/{review_session.id}/1/save",
        data={f"response[{aid}][comments]": "kept"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    page = rae_client.get(f"/me/sessions/{review_session.id}/1")
    assert "data-rs-write-refused" not in page.text
