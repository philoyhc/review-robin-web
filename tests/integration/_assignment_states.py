"""Shared lifecycle-state fixtures for the Assignments page.

A ``_``-prefixed helper imported relatively, per the convention
`_full_matrix.py` sets and `_instrument_states.py` follows: a bare
`pytest` run puts nothing on `sys.path`, so an absolute
`from tests.…` import fails collection (Segment 19I Item 6 PR 2).

Segment 19I Item 8.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
)

EDITABLE = ("draft", "validated")
LOCKED = ("ready", "expired", "archived")
ALL_STATES = EDITABLE + LOCKED


def seed_session_with_assignment(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """One reviewer / reviewee / instrument and the pair between them,
    with tags on both people so the same fixture serves Item 7."""
    r = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    s = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()

    reviewer = Reviewer(
        session_id=s.id,
        name="Ana Lim",
        email="ana@example.edu",
        tag_1="Team A",
        tag_2="Cohort 1",
    )
    reviewee = Reviewee(
        session_id=s.id,
        name="Ben Ord",
        email_or_identifier="ben@example.edu",
        tag_1="Team B",
    )
    instrument = Instrument(session_id=s.id, name="I1", order=0)
    db.add_all([reviewer, reviewee, instrument])
    db.flush()
    db.add(
        Assignment(
            session_id=s.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
            include=True,
            created_by_mode="manual",
        )
    )
    # A self-review row as well: the per-instrument self-review toggle
    # renders only when `self_review_total > 0`, so a roster of
    # distinct people leaves that control off the page entirely and a
    # test asserting on it proves nothing.
    self_reviewee = Reviewee(
        session_id=s.id,
        name="Ana Lim",
        email_or_identifier="ana@example.edu",
        tag_1="Team A",
    )
    db.add(self_reviewee)
    db.flush()
    db.add(
        Assignment(
            session_id=s.id,
            reviewer_id=reviewer.id,
            reviewee_id=self_reviewee.id,
            instrument_id=instrument.id,
            include=True,
            created_by_mode="manual",
            is_self_review=True,
        )
    )
    db.commit()
    return s
