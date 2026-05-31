"""Per-session friendly-label resolver — Segment 15A Slice 1.

Resolves a friendly label for one of the 12 in-scope
``(source_type, source_field)`` slots a session can rename. The
chain is three-step:

1. Session-wide override (``session_field_labels`` row)
2. Built-in default in ``_DEFAULT_LABELS``
3. ``f"{source_type}:{source_field}"`` last-resort fallback

The per-instrument ``InstrumentDisplayField.label`` override is
**not** in this chain (retired in Segment 15A). The model column
stays in the schema as dead data; the resolver doesn't consult
it.

Public surface:

- ``resolve(session, source_type, source_field) -> str``
- ``all_labels(session) -> dict[tuple[str, str], str]``
- ``upsert(db, session, *, source_type, source_field, label, user,
  correlation_id) -> SessionFieldLabel``
- ``clear(db, session, *, source_type, source_field, user,
  correlation_id) -> None``
- ``FieldLabelSourceError`` for invalid ``(source_type,
  source_field)`` tuples.

Slice 1 keeps the integration surface minimal: this module is
fully testable standalone, and existing callers
(``display_field_label`` etc.) continue to use the legacy chain
unchanged. Slice 2 threads ``resolve`` through every display-
layer callsite and the per-instrument override branch goes away
with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionFieldLabel, User
from app.services import audit
from app.services import session_lifecycle as lifecycle


# The 12 in-scope slots a session can rename. Source-field values
# match the canonical column / key names used elsewhere
# (``reviewee.email_or_identifier`` is the column on the
# ``reviewees`` table; ``pair_context.1`` / ``.2`` / ``.3`` are
# the three slots on the ``relationships`` row).
_DEFAULT_LABELS: dict[tuple[str, str], str] = {
    ("reviewer", "tag_1"): "Tag 1",
    ("reviewer", "tag_2"): "Tag 2",
    ("reviewer", "tag_3"): "Tag 3",
    ("reviewee", "name"): "Name",
    ("reviewee", "email_or_identifier"): "Email",
    ("reviewee", "tag_1"): "Tag 1",
    ("reviewee", "tag_2"): "Tag 2",
    ("reviewee", "tag_3"): "Tag 3",
    ("reviewee", "profile_link"): "Profile",
    ("pair_context", "1"): "Pair context 1",
    ("pair_context", "2"): "Pair context 2",
    ("pair_context", "3"): "Pair context 3",
}

# Per-source allowlist. The DB column is ``VARCHAR(64)`` with no
# enum gate, so this map is the only validation layer for what a
# session may rename. Mirrored by ``_VALID_FL_SOURCE_FIELDS`` in
# ``app/services/session_config_io/`` for Settings-CSV import.
#
# Friendly-label affordance retired for the reviewee fixed columns
# (Name / Email_Identifier / Profile) on 2026-05-31 per
# ``guide/participant_model_upgrade.md`` §3.7 — those columns mean
# what they say and operators renaming them added no signal.
# ``_DEFAULT_LABELS`` retains the canonical strings so display
# callers (table headers, etc.) still resolve to "Name" / "Email"
# / "Profile"; only the *override* path is closed.
_VALID_SOURCE_FIELDS: dict[str, frozenset[str]] = {
    "reviewer": frozenset({"tag_1", "tag_2", "tag_3"}),
    "reviewee": frozenset({"tag_1", "tag_2", "tag_3"}),
    "pair_context": frozenset({"1", "2", "3"}),
}


class FieldLabelSourceError(ValueError):
    """Raised when ``(source_type, source_field)`` is not one of
    the 12 in-scope slots."""


def _require_known_source(source_type: str, source_field: str) -> None:
    allowed = _VALID_SOURCE_FIELDS.get(source_type)
    if allowed is None:
        raise FieldLabelSourceError(
            f"unknown source_type {source_type!r}; expected one of "
            f"{sorted(_VALID_SOURCE_FIELDS)}"
        )
    if source_field not in allowed:
        raise FieldLabelSourceError(
            f"unknown source_field {source_field!r} for "
            f"source_type {source_type!r}; expected one of "
            f"{sorted(allowed)}"
        )


def _builtin_default(source_type: str, source_field: str) -> str:
    inferred = _DEFAULT_LABELS.get((source_type, source_field))
    if inferred is not None:
        return inferred
    return f"{source_type}:{source_field}"


def resolve(
    session: ReviewSession, source_type: str, source_field: str
) -> str:
    """Return the friendly label for a slot under ``session``.

    Three-step chain: session override → built-in default →
    ``"{source_type}:{source_field}"`` fallback. The slot's
    ``(source_type, source_field)`` does **not** have to be in
    ``_VALID_SOURCE_FIELDS`` — the resolver is permissive on
    read so unknown slots still produce a usable string. The
    ``upsert`` / ``clear`` mutators are strict.
    """
    overrides = all_labels(session)
    override = overrides.get((source_type, source_field))
    if override is not None:
        return override
    return _builtin_default(source_type, source_field)


def all_labels(session: ReviewSession) -> dict[tuple[str, str], str]:
    """Return every override row for ``session`` as a flat dict.

    Materialised by walking ``session.field_labels`` (lazy-loaded
    by SQLAlchemy on first access); callers that resolve many
    slots in one request reuse the dict instead of triggering a
    query per slot.
    """
    return {
        (row.source_type, row.source_field): row.label
        for row in session.field_labels
    }


def canonical_default(source_type: str, source_field: str) -> str:
    """Return the built-in default label for a slot (e.g. ``"Tag 1"``).

    Skips the session override layer — useful when an operator-
    facing surface wants to show the canonical name alongside the
    friendly override (the two-line ``Friendly / canonical``
    header render).
    """
    return _builtin_default(source_type, source_field)


@dataclass(frozen=True)
class LabelPair:
    """Render-ready pair of friendly + canonical labels for a slot.

    Operator-facing display surfaces use both: the friendly label
    on top in the normal header weight, the canonical name as a
    muted subtext when ``has_override`` is true. Reviewer-facing
    surfaces only need ``friendly`` and ignore the rest.
    """

    friendly: str
    canonical: str
    has_override: bool


def resolve_pair(
    session: ReviewSession, source_type: str, source_field: str
) -> LabelPair:
    """Resolve ``friendly`` + ``canonical`` + ``has_override`` for a slot.

    Single point for operator-facing surfaces that want to show
    the friendly rename alongside the canonical orientation
    string. Reviewer-facing surfaces should keep calling
    :func:`resolve` — they don't render the canonical orientation.
    """
    overrides = all_labels(session)
    canonical = _builtin_default(source_type, source_field)
    if (source_type, source_field) in overrides:
        return LabelPair(
            friendly=overrides[(source_type, source_field)],
            canonical=canonical,
            has_override=True,
        )
    return LabelPair(
        friendly=canonical, canonical=canonical, has_override=False
    )


def upsert(
    db: Session,
    session: ReviewSession,
    *,
    source_type: str,
    source_field: str,
    label: str,
    user: User,
    correlation_id: str | None = None,
) -> SessionFieldLabel:
    """Insert or update the override for one slot.

    Empty / whitespace-only ``label`` is rejected — call
    ``clear`` to remove a row. Raises
    ``FieldLabelSourceError`` for slots outside the 12-slot
    allowlist.

    Invalidates ``validated`` via
    ``lifecycle.invalidate_if_validated`` and emits a
    ``session_field_label.set`` audit event carrying the
    ``[old, new]`` change pair.
    """
    _require_known_source(source_type, source_field)
    normalised = (label or "").strip()
    if not normalised:
        raise ValueError(
            "label cannot be empty or whitespace — call "
            "field_labels.clear() to remove an override"
        )

    existing = db.execute(
        select(SessionFieldLabel).where(
            SessionFieldLabel.session_id == session.id,
            SessionFieldLabel.source_type == source_type,
            SessionFieldLabel.source_field == source_field,
        )
    ).scalar_one_or_none()

    lifecycle.invalidate_if_validated(
        db,
        review_session=session,
        user=user,
        reason="session_field_label_updated",
        correlation_id=correlation_id,
    )

    if existing is None:
        row = SessionFieldLabel(
            session_id=session.id,
            source_type=source_type,
            source_field=source_field,
            label=normalised,
        )
        db.add(row)
        old_value: str | None = None
    else:
        row = existing
        old_value = row.label
        row.label = normalised
    db.flush()

    audit.write_event(
        db,
        event_type="session_field_label.set",
        summary=(
            f"Set friendly label for {source_type}.{source_field} "
            f"to {normalised!r}"
        ),
        actor_user_id=user.id if user else None,
        session=session,
        payload=audit.changes({"label": [old_value, normalised]}),
        context={
            "source_type": source_type,
            "source_field": source_field,
        },
        correlation_id=correlation_id,
    )
    db.commit()
    return row


def clear(
    db: Session,
    session: ReviewSession,
    *,
    source_type: str,
    source_field: str,
    user: User,
    correlation_id: str | None = None,
) -> None:
    """Delete the override for one slot, if present.

    Idempotent: clearing a slot that has no override is a no-op
    (no audit event, no lifecycle invalidation).

    Raises ``FieldLabelSourceError`` for slots outside the
    12-slot allowlist — the resolver is permissive on read but
    the mutators are strict.
    """
    _require_known_source(source_type, source_field)

    existing = db.execute(
        select(SessionFieldLabel).where(
            SessionFieldLabel.session_id == session.id,
            SessionFieldLabel.source_type == source_type,
            SessionFieldLabel.source_field == source_field,
        )
    ).scalar_one_or_none()
    if existing is None:
        return

    cleared_label = existing.label

    lifecycle.invalidate_if_validated(
        db,
        review_session=session,
        user=user,
        reason="session_field_label_cleared",
        correlation_id=correlation_id,
    )

    db.delete(existing)
    db.flush()

    audit.write_event(
        db,
        event_type="session_field_label.cleared",
        summary=(
            f"Cleared friendly label for {source_type}.{source_field} "
            f"(was {cleared_label!r})"
        ),
        actor_user_id=user.id if user else None,
        session=session,
        payload=audit.snapshot(
            {
                "source_type": source_type,
                "source_field": source_field,
                "label": cleared_label,
            }
        ),
        context={
            "source_type": source_type,
            "source_field": source_field,
        },
        correlation_id=correlation_id,
    )
    db.commit()
