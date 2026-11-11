"""Segment 20K rung 4 — a stacked instrument on the reviewer surface.

``Instrument.response_layout == "stacked"``: the reviewee keeps one row,
and every response field moves into one *Responses* cell, a line each:
its label (constraint underneath) left of its box. The summary line goes,
a response field no longer sorts the table, and branching and Save work
as they do in columns. The default instrument has Rating (Integer 1–5,
compact) and Comments (String, a text box)."""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
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


@pytest.fixture
def reviewer_user() -> AuthenticatedUser:
    """The one reviewer ``_populate_rosters`` seeds."""
    return AuthenticatedUser(
        principal_id="r-oid",
        email="r@example.edu",
        name="R Reviewer",
        provider="aad",
    )


def _live(db: Session, operator: TestClient, code: str, *, layout: str, branch: bool = False):
    review_session = _make_session(operator, db, code=code)
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, db, review_session.id)
    instrument = _instrument(db, review_session.id)
    instrument.response_layout = layout
    fields = {f.field_key: f for f in instrument.response_fields}
    if branch:
        fields["rating"].branch_op, fields["rating"].branch_value = "ge", "4"
        fields["comments"].branch_parent_id = fields["rating"].id
    db.flush()
    _activate(operator, db, review_session.id)
    return review_session, fields


def _flat(body: str) -> str:
    return " ".join(body.split())


def _stack_field(flat: str, field_key: str) -> str:
    match = re.search(
        rf'<div class="rs-stack-field[^"]*"[^>]*data-rs-stack-field="{field_key}"[^>]*>', flat
    )
    assert match is not None, field_key
    return match.group(0)


def test_every_response_field_sits_on_its_own_line_in_one_cell(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, _ = _live(db, make_client(alice), "20k-stack", layout="stacked")
    flat = _flat(make_client(reviewer_user).get(f"/me/sessions/{review_session.public_id}").text)

    assert flat.count('<th scope="col" class="rs-stack">Responses</th>') == 1
    # No response field heads a column, so none sorts the table.
    assert 'data-sort-key="response:' not in flat
    assert 'data-sort-key="reviewee.name"' in flat
    assert flat.count('<td class="rs-stack">') == 1
    # Label, then its constraint under it, then the box.
    assert re.search(
        r'<span class="rs-stack-name">Rating \*</span>'
        r'<small class="rs-stack-help">1-5, steps of 1</small></div> '
        r'<div class="rs-stack-input is-compact"> <input type="number"[^>]*'
        r'name="response\[1\]\[rating\]"',
        flat,
    )
    assert re.search(
        r'<small class="rs-stack-help">0-2000 char</small></div> '
        r'<div class="rs-stack-input"> <textarea name="response\[1\]\[comments\]"',
        flat,
    )
    # The compact boxes share one width: Rating's one digit, floored at three.
    assert 'style="--rs-stack-compact: 6ch"' in flat
    # Each constraint sits under its label, so the summary line goes.
    assert 'class="rs-constraints' not in flat


def test_columns_keep_a_column_per_field(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, _ = _live(db, make_client(alice), "20k-cols", layout="columns")
    flat = _flat(make_client(reviewer_user).get(f"/me/sessions/{review_session.public_id}").text)
    assert 'class="rs-stack' not in flat
    assert 'data-sort-key="response:rating"' in flat
    assert 'class="rs-constraints' in flat


def test_a_branch_works_across_the_lines_of_the_cell(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, _ = _live(db, make_client(alice), "20k-branch", layout="stacked", branch=True)
    flat = _flat(make_client(reviewer_user).get(f"/me/sessions/{review_session.public_id}").text)
    rating = _stack_field(flat, "rating")
    assert 'data-rs-branch-parent="rating"' in rating
    assert 'data-rs-branch-op="ge"' in rating
    comments = _stack_field(flat, "comments")
    assert "rs-branch-closed" in comments
    assert 'data-rs-governed-by="rating"' in comments
    assert 'title="Opens when Rating ≥ 4"' in comments
    assert re.search(r'<textarea name="response\[1\]\[comments\]"[^>]* disabled', flat)


def test_save_stores_every_line(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, fields = _live(db, make_client(alice), "20k-save", layout="stacked")
    client = make_client(reviewer_user)
    body = client.get(f"/me/sessions/{review_session.public_id}/1").text
    digest = re.search(r'name="page_digest" value="([^"]+)"', body)
    assert digest is not None
    response = client.post(
        f"/me/sessions/{review_session.public_id}/1/save",
        data={
            "response[1][rating]": "4",
            "response[1][comments]": "Thorough",
            "page_digest": digest.group(1),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    reviewer = db.execute(
        select(Reviewer).where(
            Reviewer.session_id == review_session.id, Reviewer.email == reviewer_user.email
        )
    ).scalar_one()
    assignment = db.execute(
        select(Assignment).where(Assignment.reviewer_id == reviewer.id)
    ).scalar_one()
    values = {
        r.response_field_id: r.value
        for r in db.execute(
            select(Response).where(Response.assignment_id == assignment.id)
        ).scalars()
    }
    assert values == {fields["rating"].id: "4", fields["comments"].id: "Thorough"}


def test_the_dragged_widths_hold_on_the_surface(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="20k-widths")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, db, review_session.id)
    instrument = _instrument(db, review_session.id)
    instrument.response_layout = "stacked"
    instrument.column_widths = {"stack_label": 180, "stack_input": 400}
    db.flush()
    _activate(operator, db, review_session.id)
    flat = _flat(make_client(reviewer_user).get(f"/me/sessions/{review_session.public_id}").text)
    assert (
        'class="rs-stack-fields" style="--rs-stack-compact: 6ch; '
        '--rs-stack-label: 180px; --rs-stack-input: 400px"'
    ) in flat
    # Both saved, the Responses column holds them (Codex on #3806): the
    # widths, the 12px gap and the cell's 32px of padding.
    assert '<col style="width: 624px">' in flat
