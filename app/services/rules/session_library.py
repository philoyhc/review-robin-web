"""Session-tier RuleSet writes — Segment 15C Slice 4.

Mirrors :mod:`app.services.rules.library` but writes to
``session_rule_sets`` (the per-session copy tier) instead of
``operator_rule_sets`` + ``rule_set_revisions``. The session
tier carries a complete snapshot of the rule tree per row —
there is no per-session revisions table. Operators preserve
history via the explicit "Save to library" action
(:func:`save_to_library`) which creates a library copy with
its own revision chain.

Public API:

- :func:`load_session_rule_set` — resolve a SessionRuleSet by id.
- :func:`list_visible_session_rule_sets` — pool for the picker.
- :func:`list_library_rule_sets_not_in_session` — pool for the
  Add-from-library affordance.
- :func:`save_session_rule_set_as` — create a new SessionRuleSet
  from a validated schema (Save As / Copy / blank draft).
- :func:`update_session_rule_set_in_place` — overwrite the
  snapshot on an existing SessionRuleSet (in-place Save).
- :func:`rename_session_rule_set` — metadata-only rename.
- :func:`delete_session_rule_set` — hard delete (no soft-delete
  — past audit refs use refs.rule_set_id which already survives
  hard deletes for assignments.generated rows).
- :func:`save_to_library` — promote a SessionRuleSet to the
  operator library; mirror of
  :func:`app.services.instruments._rtds.save_session_rtd_to_library`.
- :func:`add_from_library` — copy a library RuleSet into the
  session; mirror of
  :func:`app.services.instruments._rtds.add_rtd_from_library`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    ReviewSession,
    RuleSet,
    RuleSetRevision,
    SessionRuleSet,
    User,
)
from app.services import audit


class SessionRuleSetNotFoundError(LookupError):
    """Raised when a SessionRuleSet id resolves to no row in the
    target session."""


class SessionRuleSetNameConflictError(ValueError):
    """Raised when a Save / Save-As / Add-from-library would write a
    SessionRuleSet name that already exists on the session — the
    ``uq_session_rule_set_session_name`` constraint forbids it and the
    route surfaces an inline error rather than 500-ing on the integrity
    violation."""


class LibraryRuleSetNameConflictError(ValueError):
    """Raised when ``save_to_library`` would write an operator-library
    name that already exists for the actor — the existing
    ``(owner_user_id, name)`` uniqueness on ``operator_rule_sets`` is
    enforced at the service layer for parity with the RTD path."""


class SessionRuleSetLockedError(Exception):
    """Raised when an operator attempts to mutate a seeded
    SessionRuleSet (``is_seeded=True``) — those are workspace-locked
    the same way the ten baseline RTDs are. Operators customise via
    Copy → Save-As, which writes a fresh row with ``is_seeded=False``.

    Applies to: update-in-place, rename, delete, save-to-library."""


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------


def load_session_rule_set(
    db: Session, session_rule_set_id: int, *, session_id: int
) -> SessionRuleSet | None:
    """Resolve a SessionRuleSet by id, scoped to ``session_id``."""
    return db.execute(
        select(SessionRuleSet).where(
            SessionRuleSet.id == session_rule_set_id,
            SessionRuleSet.session_id == session_id,
        )
    ).scalar_one_or_none()


def list_visible_session_rule_sets(
    db: Session, *, session_id: int
) -> list[SessionRuleSet]:
    """The picker pool for this session. Rows order by id ascending,
    which matches the materialise order
    (seeds first via 15C Slice 1, then operator-library copies via
    Slice 2, then operator-authored entries)."""
    return list(
        db.execute(
            select(SessionRuleSet)
            .where(SessionRuleSet.session_id == session_id)
            .order_by(SessionRuleSet.id)
        ).scalars()
    )


def evaluate_session_rule_eligibility(
    db: Session, review_session: ReviewSession
) -> dict[int, int]:
    """Per-rule eligibility-count map (``session_rule_sets.id ->
    N pairs``) for the rules **pinned to an instrument** in this
    session — computed by running the rule engine against the
    session's current reviewer / reviewee populations.

    Only pinned rules are evaluated. An unpinned rule has no
    instrument showing its count, so running the engine for it
    is wasted work — and the engine pass over the full
    reviewer × reviewee space is the expensive step (it scales
    with the product of the two roster sizes). Callers render
    "--" for an instrument with no pinned rule rather than a
    number.

    Shared by the per-instrument card picker, the Assignments-page
    status blocks, and the Validate page's staleness rule — all
    of which only ever read pinned-rule entries. Engine errors on
    a malformed snapshot fall back to ``0`` for that rule rather
    than tearing down the whole page render.

    The count is cached on each ``session_rule_sets`` row
    (``cached_eligible_pair_count`` + ``cached_eligibility_stamp``).
    The stamp is a content-hash of the roster + rule inputs, so a
    later call with unchanged inputs returns the stored count
    without re-running the engine; a roster or rule edit changes
    the hash and forces a recompute. Cache writes are committed
    (the callers are GET renders that otherwise would not, and the
    one POST caller — the Workflow super-button — uses compensating
    writes, not transaction rollback, so an in-place commit here is
    safe).

    No pinned rules (or empty rosters) → ``{}``.
    """
    from pydantic import TypeAdapter

    from app.schemas.rules import Rule
    from app.services import (
        assignments as assignments_service,
        relationships as relationships_service,
    )

    pinned_ids = set(
        db.execute(
            select(Instrument.rule_set_id)
            .where(
                Instrument.session_id == review_session.id,
                Instrument.rule_set_id.is_not(None),
            )
            .distinct()
        ).scalars()
    )
    if not pinned_ids:
        return {}
    rule_sets = [
        row
        for row in list_visible_session_rule_sets(
            db, session_id=review_session.id
        )
        if row.id in pinned_ids
    ]
    if not rule_sets:
        return {}
    rule_adapter = TypeAdapter(Rule)
    reviewers = assignments_service.list_reviewers(db, review_session.id)
    reviewees = assignments_service.list_reviewees(db, review_session.id)
    pair_context_lookup = relationships_service.pair_context_lookup(
        db, review_session.id
    )
    roster_sig = _roster_signature(reviewers, reviewees, pair_context_lookup)

    out: dict[int, int] = {}
    cache_dirty = False
    for row in rule_sets:
        stamp = hashlib.sha256(
            (roster_sig + _rule_signature(row)).encode()
        ).hexdigest()
        if (
            row.cached_eligibility_stamp == stamp
            and row.cached_eligible_pair_count is not None
        ):
            out[row.id] = row.cached_eligible_pair_count
            continue
        result = _evaluate_rule_row(
            row,
            reviewers=reviewers,
            reviewees=reviewees,
            pair_context_lookup=pair_context_lookup,
            rule_adapter=rule_adapter,
        )
        if result is None:
            # A malformed snapshot falls back to 0 and is NOT
            # cached — a transient error must not stick.
            out[row.id] = 0
            continue
        count = len(result.pairs)
        out[row.id] = count
        row.cached_eligible_pair_count = count
        row.cached_eligibility_stamp = stamp
        cache_dirty = True
    if cache_dirty:
        db.commit()
    return out


def _roster_signature(
    reviewers: list[Any],
    reviewees: list[Any],
    pair_context_lookup: dict[Any, Any],
) -> str:
    """Content hash of the reviewer / reviewee / relationship inputs
    the rule engine consumes — every column value of every roster
    row plus the pair-context lookup. Any add, delete, or edit
    changes the hash. This is how a stale eligibility cache is
    detected without an ``updated_at`` column on the roster tables.
    """

    def _rows(objs: list[Any]) -> list[list[str]]:
        return [
            [str(getattr(o, col.name)) for col in o.__table__.columns]
            for o in sorted(objs, key=lambda o: o.id)
        ]

    payload = repr(
        (
            _rows(reviewers),
            _rows(reviewees),
            sorted(
                (repr(k), repr(v)) for k, v in pair_context_lookup.items()
            ),
        )
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _evaluate_rule_row(
    row: SessionRuleSet,
    *,
    reviewers: list[Any],
    reviewees: list[Any],
    pair_context_lookup: dict[Any, Any],
    rule_adapter: Any,
) -> Any | None:
    """Run the rule engine for one ``SessionRuleSet`` row.

    Returns the ``EvaluationResult``, or ``None`` when the stored
    snapshot is malformed — a transient error must not tear down
    the page render. Shared by :func:`evaluate_session_rule_eligibility`
    (per-rule pair count) and :func:`evaluate_instrument_group_pair_counts`
    (per-instrument reviewer-group count)."""
    from app.schemas.rules import (
        Combinator,
        RuleSetOptions,
        RuleSetScope,
        RuleSetSchema,
    )
    from app.services.rules import engine

    try:
        schema = RuleSetSchema(
            id=row.id,
            name=row.name,
            description=row.description or "",
            scope=RuleSetScope.personal,
            combinator=Combinator(row.combinator),
            rules=[
                rule_adapter.validate_python(payload)
                for payload in row.rules_json
            ],
            options=RuleSetOptions(
                excludeSelfReviews=row.exclude_self_reviews,
                seed=row.seed,
            ),
        )
        return engine.evaluate(
            schema,
            reviewers=reviewers,
            reviewees=reviewees,
            revision_seed=row.id,
            pair_context_lookup=pair_context_lookup,
        )
    except Exception:
        return None


def evaluate_instrument_group_pair_counts(
    db: Session, review_session: ReviewSession
) -> dict[int, int]:
    """Per-instrument reviewer-group pair count for the session's
    group-scoped instruments that have a rule pinned.

    The count is the number of distinct ``(reviewer, group_key)``
    over the pinned rule's eligible pairs, where ``group_key`` is
    the boundary-tag tuple decoded from the instrument's
    ``group_kind``. Instruments with no rule pinned — and every
    per-reviewee instrument — are absent from the result.

    Unlike :func:`evaluate_session_rule_eligibility` this is
    **per-instrument** (boundary tags are an ``Instrument``
    setting, so the same rule pinned twice can yield different
    counts). The count is cached on each ``instruments`` row
    (``cached_group_pair_count`` + ``cached_group_pair_stamp``);
    the stamp is a content-hash of the roster + the pinned rule's
    definition + ``group_kind``, so a matching stamp returns the
    stored count without an engine pass, and a roster / rule /
    boundary-tag edit changes the hash and forces a recompute
    (Segment 13C PR 4 slice 4b — mirrors the 18E Part 2 per-rule
    cache). ``{}`` when no group-scoped instrument has a rule
    pinned."""
    from pydantic import TypeAdapter

    from app.schemas.rules import Rule
    from app.services import (
        assignments as assignments_service,
        instruments as instruments_service,
        relationships as relationships_service,
    )
    from app.services.responses import group_key_for_pair

    instruments = list(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id,
                Instrument.group_kind.is_not(None),
                Instrument.rule_set_id.is_not(None),
            )
        ).scalars()
    )
    if not instruments:
        return {}
    pinned_ids = {i.rule_set_id for i in instruments}
    rule_rows = {
        row.id: row
        for row in list_visible_session_rule_sets(
            db, session_id=review_session.id
        )
        if row.id in pinned_ids
    }
    reviewers = assignments_service.list_reviewers(db, review_session.id)
    reviewees = assignments_service.list_reviewees(db, review_session.id)
    pair_context_lookup = relationships_service.pair_context_lookup(
        db, review_session.id
    )
    roster_sig = _roster_signature(reviewers, reviewees, pair_context_lookup)
    rule_sig_by_id = {
        rule_id: _rule_signature(row) for rule_id, row in rule_rows.items()
    }
    rule_adapter = TypeAdapter(Rule)

    out: dict[int, int] = {}
    # The engine result is computed lazily, once per pinned rule —
    # a rule shared by two group-scoped instruments runs once.
    results: dict[int, Any] = {}
    cache_dirty = False
    for instrument in instruments:
        rule_id = instrument.rule_set_id
        rule_sig = rule_sig_by_id.get(rule_id)
        if rule_sig is None:
            # Pinned rule not resolvable — fall back to 0, uncached.
            out[instrument.id] = 0
            continue
        stamp = hashlib.sha256(
            (
                roster_sig + rule_sig + (instrument.group_kind or "")
            ).encode()
        ).hexdigest()
        if (
            instrument.cached_group_pair_stamp == stamp
            and instrument.cached_group_pair_count is not None
        ):
            out[instrument.id] = instrument.cached_group_pair_count
            continue
        if rule_id not in results:
            results[rule_id] = _evaluate_rule_row(
                rule_rows[rule_id],
                reviewers=reviewers,
                reviewees=reviewees,
                pair_context_lookup=pair_context_lookup,
                rule_adapter=rule_adapter,
            )
        result = results[rule_id]
        if result is None:
            # Malformed snapshot — fall back to 0, NOT cached.
            out[instrument.id] = 0
            continue
        boundary = instruments_service.decode_group_kind(
            instrument.group_kind
        )
        groups = {
            (
                reviewer.id,
                group_key_for_pair(
                    reviewee=reviewee,
                    reviewer_id=reviewer.id,
                    reviewee_id=reviewee.id,
                    boundary=boundary,
                    pair_context_lookup=pair_context_lookup,
                ),
            )
            for reviewer, reviewee in result.pairs
        }
        count = len(groups)
        out[instrument.id] = count
        instrument.cached_group_pair_count = count
        instrument.cached_group_pair_stamp = stamp
        cache_dirty = True
    if cache_dirty:
        db.commit()
    return out


def _rule_signature(row: SessionRuleSet) -> str:
    """Content hash of one rule's definition — the inputs that,
    alongside the roster, determine its eligible-pair count."""
    payload = json.dumps(
        {
            "combinator": row.combinator,
            "exclude_self_reviews": row.exclude_self_reviews,
            "seed": row.seed,
            "rules": row.rules_json,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def list_library_rule_sets_not_in_session(
    db: Session, *, owner_user: User, session_id: int
) -> list[RuleSet]:
    """``owner_user``'s library Personal RuleSets whose ``name`` is
    not already on ``session_id``. Drives the Add-from-library
    picker."""
    in_session = set(
        db.execute(
            select(SessionRuleSet.name).where(
                SessionRuleSet.session_id == session_id
            )
        ).scalars()
    )
    return [
        rs
        for rs in db.execute(
            select(RuleSet)
            .where(
                RuleSet.is_seed.is_(False),
                RuleSet.owner_user_id == owner_user.id,
                RuleSet.deleted_at.is_(None),
            )
            .order_by(RuleSet.id)
        ).scalars()
        if rs.name not in in_session
    ]


def name_taken_in_session(
    db: Session, *, session_id: int, candidate_name: str, exclude_id: int | None
) -> bool:
    """Service-layer mirror of the picker's `(session_id, name)`
    uniqueness constraint, used by name-collision-on-Save helpers in
    the routes layer."""
    stmt = select(SessionRuleSet.id).where(
        SessionRuleSet.session_id == session_id,
        SessionRuleSet.name == candidate_name,
    )
    if exclude_id is not None:
        stmt = stmt.where(SessionRuleSet.id != exclude_id)
    return db.execute(stmt).scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Write path — Save As / Copy / blank-draft
# ---------------------------------------------------------------------------


def _rules_payload(rule_set_schema: Any) -> list[dict[str, Any]]:
    return [rule.model_dump(mode="json") for rule in rule_set_schema.rules]


def save_session_rule_set_as(
    db: Session,
    *,
    review_session: ReviewSession,
    rule_set_schema: Any,  # RuleSetSchema (avoid Pydantic forward refs)
    new_name: str,
    source_session_rule_set_id: int | None,
    library_origin_id: int | None,
    actor: User,
    correlation_id: str,
) -> SessionRuleSet:
    """Persist a SessionRuleSet from a validated schema. Used for
    blank drafts, Copy, and Save-As.

    Raises :class:`SessionRuleSetNameConflictError` if a row with
    ``new_name`` already exists on the session.
    """
    if name_taken_in_session(
        db,
        session_id=review_session.id,
        candidate_name=new_name,
        exclude_id=None,
    ):
        raise SessionRuleSetNameConflictError(
            f"A RuleSet named {new_name!r} already exists on this session"
        )
    row = SessionRuleSet(
        session_id=review_session.id,
        name=new_name,
        description=rule_set_schema.description or "",
        combinator=rule_set_schema.combinator.value,
        exclude_self_reviews=rule_set_schema.options.excludeSelfReviews,
        seed=rule_set_schema.options.seed,
        rules_json=_rules_payload(rule_set_schema),
        library_origin_id=library_origin_id,
    )
    db.add(row)
    db.flush()

    via = "save_as" if source_session_rule_set_id is not None else "blank"
    audit.write_event(
        db,
        event_type="session_rule_set.created",
        summary=(
            f"Created session RuleSet {new_name!r} on session "
            f"{review_session.code}"
        ),
        actor_user_id=actor.id,
        session=review_session,
        payload=audit.snapshot(
            {
                "id": row.id,
                "name": row.name,
                "combinator": row.combinator,
                "rule_count": len(row.rules_json or []),
            }
        ),
        refs={"session_rule_set_id": row.id}
        | (
            {"source_session_rule_set_id": source_session_rule_set_id}
            if source_session_rule_set_id is not None
            else {}
        )
        | (
            {"library_origin_id": library_origin_id}
            if library_origin_id is not None
            else {}
        ),
        context={"via": via},
        correlation_id=correlation_id,
    )
    return row


def update_session_rule_set_in_place(
    db: Session,
    *,
    session_rule_set: SessionRuleSet,
    rule_set_schema: Any,  # RuleSetSchema
    actor: User,
    correlation_id: str,
) -> SessionRuleSet:
    """Overwrite a SessionRuleSet's rule tree in place. Unlike the
    library tier there is no revisions table; the prior snapshot is
    not preserved. Operators who want history use Save-to-library.

    Audit envelope mirrors ``library.save_in_place``: ``rule_set.updated``-style
    metadata diff plus a single ``rules_edited`` boolean when the tree
    differs.
    """
    if session_rule_set.is_seeded:
        raise SessionRuleSetLockedError(
            "Seeded RuleSets are workspace-locked; Copy to a new "
            "RuleSet to customise"
        )
    new_rules = _rules_payload(rule_set_schema)
    new_combinator = rule_set_schema.combinator.value
    new_exclude_self_reviews = rule_set_schema.options.excludeSelfReviews
    new_seed = rule_set_schema.options.seed

    changes: dict[str, list[Any]] = {}
    if session_rule_set.combinator != new_combinator:
        changes["combinator"] = [
            session_rule_set.combinator, new_combinator
        ]
    if session_rule_set.exclude_self_reviews != new_exclude_self_reviews:
        changes["exclude_self_reviews"] = [
            session_rule_set.exclude_self_reviews,
            new_exclude_self_reviews,
        ]
    if session_rule_set.seed != new_seed:
        changes["seed"] = [session_rule_set.seed, new_seed]
    prev_count = len(session_rule_set.rules_json or [])
    new_count = len(new_rules)
    if prev_count != new_count:
        changes["rule_count"] = [prev_count, new_count]
    if (session_rule_set.rules_json or []) != new_rules:
        changes["rules_edited"] = [True, True]

    session_rule_set.combinator = new_combinator
    session_rule_set.exclude_self_reviews = new_exclude_self_reviews
    session_rule_set.seed = new_seed
    session_rule_set.rules_json = new_rules
    db.flush()

    audit.write_event(
        db,
        event_type="session_rule_set.updated",
        summary=(
            f"Saved session RuleSet {session_rule_set.name!r} on "
            f"session {session_rule_set.session_id}"
        ),
        actor_user_id=actor.id,
        session=session_rule_set.session,
        payload=audit.changes(changes) if changes else None,
        refs={"session_rule_set_id": session_rule_set.id},
        correlation_id=correlation_id,
    )
    return session_rule_set


def rename_session_rule_set(
    db: Session,
    *,
    session_rule_set: SessionRuleSet,
    new_name: str,
    new_description: str | None,
    actor: User,
    correlation_id: str,
) -> SessionRuleSet:
    """Rename + optionally re-describe a SessionRuleSet. Refuses on
    name collision. Audit envelope: ``session_rule_set.updated`` with
    a ``changes`` payload covering ``name`` and ``description``."""
    if session_rule_set.is_seeded:
        raise SessionRuleSetLockedError(
            "Seeded RuleSets are workspace-locked; Copy to a new "
            "RuleSet to customise"
        )
    if new_name != session_rule_set.name and name_taken_in_session(
        db,
        session_id=session_rule_set.session_id,
        candidate_name=new_name,
        exclude_id=session_rule_set.id,
    ):
        raise SessionRuleSetNameConflictError(
            f"A RuleSet named {new_name!r} already exists on this session"
        )

    changes: dict[str, list[Any]] = {}
    if session_rule_set.name != new_name:
        changes["name"] = [session_rule_set.name, new_name]
        session_rule_set.name = new_name
    if (
        new_description is not None
        and (session_rule_set.description or "") != new_description
    ):
        changes["description"] = [
            session_rule_set.description or "", new_description
        ]
        session_rule_set.description = new_description
    if changes:
        db.flush()
    audit.write_event(
        db,
        event_type="session_rule_set.updated",
        summary=(
            f"Renamed session RuleSet to {session_rule_set.name!r}"
        ),
        actor_user_id=actor.id,
        session=session_rule_set.session,
        payload=audit.changes(changes) if changes else None,
        refs={"session_rule_set_id": session_rule_set.id},
        context={"via": "rename"},
        correlation_id=correlation_id,
    )
    return session_rule_set


def delete_session_rule_set(
    db: Session,
    *,
    session_rule_set: SessionRuleSet,
    actor: User,
    correlation_id: str,
) -> None:
    """Hard-delete a SessionRuleSet. The session tier has no
    soft-delete column; past ``assignments.generated`` audit rows
    pin ``rule_set_id`` only via ``refs`` (free-form), so removing
    the row doesn't break the audit chain.

    The corresponding ``instruments.rule_set_id`` pointers (if any)
    clear via the SQL-level ``ON DELETE SET NULL`` cascade per 13D
    PR 4."""
    if session_rule_set.is_seeded:
        raise SessionRuleSetLockedError(
            "Seeded RuleSets are workspace-locked; they materialise "
            "on every session and cannot be locally deleted"
        )
    captured = {
        "id": session_rule_set.id,
        "name": session_rule_set.name,
    }
    review_session = session_rule_set.session
    db.delete(session_rule_set)
    db.flush()

    audit.write_event(
        db,
        event_type="session_rule_set.deleted",
        summary=f"Deleted session RuleSet {captured['name']!r}",
        actor_user_id=actor.id,
        session=review_session,
        payload=audit.snapshot(captured),
        refs={"session_rule_set_id": captured["id"]},
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# Cross-tier — Save to library / Add from library
# ---------------------------------------------------------------------------


def save_to_library(
    db: Session,
    *,
    session_rule_set: SessionRuleSet,
    actor: User,
    correlation_id: str,
) -> RuleSet:
    """Promote a SessionRuleSet into the actor's operator library
    (``operator_rule_sets`` + a fresh ``rule_set_revisions`` row
    snapshotting the current session-side ``rules_json``). Links
    the session row's ``library_origin_id`` back to the new library
    row.

    Raises :class:`LibraryRuleSetNameConflictError` on
    ``(owner_user_id, name)`` collision; the operator must rename
    the session row or the library row first.

    Idempotent: if ``library_origin_id`` is already set and points
    at a still-extant library row, returns that row without
    writing.

    Refuses (``SessionRuleSetLockedError``) on seeded session
    RuleSets — they're workspace-shipped, not personal, and don't
    belong in any one operator's library. To customise + save,
    operators Copy → Save-As first, then Save the resulting
    non-seeded row to library.
    """
    if session_rule_set.is_seeded:
        raise SessionRuleSetLockedError(
            "Seeded RuleSets are workspace-locked; Copy to a new "
            "RuleSet before saving to library"
        )
    if session_rule_set.library_origin_id is not None:
        existing = db.execute(
            select(RuleSet).where(
                RuleSet.id == session_rule_set.library_origin_id,
                RuleSet.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    collision = db.execute(
        select(RuleSet).where(
            RuleSet.owner_user_id == actor.id,
            RuleSet.name == session_rule_set.name,
            RuleSet.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if collision is not None:
        raise LibraryRuleSetNameConflictError(
            f"{session_rule_set.name!r} already exists in your "
            "operator library — rename or remove the library entry "
            "first"
        )

    now = datetime.now(timezone.utc)
    library_row = RuleSet(
        name=session_rule_set.name,
        description=session_rule_set.description or "",
        scope="personal",
        owner_user_id=actor.id,
        is_seed=False,
    )
    db.add(library_row)
    db.flush()
    revision = RuleSetRevision(
        rule_set_id=library_row.id,
        revision_no=1,
        combinator=session_rule_set.combinator,
        exclude_self_reviews=session_rule_set.exclude_self_reviews,
        seed=session_rule_set.seed,
        rules_json=session_rule_set.rules_json,
        created_at=now,
        created_by_user_id=actor.id,
    )
    db.add(revision)
    db.flush()
    library_row.current_revision_id = revision.id
    session_rule_set.library_origin_id = library_row.id
    db.flush()

    audit.write_event(
        db,
        event_type="rule_set.created",
        summary=(
            f"Saved RuleSet {library_row.name!r} to operator library"
        ),
        actor_user_id=actor.id,
        payload=audit.snapshot(
            {
                "id": library_row.id,
                "name": library_row.name,
                "scope": library_row.scope,
            }
        ),
        refs={
            "rule_set_id": library_row.id,
            "rule_set_revision_id": revision.id,
            "source_session_rule_set_id": session_rule_set.id,
        },
        context={"via": "save_to_library"},
        correlation_id=correlation_id,
    )
    audit.write_event(
        db,
        event_type="session_rule_sets.saved_to_library",
        summary=(
            f"Saved session RuleSet {session_rule_set.name!r} to "
            f"operator library"
        ),
        actor_user_id=actor.id,
        session=session_rule_set.session,
        payload=audit.snapshot(
            {
                "name": session_rule_set.name,
                "combinator": session_rule_set.combinator,
            }
        ),
        refs={
            "session_rule_set_id": session_rule_set.id,
            "rule_set_id": library_row.id,
        },
        context={"via": "save_to_library"},
        correlation_id=correlation_id,
    )
    return library_row


def add_from_library(
    db: Session,
    *,
    review_session: ReviewSession,
    library_rule_set: RuleSet,
    actor: User,
    correlation_id: str,
) -> SessionRuleSet:
    """Copy a library Personal RuleSet's current revision snapshot
    into ``review_session``'s ``session_rule_sets``. The session
    copy carries ``library_origin_id`` pointing back at the library
    row.

    Refuses (``SessionRuleSetNameConflictError``) on name collision;
    operator must rename one side first.
    Refuses (``ValueError``) if the library row isn't owned by the
    actor, isn't soft-deleted, or has no current revision.
    """
    if library_rule_set.owner_user_id != actor.id:
        raise ValueError("Cannot add another operator's library entry")
    if library_rule_set.deleted_at is not None:
        raise ValueError("Library entry is deleted")
    if library_rule_set.current_revision_id is None:
        raise ValueError("Library entry has no current revision")
    revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.id == library_rule_set.current_revision_id
        )
    ).scalar_one_or_none()
    if revision is None:
        raise ValueError("Library entry's current revision is missing")
    if name_taken_in_session(
        db,
        session_id=review_session.id,
        candidate_name=library_rule_set.name,
        exclude_id=None,
    ):
        raise SessionRuleSetNameConflictError(
            f"A RuleSet named {library_rule_set.name!r} already "
            "exists on this session"
        )

    row = SessionRuleSet(
        session_id=review_session.id,
        name=library_rule_set.name,
        description=library_rule_set.description or "",
        combinator=revision.combinator,
        exclude_self_reviews=revision.exclude_self_reviews,
        seed=revision.seed,
        rules_json=revision.rules_json,
        library_origin_id=library_rule_set.id,
    )
    db.add(row)
    db.flush()

    audit.write_event(
        db,
        event_type="session_rule_sets.added_from_library",
        summary=(
            f"Added RuleSet {library_rule_set.name!r} from operator "
            f"library to session {review_session.code}"
        ),
        actor_user_id=actor.id,
        session=review_session,
        payload=audit.snapshot(
            {
                "name": row.name,
                "combinator": row.combinator,
            }
        ),
        refs={
            "session_rule_set_id": row.id,
            "rule_set_id": library_rule_set.id,
        },
        context={"via": "add_from_library"},
        correlation_id=correlation_id,
    )
    return row
