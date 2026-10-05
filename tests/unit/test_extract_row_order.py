"""Pinned row order for the Data shape and By instrument extracts
(findings D9 / Dc5; ``spec/csv_contracts.md`` "Deterministic row
order").

Every fixture inserts its rows in an order that differs from the
expected output, so an extract that leaned on the database's
unordered return — insertion order, on SQLite — would fail here
rather than only on Postgres.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    DataShape,
    Instrument,
    InstrumentResponseField,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.extracts.by_instrument_extract import serialize_by_instrument
from app.services.extracts.data_shape_extract import build_shape_rows


def _session(db: Session, code: str) -> ReviewSession:
    user = User(email=f"{code}@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Order",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session


def _shape(db: Session, review_session: ReviewSession, slots: list[str]) -> DataShape:
    shape = DataShape(
        session_id=review_session.id,
        name="Order",
        axis="reviewer",
        column_chip_slots=json.dumps(slots),
        self_review_handling="include_self",
        include_empty_rows=True,
    )
    db.add(shape)
    db.flush()
    return shape


def test_data_shape_per_individual_rows_run_active_then_name_then_email(
    db: Session,
) -> None:
    review_session = _session(db, "order-ind")
    db.add_all(
        [
            Reviewer(session_id=review_session.id, name="cy", email="c2@x.edu"),
            Reviewer(
                session_id=review_session.id,
                name="ann",
                email="a@x.edu",
                status="inactive",
            ),
            Reviewer(session_id=review_session.id, name="cy", email="c1@x.edu"),
            Reviewer(session_id=review_session.id, name="bea", email="b@x.edu"),
        ]
    )
    db.flush()
    shape = _shape(db, review_session, ["reviewer:name", "reviewer:email"])

    rows = build_shape_rows(db, review_session, shape)

    assert rows[1:] == [
        ("bea", "b@x.edu"),
        ("cy", "c1@x.edu"),
        ("cy", "c2@x.edu"),
        ("ann", "a@x.edu"),
    ]


def test_data_shape_per_tag_combo_rows_sort_by_tag_values(db: Session) -> None:
    review_session = _session(db, "order-tag")
    for name, tag in (("r1", "C"), ("r2", "A"), ("r3", None), ("r4", "B"), ("r5", "A")):
        db.add(
            Reviewer(
                session_id=review_session.id,
                name=name,
                email=f"{name}@x.edu",
                tag_1=tag,
            )
        )
    db.flush()
    shape = _shape(db, review_session, ["reviewer:tag-1"])

    rows = build_shape_rows(db, review_session, shape)

    assert rows[1:] == [("",), ("A",), ("B",), ("C",)]


def test_by_instrument_rows_break_name_ties_on_email(db: Session) -> None:
    """Two reviewees share a name and two reviewers share a name: the
    old (reviewee name, reviewer name) key left those rows in query
    order."""
    review_session = _session(db, "order-byi")
    instrument = Instrument(session_id=review_session.id, name="I", order=0)
    db.add(instrument)
    db.flush()
    db.add(
        InstrumentResponseField(
            instrument_id=instrument.id,
            field_key="rating",
            label="rating",
            _inline_data_type="Integer",
            required=False,
            order=0,
        )
    )
    rae_2 = Reviewer(session_id=review_session.id, name="Rae", email="rae2@x")
    rae_1 = Reviewer(session_id=review_session.id, name="Rae", email="rae1@x")
    eli_2 = Reviewee(session_id=review_session.id, name="Eli", email_or_identifier="eli2@x")
    eli_1 = Reviewee(session_id=review_session.id, name="Eli", email_or_identifier="eli1@x")
    db.add_all([rae_2, rae_1, eli_2, eli_1])
    db.flush()
    for reviewer, reviewee in (
        (rae_2, eli_2),
        (rae_1, eli_2),
        (rae_2, eli_1),
        (rae_1, eli_1),
    ):
        db.add(
            Assignment(
                session_id=review_session.id,
                instrument_id=instrument.id,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
            )
        )
    db.flush()
    db.refresh(instrument)

    rows = list(
        serialize_by_instrument(
            db, review_session, instrument, position=1, include_metadata=False
        )
    )

    assert [(row[6], row[1]) for row in rows[1:]] == [
        ("eli1@x", "rae1@x"),
        ("eli1@x", "rae2@x"),
        ("eli2@x", "rae1@x"),
        ("eli2@x", "rae2@x"),
    ]
