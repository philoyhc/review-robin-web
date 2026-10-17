"""``session.*`` parse + apply.

Two sides of one section: ``_apply_session_kv`` consumes
``session.<key>`` rows during the parse phase; ``_apply_session_metadata``
writes the parsed overrides onto the live ``ReviewSession`` during the
apply phase.
"""
from __future__ import annotations

from sqlalchemy.orm import object_session

from app.db.models import ReviewSession
from app.services import sessions

from app.services.participant_info import (
    SelfFieldsError,
    normalize_self_fields,
    self_fields_columns,
)

from ._apply_shared import (
    _ParseError,
    _ParsedConfig,
    _parse_bool,
    _parse_datetime,
    _parse_json,
)

#: The Settings CSV's own-entry selections (participant info Items 1, 4
#: and 5): the `session.*` key, and the participant it normalizes against.
_SELF_FIELDS_KEYS = self_fields_columns()


#: The ``session.*`` keys applied only where the destination is blank
#: (``_apply_session_metadata``); the rest are force-applied.
SESSION_FALLBACK_KEYS = ("name", "code", "description", "deadline", "help_contact")


def _apply_session_kv(
    plan: _ParsedConfig, field_path: str, value: str
) -> None:
    key = field_path.removeprefix("session.")
    if key in {"assignment_mode", "status"}:
        # Defensively ignored even if exported — these are
        # machine-derived per the inclusion model.
        return
    if key in {
        "deadline",
        "scheduled_activate_at",
        "responses_release_at",
        "responses_release_until",
    }:
        plan.session_overrides[key] = _parse_datetime(value)
        return
    if key == "display_timezone":
        plan.session_overrides[key] = value or None
        return
    if key == "self_reviews_active":
        plan.session_overrides[key] = _parse_bool(value, default=True)
        return
    if key in {"relationships_enabled", "observers_enabled"}:
        # Segment 18P PR A1 — per-session feature toggles. Config,
        # not operator-typed identity, so force-applied (below) to
        # mirror the source — except that the lock-on-data rule holds
        # here as on Session Home: a roster with rows keeps its flag on
        # (findings S6, 2026-10-16).
        plan.session_overrides[key] = _parse_bool(value, default=False)
        return
    # Segment 18N PR 5 — the 18G scheduled-event offset / list /
    # retention columns. Round-trip uses typed-cell parses; the
    # ``parse_and_validate_*`` editor-side helpers in
    # ``scheduled_events`` enforce save-time constraints (lead
    # time, format) the operator gets on a direct edit. The parse
    # phase runs those rules but the lead-time floor, so an exported
    # schedule whose moments have since passed still imports
    # (``session_offset_errors``, findings L1), and the
    # cross-field ordering chain (``session_schedule_order_errors``,
    # findings G22).
    if key in {"invite_offsets", "reminder_offsets"}:
        # Comma-separated offset strings on the editor form; the
        # column stores ``list[str] | None``. Empty cell → None
        # (operator cleared the field).
        if not value:
            plan.session_overrides[key] = None
        else:
            entries = [
                entry.strip() for entry in value.split(",") if entry.strip()
            ]
            plan.session_overrides[key] = entries or None
        return
    if key == "archive_offset":
        plan.session_overrides[key] = value or None
        return
    if key == "retention_exception":
        # Tri-state column (``Boolean | None``); empty cell → None,
        # otherwise standard truthy parse.
        plan.session_overrides[key] = _parse_bool(value) if value else None
        return
    if key == "retention_overrides":
        # Open-ended JSON dict; empty cell → None to match the
        # column's nullable shape.
        parsed = _parse_json(value, default=None)
        plan.session_overrides[key] = parsed if parsed else None
        return
    if key in _SELF_FIELDS_KEYS:
        # participant info Items 1, 4 and 5. Blank → ``None`` (the
        # default); a JSON list of roster field keys otherwise, ``[]``
        # meaning nothing. An unknown key is refused rather than dropped.
        if not value:
            plan.session_overrides[key] = None
            return
        parsed = _parse_json(value, default=None)
        if not isinstance(parsed, list) or not all(
            isinstance(item, str) for item in parsed
        ):
            raise _ParseError(
                f"expected a JSON list of field keys, got {value!r}"
            )
        try:
            plan.session_overrides[key] = normalize_self_fields(
                _SELF_FIELDS_KEYS[key], parsed
            )
        except SelfFieldsError as exc:
            raise _ParseError(str(exc)) from exc
        return
    if key in {"name", "code", "description", "help_contact"}:
        plan.session_overrides[key] = value or None


def _apply_session_metadata(
    review_session: ReviewSession, plan: _ParsedConfig
) -> int:
    """Apply session.* keys with the fallback rule: write the
    snapshot value only when the destination's existing field is
    empty / None.

    The single rule covers both flows naturally — on Create New
    Session, operator-typed fields are non-empty so the snapshot
    fills in only the blanks; on Session Home (existing session),
    the destination already has values so the snapshot is
    effectively read-and-ignored. ``code`` follows the same
    rule (suffix-derivation on collision is a deferred follow-on
    per the 12A-2 plan)."""

    written = 0
    overrides = plan.session_overrides
    for key in SESSION_FALLBACK_KEYS:
        if key not in overrides:
            continue
        existing = getattr(review_session, key, None)
        if existing not in (None, ""):
            continue
        setattr(review_session, key, overrides[key])
        written += 1
    # ``display_timezone`` + ``self_reviews_active`` are session
    # *config*, not operator-typed identity — force-apply them. The
    # empty-only fallback rule above would never fire for either: a
    # created session always carries a stamped timezone and a
    # default ``self_reviews_active``. Force-apply matches the
    # wholesale replace of every other config section.
    #
    # Segment 18N PR 5 — the eight 18G scheduled-event columns
    # follow the same config-not-identity rule: force-apply on
    # every import so a deleted offset on the source disappears
    # from the destination too.
    for key in (
        "display_timezone",
        "self_reviews_active",
        "relationships_enabled",
        "observers_enabled",
        "reviewer_self_fields",
        "reviewee_self_fields",
        "observer_self_fields",
        "scheduled_activate_at",
        "responses_release_at",
        "responses_release_until",
        "invite_offsets",
        "reminder_offsets",
        "archive_offset",
        "retention_exception",
        "retention_overrides",
    ):
        if key not in overrides:
            continue
        if _locked_on(review_session, key, overrides[key]):
            continue
        setattr(review_session, key, overrides[key])
        written += 1
    return written


def _locked_on(review_session: ReviewSession, key: str, new: object) -> bool:
    """Whether turning ``key`` off would orphan roster rows, so the
    import leaves it on: the lock-on-data rule
    ``sessions.update_session`` applies to the Session Home toggle
    (``spec/participant_model.md`` §2)."""
    if new is not False or getattr(review_session, key) is not True:
        return False
    db = object_session(review_session)
    if db is None:
        return False
    if key == "relationships_enabled":
        return sessions._has_relationships(db, review_session.id)
    if key == "observers_enabled":
        return sessions._has_observers(db, review_session.id)
    return False
