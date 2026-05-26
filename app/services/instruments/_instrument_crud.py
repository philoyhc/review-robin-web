"""Instrument CRUD slice — instrument lifecycle (create / delete /
update description / update short_label) plus the default-
instrument seeding helpers and the session-level bulk
accepting / visibility toggles.

Slice 4 of the §12.A ladder (``guide/archive/major_refactor.md``) — the
final slice; with this file in place, ``_legacy.py`` is gone and
the instruments service package is fully sliced.

Owns the ``DEFAULT_INSTRUMENT_NAME`` constant and the seeding
helpers (``ensure_default_instrument`` /
``ensure_locked_display_fields``) that fire on session creation,
plus the post-creation mutation surface (``create_instrument`` /
``delete_instrument`` / ``update_instrument_description`` /
``update_short_label``) and the session-level bulk toggles
(``bulk_set_accepting`` / ``bulk_set_visibility``). Saves emit
``instrument.created`` / ``.deleted`` / ``.description_updated`` /
``.short_label_updated`` / ``instruments.bulk_accepting_responses``
/ ``instruments.bulk_visibility_when_closed`` audit events.

Source range in pre-PR-4 ``_legacy.py``: the entire file post-
PR-3 strip (~485 LOC).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Response,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import session_lifecycle as lifecycle
from app.services import audit
from app.services.instruments._response_fields import DEFAULT_RESPONSE_FIELDS
from app.services.instruments._state import _instrument_label

DEFAULT_INSTRUMENT_NAME = "Default"


def ensure_default_instrument(
    db: Session, review_session: ReviewSession
) -> Instrument:
    """Return the session's Default Instrument, creating it if missing,
    and ensuring it carries the default response fields and the locked
    Name / Email Display Fields rows."""
    instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.id)
    ).scalars().first()

    if instrument is None:
        instrument = Instrument(
            session_id=review_session.id,
            name=DEFAULT_INSTRUMENT_NAME,
            order=0,
            accepting_responses=False,
            responses_visible_when_closed=False,
        )
        db.add(instrument)
        db.flush()

    has_fields = (
        db.execute(
            select(InstrumentResponseField.id)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .limit(1)
        ).first()
        is not None
    )

    if not has_fields:
        from app.services.instruments._response_fields import (
            _inline_kwargs_from_default_spec,
            _validation_block_from_default_spec,
        )

        for spec in DEFAULT_RESPONSE_FIELDS:
            # iii-b2: default response fields carry data_type +
            # bounds inline (no RTD reference).
            db.add(
                InstrumentResponseField(
                    instrument_id=instrument.id,
                    field_key=spec["field_key"],
                    label=spec["label"],
                    required=spec["required"],
                    order=spec["order"],
                    validation=_validation_block_from_default_spec(spec),
                    **_inline_kwargs_from_default_spec(spec),
                )
            )
        db.flush()

    ensure_locked_display_fields(db, instrument=instrument)

    return instrument


def ensure_locked_display_fields(
    db: Session, *, instrument: Instrument
) -> int:
    """Idempotently seed the two locked Display Fields rows
    (RevieweeName, RevieweeEmail) on the given instrument. Returns the
    number of new rows created (0, 1, or 2). Rows that already exist
    are left alone — including their operator-typed labels."""
    existing_pairs = {
        (f.source_type, f.source_field) for f in instrument.display_fields
    }
    created = 0
    if ("reviewee", "name") not in existing_pairs:
        # New locked rows shift any existing rows up by 2 (or 1 if only
        # one is missing) so Name / Email always sit at the top.
        for f in instrument.display_fields:
            f.order = f.order + 1
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="",
                source_type="reviewee",
                source_field="name",
                order=0,
                visible=True,
            )
        )
        created += 1
    if ("reviewee", "email_or_identifier") not in existing_pairs:
        for f in instrument.display_fields:
            if (f.source_type, f.source_field) != ("reviewee", "name"):
                f.order = f.order + 1
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="",
                source_type="reviewee",
                source_field="email_or_identifier",
                order=1,
                visible=True,
            )
        )
        created += 1
    if created:
        db.flush()
        db.refresh(instrument)
    return created


def create_instrument(
    db: Session,
    *,
    review_session: ReviewSession,
    after_instrument_id: int | None = None,
    actor: User,
    group_kind: str | None = None,
) -> Instrument:
    """Create a new instrument seeded with default response and display
    fields. If ``after_instrument_id`` is given, slot the new instrument
    immediately after that one and bump subsequent ``order`` values; else
    append at the end.

    ``group_kind`` is the Segment 13C group-scoping flag — ``None``
    for an ordinary per-reviewee instrument, or a non-null value for
    a group-scoped one. A new group-scoped instrument is created
    with the no-boundary sentinel (``GROUP_KIND_SENTINEL``); the
    operator picks boundary tags later via ``set_group_boundary``.
    """
    lifecycle.invalidate_if_validated(
        db, review_session=review_session, user=actor, reason="instrument_added"
    )
    existing = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars().all()
    )

    new_order: int
    if after_instrument_id is None:
        new_order = (existing[-1].order + 1) if existing else 0
    else:
        anchor = next(
            (i for i in existing if i.id == after_instrument_id), None
        )
        if anchor is None:
            new_order = (existing[-1].order + 1) if existing else 0
        else:
            new_order = anchor.order + 1
            for inst in existing:
                if inst.order >= new_order:
                    inst.order += 1

    next_num = len(existing) + 1
    instrument = Instrument(
        session_id=review_session.id,
        name=f"instrument_{next_num}",
        order=new_order,
        accepting_responses=False,
        responses_visible_when_closed=False,
        group_kind=group_kind,
    )
    db.add(instrument)
    db.flush()

    from app.services.instruments._response_fields import (
        _inline_kwargs_from_default_spec,
        _validation_block_from_default_spec,
    )

    # iii-b2: the seeded RTD set is empty post-retirement; defaults
    # carry data_type + bounds inline on the spec dict.
    for spec in DEFAULT_RESPONSE_FIELDS:
        db.add(
            InstrumentResponseField(
                instrument_id=instrument.id,
                field_key=spec["field_key"],
                label=spec["label"],
                required=spec["required"],
                order=spec["order"],
                validation=_validation_block_from_default_spec(spec),
                **_inline_kwargs_from_default_spec(spec),
            )
        )
    db.flush()
    ensure_locked_display_fields(db, instrument=instrument)

    # Replicate assignment rows from any existing instrument so the
    # new instrument joins the matrix on every (reviewer, reviewee)
    # pair that's already assigned. Without this, full-matrix +
    # instrument.add leaves the new instrument with zero
    # assignments — the reviewer surface then hides its Page button
    # because it has nothing to render. Pick the lowest-ordered
    # existing instrument as the source so the clone is
    # deterministic; the (reviewer, reviewee, include, context)
    # tuples are identical across instruments today, so any source
    # would yield the same rows.
    cloned_assignments = 0
    if existing:
        source_instrument = existing[0]
        source_rows = list(
            db.execute(
                select(Assignment)
                .where(Assignment.session_id == review_session.id)
                .where(Assignment.instrument_id == source_instrument.id)
            ).scalars()
        )
        for source in source_rows:
            db.add(
                Assignment(
                    session_id=review_session.id,
                    reviewer_id=source.reviewer_id,
                    reviewee_id=source.reviewee_id,
                    instrument_id=instrument.id,
                    include=source.include,
                    created_by_mode=source.created_by_mode,
                )
            )
            cloned_assignments += 1
        db.flush()

    created_refs: dict[str, int] = {"instrument_id": instrument.id}
    if after_instrument_id is not None:
        created_refs["after_instrument_id"] = after_instrument_id
    audit.write_event(
        db,
        event_type="instrument.created",
        summary=f"Created instrument {instrument.name}",
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.snapshot(
            {
                "id": instrument.id,
                "name": instrument.name,
                "order": new_order,
                "description": instrument.description,
                "short_label": instrument.short_label,
            }
        ),
        refs=created_refs,
        context={"cloned_assignments": cloned_assignments},
    )
    db.commit()
    return instrument


def replicate_instrument(
    db: Session,
    *,
    review_session: ReviewSession,
    source: Instrument,
    actor: User,
) -> Instrument:
    """Clone an instrument's content into a new instrument slotted
    immediately after the source (Segment 13C PR 3).

    Copies the description, the response fields (incl. each
    field's help text), the display fields (incl. each row's
    ``visible`` Include flag), ``group_kind``, and
    ``sort_display_fields``. The copy's name is the source name +
    " (copy)"; it starts ``accepting_responses=False`` and carries
    **no** pinned rule (``rule_set_id``) — the operator pins one
    before opening it. Assignment rows are cloned from the source
    so the replica joins the matrix immediately, mirroring
    :func:`create_instrument`."""
    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=actor,
        reason="instrument_replicated",
    )
    existing = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    new_order = source.order + 1
    for inst in existing:
        if inst.order >= new_order:
            inst.order += 1

    instrument = Instrument(
        session_id=review_session.id,
        name=f"{source.name} (copy)",
        description=source.description,
        order=new_order,
        accepting_responses=False,
        responses_visible_when_closed=False,
        group_kind=source.group_kind,
        sort_display_fields=(
            [dict(entry) for entry in source.sort_display_fields]
            if source.sort_display_fields
            else source.sort_display_fields
        ),
    )
    db.add(instrument)
    db.flush()

    source_fields = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == source.id
        )
    ).scalars()
    for field in source_fields:
        db.add(
            InstrumentResponseField(
                instrument_id=instrument.id,
                field_key=field.field_key,
                label=field.label,
                required=field.required,
                order=field.order,
                validation=(
                    dict(field.validation)
                    if field.validation is not None
                    else None
                ),
                help_text=field.help_text,
                help_text_visible=field.help_text_visible,
                _inline_data_type=field._inline_data_type,
                _inline_response_type=field._inline_response_type,
                _inline_min=field._inline_min,
                _inline_max=field._inline_max,
                _inline_step=field._inline_step,
                _inline_list_csv=field._inline_list_csv,
            )
        )
    source_displays = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == source.id
        )
    ).scalars()
    for display in source_displays:
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label=display.label,
                source_type=display.source_type,
                source_field=display.source_field,
                order=display.order,
                visible=display.visible,
            )
        )
    db.flush()

    cloned_assignments = 0
    source_rows = db.execute(
        select(Assignment).where(Assignment.instrument_id == source.id)
    ).scalars()
    for source_row in source_rows:
        db.add(
            Assignment(
                session_id=review_session.id,
                reviewer_id=source_row.reviewer_id,
                reviewee_id=source_row.reviewee_id,
                instrument_id=instrument.id,
                include=source_row.include,
                created_by_mode=source_row.created_by_mode,
            )
        )
        cloned_assignments += 1
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.replicated",
        summary=f"Replicated instrument {source.name}",
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.snapshot(
            {
                "id": instrument.id,
                "name": instrument.name,
                "order": new_order,
            }
        ),
        refs={
            "instrument_id": instrument.id,
            "source_instrument_id": source.id,
        },
        context={"cloned_assignments": cloned_assignments},
    )
    db.commit()
    return instrument


def delete_instrument(
    db: Session,
    *,
    instrument: Instrument,
    actor: User,
) -> int:
    """Delete an instrument plus all its dependent rows (display/response
    fields, assignments, responses) via cascade, then re-pack the
    surviving instruments' ``order`` values to ``0..N-1``. Returns the
    deleted instrument's id.
    """
    review_session = instrument.session
    lifecycle.invalidate_if_validated(
        db, review_session=review_session, user=actor, reason="instrument_deleted"
    )
    deleted_id = instrument.id
    deleted_name = instrument.name
    deleted_order = instrument.order

    db.delete(instrument)
    db.flush()

    remaining = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars().all()
    )
    for idx, inst in enumerate(remaining):
        if inst.order != idx:
            inst.order = idx
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.deleted",
        summary=f"Deleted instrument {deleted_name}",
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.snapshot(
            {"id": deleted_id, "name": deleted_name, "order": deleted_order}
        ),
        refs={"instrument_id": deleted_id},
    )
    db.commit()
    return deleted_id


def update_instrument_description(
    db: Session,
    *,
    instrument: Instrument,
    description: str | None,
    actor: User,
) -> Instrument:
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_described",
    )
    cleaned = description.strip() if isinstance(description, str) else None
    new_value = cleaned or None
    old_value = instrument.description
    instrument.description = new_value
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.described",
        summary=f"Updated description on instrument {instrument.name}",
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes({"description": [old_value, new_value]}),
        refs={"instrument_id": instrument.id},
    )
    db.commit()
    return instrument


def update_short_label(
    db: Session,
    *,
    instrument: Instrument,
    short_label: str | None,
    actor: User,
) -> Instrument:
    """Update an instrument's reviewer-facing short label (Segment 11L).

    Trims whitespace; persists ``None`` when the trimmed value is
    empty (so the reviewer surface's "no friendly label set" fallback
    kicks in). Raises ``ValueError`` when the trimmed value exceeds
    32 chars — the HTML5 ``maxlength`` attribute on the operator-side
    input is the user-visible guardrail, but the server-side cap is
    the bedrock guard. Emits an ``instrument.short_label_updated``
    audit event only when the stored value actually changes
    (no-op edits don't write events or invalidate ``validated``).

    Mirrors the shape of :func:`update_instrument_description` so
    the two read as siblings.
    """
    cleaned = short_label.strip() if isinstance(short_label, str) else None
    new_value = cleaned or None
    if new_value is not None and len(new_value) > 32:
        raise ValueError(
            f"short_label exceeds 32 chars: {len(new_value)}"
        )
    if instrument.short_label == new_value:
        return instrument  # no-op; no audit, no invalidate
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_short_label_updated",
    )
    old_value = instrument.short_label
    instrument.short_label = new_value
    db.flush()
    audit.write_event(
        db,
        event_type="instrument.short_label_updated",
        summary=(
            f"Updated short_label on instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes({"short_label": [old_value, new_value]}),
        refs={"instrument_id": instrument.id},
    )
    db.commit()
    return instrument


_BAND1_REQUIRED_LINKS: frozenset[str] = frozenset({"link1", "link2", "link3"})


def is_configured(db: Session, instrument: Instrument) -> bool:
    """True iff this instrument has the minimum setup needed to
    function in an activated session.

    Wave 5 PR 5.3 collapsed the legacy / new-model distinction.
    Every instrument needs:

    - at least one ``visible=True``
      :class:`InstrumentResponseField` (without one, the reviewer
      page renders zero rows even though assignments exist); and
    - all three Band 1 link pills (Pool of reviewers / Pool of
      those reviewed / Unit of review) deliberately clicked into
      a set state — see ``Instrument.band1_touched_links`` for
      the "Not set" pill safety gate. Untouched links still default
      to Full Matrix at evaluate time (Wave 4 PR 1); the gate
      forces the operator to acknowledge them on the card before
      the workflow card lights up as ready.
    """
    visible_count = db.scalar(
        select(func.count(InstrumentResponseField.id))
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .where(InstrumentResponseField.visible.is_(True))
    ) or 0
    if visible_count <= 0:
        return False
    touched = set(instrument.band1_touched_links or [])
    return _BAND1_REQUIRED_LINKS.issubset(touched)


def has_unconfigured(db: Session, session_id: int) -> bool:
    """True iff the session has zero instruments, or any instrument
    fails :func:`is_configured`. Drives the Next Action card's
    "Empty Setup" state.
    """
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == session_id)
        ).scalars()
    )
    if not instruments:
        return True
    instrument_ids = [inst.id for inst in instruments]
    # Batched: which instruments have at least one visible response field?
    rows = db.execute(
        select(InstrumentResponseField.instrument_id)
        .where(InstrumentResponseField.instrument_id.in_(instrument_ids))
        .where(InstrumentResponseField.visible.is_(True))
        .distinct()
    ).all()
    configured_ids = {row[0] for row in rows}
    for inst in instruments:
        if inst.id not in configured_ids:
            return True
        if not _BAND1_REQUIRED_LINKS.issubset(
            set(inst.band1_touched_links or [])
        ):
            return True
    return False


def has_unpinned(db: Session, session_id: int) -> bool:
    """True iff the session has zero instruments, or any instrument
    has a NULL ``rule_set_id``. Drives the Next Action card's
    "Empty Setup" state — a session isn't ready to validate until
    every instrument has its assignment rule pinned."""
    total = db.scalar(
        select(func.count(Instrument.id)).where(
            Instrument.session_id == session_id
        )
    ) or 0
    if total == 0:
        return True
    unpinned = db.scalar(
        select(func.count(Instrument.id)).where(
            Instrument.session_id == session_id,
            Instrument.rule_set_id.is_(None),
        )
    ) or 0
    return unpinned > 0


def pin_rule_set(
    db: Session,
    *,
    instrument: Instrument,
    rule_set_id: int | None,
    actor: User,
) -> Instrument:
    """Pin (or clear) the ``session_rule_sets`` row this instrument
    applies (Segment 15B Slice 2a).

    ``rule_set_id=None`` clears the pin back to "— No rule —" — the
    initial post-13D PR 4 state. A non-NULL value must reference a
    ``session_rule_sets`` row in the *same* session as the instrument;
    cross-session pins raise ``ValueError``.

    Pinning is **PIN only** — no ``Assignment`` rows are touched and
    no ``assignments.generated`` event fires. Materialisation happens
    on the explicit Generate surfaces (Slice 3a / Slice 4). No-op
    saves (same id) skip the audit + ``invalidate_if_validated``
    side effects, mirroring the convention in
    :func:`update_short_label`.
    """
    if rule_set_id is not None:
        rule_set = db.get(SessionRuleSet, rule_set_id)
        if rule_set is None or rule_set.session_id != instrument.session_id:
            raise ValueError(
                f"rule_set_id {rule_set_id} is not a session_rule_sets "
                f"row in session {instrument.session_id}"
            )
    if instrument.rule_set_id == rule_set_id:
        return instrument
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_rule_pinned",
    )
    old_value = instrument.rule_set_id
    instrument.rule_set_id = rule_set_id
    db.flush()
    audit.write_event(
        db,
        event_type="instrument.rule_pinned",
        summary=(
            f"Pinned rule on instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes({"rule_set_id": [old_value, rule_set_id]}),
        refs={"instrument_id": instrument.id},
    )
    db.commit()
    return instrument


# ---------------------------------------------------------------------------
# Group-boundary tags (Segment 13C PR 2 slice A)
# ---------------------------------------------------------------------------
#
# A group-scoped instrument's ``group_kind`` column encodes its
# group-boundary spec — an ordered, comma-separated list of tag
# key-codes (``r1``-``r3`` reviewee tags, ``p1``-``p3`` pair-context
# tags). A group-scoped instrument with no boundary tag keeps the
# sentinel ``"both"`` so the column stays non-null (non-null is the
# group-scoped flag). See ``spec/group_scoped_instruments.md``.

GROUP_KIND_SENTINEL = "both"

_GROUP_BOUNDARY_CODE_BY_SOURCE: dict[tuple[str, str], str] = {
    ("reviewee", "tag_1"): "r1",
    ("reviewee", "tag_2"): "r2",
    ("reviewee", "tag_3"): "r3",
    ("pair_context", "1"): "p1",
    ("pair_context", "2"): "p2",
    ("pair_context", "3"): "p3",
}
_GROUP_BOUNDARY_SOURCE_BY_CODE: dict[str, tuple[str, str]] = {
    code: pair for pair, code in _GROUP_BOUNDARY_CODE_BY_SOURCE.items()
}


def encode_group_kind(boundary_pairs: list[tuple[str, str]]) -> str:
    """Encode an ordered list of boundary ``(source_type, source_field)``
    pairs into the ``group_kind`` column string. An empty list (no
    boundary tag) encodes to the no-boundary sentinel. Pairs that
    are not boundary-eligible tags are skipped."""
    codes: list[str] = []
    for pair in boundary_pairs:
        code = _GROUP_BOUNDARY_CODE_BY_SOURCE.get(pair)
        if code is not None and code not in codes:
            codes.append(code)
    return ",".join(codes) if codes else GROUP_KIND_SENTINEL


def decode_group_kind(group_kind: str | None) -> list[tuple[str, str]]:
    """Decode a ``group_kind`` column string into its ordered list of
    boundary ``(source_type, source_field)`` pairs. ``None`` (a
    per-reviewee instrument) and the no-boundary sentinel both decode
    to ``[]``; unrecognised codes are skipped."""
    if not group_kind:
        return []
    pairs: list[tuple[str, str]] = []
    for code in group_kind.split(","):
        pair = _GROUP_BOUNDARY_SOURCE_BY_CODE.get(code.strip())
        if pair is not None and pair not in pairs:
            pairs.append(pair)
    return pairs


def group_boundary_pairs(instrument: Instrument) -> set[tuple[str, str]]:
    """Set of ``(source_type, source_field)`` pairs that are
    group-boundary tags on this instrument. Empty for a per-reviewee
    instrument or a group instrument with no boundary tag. A
    template-facing convenience over :func:`decode_group_kind`."""
    return set(decode_group_kind(instrument.group_kind))


def set_group_boundary(
    db: Session,
    *,
    instrument: Instrument,
    boundary_pairs: list[tuple[str, str]],
    actor: User,
) -> Instrument:
    """Persist a group-scoped instrument's group-boundary spec.

    ``boundary_pairs`` is the ordered list of tag
    ``(source_type, source_field)`` pairs the operator ticked
    *Group by* on the Display Fields table. It is encoded into the
    ``group_kind`` column; an empty list stores the no-boundary
    sentinel so the column stays non-null. No-op saves skip the
    audit + lifecycle side effects.

    Only valid on a group-scoped instrument (``group_kind`` already
    non-null); raises ``ValueError`` on a per-reviewee instrument.
    """
    if instrument.group_kind is None:
        raise ValueError(
            "set_group_boundary is only valid on a group-scoped instrument."
        )
    new_value = encode_group_kind(boundary_pairs)
    if instrument.group_kind == new_value:
        return instrument
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_group_boundary_updated",
    )
    old_value = instrument.group_kind
    instrument.group_kind = new_value
    db.flush()
    audit.write_event(
        db,
        event_type="instrument.group_boundary_updated",
        summary=(
            f"Updated group boundary on instrument "
            f"{_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes({"group_kind": [old_value, new_value]}),
        refs={"instrument_id": instrument.id},
    )
    db.commit()
    return instrument


def set_unit_of_review(
    db: Session,
    *,
    instrument: Instrument,
    mode: str,
    boundary_pairs: list[tuple[str, str]],
    actor: User,
    touched: bool = False,
) -> Instrument:
    """Set the instrument's unit-of-review (Link 3 of the new-model
    instrument builder).

    ``mode`` is ``"individual"`` or ``"grouped"``. Individual stores
    ``group_kind=NULL``; Grouped encodes ``boundary_pairs`` into
    ``group_kind`` via :func:`encode_group_kind` (with the no-boundary
    sentinel ``GROUP_KIND_SENTINEL`` when ``boundary_pairs`` is empty).

    Unlike :func:`set_group_boundary` this helper accepts both
    transitions (``individual ⇄ grouped``); it is the Band 1 writer
    for new-model instruments where the operator picks the unit
    inline. No-op saves skip the audit + lifecycle side effects.
    """
    if mode == "individual":
        new_value: str | None = None
    elif mode == "grouped":
        new_value = encode_group_kind(boundary_pairs)
    else:
        raise ValueError(
            f"unit_of_review mode must be 'individual' or 'grouped'; "
            f"got {mode!r}"
        )
    existing_touched = set(instrument.band1_touched_links or [])
    desired_touched = (
        (existing_touched | {"link3"}) if touched
        else (existing_touched - {"link3"})
    )
    if desired_touched != existing_touched:
        instrument.band1_touched_links = sorted(desired_touched)
        db.flush()
    if instrument.group_kind == new_value:
        return instrument
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_unit_of_review_updated",
    )
    old_value = instrument.group_kind
    instrument.group_kind = new_value
    db.flush()
    audit.write_event(
        db,
        event_type="instrument.group_boundary_updated",
        summary=(
            f"Set unit of review on instrument "
            f"{_instrument_label(instrument)} to "
            f"{'grouped' if new_value is not None else 'individual'}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes({"group_kind": [old_value, new_value]}),
        refs={"instrument_id": instrument.id},
    )
    return instrument


_COLUMN_WIDTH_MIN_PX = 40
_COLUMN_WIDTH_MAX_PX = 1200


def set_column_widths(
    db: Session,
    *,
    instrument: Instrument,
    widths: dict[str, int],
    actor: User,
) -> Instrument:
    """Persist the per-column pixel widths the operator set by
    drag-resizing the new-model card's Band 2 preview table.

    ``widths`` is a dict keyed by ``"identity"`` and
    ``"df_<display_field_id>"`` strings, valued by positive integer
    pixels. Unknown keys are dropped; values are clamped to
    ``[_COLUMN_WIDTH_MIN_PX, _COLUMN_WIDTH_MAX_PX]``. Passing an
    empty dict clears all custom widths back to NULL — the
    reviewer surface falls back to its default auto-sized layout.

    No-op saves (the merged widths are byte-equal to the stored
    value) skip the audit + lifecycle side effects.
    """
    valid_display_field_ids = {f.id for f in instrument.display_fields}
    valid_response_field_ids = {f.id for f in instrument.response_fields}
    sanitised: dict[str, int] = {}
    for raw_key, raw_value in (widths or {}).items():
        key = str(raw_key).strip()
        if (
            key != "identity"
            and not key.startswith("df_")
            and not key.startswith("rf_")
        ):
            continue
        if key.startswith("df_"):
            try:
                field_id = int(key[len("df_"):])
            except (TypeError, ValueError):
                continue
            if field_id not in valid_display_field_ids:
                continue
        elif key.startswith("rf_"):
            # Wave 3 PR iii — response-field column widths migrated from
            # band2_state.response_fields[i].width_px into column_widths.
            # Validate against the instrument's actual response field
            # ids the same way df_ keys validate against display field
            # ids.
            try:
                field_id = int(key[len("rf_"):])
            except (TypeError, ValueError):
                continue
            if field_id not in valid_response_field_ids:
                continue
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            continue
        if value < _COLUMN_WIDTH_MIN_PX:
            value = _COLUMN_WIDTH_MIN_PX
        elif value > _COLUMN_WIDTH_MAX_PX:
            value = _COLUMN_WIDTH_MAX_PX
        sanitised[key] = value
    new_value: dict[str, int] | None = sanitised or None
    if (instrument.column_widths or None) == new_value:
        return instrument
    old_value = instrument.column_widths
    instrument.column_widths = new_value
    db.flush()
    audit.write_event(
        db,
        event_type="instrument.column_widths_updated",
        summary=(
            f"Updated reviewer-surface column widths on instrument "
            f"{_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes(
            {"column_widths": [old_value, new_value]}
        ),
        refs={"instrument_id": instrument.id},
    )
    return instrument


_BAND2_ALLOWED_DISPLAY_KEYS: frozenset[str] = frozenset(
    {
        "reviewee.name",
        "reviewee.email_or_identifier",
        "reviewee.profile_link",
        "reviewee.tag_1",
        "reviewee.tag_2",
        "reviewee.tag_3",
        "pair_context.tag_1",
        "pair_context.tag_2",
        "pair_context.tag_3",
    }
)
_BAND2_ALLOWED_DATA_TYPES: frozenset[str] = frozenset(
    {"string", "integer", "decimal", "list"}
)
_BAND2_RF_BOUND_KEYS: tuple[str, ...] = (
    "min",
    "max",
    "step",
    "list_options",
)


def set_band2_state(
    db: Session,
    *,
    instrument: Instrument,
    state: dict[str, Any],
    actor: User,
) -> Instrument:
    """Persist the operator's Band 2 selections + response-field
    definitions on a new-model instrument card.

    ``state`` is the JSON blob described in the
    ``e7c2b4d9a3f1_add_instruments_band2_state`` migration docstring:

    - ``selected_display_keys``: list of canonical pill identifiers
      (``"reviewee.name"`` etc.) the operator has toggled into the
      preview row. Unknown keys are dropped silently.
    - ``response_fields``: ordered list of dicts describing each
      response-field row the operator has committed (via the ✓
      button). Each dict carries ``name`` (str, required, ≤255
      chars), ``data_type`` (one of ``string`` / ``integer`` /
      ``decimal`` / ``list``), ``min`` / ``max`` / ``step`` /
      ``list_options`` (str, optional), and ``selected`` (bool).

    Passing ``None`` (or a payload that reduces to empty
    selections + zero response_fields) clears ``band2_state``
    back to NULL — the new-model card falls back to its default
    "nothing selected, no response fields" shape.

    No-op saves (the merged payload matches what's already
    persisted) skip the audit + lifecycle side effects.
    """
    sanitised: dict[str, Any] = {}
    existing = instrument.band2_state or {}
    # Field-presence semantics: every top-level key in band2_state
    # is independently writable. A payload that *omits* a key
    # carries the existing value forward; a payload that *includes*
    # a key (even with an empty value) replaces it. This lets the
    # pill-toggle save send only ``selected_display_keys`` without
    # nuking the operator's ``response_fields`` or
    # ``sample_reviewee_name``, and lets ↻ Refresh send only
    # ``sample_reviewee_name`` without nuking the pill / RF state.
    selected_keys_in_payload = (
        isinstance(state, dict) and "selected_display_keys" in state
    )
    if selected_keys_in_payload:
        raw_keys = state.get("selected_display_keys")
        if isinstance(raw_keys, list):
            sanitised_keys: list[str] = []
            for raw in raw_keys:
                k = str(raw).strip()
                if k in _BAND2_ALLOWED_DISPLAY_KEYS and k not in sanitised_keys:
                    sanitised_keys.append(k)
            if sanitised_keys:
                sanitised["selected_display_keys"] = sanitised_keys
            # Gap 1: propagate the pill selection to
            # ``InstrumentDisplayField.visible`` so the reviewer
            # surface honours the operator's pill toggles. Locked
            # Name / Email rows stay visible regardless.
            _sync_display_field_visibility(
                db,
                instrument=instrument,
                selected_keys=set(sanitised_keys)
                if isinstance(raw_keys, list)
                else None,
                actor=actor,
            )
    else:
        existing_keys = existing.get("selected_display_keys")
        if isinstance(existing_keys, list) and existing_keys:
            sanitised["selected_display_keys"] = list(existing_keys)
    # Wave 3 PR iii — sanitised response_fields is no longer
    # persisted into band2_state JSON. It still gets built as a
    # local list, sent through ``_sync_response_fields_to_db`` to
    # land on real ``InstrumentResponseField`` rows, then dropped.
    # Per-response-field width_px values (if any) get peeled off
    # into the parallel ``column_widths`` update below.
    incoming_rfs: list[dict[str, Any]] | None = None
    rf_widths_by_id: dict[int, int] = {}
    rf_widths_by_name: dict[str, int] = {}
    if isinstance(state, dict) and "response_fields" in state:
        raw_rfs = state.get("response_fields")
        if isinstance(raw_rfs, list):
            incoming_rfs = []
            for raw in raw_rfs:
                if not isinstance(raw, dict):
                    continue
                name = str(raw.get("name") or "").strip()[:255]
                if not name:
                    continue
                data_type = str(raw.get("data_type") or "string").strip().lower()
                if data_type not in _BAND2_ALLOWED_DATA_TYPES:
                    data_type = "string"
                rf: dict[str, Any] = {"name": name, "data_type": data_type}
                raw_id = raw.get("id")
                if isinstance(raw_id, int) and raw_id > 0:
                    rf["id"] = raw_id
                elif isinstance(raw_id, str) and raw_id.strip().isdigit():
                    rf["id"] = int(raw_id)
                for bound_key in _BAND2_RF_BOUND_KEYS:
                    value = raw.get(bound_key)
                    rf[bound_key] = str(value).strip()[:255] if value is not None else ""
                rf["selected"] = bool(raw.get("selected"))
                rf["required"] = bool(raw.get("required"))
                rf["help_text_visible"] = bool(raw.get("help_text_visible"))
                help_text_raw = raw.get("help_text")
                rf["help_text"] = (
                    str(help_text_raw)[:1000] if help_text_raw is not None else ""
                )
                # Wave 3 PR iii — per-response-field column width (px)
                # moves out of band2_state JSON into the canonical
                # ``column_widths`` dict on the instrument under
                # ``rf_<id>`` keys, alongside ``df_<id>`` and
                # ``identity``. Captured here keyed by id when we know
                # one, by name otherwise; the dual-write below
                # back-fills the id and we re-key by id afterwards.
                raw_width = raw.get("width_px")
                if raw_width not in (None, ""):
                    try:
                        width_int = int(raw_width)
                    except (TypeError, ValueError):
                        width_int = 0
                    if width_int >= _COLUMN_WIDTH_MIN_PX:
                        clamped = min(width_int, _COLUMN_WIDTH_MAX_PX)
                        rf_id = rf.get("id")
                        if isinstance(rf_id, int):
                            rf_widths_by_id[rf_id] = clamped
                        else:
                            rf_widths_by_name[name] = clamped
                incoming_rfs.append(rf)
    if isinstance(state, dict) and "sample_reviewee_name" in state:
        candidate = str(state.get("sample_reviewee_name") or "").strip()[:255]
        if candidate:
            sanitised["sample_reviewee_name"] = candidate
    else:
        existing_sample = existing.get("sample_reviewee_name")
        if existing_sample:
            sanitised["sample_reviewee_name"] = str(existing_sample)[:255]
    # Gap 10: rule-surviving group member ID set persisted alongside
    # sample_reviewee_name by the preview-sample route. Present +
    # list-of-ints stores; present + None / non-list drops (e.g.
    # boundary switched off — render falls back to unconstrained
    # partition). Missing preserves existing.
    if isinstance(state, dict) and "sample_group_member_ids" in state:
        raw_ids = state.get("sample_group_member_ids")
        if isinstance(raw_ids, list):
            cleaned_ids: list[int] = []
            for raw in raw_ids:
                try:
                    rid = int(raw)
                except (TypeError, ValueError):
                    continue
                if rid > 0 and rid not in cleaned_ids:
                    cleaned_ids.append(rid)
            if cleaned_ids:
                sanitised["sample_group_member_ids"] = cleaned_ids
    else:
        existing_ids = existing.get("sample_group_member_ids")
        if isinstance(existing_ids, list) and existing_ids:
            sanitised["sample_group_member_ids"] = list(existing_ids)
    # Wave 3 PR iii — DB rows are now authoritative for response
    # fields; JSON ``response_fields`` retired. The dual-write helper
    # still runs but the previous-state reference switches from "ids
    # in the old JSON" to "ids of all current InstrumentResponseField
    # rows" so the delete contract becomes "any DB row not in the
    # incoming payload by id gets deleted." The (b) contract in
    # ``_new_model_band2_state`` (view layer) guarantees the first
    # render populates the payload from DB rows, so the JS always
    # round-trips the full id set on the next save — no row ever
    # surprises the delete check.
    if incoming_rfs is not None:
        previous_ids: set[int] = {f.id for f in instrument.response_fields}
        _sync_response_fields_to_db(
            db,
            instrument=instrument,
            sanitised_rfs=incoming_rfs,
            previous_json_ids=previous_ids,
            actor=actor,
        )
        # Now that ``_sync_response_fields_to_db`` has back-filled
        # ids on newly-created rows, re-key any name-bound widths
        # we set aside above and merge with the id-keyed widths.
        if rf_widths_by_name:
            name_to_id: dict[str, int] = {}
            for rf in incoming_rfs:
                rf_id = rf.get("id")
                if isinstance(rf_id, int):
                    name_to_id.setdefault(rf["name"], rf_id)
            for name, width in rf_widths_by_name.items():
                rf_id = name_to_id.get(name)
                if rf_id is not None:
                    rf_widths_by_id.setdefault(rf_id, width)
        # Merge incoming response-column widths into ``column_widths``.
        # Display-field widths + identity stay untouched. Refresh the
        # response_fields relationship first: ``_sync_response_fields_to_db``
        # ``db.add()``'d newly-created rows + flushed them, but the
        # relationship-loaded list on the instrument is stale, and
        # ``set_column_widths``'s validator (which builds the valid-
        # id set from that list) would otherwise drop ``rf_<new_id>``
        # keys as unknown.
        if rf_widths_by_id:
            db.refresh(instrument, attribute_names=["response_fields"])
            existing_widths = dict(instrument.column_widths or {})
            for rf_id, width in rf_widths_by_id.items():
                existing_widths[f"rf_{rf_id}"] = width
            set_column_widths(
                db,
                instrument=instrument,
                widths=existing_widths,
                actor=actor,
            )

    new_value: dict[str, Any] | None = sanitised or None
    if (instrument.band2_state or None) == new_value:
        return instrument
    old_value = instrument.band2_state
    instrument.band2_state = new_value
    db.flush()
    audit.write_event(
        db,
        event_type="instrument.band2_state_updated",
        summary=(
            f"Updated new-model band2 state on instrument "
            f"{_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes(
            {"band2_state": [old_value, new_value]}
        ),
        refs={"instrument_id": instrument.id},
    )
    return instrument


_BAND2_DATA_TYPE_TO_INLINE: dict[str, str] = {
    "string": "String",
    "integer": "Integer",
    "decimal": "Decimal",
    "list": "List",
}


def _band2_parse_float(value: Any) -> float | None:
    """Parse a band2_state numeric string ("1", "0.5", "") into a
    float. Returns ``None`` for empty / unparseable values so the
    inline column stays nullable rather than landing 0 for absent
    bounds."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _validate_response_field_shape(rf: dict[str, Any]) -> str | None:
    """Wave 3 PR ii — check a sanitised band2_state response-field
    entry against the locked-decision-11 authoring rules. Returns
    an operator-facing error message or None.

    Sanitised numeric fields arrive as strings ("" for unset);
    parse here and accept None as "no bound" for Integer / Decimal.
    For List the option set must be non-empty; for String the
    max_length (carried on the ``max`` slot) must be > 0 when set.
    """
    data_type = rf.get("data_type", "string")
    if data_type in ("integer", "decimal"):
        min_ = _band2_parse_float(rf.get("min"))
        max_ = _band2_parse_float(rf.get("max"))
        step = _band2_parse_float(rf.get("step"))
        if min_ is not None and max_ is not None and max_ < min_:
            return "Max must be at least Min."
        if step is not None and step <= 0:
            return "Step must be greater than zero."
        # Step must be reachable at least once from Min — i.e.
        # ``step <= (max - min)`` so the field has at least two
        # valid values (Min and Min+step). A larger step leaves only
        # Min as a valid value and the Step bound adds nothing the
        # operator couldn't achieve with a fixed value. Equal is
        # accepted (min=0, max=1, step=1 → values 0, 1 — useful for
        # Boolean-like numeric fields). Tiny epsilon guards against
        # float-precision drift.
        if (
            min_ is not None
            and max_ is not None
            and step is not None
            and max_ > min_
            and step > (max_ - min_) + 1e-9
        ):
            return (
                "Step must be at most (Max − Min) so the field has "
                "at least two valid values."
            )
        return None
    if data_type == "string":
        max_ = _band2_parse_float(rf.get("max"))
        if max_ is not None and max_ <= 0:
            return "Max length must be greater than zero."
        return None
    if data_type == "list":
        list_csv = (rf.get("list_options") or "").strip()
        options = [opt.strip() for opt in list_csv.split(",") if opt.strip()]
        if not options:
            return "List options must include at least one entry."
        return None
    return None


def _band2_unique_field_key(
    name: str, used_keys: set[str], existing_key: str | None = None
) -> str:
    """Slugify ``name`` to a field_key, suffixing -2 / -3 / ...
    on collision. If ``existing_key`` is supplied and already
    matches the slug of the new name (or is already taken), keep
    it unchanged (decision 9: field_key stable across renames)."""
    from app.services.instruments._response_fields import slugify_field_key

    if existing_key:
        # Decision 9 — once a field has an id, field_key never
        # changes. The caller only invokes this branch when
        # there's no existing key (new row), so this is just a
        # safety net.
        return existing_key
    base = slugify_field_key(name) or "field"
    candidate = base
    suffix = 2
    while candidate in used_keys:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _sync_response_fields_to_db(
    db: Session,
    *,
    instrument: Instrument,
    sanitised_rfs: list[dict[str, Any]],
    previous_json_ids: set[int],
    actor: User,
) -> None:
    """Wave 3 PR i — dual-write the operator-authored response-
    field JSON entries through to real ``InstrumentResponseField``
    rows.

    - JSON entry with an ``id`` matching one of this instrument's
      rows → update that row in place (label / inline type +
      bounds / required / visible / help_text / help_text_visible /
      order).
    - JSON entry without ``id`` → create a new row; back-fill
      ``id`` into the JSON entry so subsequent saves can id-match.
    - DB row whose id is absent from the JSON payload → delete
      (raises :class:`ResponsesPresentError` if the row has
      attached :class:`Response` rows; the operator-side X is
      rendered disabled when ``has_responses`` is true to prevent
      this surfacing in the typical flow).

    The reviewer-surface read path is untouched in this PR — it
    still pulls only the seeded ``DEFAULT_RESPONSE_FIELDS`` rows.
    PR ii flips the read path to ``WHERE visible=true``.

    ``sanitised_rfs`` is mutated in place: every entry has its
    ``id`` field populated on return (either preserved if already
    present, or back-filled from a newly-created row's PK).
    """
    from app.services.instruments._response_fields import (
        InvalidResponseFieldShapeError,
        ResponseFieldShapeChangeError,
        ResponsesPresentError,
    )

    # Wave 3 PR ii — authoring-shape validation. Reject the whole
    # payload (atomic save) when any entry has nonsensical bounds,
    # mirroring the locked-decision-11 contract.
    shape_errors: list[tuple[str, str]] = []
    for rf in sanitised_rfs:
        msg = _validate_response_field_shape(rf)
        if msg is not None:
            shape_errors.append((rf["name"], msg))
    if shape_errors:
        raise InvalidResponseFieldShapeError(shape_errors)

    existing_by_id: dict[int, InstrumentResponseField] = {
        f.id: f for f in instrument.response_fields
    }
    used_field_keys: set[str] = {
        f.field_key for f in instrument.response_fields
    }
    seen_ids: set[int] = set()

    for order_idx, rf in enumerate(sanitised_rfs):
        rf_id_raw = rf.get("id")
        rf_id: int | None = None
        if isinstance(rf_id_raw, int):
            rf_id = rf_id_raw
        elif isinstance(rf_id_raw, str) and rf_id_raw.strip().isdigit():
            rf_id = int(rf_id_raw)

        if rf_id is not None and rf_id in existing_by_id:
            field = existing_by_id[rf_id]
        else:
            # New row — slugify the name to a unique field_key.
            field = InstrumentResponseField(
                instrument_id=instrument.id,
                field_key=_band2_unique_field_key(rf["name"], used_field_keys),
                label=rf["name"][:255],
                order=order_idx,
            )
            db.add(field)
            db.flush()  # populate field.id
            used_field_keys.add(field.field_key)
            rf["id"] = field.id

        seen_ids.add(field.id)

        # Update label + flags + order.
        field.label = rf["name"][:255]
        field.order = order_idx
        field.required = bool(rf.get("required"))
        # Band 2 response-pill "selected" flag flows through to
        # the new visible column. Mirrors how Gap 1 wired the
        # display-field pill to InstrumentDisplayField.visible.
        field.visible = bool(rf.get("selected", True))
        help_text_raw = rf.get("help_text")
        field.help_text = (
            str(help_text_raw)[:1000] if help_text_raw else None
        )
        field.help_text_visible = bool(rf.get("help_text_visible"))

        # Inline type + bounds. Sanitised JSON uses lowercase
        # ``string`` / ``integer`` / ``decimal`` / ``list``; the
        # inline column keeps the legacy capitalised form for
        # round-trip compat with the Wave 2 _inline_* columns.
        data_type_lower = rf.get("data_type", "string")
        new_data_type = _BAND2_DATA_TYPE_TO_INLINE.get(
            data_type_lower, "String"
        )
        new_min = _band2_parse_float(rf.get("min"))
        new_max = _band2_parse_float(rf.get("max"))
        new_step = _band2_parse_float(rf.get("step"))
        new_list_csv_raw = rf.get("list_options") or ""
        new_list_csv = new_list_csv_raw if new_list_csv_raw else None

        # Wave 3 PR ii — block any data_type / bounds change on a row
        # that already has saved responses. The Band 3 row's data_type
        # select + bound inputs are rendered ``disabled`` when
        # ``has_responses`` is true; this server-side guard catches
        # direct API hits / forged sendBeacon payloads. Operator must
        # clear the responses first to re-shape the field.
        #
        # Use a counted SELECT rather than touching ``field.responses``
        # so the relationship cache stays untouched — populating it
        # here would persist a stale empty list across the request
        # boundary (sessions use ``expire_on_commit=False``) and let
        # the downstream delete-cascade check miss a freshly-attached
        # Response row.
        shape_changed: list[str] = []
        if field._inline_data_type != new_data_type:
            shape_changed.append("data_type")
        if field._inline_min != new_min:
            shape_changed.append("min")
        if field._inline_max != new_max:
            shape_changed.append("max")
        if field._inline_step != new_step:
            shape_changed.append("step")
        if field._inline_list_csv != new_list_csv:
            shape_changed.append("list_options")
        if shape_changed:
            response_count = db.execute(
                select(func.count(Response.id)).where(
                    Response.response_field_id == field.id
                )
            ).scalar_one()
            if response_count:
                raise ResponseFieldShapeChangeError(
                    field_label=field.label,
                    count=response_count,
                    changed_attrs=shape_changed,
                )

        field._inline_data_type = new_data_type
        field._inline_min = new_min
        field._inline_max = new_max
        field._inline_step = new_step
        field._inline_list_csv = new_list_csv

    # Delete rows whose ids were in the *previous* JSON state but
    # not in the new payload — i.e. operator clicked X on a row
    # that had been saved before. Rows that exist in DB but were
    # NEVER tracked in JSON (e.g. seeded DEFAULT_RESPONSE_FIELDS
    # rows on a fresh new-model instrument that the operator
    # hasn't yet round-tripped through Band 3) stay put — the
    # operator's payload reflects only what they're actively
    # managing, so missing ids without provenance mean "leave
    # alone", not "delete".
    #
    # ``cascade="all, delete-orphan"`` on the responses
    # relationship would silently cascade if we just ``db.delete``;
    # intercept by checking for attached Response rows first and
    # raising so the route surfaces the error rather than letting
    # the operator nuke saved response data invisibly.
    for rf_id in previous_json_ids - seen_ids:
        field = existing_by_id.get(rf_id)
        if field is None:
            continue
        if field.responses:
            raise ResponsesPresentError(len(field.responses))
        db.delete(field)


def _sync_display_field_visibility(
    db: Session,
    *,
    instrument: Instrument,
    selected_keys: set[str] | None,
    actor: User,
) -> None:
    """Gap 1 — propagate the operator's pill selection (Band 2's
    ``selected_display_keys``) onto each
    ``InstrumentDisplayField.visible`` so the reviewer surface
    honours the toggle.

    For every non-locked display field on the instrument: visible
    is set True when the field's canonical
    ``"{source_type}.{source_field}"`` key is in ``selected_keys``,
    False otherwise. Locked rows (Name / Email) always stay
    visible — :func:`update_display_field` would refuse the flip
    anyway, but we skip the call to keep the audit log quiet.
    """
    if selected_keys is None:
        return
    # Local import to avoid module-load circular dep:
    # _display_fields → _instrument_crud already exists via the
    # public re-exports in __init__.py.
    from app.services.instruments._display_fields import (
        is_locked_display_source,
        update_display_field,
    )

    for field in list(instrument.display_fields):
        if is_locked_display_source(field.source_type, field.source_field):
            continue
        key = f"{field.source_type}.{field.source_field}"
        desired = key in selected_keys
        if field.visible == desired:
            continue
        update_display_field(
            db,
            field=field,
            label=field.label,
            visible=desired,
            actor=actor,
        )


def bulk_set_accepting(
    db: Session,
    *,
    review_session: ReviewSession,
    target: bool,
    actor: User,
) -> list[int]:
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    changed: list[int] = []
    for instrument in instruments:
        if instrument.accepting_responses != target:
            instrument.accepting_responses = target
            changed.append(instrument.id)
    if changed:
        db.flush()
        audit.write_event(
            db,
            event_type="instruments.bulk_accepting_responses",
            summary=(
                f"Set accepting_responses={target} on "
                f"{len(changed)} instrument(s)"
            ),
            actor_user_id=actor.id if actor else None,
            session=review_session,
            payload=audit.set_changes(
                updated=[{"instrument_id": i} for i in changed]
            ),
            context={"target": bool(target)},
        )
        db.commit()
    return changed


def bulk_set_visibility(
    db: Session,
    *,
    review_session: ReviewSession,
    target: bool,
    actor: User,
) -> list[int]:
    # #16 — visibility-when-closed is a display flag, not part of the
    # validation snapshot. Deliberately does NOT call
    # ``lifecycle.invalidate_if_validated``. See ``docs/status.md`` and
    # ``test_invalidation_on_setup_mutation.py`` for the regression test.
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    changed: list[int] = []
    for instrument in instruments:
        if instrument.responses_visible_when_closed != target:
            instrument.responses_visible_when_closed = target
            changed.append(instrument.id)
    if changed:
        db.flush()
        audit.write_event(
            db,
            event_type="instruments.bulk_visibility_when_closed",
            summary=(
                f"Set responses_visible_when_closed={target} on "
                f"{len(changed)} instrument(s)"
            ),
            actor_user_id=actor.id if actor else None,
            session=review_session,
            payload=audit.set_changes(
                updated=[{"instrument_id": i} for i in changed]
            ),
            context={"target": bool(target)},
        )
        db.commit()
    return changed
