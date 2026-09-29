"""19T Item 13 rung 3a — the rule: under a require-mode parent a governed
field is always answerable, and required exactly while the condition
holds, its own ``required`` ignored.

Each test sets ``branch_mode`` directly: no write path accepts it until
rung 3b. The default instrument's Rating (Integer 1–5, required) governs
Comments while Rating ≥ 4, and Comments' own ``required`` is False."""

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
from app.db.models import Assignment, Response, Reviewer
from app.schemas.responses import ResponseUpsert
from app.services import monitoring
from app.services import responses as responses_service
from app.services.extracts.by_instrument_extract import serialize_by_instrument
from app.services.extracts.entity_stats_extract import build_entity_stats

from .test_monitoring_rollup_parity import (
    REVIEWEE_IMPLEMENTATIONS,
    REVIEWER_IMPLEMENTATIONS,
    _by_email,
    _by_identifier,
)
from .test_required_governed_fields import (  # noqa: F401 (fixture)
    _answer,
    _comments_control,
    _live,
    _seed,
    _submit,
    reviewer_user,
)
from .test_required_governed_rollups import _mixed_session

# The pure rule.


def _f(id_, *, required=False, parent=None, op=None, value=None, mode=None, visible=True):
    return SimpleNamespace(
        id=id_, label=f"F{id_}", order=id_, required=required, visible=visible,
        branch_parent_id=parent, branch_op=op, branch_value=value, branch_mode=mode,
        _inline_data_type="Integer", _inline_list_csv=None,
    )


def _pair(mode, *, governed_required=False):
    return [
        _f(1, required=True, op="ge", value="4", mode=mode),
        _f(2, required=governed_required, parent=1),
    ]


def test_a_require_mode_field_always_applies() -> None:
    fields = _pair("require")
    for answer in (None, "", "2", "5"):
        assert responses_service.applicable_field_ids(fields, {1: answer}) == {1, 2}
    # Show keeps Item 10's meaning, as does a null or unknown mode.
    for mode in ("show", None, "bogus"):
        assert responses_service.applicable_field_ids(_pair(mode), {1: "2"}) == {1}


def test_a_require_mode_field_is_required_exactly_while_the_condition_holds() -> None:
    for governed_required in (False, True):
        fields = _pair("require", governed_required=governed_required)
        req = responses_service.required_field_ids
        assert req(fields, {1: "5"}) == {1, 2}
        assert req(fields, {1: "2"}) == {1}
        # An unanswered parent holds nothing.
        assert req(fields, {}) == {1}
    # Show: the field's own flag, while open.
    assert responses_service.required_field_ids(_pair("show"), {1: "5"}) == {1}
    assert responses_service.required_field_ids(
        _pair("show", governed_required=True), {1: "5"}
    ) == {1, 2}


def test_a_hidden_require_mode_field_is_never_required() -> None:
    """Its R is grayed out, so nothing else could stop a field no reviewer
    sees from being owed (the cumulative read on #2676)."""
    fields = _pair("require", governed_required=True)
    fields[1].visible = False
    assert responses_service.required_field_ids(fields, {1: "5"}) == {1}
    assert responses_service.may_be_required_field_ids(fields) == {1}


def test_may_be_required_marks_every_require_mode_field() -> None:
    mbr = responses_service.may_be_required_field_ids
    assert mbr(_pair("require")) == {1, 2}
    assert mbr(_pair("show")) == {1}
    assert mbr(_pair("show", governed_required=True)) == {1, 2}


def test_a_require_mode_branch_needs_the_anchor() -> None:
    """Item 11's rule: a require-mode field counts as a required governed
    field, so an instrument needs an active required field outside any
    branch; the parent itself is one when it is required."""
    message = responses_service._branching.REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE
    unanchored = [
        _f(1, op="ge", value="4", mode="require"),
        _f(2, parent=1),
    ]
    assert ("F2", message) in responses_service.branch_structure_errors(unanchored)
    assert not [
        e for e in responses_service.branch_structure_errors(_pair("require"))
        if e[1] == message
    ]
    # A show-mode optional governed field needs no anchor, as before.
    assert not [
        e for e in responses_service.branch_structure_errors(
            [_f(1, op="ge", value="4"), _f(2, parent=1)]
        )
        if e[1] == message
    ]


def test_the_import_filter_keeps_a_require_mode_answer() -> None:
    assert responses_service.closed_governed_field_ids(_pair("require"), {1: "2"}) == set()
    assert responses_service.closed_governed_field_ids(_pair("show"), {1: "2"}) == {2}


# Saves, the submit gate and the row's counts.


def _require_seed(db: Session):
    op, reviewer, review_session, assignments, rating, comments = _seed(db)
    comments.required = False
    rating.branch_mode = "require"
    db.flush()
    return op, reviewer, review_session, assignments, rating, comments


def test_a_closed_condition_keeps_a_require_mode_answer(db: Session) -> None:
    op, reviewer, review_session, (a1, _), _, comments = _require_seed(db)
    _submit(db, op, reviewer, review_session, [
        ResponseUpsert(assignment_id=a1.id, field_key="rating", value="2"),
        ResponseUpsert(assignment_id=a1.id, field_key="comments", value="still here"),
    ])
    kept = db.execute(
        select(Response.value).where(
            Response.assignment_id == a1.id, Response.response_field_id == comments.id
        )
    ).scalar_one()
    assert kept == "still here"


def test_the_submit_gate_follows_the_condition(db: Session) -> None:
    op, reviewer, review_session, (a1, a2), _, _ = _require_seed(db)
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
    assert result.missing == [] and result.submitted is True


def test_the_gate_asks_a_require_mode_instrument_even_with_no_required_flag(
    db: Session,
) -> None:
    """With Rating optional too, no field's own ``required`` is set, yet
    Comments is required while Rating ≥ 4 (``may_be_required_field_ids``)."""
    op, reviewer, review_session, (a1, a2), rating, _ = _require_seed(db)
    rating.required = False
    db.flush()
    result = _submit(db, op, reviewer, review_session, [
        ResponseUpsert(assignment_id=a1.id, field_key="rating", value="4"),
    ])
    assert [(m.reviewee_name, m.field_key) for m in result.missing] == [
        ("Carol", "comments")
    ]


def test_a_rows_counts_follow_the_condition(db: Session) -> None:
    _, reviewer, review_session, (a1, a2), rating, comments = _require_seed(db)
    _answer(db, a1, rating, "2")
    _answer(db, a2, rating, "5")
    closed = responses_service.row_completion(db, a1)
    assert (closed.is_complete, closed.missing_count, closed.required_count) == (True, 0, 1)
    opened = responses_service.row_completion(db, a2)
    assert (opened.is_complete, opened.missing_count, opened.required_count) == (False, 1, 2)
    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )
    assert (state.completed_count, state.missing_required_count, state.required_total) == (1, 1, 3)
    _answer(db, a2, comments, "why")
    assert responses_service.row_completion(db, a2).is_complete is True


# The rollups (Codex on #2671).


def _require_mixed(db: Session):
    review_session, rows = _mixed_session(db)
    branched = rows["carol"].instrument
    fields = {f.field_key: f for f in branched.response_fields}
    fields["comments"].required = False
    fields["rating"].branch_mode = "require"
    db.flush()
    return review_session, rows


def test_a_require_mode_instrument_is_routed_to_python(db: Session) -> None:
    review_session, rows = _require_mixed(db)
    routed = set(db.execute(monitoring._required_governed_instrument_ids()).scalars())
    assert rows["carol"].instrument_id in routed
    assert rows["plain"].instrument_id not in routed


def test_the_rollups_count_a_require_mode_field_while_its_condition_holds(
    db: Session,
) -> None:
    """The same counts as Item 11's required governed field: Dan's Rating 5
    owes Comments, Carol's Rating 2 doesn't."""
    review_session, _ = _require_mixed(db)
    for name, rollup in REVIEWER_IMPLEMENTATIONS:
        rae = _by_email(rollup(db, review_session))["rae@example.edu"]
        assert (rae.required_total, rae.missing_required_count, rae.completed_count) == (
            4, 1, 2
        ), name
        assert rae.pill_state == "in progress", name
    for name, rollup in REVIEWEE_IMPLEMENTATIONS:
        rows = _by_identifier(rollup(db, review_session))
        carol, dan = rows["carol@example.edu"], rows["dan@example.edu"]
        assert (carol.completed_count, dan.completed_count) == (2, 0), name


def test_the_rollups_never_owe_a_hidden_require_mode_field(db: Session) -> None:
    """Hidden, Comments is owed nowhere: Dan's Rating 5 completes his row
    on both rollups, which don't otherwise filter ``visible`` alike."""
    review_session, rows = _require_mixed(db)
    comments = next(
        f for f in rows["carol"].instrument.response_fields if f.field_key == "comments"
    )
    comments.visible = False
    comments.required = True
    db.flush()
    for name, rollup in REVIEWER_IMPLEMENTATIONS:
        rae = _by_email(rollup(db, review_session))["rae@example.edu"]
        assert (rae.required_total, rae.missing_required_count, rae.completed_count) == (
            3, 0, 3
        ), name
    for name, rollup in REVIEWEE_IMPLEMENTATIONS:
        by_id = _by_identifier(rollup(db, review_session))
        assert by_id["dan@example.edu"].completed_count == 1, name


# The reviewer surface.


def _require_live(db: Session, operator: TestClient, code: str):
    review_session, fields = _live(db, operator, code)
    fields["comments"].required = False
    fields["rating"].branch_mode = "require"
    db.commit()
    return review_session, fields


def test_the_surface_keeps_a_require_mode_cell_answerable(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,  # noqa: F811
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, fields = _require_live(db, make_client(alice), "13-surface")
    client = make_client(reviewer_user)
    body = client.get(f"/me/sessions/{review_session.id}").text
    control = _comments_control(body)
    # Unanswered parent: enabled, not closed, not required, no hint.
    assert " disabled" not in control and "(required)" not in control
    cell = re.search(r'<td[^>]*data-rs-governed-by="rating"[^>]*>', body).group(0)
    assert "rs-branch-closed" not in cell and "title=" not in cell
    assert 'data-rs-required="true"' in cell
    assert re.search(r'data-rs-branch-parent="rating"[^>]*data-rs-branch-mode="require"', body)
    # Its header carries the "*" though its own ``required`` is False.
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


def test_the_surface_script_keeps_a_require_mode_cell_enabled(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,  # noqa: F811
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    review_session, _ = _require_live(db, make_client(alice), "13-surface-js")
    body = make_client(reviewer_user).get(f"/me/sessions/{review_session.id}").text
    start = body.index("function isOpen(op, value, raw)")
    script = body[start : body.index("})();", start)]
    assert 'var requireMode = parentCell.dataset.rsBranchMode === "require";' in script
    assert 'var applies = parentApplies && (open || requireMode);' in script
    assert 'cell.classList.toggle("rs-branch-closed", !applies);' in script
    assert "c.disabled = !applies;" in script
    assert (
        'var requiredNow = parentApplies && open && cell.dataset.rsRequired === "true";'
        in script
    )


# The extracts.


def test_the_by_instrument_extract_reads_required_when(db: Session) -> None:
    _, _, review_session, (a1, _), _, _ = _require_seed(db)
    lines = serialize_by_instrument(db, review_session, a1.instrument, position=1)
    buffer = io.StringIO()
    csv.writer(buffer).writerows(lines)
    rows = list(csv.reader(io.StringIO(buffer.getvalue())))
    meta = rows[: rows.index([])]
    assert ["Required when", "Rating ≥ 4"] in meta
    assert all(row[:1] != ["Shown when"] for row in meta)


def test_entity_stats_count_a_require_mode_answer_as_required_only_while_it_holds(
    db: Session,
) -> None:
    _, _, review_session, (a1, a2), rating, comments = _require_seed(db)
    for assignment, value in ((a1, "2"), (a2, "5")):
        _answer(db, assignment, rating, value)
        _answer(db, assignment, comments, "text")
    reviewer_rows, reviewee_rows = build_entity_stats(db, review_session)
    header = reviewee_rows[0]
    col = next(i for i, h in enumerate(header) if "equired" in h)
    by_name = {row[0]: row for row in reviewee_rows[1:]}
    # Carol (Rating 2): only Rating counts; Dan (Rating 5): Rating and Comments.
    assert [by_name[n][col] for n in ("Carol", "Dan")] == ["1", "2"]
    reviewer_header = reviewer_rows[0]
    rcol = next(i for i, h in enumerate(reviewer_header) if "equired" in h)
    assert reviewer_rows[1][rcol] == "3"


# The reviewer summary and the reviewee's results mark "*" by
# ``may_be_required_field_ids`` (the cumulative read on #2676).


def test_the_summary_and_results_headers_mark_a_require_mode_field(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    from app.db.models import Instrument, InstrumentResponseField, Reviewee
    from app.web.views._reviewee_results import build_reviewee_results_context
    from app.web.views._reviewer_summary import build_reviewer_summary_context

    from .test_reviewee_results_body import (
        _enable_reviewee_after_release_raw,
        _operator_user,
        _seed_and_activate,
        _seed_submitted_responses,
    )

    review_session = _seed_and_activate(make_client(alice), db, code="13-headers")
    _seed_submitted_responses(db, review_session, rating_value="2")
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=True
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    fields = {
        f.field_key: f
        for f in db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    }
    fields["rating"].branch_op, fields["rating"].branch_value = "ge", "4"
    fields["comments"].branch_parent_id = fields["rating"].id
    fields["comments"].required = False
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalar_one()

    def marks() -> tuple[dict[str, bool], dict[str, bool]]:
        db.commit()
        summary = build_reviewer_summary_context(
            db, review_session=review_session, reviewer=reviewer
        )
        results = build_reviewee_results_context(
            db, review_session=review_session, reviewee=reviewee
        )
        return (
            {c.field_key: c.required for c in summary.sections[0].field_cols},
            {c.field_key: c.required for c in results.sections[0].field_cols},
        )

    assert marks() == ({"rating": True, "comments": False},) * 2
    fields["rating"].branch_mode = "require"
    assert marks() == ({"rating": True, "comments": True},) * 2
