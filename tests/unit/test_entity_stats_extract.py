"""Unit tests for ``app.services.extracts.entity_stats_extract`` —
Segment 18H Part 3.

Covers the two pinned headers, the header-only empty case, the
zero row for a roster entry with no responses, the draft /
submitted partition, the non-empty-value gate, the required-field
and string-char metrics, the distinct-partner counts, and the
group-scoped fan-out dedupe on the reviewer side.
"""

from __future__ import annotations

import datetime as dt

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
from app.services.extracts.entity_stats_extract import (
    REVIEWEE_STATS_HEADER,
    REVIEWER_STATS_HEADER,
    build_entity_stats,
)

_SUBMITTED = dt.datetime(2026, 5, 10, tzinfo=dt.timezone.utc)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _session(db: Session, *, code: str = "stat") -> ReviewSession:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Stats",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session


# Inline shape specs replacing the RTD seed lookups. Mirrors the
# Rating-Integer-1-5 / Long-text seeds the retired
# ``ensure_default_response_type_definitions`` produced.
_INLINE_SPECS: dict[str, dict[str, object]] = {
    "Long_text": {
        "_inline_data_type": "String",
        "_inline_response_type": "Long_text",
        "_inline_min": 0.0,
        "_inline_max": 2000.0,
    },
    "100int": {
        "_inline_data_type": "Integer",
        "_inline_response_type": "100int",
        "_inline_min": 0.0,
        "_inline_max": 100.0,
        "_inline_step": 1.0,
    },
}


def _rtd(
    db: Session, review_session: ReviewSession, response_type: str
) -> dict[str, object]:
    return _INLINE_SPECS[response_type]


def _reviewer(
    db: Session, review_session: ReviewSession, *, name: str, email: str
) -> Reviewer:
    r = Reviewer(session_id=review_session.id, name=name, email=email)
    db.add(r)
    db.flush()
    return r


def _reviewee(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str,
    identifier: str,
    tag_1: str | None = None,
) -> Reviewee:
    e = Reviewee(
        session_id=review_session.id,
        name=name,
        email_or_identifier=identifier,
        tag_1=tag_1,
    )
    db.add(e)
    db.flush()
    return e


def _instrument(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str = "Form",
    group_kind: str | None = None,
) -> Instrument:
    i = Instrument(
        session_id=review_session.id, name=name, group_kind=group_kind
    )
    db.add(i)
    db.flush()
    return i


def _field(
    db: Session,
    instrument: Instrument,
    rtd: dict[str, object],
    *,
    field_key: str,
    required: bool = False,
    order: int = 0,
) -> InstrumentResponseField:
    f = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=field_key,
        label=field_key.title(),
        required=required,
        order=order,
        # iii-b4: FK retired; inline columns carry data_type for
        # the extract's "string chars" filter.
        **rtd,
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
    value: str | None,
    submitted: bool = False,
) -> Response:
    resp = Response(
        assignment_id=assignment.id,
        response_field_id=field.id,
        value=value,
        saved_at=dt.datetime(2026, 5, 9, tzinfo=dt.timezone.utc),
        submitted_at=_SUBMITTED if submitted else None,
    )
    db.add(resp)
    db.flush()
    return resp


def _row(
    rows: list[tuple[str, ...]],
    header: tuple[str, ...],
    name: str,
) -> dict[str, str]:
    for row in rows[1:]:
        if row[0] == name:
            return dict(zip(header, row))
    raise AssertionError(f"no row named {name!r}")


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_headers_are_pinned() -> None:
    assert REVIEWER_STATS_HEADER == (
        "ReviewerName",
        "ReviewerEmail",
        "ReviewerTag1",
        "ReviewerTag2",
        "ReviewerTag3",
        "RevieweesReviewedDraft",
        "RevieweesReviewedSubmitted",
        "FieldsAnsweredDraft",
        "FieldsAnsweredSubmitted",
        "RequiredFieldsAnsweredDraft",
        "RequiredFieldsAnsweredSubmitted",
        "StringResponseCharsDraft",
        "StringResponseCharsSubmitted",
    )
    assert REVIEWEE_STATS_HEADER == (
        "RevieweeName",
        "RevieweeEmail",
        "RevieweeTag1",
        "RevieweeTag2",
        "RevieweeTag3",
        "PhotoLink",
        "ReviewersDraft",
        "ReviewersSubmitted",
        "FieldsAnsweredDraft",
        "FieldsAnsweredSubmitted",
        "RequiredFieldsAnsweredDraft",
        "RequiredFieldsAnsweredSubmitted",
        "StringResponseCharsDraft",
        "StringResponseCharsSubmitted",
    )


def test_empty_session_yields_header_only(db: Session) -> None:
    review_session = _session(db, code="empty")
    reviewer_rows, reviewee_rows = build_entity_stats(db, review_session)
    assert reviewer_rows == [REVIEWER_STATS_HEADER]
    assert reviewee_rows == [REVIEWEE_STATS_HEADER]


def test_roster_entry_without_responses_yields_zero_row(
    db: Session,
) -> None:
    review_session = _session(db, code="zero")
    _reviewer(db, review_session, name="Rita", email="rita@x.edu")
    _reviewee(db, review_session, name="Eli", identifier="eli@x.edu")

    reviewer_rows, reviewee_rows = build_entity_stats(db, review_session)
    rita = _row(reviewer_rows, REVIEWER_STATS_HEADER, "Rita")
    eli = _row(reviewee_rows, REVIEWEE_STATS_HEADER, "Eli")
    for key in REVIEWER_STATS_HEADER[5:]:
        assert rita[key] == "0"
    for key in REVIEWEE_STATS_HEADER[6:]:
        assert eli[key] == "0"


def test_draft_and_submitted_metrics_partition(db: Session) -> None:
    review_session = _session(db, code="part")
    reviewer = _reviewer(db, review_session, name="Rita", email="rita@x.edu")
    reviewee = _reviewee(db, review_session, name="Eli", identifier="eli@x")
    instrument = _instrument(db, review_session)
    long_text = _rtd(db, review_session, "Long_text")
    f_req = _field(
        db, instrument, long_text, field_key="strengths", required=True
    )
    f_opt = _field(
        db, instrument, long_text, field_key="notes", order=1
    )
    assignment = _assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instrument,
    )
    # Required field saved as a draft; optional field submitted.
    _response(db, assignment=assignment, field=f_req, value="hello")
    _response(
        db,
        assignment=assignment,
        field=f_opt,
        value="world!",
        submitted=True,
    )

    reviewer_rows, reviewee_rows = build_entity_stats(db, review_session)
    rita = _row(reviewer_rows, REVIEWER_STATS_HEADER, "Rita")
    eli = _row(reviewee_rows, REVIEWEE_STATS_HEADER, "Eli")

    assert rita["RevieweesReviewedDraft"] == "1"
    assert rita["RevieweesReviewedSubmitted"] == "1"
    assert rita["FieldsAnsweredDraft"] == "1"
    assert rita["FieldsAnsweredSubmitted"] == "1"
    assert rita["RequiredFieldsAnsweredDraft"] == "1"
    assert rita["RequiredFieldsAnsweredSubmitted"] == "0"
    assert rita["StringResponseCharsDraft"] == "5"
    assert rita["StringResponseCharsSubmitted"] == "6"

    assert eli["ReviewersDraft"] == "1"
    assert eli["ReviewersSubmitted"] == "1"
    assert eli["FieldsAnsweredDraft"] == "1"
    assert eli["FieldsAnsweredSubmitted"] == "1"


def test_empty_or_cleared_value_is_not_counted(db: Session) -> None:
    review_session = _session(db, code="blank")
    reviewer = _reviewer(db, review_session, name="Rita", email="rita@x.edu")
    reviewee = _reviewee(db, review_session, name="Eli", identifier="eli@x")
    instrument = _instrument(db, review_session)
    long_text = _rtd(db, review_session, "Long_text")
    f_null = _field(db, instrument, long_text, field_key="a")
    f_blank = _field(db, instrument, long_text, field_key="b", order=1)
    assignment = _assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instrument,
    )
    _response(db, assignment=assignment, field=f_null, value=None)
    _response(db, assignment=assignment, field=f_blank, value="")

    reviewer_rows, _ = build_entity_stats(db, review_session)
    rita = _row(reviewer_rows, REVIEWER_STATS_HEADER, "Rita")
    assert rita["FieldsAnsweredDraft"] == "0"
    assert rita["RevieweesReviewedDraft"] == "0"


def test_string_chars_count_only_string_typed_fields(
    db: Session,
) -> None:
    review_session = _session(db, code="chars")
    reviewer = _reviewer(db, review_session, name="Rita", email="rita@x.edu")
    reviewee = _reviewee(db, review_session, name="Eli", identifier="eli@x")
    instrument = _instrument(db, review_session)
    long_text = _rtd(db, review_session, "Long_text")
    integer = _rtd(db, review_session, "100int")
    f_text = _field(db, instrument, long_text, field_key="comment")
    f_num = _field(db, instrument, integer, field_key="score", order=1)
    assignment = _assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instrument,
    )
    _response(
        db, assignment=assignment, field=f_text, value="abcd", submitted=True
    )
    _response(
        db, assignment=assignment, field=f_num, value="100", submitted=True
    )

    reviewer_rows, _ = build_entity_stats(db, review_session)
    rita = _row(reviewer_rows, REVIEWER_STATS_HEADER, "Rita")
    # Both fields counted as answered; only the String one in chars.
    assert rita["FieldsAnsweredSubmitted"] == "2"
    assert rita["StringResponseCharsSubmitted"] == "4"


def test_distinct_partner_counts(db: Session) -> None:
    review_session = _session(db, code="dist")
    reviewer_a = _reviewer(db, review_session, name="Ann", email="ann@x.edu")
    reviewer_b = _reviewer(db, review_session, name="Bob", email="bob@x.edu")
    reviewee_x = _reviewee(db, review_session, name="Xan", identifier="xan@x")
    reviewee_y = _reviewee(db, review_session, name="Yas", identifier="yas@x")
    instrument = _instrument(db, review_session)
    long_text = _rtd(db, review_session, "Long_text")
    fld = _field(db, instrument, long_text, field_key="c")

    for reviewer in (reviewer_a, reviewer_b):
        for reviewee in (reviewee_x, reviewee_y):
            assignment = _assignment(
                db,
                review_session,
                reviewer=reviewer,
                reviewee=reviewee,
                instrument=instrument,
            )
            _response(
                db,
                assignment=assignment,
                field=fld,
                value="ok",
                submitted=True,
            )

    reviewer_rows, reviewee_rows = build_entity_stats(db, review_session)
    ann = _row(reviewer_rows, REVIEWER_STATS_HEADER, "Ann")
    xan = _row(reviewee_rows, REVIEWEE_STATS_HEADER, "Xan")
    assert ann["RevieweesReviewedSubmitted"] == "2"
    assert xan["ReviewersSubmitted"] == "2"


def test_group_scoped_fan_out_deduped_on_reviewer_side(
    db: Session,
) -> None:
    """A group-scoped answer is fanned across member assignments;
    the reviewer's field / char metrics count it once per group,
    while both member reviewees are still credited."""
    review_session = _session(db, code="grp")
    reviewer = _reviewer(db, review_session, name="Rita", email="rita@x.edu")
    # Two reviewees sharing tag_1 form one group.
    member_1 = _reviewee(
        db, review_session, name="M1", identifier="m1@x", tag_1="TeamA"
    )
    member_2 = _reviewee(
        db, review_session, name="M2", identifier="m2@x", tag_1="TeamA"
    )
    instrument = _instrument(db, review_session, group_kind="r1")
    long_text = _rtd(db, review_session, "Long_text")
    fld = _field(db, instrument, long_text, field_key="grpfield")
    # The group answer is fanned: an identical Response on each
    # member assignment.
    for reviewee in (member_1, member_2):
        assignment = _assignment(
            db,
            review_session,
            reviewer=reviewer,
            reviewee=reviewee,
            instrument=instrument,
        )
        _response(
            db,
            assignment=assignment,
            field=fld,
            value="great",
            submitted=True,
        )

    reviewer_rows, reviewee_rows = build_entity_stats(db, review_session)
    rita = _row(reviewer_rows, REVIEWER_STATS_HEADER, "Rita")
    # Field / char metrics count the group answer once.
    assert rita["FieldsAnsweredSubmitted"] == "1"
    assert rita["StringResponseCharsSubmitted"] == "5"
    # Both members are still credited as reviewed.
    assert rita["RevieweesReviewedSubmitted"] == "2"
    # Each member reviewee carries its own copy.
    m1 = _row(reviewee_rows, REVIEWEE_STATS_HEADER, "M1")
    assert m1["FieldsAnsweredSubmitted"] == "1"
    assert m1["StringResponseCharsSubmitted"] == "5"
