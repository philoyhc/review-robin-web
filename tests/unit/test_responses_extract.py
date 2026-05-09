"""Unit tests for ``app.services.extracts.responses_extract`` —
Segment 12A-1 PR 4 + PR 4a.

Covers the 20-column HEADER (incl. PR 4a's ``SelfReview`` flag),
the per-row column shape, the deterministic ordering, the
empty-cell vs no-row semantics for null and absent responses, the
lifecycle distinction (saved vs submitted vs version), and the
multi-instrument interleaving.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    ResponseTypeDefinition,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.extracts.responses_extract import (
    HEADER,
    serialize_responses,
)
from app.services.instruments import (
    ensure_default_response_type_definitions,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _user(db: Session) -> User:
    user = User(email="alice@example.edu", display_name="Alice")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, *, code: str = "rsp") -> ReviewSession:
    user = _user(db)
    review_session = ReviewSession(
        name="Responses",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    ensure_default_response_type_definitions(db, review_session)
    db.flush()
    return review_session


def _likert(db: Session, review_session: ReviewSession) -> ResponseTypeDefinition:
    return (
        db.query(ResponseTypeDefinition)
        .filter(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "Likert5",
        )
        .one()
    )


def _add_reviewer(
    db: Session,
    review_session: ReviewSession,
    *,
    email: str,
    name: str,
    tag_1: str | None = None,
    tag_2: str | None = None,
    tag_3: str | None = None,
) -> Reviewer:
    r = Reviewer(
        session_id=review_session.id,
        name=name,
        email=email,
        tag_1=tag_1,
        tag_2=tag_2,
        tag_3=tag_3,
    )
    db.add(r)
    db.flush()
    return r


def _add_reviewee(
    db: Session,
    review_session: ReviewSession,
    *,
    identifier: str,
    name: str,
    tag_1: str | None = None,
    tag_2: str | None = None,
    tag_3: str | None = None,
) -> Reviewee:
    e = Reviewee(
        session_id=review_session.id,
        name=name,
        email_or_identifier=identifier,
        tag_1=tag_1,
        tag_2=tag_2,
        tag_3=tag_3,
    )
    db.add(e)
    db.flush()
    return e


def _add_instrument(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str,
    short_label: str | None = None,
    order: int = 0,
) -> Instrument:
    i = Instrument(
        session_id=review_session.id,
        name=name,
        short_label=short_label,
        order=order,
    )
    db.add(i)
    db.flush()
    return i


def _add_field(
    db: Session,
    instrument: Instrument,
    *,
    field_key: str,
    label: str,
    rtd: ResponseTypeDefinition,
    order: int = 0,
) -> InstrumentResponseField:
    f = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=field_key,
        label=label,
        response_type_id=rtd.id,
        order=order,
    )
    db.add(f)
    db.flush()
    return f


def _add_assignment(
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


def _add_response(
    db: Session,
    *,
    assignment: Assignment,
    field: InstrumentResponseField,
    value: str | None,
    saved_at: dt.datetime | None = None,
    submitted_at: dt.datetime | None = None,
    version: int = 1,
) -> Response:
    resp = Response(
        assignment_id=assignment.id,
        response_field_id=field.id,
        value=value,
        saved_at=saved_at or dt.datetime(2026, 5, 9, tzinfo=dt.timezone.utc),
        submitted_at=submitted_at,
        version=version,
    )
    db.add(resp)
    db.flush()
    return resp


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_header_is_20_columns_in_canonical_order() -> None:
    """Pin the column order so a rename or reorder fails loud
    and forces analysts of the file to update their pipelines
    deliberately. ``SelfReview`` (col index 16) was added in
    PR 4a between ``Value`` and ``SavedAt``."""

    assert len(HEADER) == 20
    assert HEADER == (
        "ReviewerName",
        "ReviewerEmail",
        "ReviewerTag1",
        "ReviewerTag2",
        "ReviewerTag3",
        "RevieweeName",
        "RevieweeEmail",
        "RevieweeTag1",
        "RevieweeTag2",
        "RevieweeTag3",
        "InstrumentName",
        "InstrumentShortLabel",
        "FieldKey",
        "FieldLabel",
        "ResponseType",
        "Value",
        "SelfReview",
        "SavedAt",
        "SubmittedAt",
        "Version",
    )


def test_empty_session_emits_header_only(db: Session) -> None:
    review_session = _session(db, code="empty")
    rows = list(serialize_responses(db, review_session))
    assert rows == [HEADER]


def test_per_row_shape_denormalises_all_join_keys(db: Session) -> None:
    review_session = _session(db, code="shape")
    likert = _likert(db, review_session)
    reviewer = _add_reviewer(
        db,
        review_session,
        email="alex@example.edu",
        name="Alex Adams",
        tag_1="cohort-a",
        tag_2="2026",
    )
    reviewee = _add_reviewee(
        db,
        review_session,
        identifier="carol@example.edu",
        name="Carol Carter",
        tag_1="design",
    )
    instr = _add_instrument(
        db,
        review_session,
        name="Peer evaluation",
        short_label="Peer",
    )
    field = _add_field(
        db, instr, field_key="overall", label="Overall", rtd=likert
    )
    assignment = _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instr,
    )
    saved_at = dt.datetime(2026, 5, 1, 12, 0, tzinfo=dt.timezone.utc)
    submitted_at = dt.datetime(2026, 5, 2, 9, 30, tzinfo=dt.timezone.utc)
    _add_response(
        db,
        assignment=assignment,
        field=field,
        value="4",
        saved_at=saved_at,
        submitted_at=submitted_at,
        version=2,
    )

    rows = list(serialize_responses(db, review_session))
    assert rows[0] == HEADER
    body_row = rows[1]
    # 20 columns; spot-check identity, tags, instrument, field,
    # response type, value, self-review, version. ``saved_at`` /
    # ``submitted_at`` round-trip an ISO-8601 prefix; the
    # exact timezone suffix varies between SQLite (strips tz)
    # and Postgres (preserves it), so just assert the
    # iso-prefix is present.
    assert body_row[:17] == (
        "Alex Adams",
        "alex@example.edu",
        "cohort-a",
        "2026",
        "",
        "Carol Carter",
        "carol@example.edu",
        "design",
        "",
        "",
        "Peer evaluation",
        "Peer",
        "overall",
        "Overall",
        "Likert5",
        "4",
        "FALSE",  # SelfReview — alex@ != carol@
    )
    assert body_row[17].startswith("2026-05-01T12:00:00")  # SavedAt
    assert body_row[18].startswith("2026-05-02T09:30:00")  # SubmittedAt
    assert body_row[19] == "2"  # Version


def test_null_value_emits_empty_cell_with_row_still_present(
    db: Session,
) -> None:
    """``Response.value IS NULL`` (reviewer cleared the field)
    emits an empty Value cell — the row is still emitted because
    the reviewer interacted with the field."""

    review_session = _session(db, code="null")
    likert = _likert(db, review_session)
    reviewer = _add_reviewer(
        db, review_session, email="r@example.edu", name="R"
    )
    reviewee = _add_reviewee(
        db, review_session, identifier="e@example.edu", name="E"
    )
    instr = _add_instrument(db, review_session, name="I")
    field = _add_field(
        db, instr, field_key="q", label="Q", rtd=likert
    )
    a = _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instr,
    )
    _add_response(db, assignment=a, field=field, value=None)

    rows = list(serialize_responses(db, review_session))
    body = rows[1:]
    assert len(body) == 1
    assert body[0][15] == ""  # Value column


def test_assignment_with_no_responses_emits_no_row(db: Session) -> None:
    """A reviewer who never saved any value produces no Response
    row — and therefore no row in the CSV. The absence is the
    signal; the row count equals ``len(responses)`` so
    "responses received" is a one-line count from the file."""

    review_session = _session(db, code="absent")
    likert = _likert(db, review_session)
    reviewer = _add_reviewer(
        db, review_session, email="r@example.edu", name="R"
    )
    reviewee = _add_reviewee(
        db, review_session, identifier="e@example.edu", name="E"
    )
    instr = _add_instrument(db, review_session, name="I")
    _add_field(db, instr, field_key="q", label="Q", rtd=likert)
    _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instr,
    )
    # No _add_response call — the assignment exists but the
    # reviewer never touched the field.

    rows = list(serialize_responses(db, review_session))
    assert rows == [HEADER]


def test_submitted_at_distinguishes_drafts_from_submitted(
    db: Session,
) -> None:
    review_session = _session(db, code="lifecycle")
    likert = _likert(db, review_session)
    reviewer = _add_reviewer(
        db, review_session, email="r@example.edu", name="R"
    )
    reviewee = _add_reviewee(
        db, review_session, identifier="e@example.edu", name="E"
    )
    instr = _add_instrument(db, review_session, name="I")
    field = _add_field(db, instr, field_key="q", label="Q", rtd=likert)
    a = _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instr,
    )
    _add_response(
        db,
        assignment=a,
        field=field,
        value="3",
        submitted_at=None,  # draft
    )

    rows = list(serialize_responses(db, review_session))
    assert rows[1][18] == ""  # SubmittedAt empty for drafts.


def test_ordering_groups_by_reviewer_then_reviewee_then_instrument_then_field(
    db: Session,
) -> None:
    review_session = _session(db, code="order")
    likert = _likert(db, review_session)
    alice = _add_reviewer(
        db, review_session, email="alice@example.edu", name="Alice"
    )
    bob = _add_reviewer(
        db, review_session, email="bob@example.edu", name="Bob"
    )
    carol = _add_reviewee(
        db,
        review_session,
        identifier="carol@example.edu",
        name="Carol",
    )
    instr_first = _add_instrument(
        db, review_session, name="First", order=0
    )
    instr_second = _add_instrument(
        db, review_session, name="Second", order=1
    )
    f1 = _add_field(
        db, instr_first, field_key="q1", label="Q1", rtd=likert, order=0
    )
    f2 = _add_field(
        db,
        instr_second,
        field_key="q2",
        label="Q2",
        rtd=likert,
        order=0,
    )

    # Insert in a deliberately scrambled order — query ordering
    # should still group as documented.
    a_bob_second = _add_assignment(
        db,
        review_session,
        reviewer=bob,
        reviewee=carol,
        instrument=instr_second,
    )
    a_alice_first = _add_assignment(
        db,
        review_session,
        reviewer=alice,
        reviewee=carol,
        instrument=instr_first,
    )
    a_alice_second = _add_assignment(
        db,
        review_session,
        reviewer=alice,
        reviewee=carol,
        instrument=instr_second,
    )
    a_bob_first = _add_assignment(
        db,
        review_session,
        reviewer=bob,
        reviewee=carol,
        instrument=instr_first,
    )

    _add_response(db, assignment=a_bob_second, field=f2, value="b")
    _add_response(db, assignment=a_alice_first, field=f1, value="a1")
    _add_response(db, assignment=a_alice_second, field=f2, value="a2")
    _add_response(db, assignment=a_bob_first, field=f1, value="b1")

    body = list(serialize_responses(db, review_session))[1:]
    # alice→Carol[First/q1, Second/q2], bob→Carol[First/q1, Second/q2].
    assert [(r[1], r[10], r[12]) for r in body] == [
        ("alice@example.edu", "First", "q1"),
        ("alice@example.edu", "Second", "q2"),
        ("bob@example.edu", "First", "q1"),
        ("bob@example.edu", "Second", "q2"),
    ]


def test_response_type_resolves_for_seeded_and_operator_defined_rtds(
    db: Session,
) -> None:
    review_session = _session(db, code="rtd")
    likert = _likert(db, review_session)
    custom = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type="GPA4",
        data_type="decimal",
        min=0.0,
        max=4.0,
        is_seeded=False,
    )
    db.add(custom)
    db.flush()

    reviewer = _add_reviewer(
        db, review_session, email="r@example.edu", name="R"
    )
    reviewee = _add_reviewee(
        db, review_session, identifier="e@example.edu", name="E"
    )
    instr = _add_instrument(db, review_session, name="I")
    field_seed = _add_field(
        db, instr, field_key="q1", label="Q1", rtd=likert, order=0
    )
    field_custom = _add_field(
        db, instr, field_key="q2", label="Q2", rtd=custom, order=1
    )
    a = _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instr,
    )
    _add_response(db, assignment=a, field=field_seed, value="3")
    _add_response(db, assignment=a, field=field_custom, value="3.7")

    body = list(serialize_responses(db, review_session))[1:]
    response_types = [r[14] for r in body]
    assert response_types == ["Likert5", "GPA4"]


def test_list_response_value_round_trips_as_stored(db: Session) -> None:
    """List-type responses serialise as the same comma-separated
    literal the database stores."""

    review_session = _session(db, code="listval")
    list_rtd = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type="Topics",
        data_type="list",
        list_csv="design,research,ops",
        is_seeded=False,
    )
    db.add(list_rtd)
    db.flush()

    reviewer = _add_reviewer(
        db, review_session, email="r@example.edu", name="R"
    )
    reviewee = _add_reviewee(
        db, review_session, identifier="e@example.edu", name="E"
    )
    instr = _add_instrument(db, review_session, name="I")
    field = _add_field(
        db, instr, field_key="topics", label="Topics", rtd=list_rtd
    )
    a = _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instr,
    )
    _add_response(db, assignment=a, field=field, value="design,research")

    body = list(serialize_responses(db, review_session))[1:]
    assert body[0][15] == "design,research"


# --------------------------------------------------------------------------- #
# PR 4a — SelfReview column
# --------------------------------------------------------------------------- #


def test_self_review_emits_TRUE_when_reviewer_email_matches_reviewee_id(
    db: Session,
) -> None:
    """When ``reviewer.email`` matches ``reviewee.email_or_identifier``
    (case-insensitive), the SelfReview cell is ``TRUE``."""

    review_session = _session(db, code="self-true")
    likert = _likert(db, review_session)
    reviewer = _add_reviewer(
        db, review_session, email="alex@example.edu", name="Alex"
    )
    reviewee = _add_reviewee(
        db,
        review_session,
        identifier="alex@example.edu",
        name="Alex (as reviewee)",
    )
    instr = _add_instrument(db, review_session, name="I")
    field = _add_field(db, instr, field_key="q", label="Q", rtd=likert)
    a = _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instr,
    )
    _add_response(db, assignment=a, field=field, value="3")

    body = list(serialize_responses(db, review_session))[1:]
    assert body[0][16] == "TRUE"


def test_self_review_emits_FALSE_when_emails_differ(db: Session) -> None:
    review_session = _session(db, code="self-false")
    likert = _likert(db, review_session)
    reviewer = _add_reviewer(
        db, review_session, email="alex@example.edu", name="Alex"
    )
    reviewee = _add_reviewee(
        db, review_session, identifier="carol@example.edu", name="Carol"
    )
    instr = _add_instrument(db, review_session, name="I")
    field = _add_field(db, instr, field_key="q", label="Q", rtd=likert)
    a = _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instr,
    )
    _add_response(db, assignment=a, field=field, value="3")

    body = list(serialize_responses(db, review_session))[1:]
    assert body[0][16] == "FALSE"


def test_self_review_is_case_insensitive(db: Session) -> None:
    """Email comparison casefolds both sides — an operator-typed
    reviewer email and a roster-typed reviewee identifier with
    different casing still match."""

    review_session = _session(db, code="self-case")
    likert = _likert(db, review_session)
    reviewer = _add_reviewer(
        db, review_session, email="Alex@Example.Edu", name="Alex"
    )
    reviewee = _add_reviewee(
        db, review_session, identifier="alex@example.edu", name="Alex"
    )
    instr = _add_instrument(db, review_session, name="I")
    field = _add_field(db, instr, field_key="q", label="Q", rtd=likert)
    a = _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instr,
    )
    _add_response(db, assignment=a, field=field, value="3")

    body = list(serialize_responses(db, review_session))[1:]
    assert body[0][16] == "TRUE"


def test_self_review_emits_FALSE_when_reviewee_id_is_not_an_email(
    db: Session,
) -> None:
    """Non-email reviewee identifiers (cohorts that match by
    student-id / handle) can't be self-reviews — there's no email
    to compare against. Mirrors ``is_self_review``'s
    ``"@" not in identifier`` guard."""

    review_session = _session(db, code="self-noemail")
    likert = _likert(db, review_session)
    reviewer = _add_reviewer(
        db, review_session, email="alex@example.edu", name="Alex"
    )
    reviewee = _add_reviewee(
        db, review_session, identifier="student-001", name="Student 1"
    )
    instr = _add_instrument(db, review_session, name="I")
    field = _add_field(db, instr, field_key="q", label="Q", rtd=likert)
    a = _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instr,
    )
    _add_response(db, assignment=a, field=field, value="3")

    body = list(serialize_responses(db, review_session))[1:]
    assert body[0][16] == "FALSE"
