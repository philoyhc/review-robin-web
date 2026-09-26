"""19T Item 10 rung 4 — the reviewer surface: a governed field can be
answered only while its branch is open.

The default instrument gets a branch directly (no page authors one yet):
Rating (Integer 1–5) governs Comments while Rating ≥ 4."""

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


def _branched_live_session(db: Session, operator: TestClient, code: str):
    review_session = _make_session(operator, db, code=code)
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, db, review_session.id)
    instrument = _instrument(db, review_session.id)
    fields = {f.field_key: f for f in instrument.response_fields}
    fields["rating"].branch_op, fields["rating"].branch_value = "ge", "4"
    fields["comments"].branch_parent_id = fields["rating"].id
    db.flush()
    _activate(operator, db, review_session.id)
    return review_session, fields


def _cells(body: str, field_key: str) -> list[str]:
    """The opening ``<td …>`` tag of every response cell for ``field_key``."""
    return re.findall(
        r'<td[^>]*>\s*(?:\{#[^#]*#\}\s*)?<(?:input|textarea|select)[^>]*'
        rf'name="response\[\d+\]\[{field_key}\]"',
        body,
    )


def _controls(body: str, field_key: str) -> list[str]:
    return re.findall(
        rf'<(?:input|textarea|select)[^>]*name="response\[\d+\]\[{field_key}\]"[^>]*>',
        body,
    )


def test_a_governed_cell_is_closed_until_its_parent_is_answered(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, _ = _branched_live_session(db, make_client(alice), "br-surface")
    body = make_client(reviewer_user).get(f"/me/sessions/{review_session.id}").text
    comments = _cells(body, "comments")
    assert comments
    for td in comments:
        assert "rs-branch-closed" in td
        assert 'data-rs-governed-by="rating"' in td
        assert 'title="Opens when Rating ≥ 4"' in td
    assert all(" disabled" in c for c in _controls(body, "comments"))
    # The parent carries the condition its script re-judges.
    for td in _cells(body, "rating"):
        assert 'data-rs-branch-parent="rating"' in td
        assert 'data-rs-branch-op="ge"' in td
        assert 'data-rs-branch-value="4"' in td
        assert "rs-branch-closed" not in td
    assert all(" disabled" not in c for c in _controls(body, "rating"))
    # A closed cell can't be answered, so it isn't an item.
    assert "All items completed: 0/1" in body


def test_an_answer_that_meets_the_condition_opens_the_cell(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, fields = _branched_live_session(
        db, make_client(alice), "br-surface-open"
    )
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
        assignment_id=assignment.id, response_field_id=fields["rating"].id, value="2"
    )
    db.add(rating)
    db.flush()
    client = make_client(reviewer_user)
    body = client.get(f"/me/sessions/{review_session.id}").text
    assert all(" disabled" in c for c in _controls(body, "comments"))
    rating.value = "5"
    db.flush()
    body = client.get(f"/me/sessions/{review_session.id}").text
    assert all(" disabled" not in c for c in _controls(body, "comments"))
    assert all("rs-branch-closed" not in td for td in _cells(body, "comments"))
    assert "All items completed: 1/2" in body


def test_the_surface_script_mirrors_the_service_rule(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The script opens and closes cells as the parent changes; its
    rule is ``branch_is_open``'s (pinned here, driven in Chromium at
    build time)."""
    review_session, _ = _branched_live_session(db, make_client(alice), "br-surface-js")
    body = make_client(reviewer_user).get(f"/me/sessions/{review_session.id}").text
    start = body.index("function isOpen(op, value, raw)")
    script = body[start : body.index("})();", start)]
    assert 'if (!op || raw === "") { return false; }' in script
    assert 'if (op === "is") {' in script
    for op, js in (("eq", "==="), ("ne", "!=="), ("gt", ">"), ("ge", ">="),
                   ("lt", "<"), ("le", "<=")):
        assert f'if (op === "{op}") {{ return a {js} b; }}' in script
    # Only governed cells follow the parent, and only within its row.
    assert "cell.classList.toggle(\"rs-branch-closed\", !open);" in script
    assert "c.disabled = !open;" in script
    assert 'document.addEventListener("input", onEdit);' in script
    assert 'document.addEventListener("change", onEdit);' in script


def test_an_instrument_without_a_branch_renders_as_before(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="br-surface-none")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, db, review_session.id)
    _activate(operator, db, review_session.id)
    body = make_client(reviewer_user).get(f"/me/sessions/{review_session.id}").text
    comments = _cells(body, "comments")
    assert comments
    assert all("rs-branch-closed" not in td for td in comments)
    assert re.search(r"<td[^>]*data-rs-governed-by", body) is None
    assert re.search(r"<td[^>]*data-rs-branch-parent", body) is None
    assert all(" disabled" not in c for c in _controls(body, "comments"))
