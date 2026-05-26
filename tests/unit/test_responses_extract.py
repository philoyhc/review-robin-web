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
    InstrumentDisplayField,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.extracts.responses_extract import (
    HEADER,
    serialize_responses,
    serialize_responses_for_instrument,
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
    return review_session


# RTD seed retired 2026-05-26 — tests that need a Likert5 inline
# spec get it from this dict and splat it into the field
# constructor below.
_LIKERT5_SPEC: dict[str, object] = {
    "_inline_data_type": "Integer",
    "_inline_response_type": "Likert5",
    "_inline_min": 1.0,
    "_inline_max": 5.0,
    "_inline_step": 1.0,
}


def _likert(db: Session, review_session: ReviewSession) -> dict[str, object]:
    return _LIKERT5_SPEC


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
    rtd: dict[str, object],
    order: int = 0,
    help_text: str | None = None,
) -> InstrumentResponseField:
    f = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=field_key,
        label=label,
        order=order,
        help_text=help_text,
        # iii-b4: FK retired; populate inline columns directly so
        # downstream readers (extracts, properties) see the right
        # data_type / response_type.
        **rtd,
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


def _data(rows: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    """The data rows — everything after HEADER (skips the
    per-instrument preamble + blank-row gap)."""
    return rows[rows.index(HEADER) + 1 :]


def _preamble(rows: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    """The preamble rows — everything before the blank-row gap."""
    pre = rows[: rows.index(HEADER)]
    return pre[:-1] if pre and pre[-1] == () else pre


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_header_is_21_columns_in_canonical_order() -> None:
    """Pin the column order so a rename or reorder fails loud
    and forces analysts of the file to update their pipelines
    deliberately. ``SelfReview`` (col index 16) was added in
    PR 4a between ``Value`` and ``SavedAt``; ``InstrumentFlavour``
    (col index 20) appended in Segment 13C slice D2."""

    assert len(HEADER) == 21
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
        "InstrumentFlavour",
    )


def test_empty_session_emits_header_only(db: Session) -> None:
    """A session with no instruments has no preamble and no gap —
    just the header."""
    review_session = _session(db, code="empty")
    rows = list(serialize_responses(db, review_session))
    assert rows == [HEADER]


def test_preamble_lists_instrument_with_field_help_texts(
    db: Session,
) -> None:
    """The preamble names the instrument positionally, then emits
    one (FieldKey, HelpText) row per response field — a field
    dictionary that keeps help text out of the data table."""
    review_session = _session(db, code="preamble")
    likert = _likert(db, review_session)
    instr = _add_instrument(db, review_session, name="Default")
    _add_field(
        db, instr, field_key="q1", label="Q1", rtd=likert, order=0,
        help_text="How clear was the explanation?",
    )
    _add_field(
        db, instr, field_key="q2", label="Q2", rtd=likert, order=1
    )

    rows = list(serialize_responses(db, review_session))
    assert _preamble(rows) == [
        ("instrument_1",),
        ("q1", "How clear was the explanation?"),
        ("q2", ""),
    ]


def test_preamble_stacks_multiple_instruments(db: Session) -> None:
    """Each instrument gets its own stacked preamble block, named
    positionally by instrument order."""
    review_session = _session(db, code="multi-pre")
    likert = _likert(db, review_session)
    first = _add_instrument(db, review_session, name="A", order=0)
    second = _add_instrument(db, review_session, name="B", order=1)
    _add_field(db, first, field_key="a1", label="A1", rtd=likert)
    _add_field(
        db, second, field_key="b1", label="B1", rtd=likert,
        help_text="B help",
    )

    rows = list(serialize_responses(db, review_session))
    assert _preamble(rows) == [
        ("instrument_1",),
        ("a1", ""),
        ("instrument_2",),
        ("b1", "B help"),
    ]


def test_blank_row_gap_precedes_the_header(db: Session) -> None:
    """A blank row separates the preamble from the data table."""
    review_session = _session(db, code="gap")
    likert = _likert(db, review_session)
    instr = _add_instrument(db, review_session, name="I")
    _add_field(db, instr, field_key="q", label="Q", rtd=likert)

    rows = list(serialize_responses(db, review_session))
    assert rows[rows.index(HEADER) - 1] == ()


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
    body_row = _data(rows)[0]
    # 20 columns; spot-check identity, tags, instrument, field,
    # response type, value, self-review, version. ``InstrumentName``
    # is the positional id ``instrument_1`` (not the operator's
    # typed name). ``saved_at`` / ``submitted_at`` round-trip an
    # ISO-8601 prefix; the exact timezone suffix varies between
    # SQLite (strips tz) and Postgres (preserves it), so just
    # assert the iso-prefix is present.
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
        "instrument_1",
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
    assert body_row[20] == "per-reviewee"  # InstrumentFlavour


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

    body = _data(list(serialize_responses(db, review_session)))
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
    # No data rows — the preamble still lists the instrument + field.
    assert _data(rows) == []
    assert _preamble(rows) == [("instrument_1",), ("q", "")]


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
    assert _data(rows)[0][18] == ""  # SubmittedAt empty for drafts.


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

    body = _data(list(serialize_responses(db, review_session)))
    # alice→Carol[first/q1, second/q2], bob→Carol[first/q1, second/q2].
    # InstrumentName is the positional id: First→instrument_1,
    # Second→instrument_2 (by Instrument.order).
    assert [(r[1], r[10], r[12]) for r in body] == [
        ("alice@example.edu", "instrument_1", "q1"),
        ("alice@example.edu", "instrument_2", "q2"),
        ("bob@example.edu", "instrument_1", "q1"),
        ("bob@example.edu", "instrument_2", "q2"),
    ]


def test_response_type_resolves_for_seeded_and_operator_defined_rtds(
    db: Session,
) -> None:
    review_session = _session(db, code="rtd")
    likert = _likert(db, review_session)
    custom: dict[str, object] = {
        "_inline_data_type": "decimal",
        "_inline_response_type": "GPA4",
        "_inline_min": 0.0,
        "_inline_max": 4.0,
    }

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

    body = _data(list(serialize_responses(db, review_session)))
    response_types = [r[14] for r in body]
    assert response_types == ["Likert5", "GPA4"]


def test_list_response_value_round_trips_as_stored(db: Session) -> None:
    """List-type responses serialise as the same comma-separated
    literal the database stores."""

    review_session = _session(db, code="listval")
    list_rtd: dict[str, object] = {
        "_inline_data_type": "list",
        "_inline_response_type": "Topics",
        "_inline_list_csv": "design,research,ops",
    }

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

    body = _data(list(serialize_responses(db, review_session)))
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

    body = _data(list(serialize_responses(db, review_session)))
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

    body = _data(list(serialize_responses(db, review_session)))
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

    body = _data(list(serialize_responses(db, review_session)))
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

    body = _data(list(serialize_responses(db, review_session)))
    assert body[0][16] == "FALSE"


# --------------------------------------------------------------------------- #
# Segment 13C slice D2 — group-scoped instrument collapse
# --------------------------------------------------------------------------- #


def test_group_scoped_instrument_collapses_to_one_row_per_group(
    db: Session,
) -> None:
    """A group-scoped instrument's fanned-out per-member Response
    rows collapse to one row per boundary group: the composed
    identity lands in RevieweeName, the other reviewee columns are
    empty, and InstrumentFlavour reads ``group-scoped``."""
    review_session = _session(db, code="grp-collapse")
    likert = _likert(db, review_session)
    reviewer = _add_reviewer(
        db, review_session, email="r@example.edu", name="R"
    )
    carol = _add_reviewee(
        db, review_session, identifier="carol@example.edu",
        name="Carol", tag_1="Team A",
    )
    eve = _add_reviewee(
        db, review_session, identifier="eve@example.edu",
        name="Eve", tag_1="Team A",
    )
    dan = _add_reviewee(
        db, review_session, identifier="dan@example.edu",
        name="Dan", tag_1="Team B",
    )
    instr = _add_instrument(db, review_session, name="Grp")
    instr.group_kind = "r1"  # group by reviewee tag 1
    db.flush()
    field = _add_field(db, instr, field_key="q", label="Q", rtd=likert)
    for reviewee in (carol, eve, dan):
        a = _add_assignment(
            db, review_session, reviewer=reviewer,
            reviewee=reviewee, instrument=instr,
        )
        # The save-time fan-out writes the same value to every
        # member assignment of the group.
        _add_response(db, assignment=a, field=field, value="4")

    body = _data(list(serialize_responses(db, review_session)))
    # 3 member Response rows → 2 boundary groups → 2 rows.
    assert len(body) == 2
    assert [r[5] for r in body] == ["Team A", "Team B"]  # RevieweeName
    for row in body:
        assert row[6] == ""  # RevieweeEmail blank
        assert row[7] == row[8] == row[9] == ""  # tag columns blank
        assert row[15] == "4"  # Value
        assert row[16] == "FALSE"  # SelfReview
        assert row[20] == "group-scoped"  # InstrumentFlavour


def test_group_identity_includes_member_names_when_name_field_included(
    db: Session,
) -> None:
    """When the RevieweeName Display Field is Included on a
    group-scoped instrument, the export identity appends the full
    (untruncated) member-name list."""
    review_session = _session(db, code="grp-names")
    likert = _likert(db, review_session)
    reviewer = _add_reviewer(
        db, review_session, email="r@example.edu", name="R"
    )
    carol = _add_reviewee(
        db, review_session, identifier="carol@example.edu",
        name="Carol", tag_1="Team A",
    )
    eve = _add_reviewee(
        db, review_session, identifier="eve@example.edu",
        name="Eve", tag_1="Team A",
    )
    instr = _add_instrument(db, review_session, name="Grp")
    instr.group_kind = "r1"
    db.flush()
    db.add(
        InstrumentDisplayField(
            instrument_id=instr.id,
            label="Name",
            source_type="reviewee",
            source_field="name",
            visible=True,
            order=0,
        )
    )
    field = _add_field(db, instr, field_key="q", label="Q", rtd=likert)
    for reviewee in (carol, eve):
        a = _add_assignment(
            db, review_session, reviewer=reviewer,
            reviewee=reviewee, instrument=instr,
        )
        _add_response(db, assignment=a, field=field, value="4")

    body = _data(list(serialize_responses(db, review_session)))
    assert len(body) == 1
    assert body[0][5] == "Team A (Carol, Eve)"


# --------------------------------------------------------------------------- #
# serialize_responses_for_instrument — 18H Part 2
# --------------------------------------------------------------------------- #


def test_per_instrument_emits_only_that_instrument(db: Session) -> None:
    """The per-instrument file is filtered to one instrument; the
    other instrument's responses don't bleed in."""
    review_session = _session(db, code="per-i")
    likert = _likert(db, review_session)
    rita = _add_reviewer(
        db, review_session, email="rita@x.edu", name="Rita"
    )
    eli = _add_reviewee(
        db, review_session, identifier="eli@x.edu", name="Eli"
    )
    instr_a = _add_instrument(db, review_session, name="A", order=0)
    instr_b = _add_instrument(db, review_session, name="B", order=1)
    f_a = _add_field(db, instr_a, field_key="qa", label="QA", rtd=likert)
    f_b = _add_field(db, instr_b, field_key="qb", label="QB", rtd=likert)
    asg_a = _add_assignment(
        db, review_session, reviewer=rita, reviewee=eli, instrument=instr_a
    )
    asg_b = _add_assignment(
        db, review_session, reviewer=rita, reviewee=eli, instrument=instr_b
    )
    _add_response(db, assignment=asg_a, field=f_a, value="3")
    _add_response(db, assignment=asg_b, field=f_b, value="5")

    rows_a = list(
        serialize_responses_for_instrument(
            db, review_session, instr_a, position=1
        )
    )
    body_a = _data(rows_a)
    pre_a = _preamble(rows_a)
    # One data row, only instrument A's value.
    assert [row[12] for row in body_a] == ["qa"]
    assert [row[15] for row in body_a] == ["3"]
    # Preamble names only instrument_1.
    assert pre_a[0] == ("instrument_1",)
    assert ("instrument_2",) not in pre_a


def test_per_instrument_sorts_by_reviewee_then_reviewer(
    db: Session,
) -> None:
    """Data rows are ordered ``(reviewee → reviewer → field)`` so
    each reviewee's reviewers cluster consecutively."""
    review_session = _session(db, code="per-sort")
    likert = _likert(db, review_session)
    ann = _add_reviewer(db, review_session, email="ann@x.edu", name="Ann")
    bob = _add_reviewer(db, review_session, email="bob@x.edu", name="Bob")
    xan = _add_reviewee(
        db, review_session, identifier="xan@x.edu", name="Xan"
    )
    yas = _add_reviewee(
        db, review_session, identifier="yas@x.edu", name="Yas"
    )
    instr = _add_instrument(db, review_session, name="Form", order=0)
    fld = _add_field(db, instr, field_key="q", label="Q", rtd=likert)
    for reviewer in (bob, ann):
        for reviewee in (yas, xan):
            asg = _add_assignment(
                db,
                review_session,
                reviewer=reviewer,
                reviewee=reviewee,
                instrument=instr,
            )
            _add_response(db, assignment=asg, field=fld, value="4")

    rows = list(
        serialize_responses_for_instrument(
            db, review_session, instr, position=1
        )
    )
    body = _data(rows)
    # Sort key is (RevieweeName col 5, ReviewerEmail col 1) — Xan
    # before Yas, and within each reviewee Ann before Bob.
    assert [(r[5], r[1]) for r in body] == [
        ("Xan", "ann@x.edu"),
        ("Xan", "bob@x.edu"),
        ("Yas", "ann@x.edu"),
        ("Yas", "bob@x.edu"),
    ]


def test_per_instrument_for_group_scoped_collapses_and_sorts_by_group(
    db: Session,
) -> None:
    """A group-scoped instrument's fan-out collapses to one row
    per (reviewer, group, field); the per-instrument file sorts
    by the composed group identity so all of a group's rows
    cluster together."""
    review_session = _session(db, code="per-grp")
    likert = _likert(db, review_session)
    rita = _add_reviewer(
        db, review_session, email="rita@x.edu", name="Rita"
    )
    # Two groups by tag_1: Team A (Carol, Dan), Team B (Eve, Frank).
    carol = _add_reviewee(
        db, review_session, identifier="carol@x.edu", name="Carol",
        tag_1="Team A",
    )
    dan = _add_reviewee(
        db, review_session, identifier="dan@x.edu", name="Dan",
        tag_1="Team A",
    )
    eve = _add_reviewee(
        db, review_session, identifier="eve@x.edu", name="Eve",
        tag_1="Team B",
    )
    frank = _add_reviewee(
        db, review_session, identifier="frank@x.edu", name="Frank",
        tag_1="Team B",
    )
    instr = Instrument(
        session_id=review_session.id,
        name="Form",
        order=0,
        group_kind="r1",
    )
    db.add(instr)
    db.flush()
    fld = _add_field(db, instr, field_key="q", label="Q", rtd=likert)
    for reviewee in (carol, dan, eve, frank):
        asg = _add_assignment(
            db,
            review_session,
            reviewer=rita,
            reviewee=reviewee,
            instrument=instr,
        )
        _add_response(db, assignment=asg, field=fld, value="4")

    rows = list(
        serialize_responses_for_instrument(
            db, review_session, instr, position=1
        )
    )
    body = _data(rows)
    # Two collapsed rows — Team A then Team B (alpha sort on
    # composed RevieweeName).
    assert len(body) == 2
    assert body[0][5] == "Team A"
    assert body[1][5] == "Team B"
