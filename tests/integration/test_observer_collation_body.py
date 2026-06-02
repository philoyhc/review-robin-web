"""Integration tests for the observer collation surface body
(`/me/sessions/{id}/collation`) and the per-instrument CSV
download (`.../collation/instruments/{instrument_id}.csv`).

Pins the W17 MVP: per-instrument 3-row tables (reviewer stats /
reviewee stats / conditional download), cohort filtering, and
the Anonymized → tokens behaviour on the CSV.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    InstrumentViewPolicy,
    Observer,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)


def _make_session(
    client: TestClient,
    db: Session,
    *,
    code: str,
    description: str = "",
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Cohort A", "code": code, "description": description},
        follow_redirects=False,
    )
    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    # Flip to ready so the ``while_ongoing_open`` window is
    # active — Band 3 ``while_ongoing_*`` slots then resolve.
    review_session.status = "ready"
    db.commit()
    return review_session


def _seed_one_instrument(
    db: Session,
    review_session: ReviewSession,
    *,
    while_ongoing_identification: str = "identified",
    while_ongoing_granularity: str = "row",
) -> dict:
    """One instrument + one Integer response field + one Band 3
    policy granting the observer audience access. Plus one
    reviewer, one reviewee, one assignment, one submitted
    response."""
    inst = Instrument(
        session_id=review_session.id, name="Instrument 1", order=0
    )
    db.add(inst)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=inst.id,
        field_key="rating",
        label="Rating",
        _inline_data_type="Integer",
        required=False,
        order=0,
    )
    db.add(field)
    db.add(
        InstrumentViewPolicy(
            instrument_id=inst.id,
            audience="observer",
            while_ongoing_granularity=while_ongoing_granularity,
            while_ongoing_identification=while_ongoing_identification,
        )
    )
    r = Reviewer(
        session_id=review_session.id,
        name="Rev",
        email="rev@x",
        tag_1="mathcohort",
    )
    e = Reviewee(
        session_id=review_session.id,
        name="Ree",
        email_or_identifier="ree@x",
        tag_1="mathcohort",
    )
    db.add_all([r, e])
    db.flush()
    a = Assignment(
        session_id=review_session.id,
        instrument_id=inst.id,
        reviewer_id=r.id,
        reviewee_id=e.id,
    )
    db.add(a)
    db.flush()
    db.add(
        Response(
            assignment_id=a.id,
            response_field_id=field.id,
            value="4",
            submitted_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return {
        "instrument": inst,
        "field": field,
        "reviewer": r,
        "reviewee": e,
        "assignment": a,
    }


def _add_observer(
    db: Session,
    review_session: ReviewSession,
    *,
    email: str,
    cohort_rule: dict | None = None,
    tag_1: str | None = None,
) -> Observer:
    obs = Observer(
        session_id=review_session.id,
        email=email,
        display_name="Alice",
        tag_1=tag_1,
        cohort_rule=cohort_rule,
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return obs


# ── Page body ─────────────────────────────────────────────────────────


def test_collation_shows_empty_cohort_message_when_no_rule(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="col-body-empty")
    _seed_one_instrument(db, review_session)
    _add_observer(db, review_session, email="alice@example.edu")

    body = client.get(
        f"/me/sessions/{review_session.id}/collation"
    ).text
    assert "No cohort is configured" in body


def test_collation_renders_per_instrument_table_with_two_stats_rows(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="col-body-two-rows")
    _seed_one_instrument(db, review_session)
    # Cohort rule matches the seeded reviewer + reviewee via
    # ``tag_1 = "mathcohort"``.
    _add_observer(
        db,
        review_session,
        email="alice@example.edu",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "mathcohort",
                }
            ],
        },
    )

    body = client.get(
        f"/me/sessions/{review_session.id}/collation"
    ).text
    assert "Reviewers in cohort" in body
    assert "Reviewees in cohort" in body
    # Field column header from the instrument.
    assert "Rating" in body
    # The cohort-rule-matched reviewer's rating fed the average.
    assert "Average: 4" in body
    # Download button rendered for the Raw-mode instrument.
    assert "Download CSV" in body


def test_collation_summarized_mode_omits_download_button(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client, db, code="col-body-summarized"
    )
    _seed_one_instrument(
        db,
        review_session,
        while_ongoing_granularity="aggregated",
        while_ongoing_identification="deidentified",
    )
    _add_observer(
        db,
        review_session,
        email="alice@example.edu",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "mathcohort",
                }
            ],
        },
    )

    body = client.get(
        f"/me/sessions/{review_session.id}/collation"
    ).text
    assert "Reviewers in cohort" in body
    assert "Download CSV" not in body
    assert "no row-level" in body


def test_collation_anonymized_mode_marks_download_label(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="col-body-anon")
    _seed_one_instrument(
        db,
        review_session,
        while_ongoing_granularity="row",
        while_ongoing_identification="deidentified",
    )
    _add_observer(
        db,
        review_session,
        email="alice@example.edu",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "mathcohort",
                }
            ],
        },
    )

    body = client.get(
        f"/me/sessions/{review_session.id}/collation"
    ).text
    assert "Download CSV" in body
    assert "(Anonymized)" in body


# ── CSV download ──────────────────────────────────────────────────────


def test_collation_csv_serves_raw_rows_for_cohort(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="col-csv-raw")
    seeded = _seed_one_instrument(db, review_session)
    _add_observer(
        db,
        review_session,
        email="alice@example.edu",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "mathcohort",
                }
            ],
        },
    )

    response = client.get(
        f"/me/sessions/{review_session.id}/collation/instruments/"
        f"{seeded['instrument'].id}.csv"
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    body = response.text
    # Raw mode keeps reviewer name + email.
    assert "Rev" in body
    assert "rev@x" in body
    # The submitted response value.
    assert ",4," in body or body.endswith(",4\n") or "4" in body


def test_collation_csv_anonymized_swaps_names_for_tokens(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="col-csv-anon")
    seeded = _seed_one_instrument(
        db,
        review_session,
        while_ongoing_granularity="row",
        while_ongoing_identification="deidentified",
    )
    _add_observer(
        db,
        review_session,
        email="alice@example.edu",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "mathcohort",
                }
            ],
        },
    )

    response = client.get(
        f"/me/sessions/{review_session.id}/collation/instruments/"
        f"{seeded['instrument'].id}.csv"
    )
    assert response.status_code == 200
    body = response.text
    # Anonymized strips the raw name + email.
    assert "rev@x" not in body
    # Per-session opaque tokens appear instead.
    assert "R-" in body
    assert "E-" in body


def test_collation_csv_summarized_returns_404(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client, db, code="col-csv-summarized"
    )
    seeded = _seed_one_instrument(
        db,
        review_session,
        while_ongoing_granularity="aggregated",
        while_ongoing_identification="deidentified",
    )
    _add_observer(
        db,
        review_session,
        email="alice@example.edu",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "mathcohort",
                }
            ],
        },
    )

    response = client.get(
        f"/me/sessions/{review_session.id}/collation/instruments/"
        f"{seeded['instrument'].id}.csv"
    )
    assert response.status_code == 404


def test_collation_csv_cohort_empty_returns_404(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="col-csv-no-cohort")
    seeded = _seed_one_instrument(db, review_session)
    _add_observer(
        db, review_session, email="alice@example.edu", cohort_rule=None
    )

    response = client.get(
        f"/me/sessions/{review_session.id}/collation/instruments/"
        f"{seeded['instrument'].id}.csv"
    )
    assert response.status_code == 404


def test_collation_csv_or_rule_per_row_either_side(
    client: TestClient, db: Session
) -> None:
    """A cross-side OR rule (``reviewer.tag1 = math`` OR
    ``reviewee.tag1 = junior``) must include rows where EITHER
    side matches, and only those. The set-based filter would
    have either passed every row (OR-with-fallback degenerates
    to ALL) or dropped both rules' valid cases (AND
    intersect)."""
    review_session = _make_session(client, db, code="col-csv-or")
    inst = Instrument(
        session_id=review_session.id, name="Instrument 1", order=0
    )
    db.add(inst)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=inst.id,
        field_key="rating",
        label="Rating",
        _inline_data_type="Integer",
        required=False,
        order=0,
    )
    db.add(field)
    db.add(
        InstrumentViewPolicy(
            instrument_id=inst.id,
            audience="observer",
            while_ongoing_granularity="row",
            while_ongoing_identification="identified",
        )
    )
    r_math = Reviewer(
        session_id=review_session.id,
        name="Math Rev",
        email="math@x",
        tag_1="math",
    )
    r_bio = Reviewer(
        session_id=review_session.id,
        name="Bio Rev",
        email="bio@x",
        tag_1="bio",
    )
    e_junior = Reviewee(
        session_id=review_session.id,
        name="Junior Ree",
        email_or_identifier="junior@x",
        tag_1="junior",
    )
    e_senior = Reviewee(
        session_id=review_session.id,
        name="Senior Ree",
        email_or_identifier="senior@x",
        tag_1="senior",
    )
    db.add_all([r_math, r_bio, e_junior, e_senior])
    db.flush()
    submitted = datetime.now(timezone.utc)
    # Pair 1: math + senior — matches reviewer-side rule only.
    a1 = Assignment(
        session_id=review_session.id,
        instrument_id=inst.id,
        reviewer_id=r_math.id,
        reviewee_id=e_senior.id,
    )
    # Pair 2: bio + junior — matches reviewee-side rule only.
    a2 = Assignment(
        session_id=review_session.id,
        instrument_id=inst.id,
        reviewer_id=r_bio.id,
        reviewee_id=e_junior.id,
    )
    # Pair 3: bio + senior — matches neither.
    a3 = Assignment(
        session_id=review_session.id,
        instrument_id=inst.id,
        reviewer_id=r_bio.id,
        reviewee_id=e_senior.id,
    )
    db.add_all([a1, a2, a3])
    db.flush()
    for assignment in (a1, a2, a3):
        db.add(
            Response(
                assignment_id=assignment.id,
                response_field_id=field.id,
                value="3",
                submitted_at=submitted,
            )
        )
    _add_observer(
        db,
        review_session,
        email="alice@example.edu",
        cohort_rule={
            "combinator": "OR",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "math",
                },
                {
                    "field": "reviewee.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "junior",
                },
            ],
        },
    )

    response = client.get(
        f"/me/sessions/{review_session.id}/collation/instruments/"
        f"{inst.id}.csv"
    )
    assert response.status_code == 200
    body = response.text
    # Pair 1 (Math + Senior) included via reviewer side.
    # Pair 2 (Bio + Junior) included via reviewee side.
    # Pair 3 (Bio + Senior) absent — neither rule passes.
    # Count reviewer / reviewee names: each appears once
    # because each is in exactly one of the included pairs.
    assert body.count("Math Rev") == 1
    assert body.count("Junior Ree") == 1
    assert body.count("Bio Rev") == 1
    assert body.count("Senior Ree") == 1


def test_collation_csv_excludes_rows_outside_cohort_rule(
    client: TestClient, db: Session
) -> None:
    """A single-side cohort rule (e.g. ``reviewer.tag1 IS
    mathcohort``) must drop assignments whose reviewer doesn't
    match — even though the materialiser's
    unconstrained-reviewee-side fallback includes every
    reviewee. Regression test for the OR → AND filter swap."""
    review_session = _make_session(client, db, code="col-csv-scope")
    inst = Instrument(
        session_id=review_session.id, name="Instrument 1", order=0
    )
    db.add(inst)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=inst.id,
        field_key="rating",
        label="Rating",
        _inline_data_type="Integer",
        required=False,
        order=0,
    )
    db.add(field)
    db.add(
        InstrumentViewPolicy(
            instrument_id=inst.id,
            audience="observer",
            while_ongoing_granularity="row",
            while_ongoing_identification="identified",
        )
    )
    # Two reviewers — only one matches the cohort rule.
    in_cohort = Reviewer(
        session_id=review_session.id,
        name="In Cohort",
        email="in@x",
        tag_1="mathcohort",
    )
    out_cohort = Reviewer(
        session_id=review_session.id,
        name="Out Of Cohort",
        email="out@x",
        tag_1="bio",
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Ree",
        email_or_identifier="ree@x",
    )
    db.add_all([in_cohort, out_cohort, reviewee])
    db.flush()
    a_in = Assignment(
        session_id=review_session.id,
        instrument_id=inst.id,
        reviewer_id=in_cohort.id,
        reviewee_id=reviewee.id,
    )
    a_out = Assignment(
        session_id=review_session.id,
        instrument_id=inst.id,
        reviewer_id=out_cohort.id,
        reviewee_id=reviewee.id,
    )
    db.add_all([a_in, a_out])
    db.flush()
    submitted = datetime.now(timezone.utc)
    db.add_all(
        [
            Response(
                assignment_id=a_in.id,
                response_field_id=field.id,
                value="4",
                submitted_at=submitted,
            ),
            Response(
                assignment_id=a_out.id,
                response_field_id=field.id,
                value="9",
                submitted_at=submitted,
            ),
        ]
    )
    _add_observer(
        db,
        review_session,
        email="alice@example.edu",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "mathcohort",
                }
            ],
        },
    )

    response = client.get(
        f"/me/sessions/{review_session.id}/collation/instruments/"
        f"{inst.id}.csv"
    )
    assert response.status_code == 200
    body = response.text
    # In-cohort row present; out-of-cohort row absent.
    assert "In Cohort" in body
    assert "Out Of Cohort" not in body


def test_collation_csv_anonymized_excludes_rows_outside_cohort_rule(
    client: TestClient, db: Session
) -> None:
    """Anonymized downloads run the per-row cohort filter
    identically to Raw — the tokenizer just swaps
    identification on the rows that pass. A reviewer outside
    the cohort gets dropped before tokens are computed; their
    token never appears in the CSV."""
    review_session = _make_session(client, db, code="col-csv-anon-scope")
    inst = Instrument(
        session_id=review_session.id, name="Instrument 1", order=0
    )
    db.add(inst)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=inst.id,
        field_key="rating",
        label="Rating",
        _inline_data_type="Integer",
        required=False,
        order=0,
    )
    db.add(field)
    db.add(
        InstrumentViewPolicy(
            instrument_id=inst.id,
            audience="observer",
            while_ongoing_granularity="row",
            while_ongoing_identification="deidentified",
        )
    )
    in_cohort = Reviewer(
        session_id=review_session.id,
        name="In Cohort",
        email="in@x",
        tag_1="mathcohort",
    )
    out_cohort = Reviewer(
        session_id=review_session.id,
        name="Out Of Cohort",
        email="out@x",
        tag_1="bio",
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Ree",
        email_or_identifier="ree@x",
    )
    db.add_all([in_cohort, out_cohort, reviewee])
    db.flush()
    submitted = datetime.now(timezone.utc)
    a_in = Assignment(
        session_id=review_session.id,
        instrument_id=inst.id,
        reviewer_id=in_cohort.id,
        reviewee_id=reviewee.id,
    )
    a_out = Assignment(
        session_id=review_session.id,
        instrument_id=inst.id,
        reviewer_id=out_cohort.id,
        reviewee_id=reviewee.id,
    )
    db.add_all([a_in, a_out])
    db.flush()
    db.add_all(
        [
            Response(
                assignment_id=a_in.id,
                response_field_id=field.id,
                value="4",
                submitted_at=submitted,
            ),
            Response(
                assignment_id=a_out.id,
                response_field_id=field.id,
                value="9",
                submitted_at=submitted,
            ),
        ]
    )
    _add_observer(
        db,
        review_session,
        email="alice@example.edu",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "mathcohort",
                }
            ],
        },
    )

    response = client.get(
        f"/me/sessions/{review_session.id}/collation/instruments/"
        f"{inst.id}.csv"
    )
    assert response.status_code == 200
    body = response.text
    # Identification swap: raw names + emails are out for both
    # the in-cohort and out-of-cohort reviewers.
    assert "In Cohort" not in body
    assert "Out Of Cohort" not in body
    assert "in@x" not in body
    assert "out@x" not in body
    # Per-row scoping: exactly ONE assignment row in the data
    # block — the in-cohort one. Count by response value column
    # since the data block has one row per assignment and the
    # response value is unique per row.
    # Strip meta block + header by splitting on the first
    # ``ReviewerName,`` header occurrence.
    data_body = body.split("ReviewerName,", 1)[1]
    # The out-of-cohort response value "9" should never appear.
    assert ",9," not in data_body
    # The in-cohort response value "4" should appear exactly once.
    assert data_body.count(",4,") == 1
    # Exactly one reviewer token in the data block.
    assert data_body.count("R-") == 1


def test_collation_csv_raw_filename_prefixes_observer_email(
    client: TestClient, db: Session
) -> None:
    """Filename pattern: ``<observer_email>_<instrument_slug>.csv``
    for Raw. No ``_anon`` suffix in the Raw case."""
    review_session = _make_session(
        client, db, code="col-csv-name-raw"
    )
    seeded = _seed_one_instrument(db, review_session)
    _add_observer(
        db,
        review_session,
        email="alice@example.edu",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "mathcohort",
                }
            ],
        },
    )
    response = client.get(
        f"/me/sessions/{review_session.id}/collation/instruments/"
        f"{seeded['instrument'].id}.csv"
    )
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "alice@example.edu_" in disposition
    assert disposition.endswith('.csv"')
    assert "_anon" not in disposition


def test_collation_csv_anonymized_filename_carries_anon_suffix(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client, db, code="col-csv-name-anon"
    )
    seeded = _seed_one_instrument(
        db,
        review_session,
        while_ongoing_granularity="row",
        while_ongoing_identification="deidentified",
    )
    _add_observer(
        db,
        review_session,
        email="alice@example.edu",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "mathcohort",
                }
            ],
        },
    )
    response = client.get(
        f"/me/sessions/{review_session.id}/collation/instruments/"
        f"{seeded['instrument'].id}.csv"
    )
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "alice@example.edu_" in disposition
    assert disposition.endswith('_anon.csv"')


def test_collation_csv_403_when_user_is_not_an_observer(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="col-csv-nope")
    seeded = _seed_one_instrument(db, review_session)
    # Authenticated user isn't on the observer roster.
    response = client.get(
        f"/me/sessions/{review_session.id}/collation/instruments/"
        f"{seeded['instrument'].id}.csv"
    )
    assert response.status_code == 403
