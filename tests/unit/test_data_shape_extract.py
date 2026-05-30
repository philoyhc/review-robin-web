"""Unit tests for
``app.services.extracts.data_shape_extract.build_shape_rows``
— covers the three row schemes (per-individual,
per-tag-combo, single summary) + the fan-out chips (List
items + Discrete steps).
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    DataShape,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.extracts.data_shape_extract import build_shape_rows


_INLINE_NUMERIC = {
    "_inline_data_type": "Integer",
    "_inline_response_type": "100int",
    "_inline_min": 1.0,
    "_inline_max": 5.0,
    "_inline_step": 1.0,
}
_INLINE_LIST = {
    "_inline_data_type": "List",
    "_inline_response_type": "choice",
    "_inline_list_csv": "Yes,No,Maybe",
}


def _session(db: Session, *, code: str = "ds") -> ReviewSession:
    user = User(email=f"{code}@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="DS",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session


def _reviewer(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str,
    email: str,
    tag_1: str | None = None,
) -> Reviewer:
    r = Reviewer(
        session_id=review_session.id,
        name=name,
        email=email,
        tag_1=tag_1,
    )
    db.add(r)
    db.flush()
    return r


def _reviewee(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str,
    identifier: str,
) -> Reviewee:
    e = Reviewee(
        session_id=review_session.id,
        name=name,
        email_or_identifier=identifier,
    )
    db.add(e)
    db.flush()
    return e


def _instrument(
    db: Session, review_session: ReviewSession
) -> Instrument:
    i = Instrument(
        session_id=review_session.id, name="Form", short_label="F"
    )
    db.add(i)
    db.flush()
    return i


def _field(
    db: Session,
    instrument: Instrument,
    spec: dict,
    *,
    field_key: str,
    label: str | None = None,
) -> InstrumentResponseField:
    f = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=field_key,
        label=label or field_key.title(),
        order=0,
        **spec,
    )
    db.add(f)
    db.flush()
    return f


def _assignment(
    db: Session,
    review_session: ReviewSession,
    *,
    reviewer: Reviewer,
    reviewee: Reviewee,
    instrument: Instrument,
) -> Assignment:
    a = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
        created_by_mode="manual",
    )
    db.add(a)
    db.flush()
    return a


def _response(
    db: Session,
    *,
    assignment: Assignment,
    field: InstrumentResponseField,
    value: str,
) -> Response:
    r = Response(
        assignment_id=assignment.id,
        response_field_id=field.id,
        value=value,
    )
    db.add(r)
    db.flush()
    return r


def _shape(
    db: Session,
    review_session: ReviewSession,
    *,
    axis: str = "reviewer",
    instrument: Instrument | None = None,
    field: InstrumentResponseField | None = None,
    slots: list[str],
    name: str = "Shape",
    self_review_handling: str = "include_self",
) -> DataShape:
    shape = DataShape(
        session_id=review_session.id,
        name=name,
        axis=axis,
        instrument_id=instrument.id if instrument else None,
        response_field_id=field.id if field else None,
        column_chip_slots=json.dumps(slots),
        self_review_handling=self_review_handling,
    )
    db.add(shape)
    db.flush()
    return shape


# --------------------------------------------------------------------------- #
# Per-individual rows
# --------------------------------------------------------------------------- #


def test_per_individual_basic_columns(db: Session) -> None:
    review_session = _session(db, code="ind")
    _reviewer(db, review_session, name="Rita", email="r@x.edu")
    _reviewer(db, review_session, name="Sam", email="s@x.edu")
    shape = _shape(
        db,
        review_session,
        slots=["reviewer:name", "reviewer:email"],
    )
    rows = build_shape_rows(db, review_session, shape)
    assert rows[0] == ("ReviewerName", "ReviewerEmail")
    body = sorted(rows[1:])
    assert body == [("Rita", "r@x.edu"), ("Sam", "s@x.edu")]


def test_per_individual_with_assigned_and_count(db: Session) -> None:
    review_session = _session(db, code="ind-agg")
    rita = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    eli = _reviewee(db, review_session, name="Eli", identifier="e@x")
    instrument = _instrument(db, review_session)
    fld = _field(db, instrument, _INLINE_NUMERIC, field_key="s")
    a = _assignment(
        db, review_session, reviewer=rita, reviewee=eli, instrument=instrument
    )
    _response(db, assignment=a, field=fld, value="3")
    shape = _shape(
        db,
        review_session,
        instrument=instrument,
        field=fld,
        slots=[
            "reviewer:name",
            "reviewer:email",
            "reviewer:assigned",
            "reviewer:count",
            "reviewer:mean",
        ],
    )
    rows = build_shape_rows(db, review_session, shape)
    # Header
    assert rows[0] == (
        "ReviewerName",
        "ReviewerEmail",
        "Assigned_self",
        "Count_self",
        "Mean_self",
    )
    # One row per reviewer; rita has 1 assigned + 1 count + mean=3.
    rita_row = next(r for r in rows[1:] if r[0] == "Rita")
    assert rita_row == ("Rita", "r@x.edu", "1", "1", "3")


# --------------------------------------------------------------------------- #
# Per-tag-combo rows
# --------------------------------------------------------------------------- #


def test_per_tag_combo_aggregates_across_individuals(
    db: Session,
) -> None:
    review_session = _session(db, code="tag")
    a1 = _reviewer(
        db, review_session, name="A1", email="a1@x.edu", tag_1="A"
    )
    a2 = _reviewer(
        db, review_session, name="A2", email="a2@x.edu", tag_1="A"
    )
    b1 = _reviewer(
        db, review_session, name="B1", email="b1@x.edu", tag_1="B"
    )
    eli = _reviewee(db, review_session, name="Eli", identifier="e@x")
    instrument = _instrument(db, review_session)
    fld = _field(db, instrument, _INLINE_NUMERIC, field_key="s")
    for reviewer, val in [(a1, "5"), (a2, "3"), (b1, "4")]:
        a = _assignment(
            db,
            review_session,
            reviewer=reviewer,
            reviewee=eli,
            instrument=instrument,
        )
        _response(db, assignment=a, field=fld, value=val)
    shape = _shape(
        db,
        review_session,
        instrument=instrument,
        field=fld,
        slots=["reviewer:tag-1", "reviewer:count", "reviewer:mean"],
    )
    rows = build_shape_rows(db, review_session, shape)
    assert rows[0] == ("Tag 1", "Count_self", "Mean_self")
    by_tag = {r[0]: r for r in rows[1:]}
    # A has 2 responses (5 + 3) → mean = 4
    assert by_tag["A"][1:] == ("2", "4")
    # B has 1 response (4) → mean = 4
    assert by_tag["B"][1:] == ("1", "4")


# --------------------------------------------------------------------------- #
# Single summary row
# --------------------------------------------------------------------------- #


def test_single_summary_row(db: Session) -> None:
    review_session = _session(db, code="sum")
    rita = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    sam = _reviewer(db, review_session, name="Sam", email="s@x.edu")
    eli = _reviewee(db, review_session, name="Eli", identifier="e@x")
    instrument = _instrument(db, review_session)
    fld = _field(db, instrument, _INLINE_NUMERIC, field_key="s")
    for r, val in [(rita, "1"), (sam, "5")]:
        a = _assignment(
            db,
            review_session,
            reviewer=r,
            reviewee=eli,
            instrument=instrument,
        )
        _response(db, assignment=a, field=fld, value=val)
    shape = _shape(
        db,
        review_session,
        instrument=instrument,
        field=fld,
        slots=["reviewer:count", "reviewer:mean", "reviewer:min", "reviewer:max"],
    )
    rows = build_shape_rows(db, review_session, shape)
    assert rows[0] == ("Count_self", "Mean_self", "Min_self", "Max_self")
    # Single row across whole roster.
    assert len(rows) == 2
    assert rows[1] == ("2", "3", "1", "5")


# --------------------------------------------------------------------------- #
# Fan-out chips
# --------------------------------------------------------------------------- #


def test_discrete_steps_fan_out_one_column_per_value(
    db: Session,
) -> None:
    review_session = _session(db, code="disc")
    rita = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    eli = _reviewee(db, review_session, name="Eli", identifier="e@x")
    ann = _reviewee(db, review_session, name="Ann", identifier="a@x")
    instrument = _instrument(db, review_session)
    fld = _field(db, instrument, _INLINE_NUMERIC, field_key="s")
    for ree, val in [(eli, "3"), (ann, "5")]:
        a = _assignment(
            db,
            review_session,
            reviewer=rita,
            reviewee=ree,
            instrument=instrument,
        )
        _response(db, assignment=a, field=fld, value=val)
    shape = _shape(
        db,
        review_session,
        instrument=instrument,
        field=fld,
        slots=["reviewer:name", "reviewer:discrete-steps"],
    )
    rows = build_shape_rows(db, review_session, shape)
    # Header: name + 5 discrete steps (1..5)
    assert rows[0] == (
        "ReviewerName", "1_self", "2_self", "3_self", "4_self", "5_self",
    )
    rita_row = next(r for r in rows[1:] if r[0] == "Rita")
    # Counts: 0 for 1, 0 for 2, 1 for 3, 0 for 4, 1 for 5
    assert rita_row[1:] == ("0", "0", "1", "0", "1")


def test_list_items_fan_out(db: Session) -> None:
    review_session = _session(db, code="list")
    rita = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    instrument = _instrument(db, review_session)
    fld = _field(
        db, instrument, _INLINE_LIST, field_key="choice", label="Choice"
    )
    # Three distinct (reviewer × reviewee × instrument)
    # assignments so the unique constraint doesn't fire.
    for n, val in (("Eli", "Yes"), ("Ann", "Yes"), ("Bea", "No")):
        ree = _reviewee(
            db, review_session, name=n, identifier=f"{n.lower()}@x"
        )
        a = _assignment(
            db,
            review_session,
            reviewer=rita,
            reviewee=ree,
            instrument=instrument,
        )
        _response(db, assignment=a, field=fld, value=val)
    shape = _shape(
        db,
        review_session,
        instrument=instrument,
        field=fld,
        slots=["reviewer:name", "reviewer:list-items"],
    )
    rows = build_shape_rows(db, review_session, shape)
    # Header: name + the three list options.
    assert rows[0] == (
        "ReviewerName", "Yes_self", "No_self", "Maybe_self",
    )
    rita_row = next(r for r in rows[1:] if r[0] == "Rita")
    # 2 ``Yes`` (Eli + Ann), 1 ``No`` (Bea), 0 ``Maybe``.
    assert rita_row[1:] == ("2", "1", "0")


# --------------------------------------------------------------------------- #
# Self-review handling chip — PR B
# --------------------------------------------------------------------------- #


def _seed_alice_with_self_pair(
    db: Session, *, code: str
) -> tuple[ReviewSession, Reviewer, Reviewee, Reviewee, Instrument, InstrumentResponseField]:
    """Seed Alice reviewing herself + Bob on a single-field
    instrument. Calls the PR 2 (self-review consolidation)
    recompute hook so ``Assignment.is_self_review`` is populated
    for the Self-review handling chip's per-state filter."""
    review_session = _session(db, code=code)
    alice_r = _reviewer(
        db, review_session, name="Alice", email="alice@example.edu"
    )
    alice_e = _reviewee(
        db, review_session, name="Alice", identifier="alice@example.edu"
    )
    bob_e = _reviewee(
        db, review_session, name="Bob", identifier="bob@example.edu"
    )
    instrument = _instrument(db, review_session)
    fld = _field(db, instrument, _INLINE_NUMERIC, field_key="s")
    for ree, val in [(alice_e, "10"), (bob_e, "80")]:
        a = _assignment(
            db,
            review_session,
            reviewer=alice_r,
            reviewee=ree,
            instrument=instrument,
        )
        _response(db, assignment=a, field=fld, value=val)
    from app.services import assignments as assignments_service

    assignments_service.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    return review_session, alice_r, alice_e, bob_e, instrument, fld


def test_include_self_state_carries_self_suffix(db: Session) -> None:
    """``include_self`` rolls every ``include=True`` row in;
    aggregate columns carry the ``_self`` suffix."""
    review_session, _, _, _, instrument, fld = _seed_alice_with_self_pair(
        db, code="ds-incl"
    )
    shape = _shape(
        db,
        review_session,
        axis="reviewer",
        instrument=instrument,
        field=fld,
        slots=[
            "reviewer:name",
            "reviewer:email",
            "reviewer:count",
            "reviewer:mean",
        ],
        self_review_handling="include_self",
    )
    rows = build_shape_rows(db, review_session, shape)
    assert rows[0] == (
        "ReviewerName",
        "ReviewerEmail",
        "Count_self",
        "Mean_self",
    )
    alice = next(r for r in rows[1:] if r[0] == "Alice")
    # Both responses fold in: count=2, mean=(10+80)/2=45.
    assert alice[2:] == ("2", "45")


def test_exclude_self_state_drops_self_review(db: Session) -> None:
    """``exclude_self`` filters out Alice's self-review row;
    aggregate columns carry the ``_noself`` suffix."""
    review_session, _, _, _, instrument, fld = _seed_alice_with_self_pair(
        db, code="ds-excl"
    )
    shape = _shape(
        db,
        review_session,
        axis="reviewer",
        instrument=instrument,
        field=fld,
        slots=[
            "reviewer:name",
            "reviewer:count",
            "reviewer:mean",
        ],
        self_review_handling="exclude_self",
    )
    rows = build_shape_rows(db, review_session, shape)
    assert rows[0] == (
        "ReviewerName",
        "Count_noself",
        "Mean_noself",
    )
    alice = next(r for r in rows[1:] if r[0] == "Alice")
    # Only the Alice→Bob row survives: count=1, mean=80.
    assert alice[1:] == ("1", "80")


def test_both_state_emits_self_and_noself_blocks_side_by_side(
    db: Session,
) -> None:
    """``both`` runs the pipeline twice and concatenates the
    aggregate-column blocks (``_self`` first, then ``_noself``)."""
    review_session, _, _, _, instrument, fld = _seed_alice_with_self_pair(
        db, code="ds-both"
    )
    shape = _shape(
        db,
        review_session,
        axis="reviewer",
        instrument=instrument,
        field=fld,
        slots=[
            "reviewer:name",
            "reviewer:count",
            "reviewer:mean",
        ],
        self_review_handling="both",
    )
    rows = build_shape_rows(db, review_session, shape)
    assert rows[0] == (
        "ReviewerName",
        "Count_self",
        "Mean_self",
        "Count_noself",
        "Mean_noself",
    )
    alice = next(r for r in rows[1:] if r[0] == "Alice")
    # ``_self`` block: both responses; ``_noself``: only Bob.
    assert alice[1:] == ("2", "45", "1", "80")
