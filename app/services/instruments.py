from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentResponseField, ReviewSession

DEFAULT_INSTRUMENT_NAME = "Default"

DEFAULT_RESPONSE_FIELDS: list[dict[str, Any]] = [
    {
        "field_key": "rating",
        "label": "Rating",
        "response_type": "integer",
        "required": True,
        "order": 1,
        "validation": {"min": 1, "max": 5},
    },
    {
        "field_key": "comments",
        "label": "Comments",
        "response_type": "long_text",
        "required": False,
        "order": 2,
        "validation": None,
    },
]


def ensure_default_instrument(
    db: Session, review_session: ReviewSession
) -> Instrument:
    """Return the session's Default Instrument, creating it if missing,
    and ensuring it carries the default response fields.

    Model invariant (per ARCHITECTURE.md "Conceptual hierarchy"): every
    ReviewSession has at least one Instrument. New sessions get the
    Default Instrument at creation. This helper backfills it for
    sessions created before the invariant was tightened.
    """
    instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.id)
    ).scalars().first()

    if instrument is None:
        instrument = Instrument(
            session_id=review_session.id,
            name=DEFAULT_INSTRUMENT_NAME,
            order=0,
            accepting_responses=False,
            responses_visible_when_closed=False,
        )
        db.add(instrument)
        db.flush()

    has_fields = (
        db.execute(
            select(InstrumentResponseField.id)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .limit(1)
        ).first()
        is not None
    )

    if not has_fields:
        for spec in DEFAULT_RESPONSE_FIELDS:
            db.add(
                InstrumentResponseField(
                    instrument_id=instrument.id,
                    field_key=spec["field_key"],
                    label=spec["label"],
                    response_type=spec["response_type"],
                    required=spec["required"],
                    order=spec["order"],
                    validation=spec["validation"],
                )
            )
        db.flush()

    return instrument
