"""18P PR H — orchestrator-level guarantees for ``rehydrate_session``.

Covers the all-or-nothing rollback: a failure partway through the
reconstruction pipeline hard-deletes the partially-built session so no
half-rehydrated rows survive (``docs/rehydrate.md`` §7).
"""

from __future__ import annotations

import csv
import datetime as dt
import io

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)
from app.services import session_rehydrate
from app.services.extracts import responses_import
from app.services.session_config_io import serialize_session_config
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers
from app.services.extracts.responses_extract import serialize_responses

_INLINE = dict(
    _inline_data_type="Integer",
    _inline_response_type="Likert5",
    _inline_min=1.0,
    _inline_max=5.0,
    _inline_step=1.0,
)


def _to_csv(rows) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _seed(db: Session) -> tuple[ReviewSession, User]:
    user = User(email="op@e.edu", display_name="Op")
    db.add(user)
    db.flush()
    rs = ReviewSession(name="Spring", code="spring", created_by_user_id=user.id)
    db.add(rs)
    db.flush()
    db.add(SessionOperator(session_id=rs.id, user_id=user.id, role="owner"))
    inst = Instrument(session_id=rs.id, name="Inst", short_label="INST", order=1)
    db.add(inst)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=inst.id,
        field_key="q1",
        label="Q1",
        order=1,
        visible=True,
        **_INLINE,
    )
    db.add(field)
    db.flush()
    rvr = Reviewer(session_id=rs.id, name="Ana", email="ana@e.edu")
    rve = Reviewee(session_id=rs.id, name="Bo", email_or_identifier="bo@e.edu")
    db.add_all([rvr, rve])
    db.flush()
    a = Assignment(
        session_id=rs.id,
        reviewer_id=rvr.id,
        reviewee_id=rve.id,
        instrument_id=inst.id,
        include=True,
        is_self_review=False,
    )
    db.add(a)
    db.flush()
    db.add(
        Response(
            assignment_id=a.id,
            response_field_id=field.id,
            value="4",
            saved_at=dt.datetime(2026, 6, 1, 9, 0, tzinfo=dt.timezone.utc),
            version=1,
        )
    )
    db.flush()
    return rs, user


def _file_set(db: Session, rs: ReviewSession) -> dict[str, bytes]:
    settings_rows = [("field", "value", "data_type")] + [
        (r.field, r.value, r.data_type) for r in serialize_session_config(db, rs)
    ]
    return {
        f"{rs.code}_settings.csv": _to_csv(settings_rows),
        f"{rs.code}_reviewers.csv": _to_csv(serialize_reviewers(db, rs)),
        f"{rs.code}_reviewees.csv": _to_csv(serialize_reviewees(db, rs)),
        f"{rs.code}_responses.csv": _to_csv(serialize_responses(db, rs)),
    }


def test_rollback_leaves_no_partial_session(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    rs, user = _seed(db)
    files = _file_set(db, rs)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure in the last pipeline step")

    # Fail on the final step — after the shell, settings, rosters, and
    # assignments have all been written and committed by their services.
    monkeypatch.setattr(responses_import, "load_responses", _boom)

    with pytest.raises(RuntimeError):
        session_rehydrate.rehydrate_session(db, files=files, user=user)

    # The partially-built session was hard-deleted — zero rows survive.
    assert (
        db.execute(
            select(ReviewSession).where(
                ReviewSession.name == "Spring_REHYD"
            )
        ).scalar_one_or_none()
        is None
    )
    assert (
        db.execute(
            select(ReviewSession).where(ReviewSession.code == "spring-rehyd")
        ).scalar_one_or_none()
        is None
    )
    # No orphaned rosters from the deleted session (only the source's).
    reviewer_sessions = set(
        db.execute(select(Reviewer.session_id)).scalars()
    )
    assert reviewer_sessions == {rs.id}


def test_orchestrator_lands_draft_with_note(db: Session) -> None:
    rs, user = _seed(db)
    files = _file_set(db, rs)

    rehyd = session_rehydrate.rehydrate_session(
        db, files=files, user=user, today=dt.date(2026, 8, 15)
    )
    assert rehyd.status == "draft"
    assert rehyd.name == "Spring_REHYD"
    assert "Rehydrated 2026-08-15" in (rehyd.description or "")
