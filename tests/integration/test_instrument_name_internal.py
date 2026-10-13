"""An instrument's ``name`` is internal (author, 2026-10-13).

No page sets or shows it: operator-facing copy names an instrument by
its short label, else the ``Instrument_{N}`` fallback
(``instruments._instrument_label``). These tests pin the audit
summaries that used to carry the name — the Sys Admin audit log and its
CSV show them — and leave the detail snapshots, which keep it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession, User
from app.services import instruments as instruments_service
from app.services import session_lifecycle as lifecycle
from app.services.assignments import replace_assignments

from .test_scheduled_activation import _make_validated_session

INTERNAL = "internal-handle"


def _summaries(db: Session, session: ReviewSession, event_type: str) -> list[str]:
    return list(
        db.execute(
            select(AuditEvent.summary)
            .where(AuditEvent.session_id == session.id)
            .where(AuditEvent.event_type == event_type)
            .order_by(AuditEvent.id)
        ).scalars()
    )


def _labelled_session(db: Session, code: str) -> tuple[ReviewSession, Instrument]:
    session = _make_validated_session(db, code)
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalar_one()
    instrument.name = INTERNAL
    instrument.short_label = "Peer"
    db.commit()
    return session, instrument


def _operator(db: Session, session: ReviewSession) -> User:
    return db.get(User, session.created_by_user_id)


def test_deadline_close_and_live_reopen_summaries_name_the_label(
    db: Session,
) -> None:
    session, instrument = _labelled_session(db, "name-int-deadline")
    session.status = "ready"
    session.deadline = datetime.now(timezone.utc) + timedelta(days=1)
    instrument.accepting_responses = False
    db.commit()

    lifecycle.observe_deadline(db, session)  # live: reopens
    session.deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    lifecycle.observe_deadline(db, session)  # past: closes

    for event_type in ("instrument.opened", "instrument.closed"):
        (summary,) = _summaries(db, session, event_type)
        assert "Peer" in summary
        assert INTERNAL not in summary


def test_replicate_delete_and_generate_summaries_name_the_label(
    db: Session,
) -> None:
    session, instrument = _labelled_session(db, "name-int-crud")
    actor = _operator(db, session)

    replace_assignments(
        db, review_session=session, user=actor, correlation_id="c-gen"
    )
    db.commit()
    replica = instruments_service.replicate_instrument(
        db, review_session=session, source=instrument, actor=actor
    )
    db.commit()
    replica_label = instruments_service._instrument_label(replica)
    instruments_service.delete_instrument(db, instrument=replica, actor=actor)
    db.commit()

    (generated,) = _summaries(db, session, "assignments.generated")
    (replicated,) = _summaries(db, session, "instrument.replicated")
    (deleted,) = _summaries(db, session, "instrument.deleted")
    assert "'Peer'" in generated
    assert replicated == "Replicated instrument Peer"
    assert deleted == f"Deleted instrument {replica_label}"
    for summary in (generated, replicated, deleted):
        assert INTERNAL not in summary
