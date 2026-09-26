"""The save rule for branching (19T Item 10 rung 3): **a closed branch
holds no value.**

``guide/advanced_instruments.md`` Item 1, Pre-positioning 3: every writer
of ``Response`` rows ends here, so a governed answer never outlives its
branch closing. Save and submit (``_apply_upserts``) and the group re-fan
(``_refan_group_responses``) call :func:`drop_closed_branch_answers` after
writing; the responses import, which reports each row it can't place,
filters with :func:`closed_governed_field_ids` before inserting. Both are
built on :func:`applicable_field_ids`, so they can't disagree with each
other or with the reviewer surface.

Item 2's stored branch state, if it is ever chosen, is one more write in
:func:`drop_closed_branch_answers`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Assignment, InstrumentResponseField, Response

from ._branching import BranchField, applicable_field_ids


def closed_governed_field_ids(
    fields: Iterable[BranchField],
    answer_by_field_id: Mapping[int, str | None],
) -> set[int]:
    """The governed fields among ``fields`` whose branch is closed for these
    answers: the ones that may hold no value."""
    field_list = list(fields)
    applicable = applicable_field_ids(field_list, answer_by_field_id)
    return {
        f.id
        for f in field_list
        if f.branch_parent_id is not None and f.id not in applicable
    }


def drop_closed_branch_answers(db: Session, assignment_ids: Iterable[int]) -> int:
    """Delete the answers the given assignments hold for governed fields
    whose branch is now closed. Returns how many were deleted.

    Reads the answers as they stand after the caller's writes, so a parent
    changed in the same save is judged on its new value. One query and no
    deletes when none of the assignments' instruments has a branch."""
    ids = set(assignment_ids)
    if not ids:
        return 0
    instrument_by_assignment: dict[int, int] = {
        assignment_id: instrument_id
        for assignment_id, instrument_id in db.execute(
            select(Assignment.id, Assignment.instrument_id).where(
                Assignment.id.in_(ids)
            )
        ).all()
    }
    branch_fields = list(
        db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id.in_(
                    set(instrument_by_assignment.values())
                ),
                or_(
                    InstrumentResponseField.branch_parent_id.is_not(None),
                    InstrumentResponseField.branch_op.is_not(None),
                ),
            )
        ).scalars()
    )
    if not any(f.branch_parent_id is not None for f in branch_fields):
        return 0
    fields_by_instrument: dict[int, list[InstrumentResponseField]] = {}
    for field in branch_fields:
        fields_by_instrument.setdefault(field.instrument_id, []).append(field)
    rows_by_assignment: dict[int, list[Response]] = {}
    for row in db.execute(
        select(Response).where(
            Response.assignment_id.in_(ids),
            Response.response_field_id.in_({f.id for f in branch_fields}),
        )
    ).scalars():
        rows_by_assignment.setdefault(row.assignment_id, []).append(row)
    removed = 0
    for assignment_id, rows in rows_by_assignment.items():
        closed = closed_governed_field_ids(
            fields_by_instrument.get(instrument_by_assignment[assignment_id], []),
            {row.response_field_id: row.value for row in rows},
        )
        for row in rows:
            if row.response_field_id in closed:
                db.delete(row)
                removed += 1
    if removed:
        db.flush()
    return removed
