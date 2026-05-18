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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import session_lifecycle as lifecycle
from app.services import audit
from app.services.instruments._response_fields import DEFAULT_RESPONSE_FIELDS
from app.services.instruments._rtds import (
    ensure_default_response_type_definitions,
    validation_block_for_rtd,
)
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

    rtds_by_name = ensure_default_response_type_definitions(db, review_session)

    has_fields = (
        db.execute(
            select(InstrumentResponseField.id)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .limit(1)
        ).first()
        is not None
    )

    if not has_fields:
        for spec in DEFAULT_RESPONSE_FIELDS:
            rtd = rtds_by_name[spec["rtd_name"]]
            db.add(
                InstrumentResponseField(
                    instrument_id=instrument.id,
                    field_key=spec["field_key"],
                    label=spec["label"],
                    response_type_id=rtd.id,
                    required=spec["required"],
                    order=spec["order"],
                    validation=validation_block_for_rtd(rtd),
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

    ``group_kind`` is the Segment 13C group-scoping flavour — ``None``
    for an ordinary per-reviewee instrument, or a non-null value
    (``members`` / ``summary`` / ``both``) for a group-scoped one.
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

    rtds_by_name = ensure_default_response_type_definitions(db, review_session)
    for spec in DEFAULT_RESPONSE_FIELDS:
        rtd = rtds_by_name[spec["rtd_name"]]
        db.add(
            InstrumentResponseField(
                instrument_id=instrument.id,
                field_key=spec["field_key"],
                label=spec["label"],
                response_type_id=rtd.id,
                required=spec["required"],
                order=spec["order"],
                validation=validation_block_for_rtd(rtd),
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
