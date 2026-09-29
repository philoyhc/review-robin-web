"""19T Item 14 rung 2 — two levels of branching, evaluated before they
can be authored: a field applies only while every branch above it is open,
the save hold and the surface script walk the chain, and the counts and
the extract follow. Rung 2 still refused a second level, so each test
seeds the chain in the database.

The chain: Familiarity (Integer) governs Rating while Familiarity > 0, and
Rating governs Comments while Rating ≥ 4."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, InstrumentResponseField, Response, Reviewer
from app.schemas.responses import ResponseUpsert
from app.services import responses as responses_service
from app.services.extracts.by_instrument_extract import serialize_by_instrument

from .test_monitoring_rollup_parity import (
    REVIEWEE_IMPLEMENTATIONS,
    REVIEWER_IMPLEMENTATIONS,
    _by_email,
    _by_identifier,
)
from .test_required_governed_fields import (  # noqa: F401 (fixture)
    _answer,
    _live,
    _seed,
    _submit,
    reviewer_user,
)
from .test_required_governed_rollups import T0, _mixed_session

# The pure rule.


def _f(id_, *, required=False, parent=None, op=None, value=None, mode=None):
    return SimpleNamespace(
        id=id_, label=f"F{id_}", order=id_, required=required, visible=True,
        branch_parent_id=parent, branch_op=op, branch_value=value, branch_mode=mode,
        _inline_data_type="Integer", _inline_list_csv=None,
    )


def _chain(*, level1_mode=None, level0_mode=None):
    """F1 (Familiarity) > 0 governs F2 (Rating); F2 ≥ 4 governs F3."""
    return [
        _f(1, op="gt", value="0", mode=level0_mode),
        _f(2, required=True, parent=1, op="ge", value="4", mode=level1_mode),
        _f(3, required=True, parent=2),
    ]


def test_a_field_applies_only_while_every_branch_above_it_is_open() -> None:
    applies = responses_service.applicable_field_ids
    fields = _chain()
    assert applies(fields, {1: "3", 2: "5"}) == {1, 2, 3}
    assert applies(fields, {1: "3", 2: "2"}) == {1, 2}
    # A stale Rating that meets its own condition doesn't open Comments
    # while Familiarity closes Rating.
    assert applies(fields, {1: "0", 2: "5"}) == {1}
    assert applies(fields, {}) == {1}


def test_required_follows_the_whole_chain() -> None:
    required = responses_service.required_field_ids
    assert required(_chain(), {1: "3", 2: "5"}) == {2, 3}
    assert required(_chain(), {1: "0", 2: "5"}) == set()
    # A Require branch one level down is required only while it applies.
    fields = _chain(level1_mode="require")
    assert required(fields, {1: "3", 2: "5"}) == {2, 3}
    assert required(fields, {1: "3", 2: "2"}) == {2}
    assert required(fields, {1: "0", 2: "5"}) == set()


def test_the_structure_rules_accept_a_second_level() -> None:
    """Rung 2 refused it until the builder could show a chain; rung 4
    accepts it (a third level is refused in
    ``test_two_level_branching_authoring.py``)."""
    assert responses_service.branch_structure_errors([_f(0, required=True), *_chain()]) == []


# The save path.


def _chain_seed(db: Session):
    op, reviewer, review_session, assignments, rating, comments = _seed(db)
    familiarity = InstrumentResponseField(
        instrument_id=rating.instrument_id, field_key="familiarity",
        label="Familiarity", required=False, order=rating.order - 1,
        _inline_data_type="Integer", branch_op="gt", branch_value="0",
    )
    db.add(familiarity)
    db.flush()
    rating.branch_parent_id = familiarity.id
    db.flush()
    return op, reviewer, review_session, assignments, familiarity, rating, comments


def _values(db: Session, assignment: Assignment) -> dict[int, str]:
    return dict(
        db.execute(
            select(Response.response_field_id, Response.value).where(
                Response.assignment_id == assignment.id
            )
        ).all()
    )


def test_the_save_rule_drops_a_whole_closed_chain(db: Session) -> None:
    op, reviewer, review_session, (a1, _), familiarity, rating, comments = _chain_seed(db)
    _submit(db, op, reviewer, review_session, [
        ResponseUpsert(assignment_id=a1.id, field_key="familiarity", value="0"),
        ResponseUpsert(assignment_id=a1.id, field_key="rating", value="5"),
        ResponseUpsert(assignment_id=a1.id, field_key="comments", value="gone"),
    ])
    assert _values(db, a1) == {familiarity.id: "0"}


def test_a_grandchild_is_held_behind_a_refused_grandparent(db: Session) -> None:
    """Familiarity's typed value is refused, so its answer isn't written;
    writing Comments would let the save rule drop it at once. It comes
    back as an error, like Rating's, naming Familiarity."""
    op, reviewer, review_session, (a1, _), familiarity, rating, comments = _chain_seed(db)
    familiarity._inline_max = 5
    db.flush()
    result = responses_service.save_draft(
        db, review_session=review_session, reviewer=reviewer, user=op,
        upserts=[
            ResponseUpsert(assignment_id=a1.id, field_key="familiarity", value="9"),
            ResponseUpsert(assignment_id=a1.id, field_key="rating", value="5"),
            ResponseUpsert(assignment_id=a1.id, field_key="comments", value="kept"),
        ],
        correlation_id="c",
    )
    held = {e.field_key: e for e in result.errors if e.field_key != "familiarity"}
    assert set(held) == {"rating", "comments"}
    assert "Familiarity" in held["comments"].message
    assert held["comments"].value == "kept"
    assert _values(db, a1) == {}


# The counts.


def _chain_mixed(db: Session):
    """`_mixed_session` with Familiarity above Rating: Carol's Familiarity
    3 opens Rating (2, so Comments stays closed); Dan's 0 closes Rating,
    and with it Comments, whatever his stale Rating 5 says."""
    review_session, rows = _mixed_session(db)
    branched = rows["carol"].instrument
    fields = {f.field_key: f for f in branched.response_fields}
    familiarity = InstrumentResponseField(
        instrument_id=branched.id, field_key="familiarity", label="Familiarity",
        required=False, order=-1, _inline_data_type="Integer",
        branch_op="gt", branch_value="0",
    )
    db.add(familiarity)
    db.flush()
    fields["rating"].branch_parent_id = familiarity.id
    for key, value in (("carol", "3"), ("dan", "0")):
        db.add(Response(
            assignment_id=rows[key].id, response_field_id=familiarity.id,
            value=value, saved_at=T0, submitted_at=T0,
        ))
    db.flush()
    return review_session, rows


def test_the_rollups_count_a_chain(db: Session) -> None:
    review_session, rows = _chain_mixed(db)
    for name, rollup in REVIEWER_IMPLEMENTATIONS:
        rae = _by_email(rollup(db, review_session))["rae@example.edu"]
        # Carol's Rating and the plain Score; Dan owes nothing.
        assert (rae.required_total, rae.missing_required_count, rae.completed_count) == (
            2, 0, 3
        ), name
    for name, rollup in REVIEWEE_IMPLEMENTATIONS:
        by_id = _by_identifier(rollup(db, review_session))
        assert by_id["carol@example.edu"].completed_count == 2, name
        assert by_id["dan@example.edu"].completed_count == 1, name


def test_the_extract_names_each_fields_own_parent(db: Session) -> None:
    _, _, review_session, (a1, _), _, _, _ = _chain_seed(db)
    lines = serialize_by_instrument(db, review_session, a1.instrument, position=1)
    buffer = io.StringIO()
    csv.writer(buffer).writerows(lines)
    rows = list(csv.reader(io.StringIO(buffer.getvalue())))
    meta = rows[: rows.index([])]
    shown = [row[1] for row in meta if row[:1] == ["Shown when"]]
    assert shown == ["Familiarity > 0", "Rating ≥ 4"]


# The reviewer surface.


def _chain_live(db: Session, operator: TestClient, code: str):
    review_session, fields = _live(db, operator, code)
    familiarity = InstrumentResponseField(
        instrument_id=fields["rating"].instrument_id, field_key="familiarity",
        label="Familiarity", required=False, order=fields["rating"].order - 1,
        _inline_data_type="Integer", branch_op="gt", branch_value="0",
    )
    db.add(familiarity)
    db.flush()
    fields["rating"].branch_parent_id = familiarity.id
    db.commit()
    return review_session, fields


def test_the_surface_closes_a_chain_until_its_top_opens(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,  # noqa: F811 (fixture)
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, fields = _chain_live(db, make_client(alice), "two-level-surface")
    client = make_client(reviewer_user)
    body = client.get(f"/me/sessions/{review_session.id}").text
    # Rating is a parent and governed; both it and Comments start closed.
    assert re.search(
        r'<td[^>]*data-rs-branch-parent="rating"[^>]*data-rs-governed-by="familiarity"',
        body,
    )
    for key in ("rating", "comments"):
        control = re.search(
            rf'<(?:input|textarea)[^>]*name="response\[\d+\]\[{key}\]"[^>]*>', body
        ).group(0)
        assert " disabled" in control, key
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
    db.commit()
    body = client.get(f"/me/sessions/{review_session.id}").text
    comments = re.search(
        r'<(?:input|textarea)[^>]*name="response\[\d+\]\[comments\]"[^>]*>', body
    ).group(0)
    assert " disabled" in comments


def test_the_surface_script_cascades_down_the_chain(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,  # noqa: F811 (fixture)
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, _ = _chain_live(db, make_client(alice), "two-level-js")
    body = make_client(reviewer_user).get(f"/me/sessions/{review_session.id}").text
    start = body.index("function sync(parentCell)")
    script = " ".join(body[start : body.index("function onEdit", start)].split())
    for line in (
        'var parentApplies = !parentCell.classList.contains("rs-branch-closed");',
        "var applies = parentApplies && (open || requireMode);",
        'cell.classList.toggle("rs-branch-closed", !applies);',
        "c.disabled = !applies;",
        "if (cell.dataset.rsBranchParent) { sync(cell); }",
    ):
        assert line in script, line
