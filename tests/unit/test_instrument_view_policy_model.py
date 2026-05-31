"""Unit tests for the ``InstrumentViewPolicy`` model — pins the
per-instrument visibility-grant contract (UNIQUE on
instrument_id + audience; ``instrument.view_policies`` cascade)
before Phase 3 wiring (W7 resolver, W15 Band 3 editor) lights it
up.

See ``guide/participant_model_upgrade.md`` §3.3 and
``guide/participant_model_prep.md`` row S2.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentViewPolicy,
    ReviewSession,
    User,
)


def _instrument(db: Session, *, code: str = "ivp") -> Instrument:
    user = User(email=f"{code}@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="IVP",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    instrument = Instrument(
        session_id=review_session.id, name="Form", short_label="F"
    )
    db.add(instrument)
    db.flush()
    return instrument


def test_policy_persists_and_refetches(db: Session) -> None:
    instrument = _instrument(db)
    policy = InstrumentViewPolicy(
        instrument_id=instrument.id,
        audience="reviewee",
        enabled=True,
        granularity="per_line",
        identification="identified",
    )
    db.add(policy)
    db.commit()

    refetched = db.get(InstrumentViewPolicy, policy.id)
    assert refetched is not None
    assert refetched.audience == "reviewee"
    assert refetched.enabled is True
    assert refetched.granularity == "per_line"
    assert refetched.identification == "identified"
    assert refetched.observer_tag is None


def test_policy_enabled_defaults_to_false(db: Session) -> None:
    instrument = _instrument(db)
    policy = InstrumentViewPolicy(
        instrument_id=instrument.id,
        audience="reviewee",
        granularity="per_line",
        identification="deidentified",
    )
    db.add(policy)
    db.commit()
    assert policy.enabled is False


def test_policy_unique_per_instrument_audience(db: Session) -> None:
    instrument = _instrument(db)
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="reviewee",
            granularity="per_line",
            identification="identified",
        )
    )
    db.commit()

    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="reviewee",
            granularity="summarized",
            identification="deidentified",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_three_audiences_per_instrument_allowed(db: Session) -> None:
    instrument = _instrument(db)
    for audience in ("reviewee", "peer_reviewer", "observer"):
        db.add(
            InstrumentViewPolicy(
                instrument_id=instrument.id,
                audience=audience,
                granularity="per_line",
                identification="identified",
            )
        )
    db.commit()
    assert len(instrument.view_policies) == 3


def test_instrument_view_policies_cascade(db: Session) -> None:
    instrument = _instrument(db)
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="reviewee",
            granularity="per_line",
            identification="identified",
        )
    )
    db.commit()
    instrument_id = instrument.id

    db.delete(instrument)
    db.commit()

    remaining = (
        db.query(InstrumentViewPolicy)
        .filter(InstrumentViewPolicy.instrument_id == instrument_id)
        .count()
    )
    assert remaining == 0
