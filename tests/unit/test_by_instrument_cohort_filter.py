"""Unit tests for the observer-collation parameters added to
``app.services.extracts.by_instrument_extract.serialize_by_instrument``:

- ``row_filter`` — a per-assignment ``(Assignment) -> bool``
  callable. Rows for which it returns False are dropped before
  any further work. The observer-collation surface plugs in
  ``observer_cohort.assignment_matches_cohort`` here so the
  cohort rule's actual predicates run against each row.
- ``identification="anonymized"`` — swaps the reviewer /
  reviewee names for per-session tokens, blanks emails + tag
  columns so the only identifier is the opaque token.

Operator-side behaviour (default ``row_filter=None``,
``identification="raw"``) is exercised in the wider integration
suite — this file pins only the observer additions.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.extracts.by_instrument_extract import (
    serialize_by_instrument,
)


# ── Fixtures ─────────────────────────────────────────────────────────


def _make_session(db: Session, *, code: str) -> ReviewSession:
    user = User(email=f"{code}@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    sess = ReviewSession(
        name="Sess",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(sess)
    db.flush()
    return sess


def _make_instrument(db: Session, sess: ReviewSession) -> Instrument:
    inst = Instrument(session_id=sess.id, name="Instrument 1", order=0)
    db.add(inst)
    db.flush()
    return inst


def _make_field(
    db: Session, instrument: Instrument, *, field_key: str
) -> InstrumentResponseField:
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=field_key,
        label=field_key,
        _inline_data_type="Integer",
        required=False,
        order=0,
    )
    db.add(field)
    db.flush()
    return field


def _seed_two_pairs(db: Session) -> dict:
    sess = _make_session(db, code="ext-cohort")
    inst = _make_instrument(db, sess)
    field = _make_field(db, inst, field_key="rating")
    db.refresh(inst)

    r1 = Reviewer(
        session_id=sess.id,
        name="Alpha Reviewer",
        email="alpha@x",
        tag_1="rt1",
    )
    r2 = Reviewer(
        session_id=sess.id,
        name="Beta Reviewer",
        email="beta@x",
        tag_1="rt2",
    )
    e1 = Reviewee(
        session_id=sess.id,
        name="Alpha Reviewee",
        email_or_identifier="ea@x",
        tag_1="et1",
    )
    e2 = Reviewee(
        session_id=sess.id,
        name="Beta Reviewee",
        email_or_identifier="eb@x",
        tag_1="et2",
    )
    db.add_all([r1, r2, e1, e2])
    db.flush()

    a1 = Assignment(
        session_id=sess.id,
        instrument_id=inst.id,
        reviewer_id=r1.id,
        reviewee_id=e1.id,
    )
    a2 = Assignment(
        session_id=sess.id,
        instrument_id=inst.id,
        reviewer_id=r2.id,
        reviewee_id=e2.id,
    )
    db.add_all([a1, a2])
    db.flush()

    submitted = datetime.now(timezone.utc)
    db.add_all(
        [
            Response(
                assignment_id=a1.id,
                response_field_id=field.id,
                value="4",
                submitted_at=submitted,
            ),
            Response(
                assignment_id=a2.id,
                response_field_id=field.id,
                value="3",
                submitted_at=submitted,
            ),
        ]
    )
    db.commit()
    return {
        "sess": sess,
        "inst": inst,
        "r1": r1,
        "r2": r2,
        "e1": e1,
        "e2": e2,
    }


def _data_rows(
    rows: list[tuple[str, ...]],
) -> list[tuple[str, ...]]:
    """Strip the meta block + blank separator + header row,
    leaving only data rows."""
    body = list(rows)
    for i, row in enumerate(body):
        if row and row[0] == "ReviewerName":
            return body[i + 1 :]
    return []


# ── row_filter ───────────────────────────────────────────────────────


def test_row_filter_keeps_only_rows_where_predicate_passes(
    db: Session,
) -> None:
    seed = _seed_two_pairs(db)
    inst = seed["inst"]
    sess = seed["sess"]
    r1 = seed["r1"]
    rows = list(
        serialize_by_instrument(
            db,
            sess,
            inst,
            position=0,
            row_filter=lambda a: a.reviewer_id == r1.id,
        )
    )
    data = _data_rows(rows)
    assert len(data) == 1
    assert data[0][0] == "Alpha Reviewer"


def test_row_filter_can_test_both_sides(db: Session) -> None:
    """The predicate is over the full ``Assignment`` so callers
    can test reviewer + reviewee + assignment metadata
    together."""
    seed = _seed_two_pairs(db)
    inst = seed["inst"]
    sess = seed["sess"]
    r1 = seed["r1"]
    e2 = seed["e2"]
    rows = list(
        serialize_by_instrument(
            db,
            sess,
            inst,
            position=0,
            row_filter=lambda a: (
                a.reviewer_id == r1.id or a.reviewee_id == e2.id
            ),
        )
    )
    data = _data_rows(rows)
    # Both pairs included — r1 satisfies pair 1, e2 satisfies
    # pair 2.
    assert len(data) == 2


def test_row_filter_all_false_returns_empty_data_block(
    db: Session,
) -> None:
    seed = _seed_two_pairs(db)
    inst = seed["inst"]
    sess = seed["sess"]
    rows = list(
        serialize_by_instrument(
            db,
            sess,
            inst,
            position=0,
            row_filter=lambda a: False,
        )
    )
    assert _data_rows(rows) == []


def test_no_row_filter_preserves_operator_side_behaviour(
    db: Session,
) -> None:
    seed = _seed_two_pairs(db)
    inst = seed["inst"]
    sess = seed["sess"]
    rows = list(serialize_by_instrument(db, sess, inst, position=0))
    data = _data_rows(rows)
    # Default ``row_filter=None`` returns every assignment.
    assert len(data) == 2


# ── identification="anonymized" ───────────────────────────────────────


def test_anonymized_swaps_reviewer_and_reviewee_names_for_tokens(
    db: Session,
) -> None:
    seed = _seed_two_pairs(db)
    inst = seed["inst"]
    sess = seed["sess"]
    rows = list(
        serialize_by_instrument(
            db,
            sess,
            inst,
            position=0,
            identification="anonymized",
        )
    )
    data = _data_rows(rows)
    for row in data:
        reviewer_name = row[0]
        reviewee_name = row[5]
        assert reviewer_name.startswith("R-")
        assert reviewee_name.startswith("E-")


def test_anonymized_blanks_emails_and_tag_columns(db: Session) -> None:
    seed = _seed_two_pairs(db)
    inst = seed["inst"]
    sess = seed["sess"]
    rows = list(
        serialize_by_instrument(
            db,
            sess,
            inst,
            position=0,
            identification="anonymized",
        )
    )
    data = _data_rows(rows)
    for row in data:
        assert row[1] == ""  # ReviewerEmail
        assert row[2] == row[3] == row[4] == ""  # reviewer tags
        assert row[6] == ""  # RevieweeEmail
        assert row[7] == row[8] == row[9] == ""  # reviewee tags


def test_anonymized_preserves_response_values(db: Session) -> None:
    seed = _seed_two_pairs(db)
    inst = seed["inst"]
    sess = seed["sess"]
    rows = list(
        serialize_by_instrument(
            db,
            sess,
            inst,
            position=0,
            identification="anonymized",
        )
    )
    data = _data_rows(rows)
    response_values = {row[10] for row in data}
    assert response_values == {"4", "3"}


def test_anonymized_tokens_stable_across_invocations(
    db: Session,
) -> None:
    seed = _seed_two_pairs(db)
    inst = seed["inst"]
    sess = seed["sess"]
    first = _data_rows(
        list(
            serialize_by_instrument(
                db,
                sess,
                inst,
                position=0,
                identification="anonymized",
            )
        )
    )
    second = _data_rows(
        list(
            serialize_by_instrument(
                db,
                sess,
                inst,
                position=0,
                identification="anonymized",
            )
        )
    )
    assert [(r[0], r[5]) for r in first] == [(r[0], r[5]) for r in second]


def test_raw_identification_preserves_operator_side_columns(
    db: Session,
) -> None:
    seed = _seed_two_pairs(db)
    inst = seed["inst"]
    sess = seed["sess"]
    rows = list(serialize_by_instrument(db, sess, inst, position=0))
    data = _data_rows(rows)
    names = {(row[0], row[1]) for row in data}
    assert ("Alpha Reviewer", "alpha@x") in names
    assert ("Beta Reviewer", "beta@x") in names
