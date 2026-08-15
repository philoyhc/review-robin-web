"""18P PR F — the responses importer.

Round-trips the analysis-format ``responses.csv`` back into a
reconstructed session: ``serialize_responses`` → ``parse_responses_csv``
→ ``load_responses``. Covers per-reviewee fidelity, assignment backfill,
and group-scoped fan-out. Uses re-serialize equality for the fidelity
check so the timestamp round-trip is asserted without tz-representation
flakiness.
"""

from __future__ import annotations

import csv
import datetime as dt
import io

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
    User,
)
from app.services.extracts.responses_extract import serialize_responses
from app.services.extracts.responses_import import (
    ResponsesFormatError,
    load_responses,
    parse_responses_csv,
)

_INLINE = dict(
    _inline_data_type="Integer",
    _inline_response_type="Likert5",
    _inline_min=1.0,
    _inline_max=5.0,
    _inline_step=1.0,
)


def _build(db: Session, code: str, *, group: bool = False) -> tuple:
    user = User(email=f"op-{code}@e.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name=code, code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    instrument = Instrument(
        session_id=review_session.id,
        name="Inst",
        short_label="INST",
        order=1,
        group_kind="r1" if group else None,
    )
    db.add(instrument)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="q1",
        label="Q1",
        order=1,
        help_text="Help",
        visible=True,
        **_INLINE,
    )
    db.add(field)
    db.flush()
    return review_session, instrument, field


def _reviewer(db, rs, email, name="R"):
    r = Reviewer(session_id=rs.id, name=name, email=email)
    db.add(r)
    db.flush()
    return r


def _reviewee(db, rs, ident, name, tag_1=None):
    e = Reviewee(
        session_id=rs.id, name=name, email_or_identifier=ident, tag_1=tag_1
    )
    db.add(e)
    db.flush()
    return e


def _assignment(db, rs, reviewer, reviewee, instrument):
    a = Assignment(
        session_id=rs.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
        is_self_review=(
            reviewer.email.lower() == reviewee.email_or_identifier.lower()
        ),
    )
    db.add(a)
    db.flush()
    return a


def _response(db, assignment, field, value, *, submitted=True, version=1):
    saved = dt.datetime(2026, 6, 1, 9, 0, tzinfo=dt.timezone.utc)
    r = Response(
        assignment_id=assignment.id,
        response_field_id=field.id,
        value=value,
        saved_at=saved,
        submitted_at=(
            dt.datetime(2026, 6, 1, 10, 0, tzinfo=dt.timezone.utc)
            if submitted
            else None
        ),
        version=version,
    )
    db.add(r)
    db.flush()
    return r


def _csv_bytes(rows) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _data_rows(rows) -> list[tuple]:
    """The data table (drop preamble + blank + header)."""
    from app.services.extracts.responses_extract import HEADER

    out, seen = [], False
    for r in rows:
        if not seen:
            if tuple(r) == HEADER:
                seen = True
            continue
        if r:
            out.append(tuple(r))
    return sorted(out)


# --------------------------------------------------------------------------- #
# Parse
# --------------------------------------------------------------------------- #


def test_parse_reads_data_rows_and_flavour(db: Session) -> None:
    src, inst, field = _build(db, "parse-src")
    rvr = _reviewer(db, src, "r@e.edu")
    rve = _reviewee(db, src, "e@e.edu", "E")
    a = _assignment(db, src, rvr, rve, inst)
    _response(db, a, field, "4")

    rows = list(serialize_responses(db, src))
    parsed = parse_responses_csv(_csv_bytes(rows))
    assert len(parsed) == 1
    assert parsed[0].reviewer_email == "r@e.edu"
    assert parsed[0].reviewee_email == "e@e.edu"
    assert parsed[0].field_key == "q1"
    assert parsed[0].value == "4"
    assert parsed[0].flavour == "per-reviewee"


def test_parse_rejects_headerless_file(db: Session) -> None:
    bad = _csv_bytes([("not", "a", "responses", "file")])
    try:
        parse_responses_csv(bad)
    except ResponsesFormatError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ResponsesFormatError")


# --------------------------------------------------------------------------- #
# Per-reviewee round-trip + backfill
# --------------------------------------------------------------------------- #


def test_per_reviewee_round_trip_reserializes_identically(
    db: Session,
) -> None:
    src, s_inst, s_field = _build(db, "rt-src")
    rvr = _reviewer(db, src, "r@e.edu")
    a1 = _assignment(db, src, rvr, _reviewee(db, src, "a@e.edu", "A"), s_inst)
    a2 = _assignment(db, src, rvr, _reviewee(db, src, "b@e.edu", "B"), s_inst)
    _response(db, a1, s_field, "3", submitted=True, version=2)
    _response(db, a2, s_field, "5", submitted=False, version=1)
    src_rows = _data_rows(list(serialize_responses(db, src)))

    # Target with matching rosters + instrument + assignments, no responses.
    dst, d_inst, _ = _build(db, "rt-dst")
    d_rvr = _reviewer(db, dst, "r@e.edu")
    _assignment(db, dst, d_rvr, _reviewee(db, dst, "a@e.edu", "A"), d_inst)
    _assignment(db, dst, d_rvr, _reviewee(db, dst, "b@e.edu", "B"), d_inst)

    parsed = parse_responses_csv(_csv_bytes(list(serialize_responses(db, src))))
    result = load_responses(db, review_session=dst, rows=parsed)
    assert result.warnings == []
    assert result.responses == 2

    # The rebuilt session re-serializes to the same data table.
    assert _data_rows(list(serialize_responses(db, dst))) == src_rows


def test_per_reviewee_backfills_missing_assignment(db: Session) -> None:
    src, s_inst, s_field = _build(db, "bf-src")
    rvr = _reviewer(db, src, "r@e.edu")
    a1 = _assignment(db, src, rvr, _reviewee(db, src, "a@e.edu", "A"), s_inst)
    a2 = _assignment(db, src, rvr, _reviewee(db, src, "b@e.edu", "B"), s_inst)
    _response(db, a1, s_field, "3")
    _response(db, a2, s_field, "4")

    # Target is missing the (r, b) assignment → the importer backfills it.
    dst, d_inst, _ = _build(db, "bf-dst")
    d_rvr = _reviewer(db, dst, "r@e.edu")
    _assignment(db, dst, d_rvr, _reviewee(db, dst, "a@e.edu", "A"), d_inst)
    _reviewee(db, dst, "b@e.edu", "B")  # roster present, assignment absent

    parsed = parse_responses_csv(_csv_bytes(list(serialize_responses(db, src))))
    result = load_responses(db, review_session=dst, rows=parsed)
    assert result.assignments_created == 1
    assert result.responses == 2
    dst_responses = db.execute(
        select(Response)
        .join(Assignment)
        .where(Assignment.session_id == dst.id)
    ).scalars().all()
    assert len(dst_responses) == 2


# --------------------------------------------------------------------------- #
# Group-scoped fan-out
# --------------------------------------------------------------------------- #


def test_group_scoped_row_fans_out_to_members(db: Session) -> None:
    # Source: reviewer R reviews a Team-A group (Carol, Eve) + Team B (Dan);
    # the save-time fan-out means every member assignment carries the value.
    src, s_inst, s_field = _build(db, "grp-src", group=True)
    rvr = _reviewer(db, src, "r@e.edu")
    carol = _reviewee(db, src, "carol@e.edu", "Carol", tag_1="Team A")
    eve = _reviewee(db, src, "eve@e.edu", "Eve", tag_1="Team A")
    dan = _reviewee(db, src, "dan@e.edu", "Dan", tag_1="Team B")
    for member in (carol, eve, dan):
        a = _assignment(db, src, rvr, member, s_inst)
        _response(db, a, s_field, "4")
    # Export collapses the 3 member rows → 2 group rows.
    src_rows = _data_rows(list(serialize_responses(db, src)))
    assert len(src_rows) == 2

    # Target with the same structure + regenerated member assignments,
    # no responses.
    dst, d_inst, _ = _build(db, "grp-dst", group=True)
    d_rvr = _reviewer(db, dst, "r@e.edu")
    for ident, name, tag in (
        ("carol@e.edu", "Carol", "Team A"),
        ("eve@e.edu", "Eve", "Team A"),
        ("dan@e.edu", "Dan", "Team B"),
    ):
        _assignment(db, dst, d_rvr, _reviewee(db, dst, ident, name, tag), d_inst)

    parsed = parse_responses_csv(_csv_bytes(list(serialize_responses(db, src))))
    result = load_responses(db, review_session=dst, rows=parsed)
    assert result.warnings == []
    # The 2 group rows fan back out to 3 member Response rows.
    assert result.responses == 3
    # And the rebuilt session re-serializes to the same 2 collapsed rows.
    assert _data_rows(list(serialize_responses(db, dst))) == src_rows
