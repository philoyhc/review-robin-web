"""19T Item 12 — the reviewer surface opens and titles a range condition
(rung 2), and the settings CSV carries one (rung 3). The surface test sets
one directly: Rating (Integer 1–5) governs Comments while Rating is within
2 to 4, inclusive."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, Response, Reviewer

from .test_instrument_builder_routes import (
    _activate,
    _generate_full_matrix,
    _instrument,
    _make_session,
    _populate_rosters,
)
from .test_response_field_branching_surface import _cells, _controls, reviewer_user  # noqa: F401


def test_a_range_condition_opens_and_titles_the_cell(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,  # noqa: F811
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="range-surface")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, db, review_session.id)
    instrument = _instrument(db, review_session.id)
    fields = {f.field_key: f for f in instrument.response_fields}
    fields["rating"].branch_op, fields["rating"].branch_value = "in_inc", "2 to 4"
    fields["comments"].branch_parent_id = fields["rating"].id
    db.flush()
    _activate(operator, db, review_session.id)

    client = make_client(reviewer_user)
    body = client.get(f"/me/sessions/{review_session.id}").text
    for td in _cells(body, "comments"):
        assert 'title="Opens when 2 ≤ Rating ≤ 4"' in td
    for td in _cells(body, "rating"):
        assert 'data-rs-branch-op="in_inc"' in td
        assert 'data-rs-branch-value="2 to 4"' in td

    reviewer = db.execute(
        select(Reviewer).where(
            Reviewer.session_id == review_session.id,
            Reviewer.email == reviewer_user.email,
        )
    ).scalar_one()
    assignment = db.execute(
        select(Assignment).where(Assignment.reviewer_id == reviewer.id)
    ).scalar_one()
    rating = Response(
        assignment_id=assignment.id, response_field_id=fields["rating"].id, value="5"
    )
    db.add(rating)
    db.flush()
    body = client.get(f"/me/sessions/{review_session.id}").text
    assert all(" disabled" in c for c in _controls(body, "comments"))
    rating.value = "3"
    db.flush()
    body = client.get(f"/me/sessions/{review_session.id}").text
    assert all(" disabled" not in c for c in _controls(body, "comments"))


def test_the_settings_csv_round_trips_a_range_and_refuses_a_bad_one(
    db: Session,
) -> None:
    """From rung 3 a CSV carries a range (19T Item 12): each token
    round-trips, and a bad range is refused by the end at fault, with
    nothing applied."""
    from app.db.models import Instrument, InstrumentResponseField
    from app.services.session_config_io import (
        Row,
        apply_session_config,
        serialize_session_config,
    )

    from .test_response_field_branching_roundtrip import _rows, _session

    def with_condition(op: str, value: str) -> list[Row]:
        return [
            Row(r.field, op, r.data_type) if r.field.endswith("branch_op")
            else Row(r.field, value, r.data_type) if r.field.endswith("branch_value")
            else r
            for r in _rows()
        ]

    for op in ("in_inc", "in_exc", "out_inc", "out_exc"):
        source, _ = _session(db, f"range-csv-{op}")
        assert apply_session_config(db, source, with_condition(op, "2 to 4")).errors == []
        exported = [
            r for r in serialize_session_config(db, source)
            if r.field.startswith("instruments")
        ]
        target, _ = _session(db, f"range-csv-{op}-copy")
        assert apply_session_config(db, target, exported).errors == []
        rating = db.execute(
            select(InstrumentResponseField)
            .join(Instrument, Instrument.id == InstrumentResponseField.instrument_id)
            .where(
                Instrument.session_id == target.id,
                InstrumentResponseField.field_key == "rating",
            )
        ).scalar_one()
        assert (rating.branch_op, rating.branch_value) == (op, "2 to 4")

    bad, _ = _session(db, "range-csv-bad")
    result = apply_session_config(db, bad, with_condition("in_inc", "4 to 2"))
    assert [e.message for e in result.errors] == [
        "Rating: The range's low end must be below its high end."
    ]
    assert db.execute(
        select(Instrument).where(Instrument.session_id == bad.id)
    ).first() is None
