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
        f"/operator/sessions/{review_session.public_id}/reviewers/import",
        files={"file": ("r.csv", b"ReviewerName,ReviewerEmail\nR,rae@example.edu\n", "text/csv")},
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.public_id}/reviewees/import",
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
        f"/operator/sessions/{review_session.public_id}/workflow/prepare",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.headers["location"].endswith("?prepare_confirm=responses")
    db.refresh(review_session)
    assert lifecycle.is_draft(review_session)
    assert _answers(db, group_id) == {"Carol": "4", "Fay": "4"}

    body = " ".join(
        operator.get(
            f"/operator/sessions/{review_session.public_id}/assignments?prepare_confirm=responses"
        ).text.split()
    )
    assert "Preparing will delete 1 saved response." in body
    assert "1 is on groups it adds members to, which it clears" in body
    assert "drops 0 assignment pair" not in body


def test_acknowledged_prepare_clears_what_the_dry_run_counted(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session, group_id = _session_with_two_answered_teams(db, operator, "clr-ack")

    operator.post(
        f"/operator/sessions/{review_session.public_id}/workflow/prepare",
        data={"return_to": "assignments", "acknowledge_response_loss": "true"},
        follow_redirects=False,
    )

    assert _answers(db, group_id) == {"Carol": None, "Eve": None, "Fay": "4"}


def test_a_team_that_only_loses_a_member_projects_no_clear(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A dropped member only shrinks its group, which keeps its answer.
    The reviewer is also a member of Team A; excluding self-reviews
    drops that pair, so Team A shrinks to Carol, while a newcomer in a
    team of her own makes the dry-run project at all."""
    operator = make_client(alice)
    review_session, group_id = _session_with_two_answered_teams(db, operator, "clr-shrink")
    eve = db.scalar(select(Reviewee).where(Reviewee.email_or_identifier == "eve@example.edu"))
    eve.tag_1 = "Team D"
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Rae",
            email_or_identifier="rae@example.edu",
            tag_1="Team A",
        )
    )
    db.commit()
    operator.post(
        f"/operator/sessions/{review_session.public_id}/workflow/prepare",
        data={"return_to": "assignments", "acknowledge_response_loss": "true"},
        follow_redirects=False,
    )
    # Rae joined Team A, which was cleared; answer it again.
    field_id = db.scalar(
        select(Response.response_field_id)
        .join(Assignment, Assignment.id == Response.assignment_id)
        .where(Assignment.instrument_id == group_id)
    )
    for row in db.scalars(select(Assignment).where(Assignment.instrument_id == group_id)):
        if row.reviewee.tag_1 == "Team A":
            db.add(
                Response(
                    assignment_id=row.id,
                    response_field_id=field_id,
                    value="3",
                    saved_at=dt.datetime.now(dt.timezone.utc),
                )
            )
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Ivy",
            email_or_identifier="ivy@example.edu",
            tag_1="Team E",
        )
    )
    db.commit()

    impact = assignments_service.reconcile_impact(
        db, review_session, instrument_id=group_id, override_exclude_self_reviews=True
    )

    assert (impact.deleted, impact.new) == (1, 1)
    assert impact.responses_deleted == 1
    assert impact.group_responses_cleared == 0


def test_a_rule_set_the_dry_run_cannot_load_fails_prepare_at_generate(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Findings E3 (2026-10-22): the saved-response dry-run ran before the
    step's ``try``, so a stored rule set it could not load answered 500.
    Prepare now reports it as the Generate step's failure, and nothing
    is cleared."""
    from app.db.models import Instrument, SessionRuleSet

    operator = make_client(alice)
    review_session, group_id = _session_with_two_answered_teams(db, operator, "clr-bad-rules")
    rule_set = db.get(SessionRuleSet, db.get(Instrument, group_id).rule_set_id)
    rule_set.rules_json = [{"kind": "no-such-rule"}]
    db.commit()

    response = operator.post(
        f"/operator/sessions/{review_session.public_id}/workflow/prepare",
        data={"return_to": "home"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert "super_status=failed" in location and "super_step=generate" in location
    assert operator.get(location).status_code == 200
    assert _answers(db, group_id) == {"Carol": "4", "Fay": "4"}


def test_the_pages_that_read_staleness_report_a_rule_set_they_cannot_load(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Findings E4 (2026-10-22): the Assignments and Validate pages read
    each instrument's staleness, which ran the engine on the stored rule
    set and answered 500 when it could not load. They now say which
    instrument's rule can't be loaded, and Validate counts it an error."""
    from app.db.models import Instrument, SessionRuleSet
    from app.services import validation

    operator = make_client(alice)
    review_session, group_id = _session_with_two_answered_teams(db, operator, "e4-bad-rules")
    instrument = db.get(Instrument, group_id)
    db.get(SessionRuleSet, instrument.rule_set_id).rules_json = [{"kind": "no-such-rule"}]
    db.commit()

    page = operator.get(f"/operator/sessions/{review_session.public_id}/assignments")
    assert page.status_code == 200
    assert "data-rule-load-errors" in page.text
    assert "assignment rule can't be loaded" in page.text

    assert operator.get(f"/operator/sessions/{review_session.public_id}/validate").status_code == 200
    issues = [
        issue
        for issue in validation.validate_session_setup(db, review_session)
        if issue.rule_key == "instruments.rule_set_unloadable"
    ]
    # The helper pins one shared rule set on both instruments.
    pinned = db.scalars(
        select(Instrument.id).where(Instrument.rule_set_id == instrument.rule_set_id)
    ).all()
    assert sorted(issue.fix_anchor for issue in issues) == sorted(f"#instrument-{i}" for i in pinned)
    assert {issue.severity.value for issue in issues} == {"error"}
    state = assignments_service.staleness_by_instrument(db, review_session)[group_id]
    assert state.load_error and not state.stale
