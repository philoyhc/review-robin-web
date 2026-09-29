"""19T Item 11 rung 2 — a required governed field is required, and
missing when empty, only while its branch is open, in every Python count.

Each test sets ``required`` directly rather than through the card (the
card's own path is ``test_required_governed_authoring.py``). The default
instrument's Rating (Integer 1–5, required) governs Comments while
Rating ≥ 4, and Comments is required."""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)
from app.schemas.responses import ResponseUpsert
from app.services import responses as responses_service
from app.services.instruments import ensure_default_instrument
from app.services.responses._core import _compute_missing_required

from .test_instrument_builder_routes import (
    _activate,
    _card_slice,
    _generate_full_matrix,
    _instrument,
    _make_session,
    _new_model_with_tags,
    _populate_rosters,
)


def _seed(db: Session):
    op = User(email="op@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(name="Spring", code="req-gov", created_by_user_id=op.id)
    db.add(review_session)
    db.flush()
    db.add(SessionOperator(session_id=review_session.id, user_id=op.id, role="owner"))
    instrument = ensure_default_instrument(db, review_session)
    fields = {f.field_key: f for f in instrument.response_fields}
    rating, comments = fields["rating"], fields["comments"]
    assert rating.required and not comments.required
    rating.branch_op, rating.branch_value = "ge", "4"
    comments.branch_parent_id = rating.id
    comments.required = True
    reviewer = Reviewer(session_id=review_session.id, name="Rae", email="rae@example.edu")
    db.add(reviewer)
    db.flush()
    assignments = []
    for name in ("Carol", "Dan"):
        reviewee = Reviewee(
            session_id=review_session.id, name=name,
            email_or_identifier=f"{name.lower()}@example.edu",
        )
        db.add(reviewee)
        db.flush()
        assignment = Assignment(
            session_id=review_session.id, reviewer_id=reviewer.id,
            reviewee_id=reviewee.id, instrument_id=instrument.id,
        )
        db.add(assignment)
        db.flush()
        assignments.append(assignment)
    return op, reviewer, review_session, assignments, rating, comments


def _answer(db: Session, assignment: Assignment, field, value: str) -> None:
    db.add(Response(assignment_id=assignment.id, response_field_id=field.id, value=value))
    db.flush()


def _submit(db, op, reviewer, review_session, upserts):
    return responses_service.submit(
        db, review_session=review_session, reviewer=reviewer, user=op,
        upserts=upserts, correlation_id="c",
    )


def test_a_closed_branch_doesnt_block_a_submit(db: Session) -> None:
    op, reviewer, review_session, (a1, a2), _, _ = _seed(db)
    result = _submit(db, op, reviewer, review_session, [
        ResponseUpsert(assignment_id=a1.id, field_key="rating", value="2"),
        ResponseUpsert(assignment_id=a2.id, field_key="rating", value="3"),
    ])
    assert result.missing == []
    assert result.submitted is True


def test_an_open_branch_blocks_a_submit_until_answered(db: Session) -> None:
    """Judged on the state the submit leaves: the parent is answered in
    the same submit that finds its governed field missing."""
    op, reviewer, review_session, (a1, a2), _, _ = _seed(db)
    result = _submit(db, op, reviewer, review_session, [
        ResponseUpsert(assignment_id=a1.id, field_key="rating", value="5"),
        ResponseUpsert(assignment_id=a2.id, field_key="rating", value="2"),
    ])
    assert result.submitted is False
    assert [(m.reviewee_name, m.field_key) for m in result.missing] == [
        ("Carol", "comments")
    ]
    result = _submit(db, op, reviewer, review_session, [
        ResponseUpsert(assignment_id=a1.id, field_key="comments", value="why"),
    ])
    assert result.missing == []
    assert result.submitted is True


def test_a_parent_changed_to_close_the_branch_releases_the_submit(db: Session) -> None:
    op, reviewer, review_session, (a1, a2), rating, _ = _seed(db)
    _answer(db, a1, rating, "5")
    result = _submit(db, op, reviewer, review_session, [
        ResponseUpsert(assignment_id=a1.id, field_key="rating", value="1"),
        ResponseUpsert(assignment_id=a2.id, field_key="rating", value="1"),
    ])
    assert result.missing == []
    assert result.submitted is True


def test_a_rows_required_count_follows_its_branch(db: Session) -> None:
    _, _, _, (a1, a2), rating, comments = _seed(db)
    _answer(db, a1, rating, "2")
    _answer(db, a2, rating, "5")
    closed = responses_service.row_completion(db, a1)
    assert (closed.is_complete, closed.missing_count, closed.required_count) == (True, 0, 1)
    opened = responses_service.row_completion(db, a2)
    assert (opened.is_complete, opened.missing_count, opened.required_count) == (False, 1, 2)
    assert responses_service.compute_row_completion(db, a2)[:2] == (False, 1)
    _answer(db, a2, comments, "why")
    assert responses_service.row_completion(db, a2).is_complete is True


def test_the_reviewer_rollup_counts_per_assignment(db: Session) -> None:
    _, reviewer, review_session, (a1, a2), rating, _ = _seed(db)
    _answer(db, a1, rating, "2")
    _answer(db, a2, rating, "5")
    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )
    assert (state.completed_count, state.missing_required_count) == (1, 1)
    # 1 required field on the closed row and 2 on the open one, not 2 × 2.
    assert state.required_total == 3


def test_a_group_row_is_judged_once_on_its_answers(db: Session) -> None:
    """On a group-scoped instrument every member holds the group row's
    answers, and the gate reports a missing field once per group."""
    _, _, _, (a1, a2), rating, comments = _seed(db)
    _answer(db, a1, rating, "5")
    _answer(db, a2, rating, "5")
    missing = _compute_missing_required(
        db,
        assignments=[a1, a2],
        fields_by_instrument={a1.instrument_id: [rating, comments]},
        position_by_instrument_id={a1.instrument_id: 1},
        group_key_by_assignment={a1.id: ("g",), a2.id: ("g",)},
    )
    assert [(m.assignment_id, m.field_key) for m in missing] == [(a1.id, "comments")]
    # Closed for the group row, nothing is missing.
    for assignment in (a1, a2):
        db.execute(select(Response).where(Response.assignment_id == assignment.id)).scalar_one().value = "2"
    db.flush()
    assert _compute_missing_required(
        db,
        assignments=[a1, a2],
        fields_by_instrument={a1.instrument_id: [rating, comments]},
        position_by_instrument_id={a1.instrument_id: 1},
        group_key_by_assignment={a1.id: ("g",), a2.id: ("g",)},
    ) == []


def test_a_hidden_required_governed_field_counts_nowhere(db: Session) -> None:
    _, _, _, (a1, _), rating, comments = _seed(db)
    comments.visible = False
    db.flush()
    _answer(db, a1, rating, "5")
    state = responses_service.row_completion(db, a1)
    assert (state.missing_count, state.required_count) == (0, 1)


# The reviewer page.


@pytest.fixture
def reviewer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="r-oid", email="r@example.edu", name="R Reviewer", provider="aad",
    )


def _live(db: Session, operator: TestClient, code: str):
    review_session = _make_session(operator, db, code=code)
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, db, review_session.id)
    instrument = _instrument(db, review_session.id)
    fields = {f.field_key: f for f in instrument.response_fields}
    fields["rating"].branch_op, fields["rating"].branch_value = "ge", "4"
    fields["comments"].branch_parent_id = fields["rating"].id
    fields["comments"].required = True
    db.flush()
    _activate(operator, db, review_session.id)
    return review_session, fields


def _comments_control(body: str) -> str:
    return re.search(
        r'<(?:input|textarea)[^>]*name="response\[\d+\]\[comments\]"[^>]*>', body
    ).group(0)


def test_a_closed_required_cell_isnt_announced_as_required(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, fields = _live(db, make_client(alice), "req-gov-surface")
    client = make_client(reviewer_user)
    body = client.get(f"/me/sessions/{review_session.id}").text
    control = _comments_control(body)
    assert "(required)" not in control
    assert re.search(r'<td[^>]*data-rs-governed-by="rating" data-rs-required="true"', body)
    # The header keeps its star; the pill counts only the open field.
    assert "Comments *" in body
    assert "*Required items completed: 0/1" in body

    reviewer = db.execute(
        select(Reviewer).where(
            Reviewer.session_id == review_session.id,
            Reviewer.email == reviewer_user.email,
        )
    ).scalar_one()
    assignment = db.execute(
        select(Assignment).where(Assignment.reviewer_id == reviewer.id)
    ).scalar_one()
    _answer(db, assignment, fields["rating"], "5")
    body = client.get(f"/me/sessions/{review_session.id}").text
    assert "(required)" in _comments_control(body)
    assert "*Required items completed: 1/2" in body


def test_the_surface_script_toggles_the_required_label(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, _ = _live(db, make_client(alice), "req-gov-js")
    body = make_client(reviewer_user).get(f"/me/sessions/{review_session.id}").text
    start = body.index("function isOpen(op, value, raw)")
    script = body[start : body.index("})();", start)]
    assert (
        'var requiredNow = parentApplies && open && cell.dataset.rsRequired === "true";'
        in script
    )
    assert 'requiredNow ? label + " (required)" : label' in script


# The builder preview.


def test_the_preview_doesnt_count_a_required_governed_field(
    client: TestClient, db: Session
) -> None:
    """The preview's sample row is unanswered, so every branch is closed."""
    review_session, instrument = _new_model_with_tags(client, db, code="req-gov-prev")
    fields = {f.label: f for f in instrument.response_fields}
    required_before = sum(1 for f in fields.values() if f.required)
    fields["Rating"].branch_op, fields["Rating"].branch_value = "ge", "4"
    fields["Comments"].branch_parent_id = fields["Rating"].id
    fields["Comments"].required = True
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    card = _card_slice(" ".join(body.split()), instrument.id)
    assert (
        f"<span data-new-model-intro-required-count>{required_before}</span>" in card
    )
    assert "function rfRowRequiredNow(row) {" in body
    assert (
        "return rfRowRequired(row) && !row.hasAttribute('data-new-model-rf-governed');"
        in body
    )
    assert "committedRows.filter(rfRowRequiredNow).length" in body
    assert "window.newModelRfRowRequiredNow" in body



def test_a_group_scoped_submit_is_gated_once_per_group_row(db: Session) -> None:
    """Through ``submit`` on a real group-scoped instrument: the parent's
    answer fans out to every member, the gate reports the open branch's
    empty field once for the group row, and answering it releases every
    member (the item's cumulative read)."""
    op, reviewer, review_session, (a1, a2), rating, comments = _seed(db)
    instrument = a1.instrument
    instrument.group_kind = "r1"
    for assignment in (a1, a2):
        assignment.reviewee.tag_1 = "Team A"
    db.flush()
    result = _submit(db, op, reviewer, review_session, [
        ResponseUpsert(assignment_id=a1.id, field_key="rating", value="5"),
    ])
    assert result.submitted is False
    assert [m.field_key for m in result.missing] == ["comments"]
    # The fan-out reached a2: its branch is open (2 required), and only
    # Comments is missing, not Rating.
    for assignment in (a1, a2):
        state = responses_service.row_completion(db, assignment)
        assert (state.required_count, state.missing_count) == (2, 1)
    result = _submit(db, op, reviewer, review_session, [
        ResponseUpsert(assignment_id=a1.id, field_key="comments", value="why"),
    ])
    assert result.missing == []
    assert result.submitted is True
    for assignment in (a1, a2):
        assert responses_service.row_completion(db, assignment).is_complete


def test_a_group_scoped_closed_branch_submits(db: Session) -> None:
    op, reviewer, review_session, (a1, a2), _, _ = _seed(db)
    a1.instrument.group_kind = "r1"
    for assignment in (a1, a2):
        assignment.reviewee.tag_1 = "Team A"
    db.flush()
    result = _submit(db, op, reviewer, review_session, [
        ResponseUpsert(assignment_id=a1.id, field_key="rating", value="2"),
    ])
    assert result.missing == []
    assert result.submitted is True
