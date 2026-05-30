"""Unit tests for
``app.services.extracts.entity_metadata_extract`` — covers the
Reviewer / Reviewee response metadata extracts that back the
Extract data tab's two metadata cards.

Pinned behaviours:

* Header shape switches on the chip selection (no instruments ⇒
  base totals only; N instruments ⇒ totals + per-(instrument,
  field) blocks).
* Per-block column footprint differs by data type — numeric
  fields ship ``.Assigned/.Count/.Mean/.Median/.Min/.Max``;
  string fields ship ``.Assigned/.Count/.Length``; other types
  ship ``.Assigned/.Count``.
* ``all_*`` False filters body rows to entities with at least one
  non-empty response in scope.
* Group-scoped instruments fan responses across every member
  assignment; both Assigned and Count count the member rows so
  denominators stay aligned.
"""

from __future__ import annotations

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
from app.services import assignments as assignments_service
from app.services.extracts.entity_metadata_extract import (
    build_reviewee_metadata,
    build_reviewer_metadata,
    compute_self_review_data_state,
    self_review_handling_filename_suffix,
)


# --------------------------------------------------------------------------- #
# Fixtures (lifted from test_entity_stats_extract for shape parity).
# --------------------------------------------------------------------------- #


_LONG_TEXT = {
    "_inline_data_type": "String",
    "_inline_response_type": "Long_text",
    "_inline_min": 0.0,
    "_inline_max": 2000.0,
}
_NUMERIC = {
    "_inline_data_type": "Integer",
    "_inline_response_type": "100int",
    "_inline_min": 0.0,
    "_inline_max": 100.0,
    "_inline_step": 1.0,
}


def _session(db: Session, *, code: str = "meta") -> ReviewSession:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Meta",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session


def _reviewer(
    db: Session, review_session: ReviewSession, *, name: str, email: str
) -> Reviewer:
    r = Reviewer(session_id=review_session.id, name=name, email=email)
    db.add(r)
    db.flush()
    return r


def _reviewee(
    db: Session, review_session: ReviewSession, *, name: str, identifier: str
) -> Reviewee:
    e = Reviewee(
        session_id=review_session.id, name=name, email_or_identifier=identifier
    )
    db.add(e)
    db.flush()
    return e


def _instrument(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str = "Form",
    short_label: str | None = None,
    order: int = 0,
    group_kind: str | None = None,
) -> Instrument:
    i = Instrument(
        session_id=review_session.id,
        name=name,
        short_label=short_label,
        order=order,
        group_kind=group_kind,
    )
    db.add(i)
    db.flush()
    return i


def _reviewee_with_tag(
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


def _field(
    db: Session,
    instrument: Instrument,
    spec: dict[str, object],
    *,
    field_key: str,
    label: str | None = None,
    order: int = 0,
) -> InstrumentResponseField:
    f = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=field_key,
        label=label or field_key.title(),
        required=False,
        order=order,
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
    value: str | None,
) -> Response:
    resp = Response(
        assignment_id=assignment.id,
        response_field_id=field.id,
        value=value,
    )
    db.add(resp)
    db.flush()
    return resp


def _row_by_name(
    rows: list[tuple[str, ...]], header: tuple[str, ...], name: str
) -> dict[str, str]:
    for row in rows[1:]:
        if row[0] == name:
            return dict(zip(header, row))
    raise AssertionError(f"no row named {name!r}")


# --------------------------------------------------------------------------- #
# Header / scope
# --------------------------------------------------------------------------- #


def test_no_instruments_selected_ships_base_header_only(db: Session) -> None:
    review_session = _session(db, code="no-instr")
    _reviewer(db, review_session, name="Rita", email="rita@x.edu")

    rows = build_reviewer_metadata(
        db, review_session, instrument_ids=None, all_reviewers=True
    )
    assert rows[0] == (
        "ReviewerName",
        "ReviewerEmail",
        "Assigned_self",
        "Count_self",
    )


def test_selected_numeric_field_ships_mean_median_min_max(
    db: Session,
) -> None:
    review_session = _session(db, code="num")
    instrument = _instrument(
        db, review_session, short_label="Peer", order=0
    )
    _field(db, instrument, _NUMERIC, field_key="score", label="Score")

    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids={instrument.id},
        all_reviewers=True,
    )
    header = rows[0]
    expected_tail = (
        "#1: Peer.Score.Assigned_self",
        "#1: Peer.Score.Count_self",
        "#1: Peer.Score.Mean_self",
        "#1: Peer.Score.Median_self",
        "#1: Peer.Score.Min_self",
        "#1: Peer.Score.Max_self",
    )
    assert header[4:] == expected_tail


def test_selected_string_field_ships_length(db: Session) -> None:
    review_session = _session(db, code="str")
    instrument = _instrument(
        db, review_session, short_label="Peer", order=0
    )
    _field(db, instrument, _LONG_TEXT, field_key="notes", label="Notes")

    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids={instrument.id},
        all_reviewers=True,
    )
    assert rows[0][4:] == (
        "#1: Peer.Notes.Assigned_self",
        "#1: Peer.Notes.Count_self",
        "#1: Peer.Notes.Length_self",
    )


def test_blank_short_label_falls_back_to_positional(db: Session) -> None:
    review_session = _session(db, code="fb")
    instrument = _instrument(db, review_session, short_label=None, order=0)
    _field(db, instrument, _NUMERIC, field_key="score", label="Score")

    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids={instrument.id},
        all_reviewers=True,
    )
    assert rows[0][4].startswith("#1: Instrument_1.Score")


def test_instrument_positions_follow_session_order_not_selection(
    db: Session,
) -> None:
    """When the operator deselects instrument #1 and keeps #2,
    the per-field block prefix on #2 is still ``#2:`` — numbering
    follows the session position, not the selection rank."""
    review_session = _session(db, code="pos")
    first = _instrument(db, review_session, short_label="First", order=0)
    second = _instrument(db, review_session, short_label="Second", order=1)
    _field(db, first, _NUMERIC, field_key="a", label="A")
    _field(db, second, _NUMERIC, field_key="b", label="B")

    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids={second.id},
        all_reviewers=True,
    )
    assert rows[0][4].startswith("#2: Second.B.")


# --------------------------------------------------------------------------- #
# Body rows
# --------------------------------------------------------------------------- #


def test_assigned_counts_reviewee_times_fields(db: Session) -> None:
    """Top-level Assigned = sum over assignments of
    (# fields on that assignment's instrument). With one reviewer
    × two reviewees × one instrument × two fields, Assigned = 4."""
    review_session = _session(db, code="asn")
    reviewer = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    eli = _reviewee(db, review_session, name="Eli", identifier="eli@x")
    ann = _reviewee(db, review_session, name="Ann", identifier="ann@x")
    instrument = _instrument(db, review_session, short_label="P", order=0)
    _field(db, instrument, _NUMERIC, field_key="s", label="S")
    _field(db, instrument, _LONG_TEXT, field_key="n", label="N", order=1)
    _assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=eli,
        instrument=instrument,
    )
    _assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=ann,
        instrument=instrument,
    )

    rows = build_reviewer_metadata(
        db, review_session, instrument_ids=None, all_reviewers=True
    )
    rita = _row_by_name(rows, rows[0], "Rita")
    assert rita["Assigned_self"] == "4"
    assert rita["Count_self"] == "0"


def test_count_includes_non_empty_responses_only(db: Session) -> None:
    review_session = _session(db, code="cnt")
    reviewer = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    eli = _reviewee(db, review_session, name="Eli", identifier="eli@x")
    instrument = _instrument(db, review_session, short_label="P", order=0)
    f_a = _field(db, instrument, _NUMERIC, field_key="a", label="A")
    f_b = _field(
        db, instrument, _LONG_TEXT, field_key="b", label="B", order=1
    )
    assignment = _assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=eli,
        instrument=instrument,
    )
    _response(db, assignment=assignment, field=f_a, value="80")
    _response(db, assignment=assignment, field=f_b, value="")  # blank

    rows = build_reviewer_metadata(
        db, review_session, instrument_ids=None, all_reviewers=True
    )
    rita = _row_by_name(rows, rows[0], "Rita")
    assert rita["Count_self"] == "1"
    assert rita["Assigned_self"] == "2"


def test_numeric_aggregates_compute_from_values(db: Session) -> None:
    review_session = _session(db, code="agg")
    reviewer = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    instrument = _instrument(db, review_session, short_label="P", order=0)
    f = _field(db, instrument, _NUMERIC, field_key="s", label="S")
    for value in ("10", "20", "40"):
        reviewee = _reviewee(
            db, review_session, name=value, identifier=f"r{value}@x"
        )
        assignment = _assignment(
            db,
            review_session,
            reviewer=reviewer,
            reviewee=reviewee,
            instrument=instrument,
        )
        _response(db, assignment=assignment, field=f, value=value)

    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids={instrument.id},
        all_reviewers=True,
    )
    rita = _row_by_name(rows, rows[0], "Rita")
    # mean(10,20,40)=23.333…, median=20, min=10, max=40.
    assert rita["#1: P.S.Mean_self"].startswith("23.33")
    assert rita["#1: P.S.Median_self"] == "20"
    assert rita["#1: P.S.Min_self"] == "10"
    assert rita["#1: P.S.Max_self"] == "40"
    assert rita["#1: P.S.Count_self"] == "3"
    assert rita["#1: P.S.Assigned_self"] == "3"


def test_string_length_sums_chars(db: Session) -> None:
    review_session = _session(db, code="len")
    reviewer = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    instrument = _instrument(db, review_session, short_label="P", order=0)
    f = _field(db, instrument, _LONG_TEXT, field_key="n", label="N")
    for chars in ("hi", "world!"):
        reviewee = _reviewee(
            db, review_session, name=chars, identifier=f"{chars}@x"
        )
        assignment = _assignment(
            db,
            review_session,
            reviewer=reviewer,
            reviewee=reviewee,
            instrument=instrument,
        )
        _response(db, assignment=assignment, field=f, value=chars)

    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids={instrument.id},
        all_reviewers=True,
    )
    rita = _row_by_name(rows, rows[0], "Rita")
    assert rita["#1: P.N.Length_self"] == "8"
    assert rita["#1: P.N.Count_self"] == "2"


def test_all_reviewers_false_drops_zero_response_rows(db: Session) -> None:
    review_session = _session(db, code="all-off")
    rita = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    sam = _reviewer(db, review_session, name="Sam", email="s@x.edu")
    eli = _reviewee(db, review_session, name="Eli", identifier="e@x")
    instrument = _instrument(db, review_session, short_label="P", order=0)
    f = _field(db, instrument, _NUMERIC, field_key="s", label="S")
    a_rita = _assignment(
        db,
        review_session,
        reviewer=rita,
        reviewee=eli,
        instrument=instrument,
    )
    _assignment(
        db,
        review_session,
        reviewer=sam,
        reviewee=eli,
        instrument=instrument,
    )
    _response(db, assignment=a_rita, field=f, value="80")

    rows_all = build_reviewer_metadata(
        db, review_session, instrument_ids=None, all_reviewers=True
    )
    assert {row[0] for row in rows_all[1:]} == {"Rita", "Sam"}

    rows_active = build_reviewer_metadata(
        db, review_session, instrument_ids=None, all_reviewers=False
    )
    assert {row[0] for row in rows_active[1:]} == {"Rita"}


def test_reviewee_side_mirrors_reviewer_shape(db: Session) -> None:
    review_session = _session(db, code="ree")
    rita = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    eli = _reviewee(db, review_session, name="Eli", identifier="e@x")
    instrument = _instrument(db, review_session, short_label="P", order=0)
    f = _field(db, instrument, _NUMERIC, field_key="s", label="S")
    assignment = _assignment(
        db,
        review_session,
        reviewer=rita,
        reviewee=eli,
        instrument=instrument,
    )
    _response(db, assignment=assignment, field=f, value="50")

    rows = build_reviewee_metadata(
        db,
        review_session,
        instrument_ids={instrument.id},
        all_reviewees=True,
    )
    assert rows[0][:4] == (
        "RevieweeName",
        "RevieweeEmail",
        "Assigned_self",
        "Count_self",
    )
    eli_row = _row_by_name(rows, rows[0], "Eli")
    assert eli_row["Assigned_self"] == "1"
    assert eli_row["Count_self"] == "1"
    assert eli_row["#1: P.S.Mean_self"] == "50"


# --------------------------------------------------------------------------- #
# Multi-instrument scoping
# --------------------------------------------------------------------------- #


def test_selected_instrument_filter_scopes_totals(db: Session) -> None:
    """Picking instrument #1 means the Assigned / Count totals
    reflect only #1's data — not the unselected #2."""
    review_session = _session(db, code="scope")
    reviewer = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    reviewee = _reviewee(db, review_session, name="Eli", identifier="e@x")

    first = _instrument(db, review_session, short_label="First", order=0)
    _field(db, first, _NUMERIC, field_key="a", label="A")
    _assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=first,
    )

    second = _instrument(db, review_session, short_label="Second", order=1)
    _field(db, second, _NUMERIC, field_key="b", label="B")
    _assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=second,
    )

    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids={first.id},
        all_reviewers=True,
    )
    rita = _row_by_name(rows, rows[0], "Rita")
    # ``Assigned`` totals only the first instrument's slot
    # because that's the only instrument in scope.
    assert rita["Assigned_self"] == "1"
    # And the per-field block belongs to ``#1: First`` exclusively.
    assert "#1: First.A.Assigned_self" in rows[0]
    assert "#2: Second.B.Assigned_self" not in rows[0]


def test_group_scoped_reviewer_dedupes_by_group(db: Session) -> None:
    """Rob reviews 3 groups on a group-scoped instrument with 2
    fields, plus 3 reviewees on an individual instrument with 2
    fields. Each group has 2 members, so the group-scoped
    instrument carries 6 member-assignments for Rob — but
    ``Assigned`` counts each (Rob, group) once, giving
    ``3 × 2 + 3 × 2 = 12`` on the reviewer side, not the
    inflated ``6 × 2 + 3 × 2 = 18``."""
    review_session = _session(db, code="rob")
    rob = _reviewer(db, review_session, name="Rob", email="rob@x.edu")

    # Individual instrument: 3 reviewees, 2 fields, no fan-out.
    individual = _instrument(
        db, review_session, short_label="I", order=0
    )
    _field(db, individual, _NUMERIC, field_key="a", label="A")
    _field(db, individual, _NUMERIC, field_key="b", label="B", order=1)
    for n in range(3):
        ree = _reviewee(
            db, review_session, name=f"Ind{n}", identifier=f"i{n}@x"
        )
        _assignment(
            db,
            review_session,
            reviewer=rob,
            reviewee=ree,
            instrument=individual,
        )

    # Group instrument: 3 groups (Team A / Team B / Team C),
    # 2 members each, 2 fields. Fan-out gives Rob 6
    # member-assignments here.
    group = _instrument(
        db, review_session, short_label="G", order=1, group_kind="r1"
    )
    _field(db, group, _NUMERIC, field_key="x", label="X")
    _field(db, group, _NUMERIC, field_key="y", label="Y", order=1)
    for team in ("A", "B", "C"):
        for slot in (1, 2):
            ree = _reviewee_with_tag(
                db,
                review_session,
                name=f"{team}{slot}",
                identifier=f"{team.lower()}{slot}@x",
                tag_1=f"Team{team}",
            )
            _assignment(
                db,
                review_session,
                reviewer=rob,
                reviewee=ree,
                instrument=group,
            )

    rows = build_reviewer_metadata(
        db, review_session, instrument_ids=None, all_reviewers=True
    )
    rob_row = _row_by_name(rows, rows[0], "Rob")
    assert rob_row["Assigned_self"] == "12"


def test_group_scoped_reviewer_count_dedupes_too(db: Session) -> None:
    """The same dedupe applies to ``Count`` and the per-field
    aggregate rollups: a single group answer counts once per
    (reviewer, group, field), no matter how many members
    received the fan-out."""
    review_session = _session(db, code="rob-count")
    rob = _reviewer(db, review_session, name="Rob", email="rob@x.edu")
    group = _instrument(
        db, review_session, short_label="G", order=0, group_kind="r1"
    )
    fld = _field(db, group, _NUMERIC, field_key="x", label="X")
    # One group, 3 members; Rob's group answer is "50" — fanned
    # to all 3 member-assignments.
    for slot in (1, 2, 3):
        ree = _reviewee_with_tag(
            db,
            review_session,
            name=f"A{slot}",
            identifier=f"a{slot}@x",
            tag_1="TeamA",
        )
        assignment = _assignment(
            db,
            review_session,
            reviewer=rob,
            reviewee=ree,
            instrument=group,
        )
        _response(db, assignment=assignment, field=fld, value="50")

    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids={group.id},
        all_reviewers=True,
    )
    rob_row = _row_by_name(rows, rows[0], "Rob")
    assert rob_row["Assigned_self"] == "1"
    assert rob_row["Count_self"] == "1"
    # Mean / Min / Max all see the answer once, not three times.
    assert rob_row["#1: G.X.Count_self"] == "1"
    assert rob_row["#1: G.X.Mean_self"] == "50"


def test_group_scoped_reviewee_does_not_dedupe(db: Session) -> None:
    """Eli's group is reviewed by 3 reviewers on a group-scoped
    instrument with 2 fields, plus Eli is reviewed individually
    by 3 reviewers on an individual instrument with 2 fields.
    Eli's ``Assigned`` = 3 × 2 (individual) + 3 × 2 (group) =
    12 — no group dedupe on the reviewee side because from
    Eli's perspective each (reviewer, field) cell exists
    independently."""
    review_session = _session(db, code="eli")
    eli = _reviewee_with_tag(
        db,
        review_session,
        name="Eli",
        identifier="eli@x",
        tag_1="TeamE",
    )
    # Two other group members so the group has 3 members total.
    for slot in (2, 3):
        _reviewee_with_tag(
            db,
            review_session,
            name=f"Eli{slot}",
            identifier=f"eli{slot}@x",
            tag_1="TeamE",
        )

    individual = _instrument(
        db, review_session, short_label="I", order=0
    )
    _field(db, individual, _NUMERIC, field_key="a", label="A")
    _field(db, individual, _NUMERIC, field_key="b", label="B", order=1)
    group = _instrument(
        db, review_session, short_label="G", order=1, group_kind="r1"
    )
    _field(db, group, _NUMERIC, field_key="x", label="X")
    _field(db, group, _NUMERIC, field_key="y", label="Y", order=1)

    for n in range(3):
        reviewer = _reviewer(
            db, review_session, name=f"R{n}", email=f"r{n}@x.edu"
        )
        _assignment(
            db,
            review_session,
            reviewer=reviewer,
            reviewee=eli,
            instrument=individual,
        )
        # Group fan-out: each reviewer reviews each member of the
        # group, so Eli gets one Assignment row per reviewer on
        # the group instrument too.
        for member in db.execute(
            select(Reviewee).where(
                Reviewee.session_id == review_session.id,
                Reviewee.tag_1 == "TeamE",
            )
        ).scalars():
            _assignment(
                db,
                review_session,
                reviewer=reviewer,
                reviewee=member,
                instrument=group,
            )

    rows = build_reviewee_metadata(
        db, review_session, instrument_ids=None, all_reviewees=True
    )
    eli_row = _row_by_name(rows, rows[0], "Eli")
    assert eli_row["Assigned_self"] == "12"


def test_no_instrument_filter_scans_every_instrument(db: Session) -> None:
    """``instrument_ids is None`` means the cross-instrument
    totals scan every session instrument, even though no
    per-(instrument, field) blocks ship."""
    review_session = _session(db, code="all-instr")
    reviewer = _reviewer(db, review_session, name="Rita", email="r@x.edu")
    reviewee = _reviewee(db, review_session, name="Eli", identifier="e@x")

    first = _instrument(db, review_session, short_label="First", order=0)
    _field(db, first, _NUMERIC, field_key="a", label="A")
    _assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=first,
    )
    second = _instrument(db, review_session, short_label="Second", order=1)
    _field(db, second, _NUMERIC, field_key="b", label="B")
    _assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=second,
    )

    rows = build_reviewer_metadata(
        db, review_session, instrument_ids=None, all_reviewers=True
    )
    rita = _row_by_name(rows, rows[0], "Rita")
    # 2 assignments × 1 field each = 2 Assigned slots.
    assert rita["Assigned_self"] == "2"
    assert rows[0] == (
        "ReviewerName",
        "ReviewerEmail",
        "Assigned_self",
        "Count_self",
    )


# --------------------------------------------------------------------------- #
# Self-review handling chip — PR A
# --------------------------------------------------------------------------- #


def _seed_self_review_session(
    db: Session, *, code: str
) -> tuple[ReviewSession, Reviewer, Reviewee, Reviewee, Instrument, InstrumentResponseField]:
    """Seed a session with one (Alice→Alice) self-review and one
    (Alice→Bob) non-self pair on a single-field instrument. The
    recompute hook fires to populate ``Assignment.is_self_review``
    per the PR 2 (write paths) of the self-review consolidation
    slice."""
    review_session = _session(db, code=code)
    alice_r = _reviewer(
        db, review_session, name="Alice", email="alice@example.edu"
    )
    alice_e = _reviewee(
        db,
        review_session,
        name="Alice",
        identifier="alice@example.edu",
    )
    bob_e = _reviewee(
        db, review_session, name="Bob", identifier="bob@example.edu"
    )
    instrument = _instrument(
        db, review_session, short_label="Peer", order=0
    )
    field = _field(db, instrument, _NUMERIC, field_key="score", label="Score")
    a_self = _assignment(
        db,
        review_session,
        reviewer=alice_r,
        reviewee=alice_e,
        instrument=instrument,
    )
    a_other = _assignment(
        db,
        review_session,
        reviewer=alice_r,
        reviewee=bob_e,
        instrument=instrument,
    )
    _response(db, assignment=a_self, field=field, value="50")
    _response(db, assignment=a_other, field=field, value="80")
    assignments_service.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    return review_session, alice_r, alice_e, bob_e, instrument, field


def test_filename_suffix_maps_each_state_to_canonical_token() -> None:
    """``include_self`` → ``_self``; ``exclude_self`` → ``_noself``;
    ``both`` → ``_both``. The two non-default tokens drive the
    downstream-consumer's pool identification."""
    assert self_review_handling_filename_suffix("include_self") == "_self"
    assert self_review_handling_filename_suffix("exclude_self") == "_noself"
    assert self_review_handling_filename_suffix("both") == "_both"
    # Unknown state falls back to ``_self`` (the default).
    assert self_review_handling_filename_suffix("garbage") == "_self"


def test_include_self_state_carries_self_suffix_and_includes_pair(
    db: Session,
) -> None:
    """Default ``include_self`` state folds every ``include=True``
    row in (including the self-review pair). Header columns carry
    the ``_self`` suffix per the always-emit-suffix rule."""
    review_session, alice_r, _, _, instrument, _ = _seed_self_review_session(
        db, code="srh-include"
    )
    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids={instrument.id},
        all_reviewers=True,
        self_review_handling="include_self",
    )
    header = rows[0]
    assert "Assigned_self" in header
    assert "Count_self" in header
    assert "Assigned_noself" not in header
    # Alice's row counts both her self-review and her review of Bob.
    alice = _row_by_name(rows, header, "Alice")
    assert alice["Assigned_self"] == "2"
    assert alice["Count_self"] == "2"


def test_exclude_self_state_drops_self_review_pairs(db: Session) -> None:
    """``exclude_self`` state filters ``WHERE NOT is_self_review``
    so Alice's self-review pair drops from her aggregates. Headers
    carry the ``_noself`` suffix."""
    review_session, _, _, _, instrument, _ = _seed_self_review_session(
        db, code="srh-exclude"
    )
    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids={instrument.id},
        all_reviewers=True,
        self_review_handling="exclude_self",
    )
    header = rows[0]
    assert "Assigned_noself" in header
    assert "Count_noself" in header
    assert "Assigned_self" not in header
    alice = _row_by_name(rows, header, "Alice")
    # One non-self pair (Alice→Bob) survives.
    assert alice["Assigned_noself"] == "1"
    assert alice["Count_noself"] == "1"


def test_both_state_emits_self_and_noself_blocks_side_by_side(
    db: Session,
) -> None:
    """``both`` state runs two passes and concatenates the column
    blocks — ``_self`` first, ``_noself`` second — so a single CSV
    side-by-sides both views (Q1 / Q2 resolutions)."""
    review_session, _, _, _, instrument, _ = _seed_self_review_session(
        db, code="srh-both"
    )
    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids={instrument.id},
        all_reviewers=True,
        self_review_handling="both",
    )
    header = rows[0]
    # Both blocks present; the ``_self`` block precedes ``_noself``.
    assert "Assigned_self" in header
    assert "Assigned_noself" in header
    assert header.index("Assigned_self") < header.index("Assigned_noself")
    alice = _row_by_name(rows, header, "Alice")
    assert alice["Assigned_self"] == "2"
    assert alice["Assigned_noself"] == "1"
    assert alice["Count_self"] == "2"
    assert alice["Count_noself"] == "1"


def test_reviewee_metadata_honours_state_machine_too(db: Session) -> None:
    """The reviewee side mirrors the reviewer side — same three
    states, same suffixes, same filter."""
    review_session, _, _, _, instrument, _ = _seed_self_review_session(
        db, code="srh-ree"
    )
    rows = build_reviewee_metadata(
        db,
        review_session,
        instrument_ids={instrument.id},
        all_reviewees=True,
        self_review_handling="exclude_self",
    )
    header = rows[0]
    assert "Assigned_noself" in header
    assert "Count_noself" in header
    alice = _row_by_name(rows, header, "Alice")
    # Reviewee Alice's self-review row drops; she's left with no
    # rows about her under the exclude filter.
    assert alice["Assigned_noself"] == "0"
    assert alice["Count_noself"] == "0"
    bob = _row_by_name(rows, header, "Bob")
    assert bob["Assigned_noself"] == "1"
    assert bob["Count_noself"] == "1"


def test_compute_self_review_data_state_reports_both_pools(
    db: Session,
) -> None:
    """The server-side preflight tells the chip's lock UI which
    states are selectable. On a session with one self-review
    pair + one non-self pair, both pools are present."""
    review_session, _, _, _, instrument, _ = _seed_self_review_session(
        db, code="srh-preflight-both"
    )
    state = compute_self_review_data_state(
        db, session_id=review_session.id, instrument_ids={instrument.id}
    )
    assert state == {"has_self": True, "has_noself": True}


def test_compute_self_review_data_state_only_noself_when_no_self_pair(
    db: Session,
) -> None:
    """Session without any included self-review row → ``has_self``
    flips False so the chip can lock to ``exclude_self``."""
    review_session = _session(db, code="srh-preflight-noself")
    rita = _reviewer(
        db, review_session, name="Rita", email="rita@example.edu"
    )
    bob_e = _reviewee(
        db, review_session, name="Bob", identifier="bob@example.edu"
    )
    instrument = _instrument(db, review_session, short_label="P", order=0)
    _field(db, instrument, _NUMERIC, field_key="score", label="Score")
    _assignment(
        db, review_session,
        reviewer=rita, reviewee=bob_e, instrument=instrument,
    )
    assignments_service.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    state = compute_self_review_data_state(
        db, session_id=review_session.id, instrument_ids={instrument.id}
    )
    assert state == {"has_self": False, "has_noself": True}
