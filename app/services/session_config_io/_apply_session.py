"""``session.*`` parse + apply.

Two sides of one section: ``_apply_session_kv`` consumes
``session.<key>`` rows during the parse phase; ``_apply_session_metadata``
writes the parsed overrides onto the live ``ReviewSession`` during the
apply phase.
"""
from __future__ import annotations

from app.db.models import ReviewSession

from ._apply_shared import (
    _ParsedConfig,
    _parse_bool,
    _parse_datetime,
    _parse_json,
)


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
    # Segment 18N PR 5 — the 18G scheduled-event offset / list /
    # retention columns. Round-trip uses typed-cell parses; the
    # ``parse_and_validate_*`` editor-side helpers in
    # ``scheduled_events`` enforce save-time constraints (lead
    # time, format) the operator gets on a direct edit. A round-
    # tripped value already passed those when it was originally
    # set, so this path just persists the raw value back.
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
    for key in ("name", "code", "description", "deadline", "help_contact"):
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
        "scheduled_activate_at",
        "responses_release_at",
        "responses_release_until",
        "invite_offsets",
        "reminder_offsets",
        "archive_offset",
        "retention_exception",
        "retention_overrides",
    ):
        if key in overrides:
            setattr(review_session, key, overrides[key])
            written += 1
    return written
