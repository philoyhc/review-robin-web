"""Prepare's saved-response detour counts the group answers it clears.

A group instrument's subject is the group (author's ruling 2026-10-17),
so a Prepare that adds a member to an answered team clears that team's
answers, though it deletes no pair. Its dry-run counted only responses
on deleted pairs, so that loss ran with no confirmation.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, Response, Reviewee, ReviewSession
from app.services import assignments as assignments_service
from app.services import session_lifecycle as lifecycle

from ._full_matrix import generate_via_page_button, pin_full_matrix_on_all_instruments
from ._instrument_states import add_group_instrument


def _session_with_two_answered_teams(
    db: Session, operator: TestClient, code: str
) -> tuple[ReviewSession, int]:
    operator.post(
        "/operator/sessions", data={"name": "Teams", "code": code}, follow_redirects=False
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    group = add_group_instrument(db, review_session)
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("r.csv", b"ReviewerName,ReviewerEmail\nR,rae@example.edu\n", "text/csv")},
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail,RevieweeTag1\n"
                b"Carol,carol@example.edu,Team A\n"
                b"Fay,fay@example.edu,Team C\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    group.group_kind = "r1"
    db.commit()
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    rating = next(f for f in group.response_fields if f.field_key == "rating")
    for row in db.scalars(select(Assignment).where(Assignment.instrument_id == group.id)):
        db.add(
            Response(
                assignment_id=row.id,
                response_field_id=rating.id,
                value="4",
                saved_at=dt.datetime.now(dt.timezone.utc),
            )
        )
    # Eve joins the answered Team A; Team C is untouched.
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Eve",
            email_or_identifier="eve@example.edu",
            tag_1="Team A",
        )
    )
    db.commit()
    return review_session, group.id


def _answers(db: Session, instrument_id: int) -> dict[str, str | None]:
    db.expire_all()
    out: dict[str, str | None] = {}
    for row in db.scalars(select(Assignment).where(Assignment.instrument_id == instrument_id)):
        value = db.scalar(select(Response.value).where(Response.assignment_id == row.id))
        out[row.reviewee.name] = value
    return out


def test_a_newcomer_to_an_answered_team_detours_prepare(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session, group_id = _session_with_two_answered_teams(db, operator, "clr-detour")

    impact = assignments_service.reconcile_impact(db, review_session)
    assert (impact.responses_deleted, impact.group_responses_cleared) == (0, 1)

    response = operator.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.headers["location"].endswith("?prepare_confirm=responses")
    db.refresh(review_session)
    assert lifecycle.is_draft(review_session)
    assert _answers(db, group_id) == {"Carol": "4", "Fay": "4"}

    body = " ".join(
        operator.get(
            f"/operator/sessions/{review_session.id}/assignments?prepare_confirm=responses"
        ).text.split()
    )
    assert "Preparing will delete 1 saved response." in body
    assert "1 is on groups whose members it changes, which it clears" in body
    assert "drops 0 assignment pair" not in body


def test_acknowledged_prepare_clears_what_the_dry_run_counted(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session, group_id = _session_with_two_answered_teams(db, operator, "clr-ack")

    operator.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        data={"return_to": "assignments", "acknowledge_response_loss": "true"},
        follow_redirects=False,
    )

    assert _answers(db, group_id) == {"Carol": None, "Eve": None, "Fay": "4"}
