"""Group-scoped response reconciliation — the Segment 13C / 18H
machinery that fans a single group answer out to every member's
Response row and collapses N member rows back to one on read, plus
``clear_changed_groups``: a change that redraws a group clears it
(author's ruling 2026-10-17, which retired the 18H re-fan).

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


Pair = tuple[int, int]


def _instrument_groups(
    db: Session, *, session_id: int, instrument_id: int
) -> tuple[list[frozenset[Pair]], dict[Pair, int]]:
    """The instrument's groups, one set per reviewer and group key; on
    an Individual instrument each row is a group of its own. A member
    is its ``(reviewer_id, reviewee_id)`` pair, unique on an instrument,
    rather than its assignment id: SQLite reuses the highest id once
    it is deleted, so a reconcile that drops one row and inserts
    another could otherwise present a changed group as the same rows.
    Also returns each pair's assignment id, for the delete."""
    members = list(
        db.execute(
            select(Assignment).where(Assignment.instrument_id == instrument_id)
        ).scalars()
    )
    ids = {(m.reviewer_id, m.reviewee_id): m.id for m in members}
    keys = group_keys(db, assignments=members, session_id=session_id)
    if not keys:
        return [frozenset({pair}) for pair in ids], ids
    groups: dict[tuple[int, tuple[str, ...]], set[Pair]] = {}
    for member in members:
        groups.setdefault((member.reviewer_id, keys[member.id]), set()).add(
            (member.reviewer_id, member.reviewee_id)
        )
    return [frozenset(pairs) for pairs in groups.values()], ids


def session_group_instrument_ids(
    db: Session, *, session_id: int, source_type: str | None = None
) -> set[int]:
    """The session's group-scoped instruments, or only those whose
    boundary reads a ``source_type`` tag (``"reviewee"`` /
    ``"pair_context"``)."""
    from app.services import instruments as instruments_service

    return {
        instrument.id
        for instrument in db.execute(
            select(Instrument).where(
                Instrument.session_id == session_id,
                Instrument.group_kind.is_not(None),
            )
        ).scalars()
        if source_type is None
        or any(
            kind == source_type
            for kind, _ in instruments_service.decode_group_kind(
                instrument.group_kind
            )
        )
    }


GroupPartitions = dict[int, set[frozenset[Pair]]]


def snapshot_group_partitions(
    db: Session, *, session_id: int, instrument_ids: set[int]
) -> GroupPartitions:
    """Each listed instrument's groups, taken **before** a change that
    could redraw them, for :func:`clear_changed_groups`. Only
    instruments holding an answer are listed: with nothing answered a
    change has nothing to clear."""
    if not instrument_ids:
        return {}
    answered = set(
        db.execute(
            select(Assignment.instrument_id)
            .join(Response, Response.assignment_id == Assignment.id)
            .where(Assignment.instrument_id.in_(instrument_ids))
            .distinct()
        ).scalars()
    )
    return {
        instrument_id: set(
            _instrument_groups(
                db, session_id=session_id, instrument_id=instrument_id
            )[0]
        )
        for instrument_id in answered
    }


def clear_changed_groups(
    db: Session, *, session_id: int, before: GroupPartitions
) -> int:
    """Delete the answers of every group whose rows changed since
    ``before`` (author's ruling 2026-10-17: a group instrument's
    subject is the group, so a group whose members changed is a
    different subject and its reviewer answers it again).

    The one rule behind every change that can redraw a group: an
    instrument's boundary tags or unit of review (findings E2), a
    reviewee's boundary tag, any relationship change (a tag edit, a
    re-point, a create, import, delete, or a status switch, since an
    inactive or missing relationship reads as empty tags), and Generate
    adding or removing a member. A group whose rows are not exactly one
    group's rows in ``before`` has all its rows' answers deleted, so a
    split clears both halves, a member moving clears the group it left
    and the group it joined, and a new member clears its group. A group
    that came through with the same rows keeps its answer, so a change
    that redraws nothing (an unchanged re-import, a re-point with no
    tags) deletes nothing. No answer is copied onto a row. The caller
    flushes the change first. Returns the number of ``Response`` rows
    deleted."""
    changed: set[int] = set()
    for instrument_id, groups in before.items():
        after, ids = _instrument_groups(
            db, session_id=session_id, instrument_id=instrument_id
        )
        for group in after:
            if group not in groups:
                changed |= {ids[pair] for pair in group}
    if not changed:
        return 0
    # Deleted by assignment, not by response id: one bound parameter per
    # row rather than one per row and field.
    return db.execute(
        delete(Response).where(Response.assignment_id.in_(changed))
    ).rowcount or 0


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
