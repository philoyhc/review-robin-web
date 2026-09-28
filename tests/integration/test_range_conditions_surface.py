"""19T Item 12 rung 2 — the reviewer surface opens and titles a range
condition. No page or CSV can store a range yet (rung 3), so the test sets
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


def test_the_settings_csv_refuses_a_range_until_the_builder_shows_one(
    db: Session,
) -> None:
    """Rung 2 evaluates ranges but stores none (Codex on #2657): a CSV
    naming one is refused by the parse phase, and nothing applies."""
    from app.db.models import Instrument
    from app.services.session_config_io import Row, apply_session_config

    from .test_response_field_branching_roundtrip import _rows, _session

    review_session, _ = _session(db, "range-csv")
    rows = [
        Row(r.field, "in_inc", r.data_type) if r.field.endswith("branch_op")
        else Row(r.field, "2 to 4", r.data_type) if r.field.endswith("branch_value")
        else r
        for r in _rows()
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.errors and result.errors[0].message.startswith("unknown branch_op 'in_inc'")
    assert db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).first() is None
