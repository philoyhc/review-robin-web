"""Group-scoped response reconciliation — the Segment 13C / 18H
machinery that fans a single group answer out to every member's
Response row, collapses N member rows back to one on read, and
re-fans / defuncts rows when reviewees move between groups.

Carved out of the legacy single-file ``responses.py`` in Segment
18N PR 4 — that file had grown to 1,444 LOC across two
substantially distinct concerns: the core save / submit / state-
rollup flow and this group-reconciliation layer. The 13C
fan-out + collapse + reconcile invariants form a self-contained
subdomain that the core flow calls into (via the public
``group_keys`` / ``group_key_for_pair`` / ``_expand_group_upserts``
seam) but doesn't otherwise share helpers with — a clean lift.

Cross-slice reads (all uni-directional):

- ``app.services.instruments.decode_group_kind`` — local import
  inside ``_group_key_by_assignment`` to read each instrument's
  ``group_kind`` codec.
- ``app.services.relationships.pair_context_lookup`` — local
  import inside ``_group_key_by_assignment`` for the pair-context
  tags that compose a group key.

The core ``_core.py`` module reads from this slice
(``_expand_group_upserts``, ``_group_instrument_ids``,
``_group_key_by_assignment``, ``_session_position_map``,
``group_keys``); nothing flows the other way.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Response,
    Reviewee,
)
from app.schemas.responses import ResponseUpsert
from app.services.responses._branch_rule import drop_closed_branch_answers


class GroupKeyable(Protocol):
    """What :func:`group_keys` reads off an assignment row.

    Five attributes — stated as a protocol rather than as
    ``Assignment`` because 19S Item 3 needed the same computation over
    a column-tuple projection
    (``app.services.assignments.AssignmentPair``) to stop the
    self-review recompute re-materializing the whole session as
    entities. ``Assignment`` satisfies it structurally, so both
    shapes go through one function rather than a variant each.

    **Documentation-grade, not enforced.** The repo runs ``ruff`` and
    ``pytest``, no type checker, so nothing fails if a caller stops
    satisfying this or if the function starts reading a sixth
    attribute. The five were verified by hand against
    :func:`_group_key_by_assignment` and :func:`group_keys` when this
    was written; treat it as a claim to re-check, not a guarantee.

    ``reviewee`` is the one that makes this a projection and not a
    tuple of ids: the group-boundary spec names reviewee fields
    dynamically, so :func:`group_key_for_pair` reaches it by
    ``getattr``.
    """

    @property
    def id(self) -> int: ...

    @property
    def instrument_id(self) -> int: ...

    @property
    def reviewer_id(self) -> int: ...

    @property
    def reviewee_id(self) -> int: ...

    @property
    def reviewee(self) -> Reviewee: ...


def _session_position_map(
    db: Session, session_id: int
) -> dict[int, int]:
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == session_id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    return {inst.id: idx + 1 for idx, inst in enumerate(instruments)}


def _group_instrument_ids(db: Session, instrument_ids: set[int]) -> set[int]:
    """Of ``instrument_ids``, the ones that are group-scoped — i.e.
    ``Instrument.group_kind`` is non-null (Segment 13C)."""
    if not instrument_ids:
        return set()
    return set(
        db.execute(
            select(Instrument.id)
            .where(Instrument.id.in_(instrument_ids))
            .where(Instrument.group_kind.is_not(None))
        ).scalars()
    )


def _group_key_by_assignment(
    db: Session,
    *,
    assignments: Sequence[GroupKeyable],
    group_instrument_ids: set[int],
    session_id: int,
) -> dict[int, tuple[str, ...]]:
    """The group key per assignment on a group-scoped instrument.

    Two assignments share a group iff their group keys match. The key
    is the tuple of the instrument's group-boundary tag values for
    that assignment's ``(reviewer, reviewee)`` pair — reviewee tags
    read off the reviewee, pair-context tags off the active
    ``Relationship`` row (inactive relationships resolve to an empty
    value, mirroring ``display_field_value``). A group-scoped
    instrument with no boundary tag yields the empty key ``()`` for
    every member — one group, the reviewer's whole universe.
    Assignments on per-reviewee instruments are absent from the map.
    """
    if not group_instrument_ids:
        return {}
    # Local imports — keep the module's import graph free of the
    # instruments / relationships services at load time.
    from app.services import instruments as instruments_service
    from app.services import relationships as relationships_service

    boundary_by_instrument: dict[int, list[tuple[str, str]]] = {}
    for instrument in db.execute(
        select(Instrument).where(Instrument.id.in_(group_instrument_ids))
    ).scalars():
        boundary_by_instrument[instrument.id] = (
            instruments_service.decode_group_kind(instrument.group_kind)
        )
    # The relationships table is only needed when some boundary tag
    # is pair-context-sourced; a reviewee-tag-only boundary (the
    # common case) skips the scan entirely.
    needs_pair_lookup = any(
        source_type == "pair_context"
        for boundary in boundary_by_instrument.values()
        for source_type, _ in boundary
    )
    pair_lookup = (
        relationships_service.pair_context_lookup(db, session_id)
        if needs_pair_lookup
        else {}
    )

    keys: dict[int, tuple[str, ...]] = {}
    for assignment in assignments:
        if assignment.instrument_id not in group_instrument_ids:
            continue
        keys[assignment.id] = group_key_for_pair(
            reviewee=assignment.reviewee,
            reviewer_id=assignment.reviewer_id,
            reviewee_id=assignment.reviewee_id,
            boundary=boundary_by_instrument.get(assignment.instrument_id, []),
            pair_context_lookup=pair_lookup,
        )
    return keys


def group_key_for_pair(
    *,
    reviewee: object,
    reviewer_id: int,
    reviewee_id: int,
    boundary: list[tuple[str, str]],
    pair_context_lookup: dict[tuple[int, int], object],
) -> tuple[str, ...]:
    """The group key for one ``(reviewer, reviewee)`` pair under a
    decoded group-boundary spec — the tuple of boundary tag values
    (reviewee tags read off ``reviewee``; pair-context tags off the
    active ``Relationship``). Shared by the assignment-keyed
    :func:`_group_key_by_assignment` and the Instruments-page
    reviewer-group pair count."""
    key: list[str] = []
    for source_type, source_field in boundary:
        if source_type == "reviewee":
            raw = getattr(reviewee, source_field, None)
        else:  # pair_context
            relationship = pair_context_lookup.get(
                (reviewer_id, reviewee_id)
            )
            raw = None
            if (
                relationship is not None
                and getattr(relationship, "status", None) == "active"
            ):
                raw = getattr(relationship, f"tag_{source_field}", None)
        key.append((raw or "").strip())
    return tuple(key)


def group_keys(
    db: Session, *, assignments: Sequence[GroupKeyable], session_id: int
) -> dict[int, tuple[str, ...]]:
    """Group key per assignment on a group-scoped instrument.

    Public wrapper over :func:`_group_key_by_assignment`: resolves the
    group-scoped instruments from ``assignments`` itself. Assignments
    on per-reviewee instruments are absent from the result; group
    instruments with no boundary tag map to the empty key ``()``.
    The reviewer surface uses this to partition a reviewer's rows
    into one group row per distinct key.

    Takes anything satisfying :class:`GroupKeyable` — an
    ``Assignment`` entity, or the ``AssignmentPair`` projection the
    self-review recompute builds (19S Item 3).
    """
    return _group_key_by_assignment(
        db,
        assignments=assignments,
        group_instrument_ids=_group_instrument_ids(
            db, {a.instrument_id for a in assignments}
        ),
        session_id=session_id,
    )


def _refan_group_responses(
    db: Session,
    *,
    session_id: int,
    assignment_ids: set[int],
) -> int:
    """Restore the group fan-out invariant for assignments whose
    group membership may have just changed (a boundary tag edit or
    a relationship re-point relocated them).

    A group-scoped instrument keeps **identical** answer copies on
    every assignment in a group; the reviewer surface and the
    state rollups read one representative row per group and trust
    that invariant. When a reviewee / pair is relocated *into* an
    already-answered group, its assignment has no fanned copy — so
    if it becomes the representative the group reads blank. Each
    listed assignment that has no responses but lands in a group
    whose other members *are* answered is given a copy of that
    group's answer (Segment 18H). Assignments that already carry
    responses, or whose new group is genuinely unanswered, are
    left as-is. Returns the number of ``Response`` rows written."""
    if not assignment_ids:
        return 0
    targets = list(
        db.execute(
            select(Assignment).where(Assignment.id.in_(assignment_ids))
        ).scalars()
    )
    if not targets:
        return 0
    group_instrument_ids = set(
        db.execute(
            select(Instrument.id).where(
                Instrument.id.in_({a.instrument_id for a in targets}),
                Instrument.group_kind.is_not(None),
            )
        ).scalars()
    )
    if not group_instrument_ids:
        return 0
    # Every assignment on the affected group instruments — needed
    # to resolve a relocated assignment's new group siblings.
    siblings = list(
        db.execute(
            select(Assignment).where(
                Assignment.instrument_id.in_(group_instrument_ids)
            )
        ).scalars()
    )
    keys = group_keys(db, assignments=siblings, session_id=session_id)
    by_group: dict[tuple[int, int, tuple[str, ...]], list[Assignment]] = {}
    for sib in siblings:
        group_key = keys.get(sib.id)
        if group_key is None:
            continue
        by_group.setdefault(
            (sib.reviewer_id, sib.instrument_id, group_key), []
        ).append(sib)

    # Every sibling's answer rows, read once: a bulk relationship change
    # can relocate a whole session's rows, and a query per target and
    # per sibling grew with the square of the group size (findings B34).
    rows_by_assignment: dict[int, list[Response]] = {}
    for row in db.execute(
        select(Response)
        .join(Assignment, Assignment.id == Response.assignment_id)
        .where(Assignment.instrument_id.in_(group_instrument_ids))
        .order_by(Response.id)
    ).scalars():
        rows_by_assignment.setdefault(row.assignment_id, []).append(row)

    written = 0
    refanned: set[int] = set()
    for target in targets:
        if target.instrument_id not in group_instrument_ids:
            continue
        group_key = keys.get(target.id)
        if group_key is None:
            continue
        # Already consistent — a non-relocated assignment keeps its
        # copy; skip it (and stay idempotent).
        if rows_by_assignment.get(target.id):
            continue
        source_rows: list[Response] = []
        for sib in by_group.get(
            (target.reviewer_id, target.instrument_id, group_key), []
        ):
            if sib.id == target.id:
                continue
            rows = rows_by_assignment.get(sib.id)
            if rows:
                source_rows = rows
                break
        copies = [
            Response(
                assignment_id=target.id,
                response_field_id=row.response_field_id,
                value=row.value,
                saved_at=row.saved_at,
                submitted_at=row.submitted_at,
                version=row.version,
            )
            for row in source_rows
        ]
        if copies:
            db.add_all(copies)
            # A later target in the same group may copy from this one;
            # either way the answer comes from the same answered
            # sibling, so the copies are identical.
            rows_by_assignment[target.id] = copies
            written += len(copies)
            refanned.add(target.id)
    if written:
        db.flush()
        # 19T Item 10 — the copies came from a sibling that already held
        # to the rule; checked here too, since every writer goes through
        # the one rule.
        drop_closed_branch_answers(db, refanned)
    return written


def reconcile_group_responses_for_tag_change(
    db: Session,
    *,
    reviewee: Reviewee,
    changed_tag_fields: set[str],
) -> int:
    """Reconcile group-scoped ``Response`` rows after ``reviewee``'s
    group-boundary tags changed.

    A group-scoped instrument's `group_key` is derived from the
    **reviewee's** boundary tags. When such a tag value changes the
    reviewee moves between groups: the answer copies fanned onto
    its assignments are mis-attributed and are **deleted** (Segment
    13C PR 5), and — so the reviewee's assignment surfaces its new
    group's answer rather than a blank representative row — the
    assignment is **re-fanned** from the new group (Segment 18H).
    Only instruments whose decoded boundary actually uses a changed
    tag are touched. Returns the number of ``Response`` rows
    deleted (the re-fan is a side effect).

    ``changed_tag_fields`` is the subset of ``{"tag_1", "tag_2",
    "tag_3"}`` whose value changed on this reviewee."""
    if not changed_tag_fields:
        return 0
    from app.services import instruments as instruments_service

    affected_instrument_ids: set[int] = set()
    for instrument in db.execute(
        select(Instrument).where(
            Instrument.session_id == reviewee.session_id,
            Instrument.group_kind.is_not(None),
        )
    ).scalars():
        boundary = instruments_service.decode_group_kind(
            instrument.group_kind
        )
        if any(
            source_type == "reviewee" and source_field in changed_tag_fields
            for source_type, source_field in boundary
        ):
            affected_instrument_ids.add(instrument.id)
    if not affected_instrument_ids:
        return 0

    target_assignment_ids = set(
        db.execute(
            select(Assignment.id).where(
                Assignment.reviewee_id == reviewee.id,
                Assignment.instrument_id.in_(affected_instrument_ids),
            )
        ).scalars()
    )
    response_ids = list(
        db.execute(
            select(Response.id).where(
                Response.assignment_id.in_(target_assignment_ids)
            )
        ).scalars()
    )
    if response_ids:
        db.execute(delete(Response).where(Response.id.in_(response_ids)))
    _refan_group_responses(
        db,
        session_id=reviewee.session_id,
        assignment_ids=target_assignment_ids,
    )
    return len(response_ids)


def _answered_pair_context_assignments(
    db: Session, *, session_id: int
) -> list[Assignment]:
    """Every assignment on a group instrument whose boundary reads a
    pair-context tag, or ``[]`` when none of those assignments carries
    an answer — with nothing fanned, a relationship change has nothing
    to mis-attribute."""
    from app.services import instruments as instruments_service

    instrument_ids = {
        instrument.id
        for instrument in db.execute(
            select(Instrument).where(
                Instrument.session_id == session_id,
                Instrument.group_kind.is_not(None),
            )
        ).scalars()
        if any(
            source_type == "pair_context"
            for source_type, _ in instruments_service.decode_group_kind(
                instrument.group_kind
            )
        )
    }
    if not instrument_ids:
        return []
    answered = db.execute(
        select(Response.id)
        .join(Assignment, Assignment.id == Response.assignment_id)
        .where(Assignment.instrument_id.in_(instrument_ids))
        .limit(1)
    ).first()
    if answered is None:
        return []
    return list(
        db.execute(
            select(Assignment).where(Assignment.instrument_id.in_(instrument_ids))
        ).scalars()
    )


def snapshot_pair_context_group_keys(
    db: Session, *, session_id: int
) -> dict[int, tuple[str, ...]]:
    """The group key of every assignment a relationship change could
    move, taken **before** the change, for
    :func:`reconcile_moved_pair_context_groups` to compare against.
    Empty when no pair-context group instrument has an answer yet."""
    targets = _answered_pair_context_assignments(db, session_id=session_id)
    if not targets:
        return {}
    return group_keys(db, assignments=targets, session_id=session_id)


def copy_group_answers_to_new_assignments(
    db: Session, *, session_id: int, assignment_ids: set[int]
) -> int:
    """Give each newly generated assignment on a group-scoped
    instrument its group's existing answer (findings B13, 2026-10-03).

    Generate inserts a new member's assignment with no responses; when
    its group is already answered, the per-row readers (extracts,
    counts, monitoring, the collation pool) would read that member as
    unanswered while the surface shows the group's answer. This is the
    re-fan half of the relocation path: rows that already carry
    responses, and groups nobody has answered, are left alone. The
    caller flushes the inserts first. Returns the number of
    ``Response`` rows written."""
    return _refan_group_responses(
        db, session_id=session_id, assignment_ids=assignment_ids
    )


def reconcile_moved_pair_context_groups(
    db: Session,
    *,
    session_id: int,
    before: dict[int, tuple[str, ...]],
) -> int:
    """Reconcile the group answer copies of every assignment whose
    pair-context group key moved since ``before`` was taken (findings
    B34).

    The pair-context counterpart of
    :func:`reconcile_group_responses_for_tag_change`, for every
    relationship change: a tag edit, a re-point, a relationship created,
    imported or deleted, or one switched active / inactive (an inactive
    or missing relationship reads as empty tags). A moved assignment's
    copies are mis-attributed, so they are deleted and it is re-fanned
    from its new group; when no other member of that group holds an
    answer, the answer is gone (author's ruling 2026-10-03). Only the
    assignments whose key changed are touched, so re-importing an
    unchanged file, or re-pointing a relationship with no tags, deletes
    nothing. The
    caller flushes the change first. Returns the number of
    ``Response`` rows deleted (the re-fan is a side effect)."""
    if not before:
        return 0
    targets = list(
        db.execute(
            select(Assignment).where(Assignment.id.in_(list(before)))
        ).scalars()
    )
    after = group_keys(db, assignments=targets, session_id=session_id)
    moved = {
        assignment_id
        for assignment_id, key in before.items()
        if assignment_id in after and after[assignment_id] != key
    }
    if not moved:
        return 0
    # Deleted by assignment, not by response id: one bound parameter per
    # moved row rather than one per row and field.
    defuncted = db.execute(
        delete(Response).where(Response.assignment_id.in_(moved))
    ).rowcount
    _refan_group_responses(db, session_id=session_id, assignment_ids=moved)
    return defuncted or 0


def _expand_group_upserts(
    upserts: list[ResponseUpsert],
    *,
    assignments: list[Assignment],
    group_instrument_ids: set[int],
    group_key_by_assignment: dict[int, tuple[str, ...]],
) -> list[ResponseUpsert]:
    """Fan a group-scoped instrument's upserts out to its group members.

    For a group-scoped instrument the reviewer answers once per group;
    each posted upsert is replicated to every assignment in the **same
    boundary-defined group** — the members sharing the upsert
    assignment's group key — so the single answer lands on that
    group's Response rows (Segment 13C "write fan-out"). The fan stays
    inside the group: members of a *different* group on the same
    instrument are untouched. Per-reviewee upserts pass through
    unchanged. Group upserts are first deduplicated per
    ``(instrument, group_key, field_key)`` — last value wins — so a
    payload that still carries one row per member (the interim before
    the reviewer surface collapses to one group row) does not blow up
    into N x N.
    """
    if not group_instrument_ids:
        return upserts
    assignment_instrument = {a.id: a.instrument_id for a in assignments}
    members_by_group: dict[tuple[int, tuple[str, ...]], list[int]] = {}
    for a in assignments:
        if a.instrument_id in group_instrument_ids:
            group_key = group_key_by_assignment.get(a.id, ())
            members_by_group.setdefault(
                (a.instrument_id, group_key), []
            ).append(a.id)

    passthrough: list[ResponseUpsert] = []
    group_value: dict[tuple[int, tuple[str, ...], str], str] = {}
    group_order: list[tuple[int, tuple[str, ...], str]] = []
    for upsert in upserts:
        instrument_id = assignment_instrument.get(upsert.assignment_id)
        if instrument_id is None or instrument_id not in group_instrument_ids:
            passthrough.append(upsert)
            continue
        group_key = group_key_by_assignment.get(upsert.assignment_id, ())
        key = (instrument_id, group_key, upsert.field_key)
        if key not in group_value:
            group_order.append(key)
        group_value[key] = upsert.value

    expanded = list(passthrough)
    for instrument_id, group_key, field_key in group_order:
        for member_id in members_by_group.get((instrument_id, group_key), []):
            expanded.append(
                ResponseUpsert(
                    assignment_id=member_id,
                    field_key=field_key,
                    value=group_value[(instrument_id, group_key, field_key)],
                )
            )
    return expanded
