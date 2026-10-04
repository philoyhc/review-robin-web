"""Email dates follow the session zone, on real rows.

``spec/timezone_display.md``: reviewer emails render ``$deadline`` and
``$submitted_at`` in the session's resolved zone — the session's own
zone, else its creating operator's default, else UTC. They rendered in
UTC until 2026-10-01 (``guide/archive/findings_2026-10-01_corpus.md`` C18 =
D25). The unit tests pin the rule on stand-ins; this runs it on mapped
rows, through the relationship the resolver walks.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Reviewer, ReviewSession, User
from app.services import email_templates

_NINE_UTC = datetime(2026, 6, 30, 9, 0, tzinfo=timezone.utc)


def _session(db: Session, *, code: str, own_zone: str | None) -> ReviewSession:
    user = User(
        email=f"op-{code}@example.edu",
        preferences={"display_timezone": "America/New_York"},
    )
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Zones",
        code=code,
        created_by_user_id=user.id,
        deadline=_NINE_UTC,
        display_timezone=own_zone,
        email_template_overrides={"invitation_body": "Due $deadline"},
    )
    db.add(review_session)
    db.flush()
    return review_session


def test_the_sessions_own_zone_wins(db: Session) -> None:
    review_session = _session(db, code="mail-sg", own_zone="Asia/Singapore")
    reviewer = Reviewer(session_id=review_session.id, name="R", email="r@e.edu")
    db.add(reviewer)
    db.flush()

    _, body = email_templates.render_invitation(
        review_session, reviewer, invite_url="https://app/x"
    )
    assert body == "Due 2026-06-30 17:00"


def test_without_one_the_creators_zone_applies(db: Session) -> None:
    review_session = _session(db, code="mail-ny", own_zone=None)
    reviewer = Reviewer(session_id=review_session.id, name="R", email="r@e.edu")
    db.add(reviewer)
    db.flush()

    _, body = email_templates.render_invitation(
        review_session, reviewer, invite_url="https://app/x"
    )
    assert body == "Due 2026-06-30 05:00"


def test_submitted_at_reads_a_real_submission_in_the_session_zone(
    db: Session,
) -> None:
    """``$submitted_at`` is the reviewer's latest ``Response.submitted_at``,
    looked up through the mapped rows, then rendered in the session zone."""
    from app.db.models import Assignment, Response, Reviewee
    from app.services.instruments import ensure_default_instrument

    review_session = _session(db, code="mail-sub", own_zone="Asia/Singapore")
    review_session.email_template_overrides = {
        "responses_received_body": "Sent $submitted_at"
    }
    reviewer = Reviewer(session_id=review_session.id, name="R", email="r@e.edu")
    reviewee = Reviewee(
        session_id=review_session.id, name="E", email_or_identifier="e@e.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
    )
    db.add(assignment)
    db.flush()
    field = instrument.response_fields[0]
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value="4",
            submitted_at=_NINE_UTC,
        )
    )
    db.flush()

    _, body = email_templates.render_responses_received(review_session, reviewer)
    assert body == "Sent 2026-06-30 17:00"
