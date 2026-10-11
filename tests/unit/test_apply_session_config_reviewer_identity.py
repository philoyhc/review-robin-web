"""The Settings CSV carries a view policy's reviewer-identity level.

ProfileLink updates Item 2 rung 2 (``guide/profilelink_updates.md``):
``instruments[N].view_policies[<audience>].after_release_reviewer_identity``
on the reviewee and observer rows, empty for the default. Until rung 3
the import is the only writer, so it refuses what the card will refuse:
a value that is not a level, and any level on the reviewer row.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentViewPolicy, ReviewSession, User
from app.services import visibility_policies
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)

_FIELD = "after_release_reviewer_identity"


def _session(db: Session, *, code: str) -> ReviewSession:
    user = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _policies(db: Session, review_session: ReviewSession) -> dict[str, InstrumentViewPolicy]:
    rows = db.execute(
        select(InstrumentViewPolicy)
        .join(Instrument)
        .where(Instrument.session_id == review_session.id)
    ).scalars()
    return {row.audience: row for row in rows}


def test_the_level_round_trips_and_only_its_audiences_emit_it(db: Session) -> None:
    src = _session(db, code="rid-rt")
    instrument = Instrument(session_id=src.id, name="Survey", order=1)
    db.add(instrument)
    db.flush()
    granularity, identification = visibility_policies.MODE_LABELS["raw"]
    for audience, level in (
        ("peer_reviewer", None),
        ("reviewee", "name_email_profile"),
        ("observer", None),
    ):
        db.add(
            InstrumentViewPolicy(
                instrument_id=instrument.id,
                audience=audience,
                # The reviewer's own Session ongoing cell is always Raw.
                while_ongoing_granularity=(
                    granularity if audience == "peer_reviewer" else None
                ),
                while_ongoing_identification=(
                    identification if audience == "peer_reviewer" else None
                ),
                after_release_granularity=granularity,
                after_release_identification=identification,
                after_release_reviewer_identity=level,
            )
        )
    db.commit()

    rows = serialize_session_config(db, src)
    emitted = {r.field: r.value for r in rows if r.field.endswith(_FIELD)}
    assert emitted == {
        f"instruments[1].view_policies[observer].{_FIELD}": "",
        f"instruments[1].view_policies[reviewee].{_FIELD}": "name_email_profile",
    }

    target = _session(db, code="rid-rt2")
    result = apply_session_config(db, target, rows)
    assert result.errors == []
    applied = _policies(db, target)
    assert applied["reviewee"].after_release_reviewer_identity == "name_email_profile"
    assert applied["observer"].after_release_reviewer_identity is None
    assert applied["peer_reviewer"].after_release_reviewer_identity is None


def _apply(db: Session, code: str, audience: str, value: str):
    review_session = _session(db, code=code)
    prefix = f"instruments[1].view_policies[{audience}]"
    rows = [
        Row("instruments[1].name", "Survey", "string"),
        Row(f"{prefix}.{_FIELD}", value, "string"),
    ]
    if audience == "peer_reviewer":
        # The reviewer's own Session ongoing cell is always Raw.
        granularity, identification = visibility_policies.MODE_LABELS["raw"]
        rows += [
            Row(f"{prefix}.while_ongoing_granularity", granularity, "string"),
            Row(f"{prefix}.while_ongoing_identification", identification, "string"),
        ]
    result = apply_session_config(db, review_session, rows)
    return review_session, result


def test_a_value_that_is_not_a_level_is_refused(db: Session) -> None:
    review_session, result = _apply(db, "rid-bad", "reviewee", "everything")
    assert not result.ok
    assert any("reviewer identity must be one of" in e.message for e in result.errors)
    assert _policies(db, review_session) == {}


def test_a_level_on_the_reviewer_row_is_refused(db: Session) -> None:
    review_session, result = _apply(db, "rid-peer", "peer_reviewer", "name")
    assert not result.ok
    assert any("carries no reviewer identity level" in e.message for e in result.errors)
    assert _policies(db, review_session) == {}


def test_an_empty_value_on_the_reviewer_row_is_accepted(db: Session) -> None:
    _, result = _apply(db, "rid-peer-empty", "peer_reviewer", "")
    assert result.errors == []
