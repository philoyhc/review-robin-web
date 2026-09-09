"""Shared lifecycle-state fixtures for the Instruments surface.

A ``_``-prefixed helper module rather than an import between two test
modules, matching ``_full_matrix.py``: relative imports are what work
under a bare ``pytest`` run (`tests/integration/__init__.py` makes the
package, and nothing puts the repo root on ``sys.path``).

Segment 19I Item 6.
"""
from __future__ import annotations

import datetime as _dt

from fastapi.testclient import TestClient
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
)

EDITABLE = ("draft", "validated")
LOCKED = ("ready", "expired", "archived")
ALL_STATES = EDITABLE + LOCKED


def seed_session_with_instruments(
    client: TestClient, db: Session, *, code: str
) -> tuple[ReviewSession, int]:
    """Two instruments (so ``is_only_instrument`` never confounds the
    Delete button), one assignment, one submitted response.

    Returns the session and the first instrument's id — the one the
    assignment and response hang off, so a delete of it is the
    destructive case.
    """
    r = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    s = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()

    reviewer = Reviewer(session_id=s.id, name="R", email="r@example.edu")
    reviewee = Reviewee(
        session_id=s.id, name="E", email_or_identifier="e@example.edu"
    )
    first = Instrument(session_id=s.id, name="I1", order=0)
    second = Instrument(session_id=s.id, name="I2", order=1)
    db.add_all([reviewer, reviewee, first, second])
    db.flush()

    field = InstrumentResponseField(
        instrument_id=first.id,
        field_key="f0",
        label="F0",
        _inline_data_type="Integer",
        _inline_response_type="Likert5",
        order=0,
    )
    db.add(field)
    assignment = Assignment(
        session_id=s.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=first.id,
        include=True,
        created_by_mode="manual",
    )
    db.add(assignment)
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value="3",
            saved_at=_dt.datetime(2026, 9, 9, tzinfo=_dt.timezone.utc),
            version=1,
        )
    )
    db.commit()
    return s, first.id
