"""Email-template rendering for invitations, reminders, and the
post-submit responses-received confirmation.

Layered between ``app/services/invitations.py`` / the reviewer-submit
handler (Segment 11C Part 2 PR H) and the ``email_template_overrides``
JSON column on ``ReviewSession`` (populated by the operator-facing
editor — Segment 11E PRs 2 + 6). Per-session overrides fall through
key-by-key to the in-code defaults below; rendering uses
``string.Template.safe_substitute`` so a typo'd merge tag in an
override doesn't 500 the send path.

Merge-field sets:

- Invitation / reminder: ``$reviewer_name``, ``$session_name``,
  ``$deadline``, ``$help_contact``, ``$invite_url`` — five tags.
- Responses-received: ``$reviewer_name``, ``$session_name``,
  ``$deadline``, ``$help_contact``, ``$submitted_at`` — drops
  ``$invite_url`` (moot post-submit), adds ``$submitted_at``.

Operators type their templates with these tags and we substitute at
send time.

The ``string.Template``-style ``$placeholder`` syntax is preferred
over ``{{placeholder}}`` (Jinja-style) because ``Template`` is in
the stdlib and the renderer never needs full template-engine
machinery (loops / conditionals / filters) — substitution is the
whole job. The editor surface in PR 2 will document the tag
notation in operator-facing copy.
"""

from __future__ import annotations

from datetime import datetime
from string import Template
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as ORMSession
from sqlalchemy.orm.exc import UnmappedInstanceError

from app.db.models import Assignment, Response, Reviewer, ReviewSession, User
from app.services import audit as audit_service
from app.services.date_formatting import format_datetime

# Default templates — verbatim parameterisations of the strings the
# original ``invitations._email_body`` / ``_reminder_body`` helpers
# produced (with the new merge fields slotted in). A session whose
# ``email_template_overrides`` is ``NULL`` (the post-migration default
# for every existing row) renders byte-identically to the pre-Segment-
# 11E behaviour modulo the new merge tags.

DEFAULT_INVITATION_SUBJECT = "Invitation to review: $session_name"
DEFAULT_INVITATION_BODY = (
    "You've been invited to review for: $session_name.\n"
    "Open this link (sign in with your work email): $invite_url\n"
)
DEFAULT_REMINDER_SUBJECT = "Reminder: review for $session_name"
DEFAULT_REMINDER_BODY = (
    "Reminder — your review for $session_name isn't complete yet.\n"
    "Open this link (sign in with your work email): $invite_url\n"
)
DEFAULT_RESPONSES_RECEIVED_SUBJECT = "Responses received: $session_name"
DEFAULT_RESPONSES_RECEIVED_BODY = (
    "Hi $reviewer_name,\n"
    "\n"
    "Thanks. Your responses for $session_name are recorded as of "
    "$submitted_at.\n"
    "\n"
    "Questions? Contact $help_contact.\n"
)
# Variant rendered automatically when ``session.help_contact`` is
# unset and the operator hasn't overridden the body — printing
# "Questions? Contact ()" reads worse in a closing confirmation
# than just dropping the line. Override bodies that reference
# ``$help_contact`` always go through the substitute path verbatim,
# so an operator who explicitly wants the placeholder behaviour
# gets it.
DEFAULT_RESPONSES_RECEIVED_BODY_NO_HELP_CONTACT = (
    "Hi $reviewer_name,\n"
    "\n"
    "Thanks. Your responses for $session_name are recorded as of "
    "$submitted_at.\n"
)


# Override-keys recognised on ``ReviewSession.email_template_overrides``.
# Listed here so a future addition (or the editor in PR 2) has one
# place to update. The ``responses_received_enabled`` boolean toggle
# lives outside this tuple — ``set_overrides`` only handles string
# overrides; ``responses_received_enabled`` has its own getter / setter.
OVERRIDE_KEYS = (
    "invitation_subject",
    "invitation_body",
    "invitation_cc",
    "invitation_bcc",
    "reminder_subject",
    "reminder_body",
    "reminder_cc",
    "reminder_bcc",
    "responses_received_subject",
    "responses_received_body",
    "responses_received_cc",
    "responses_received_bcc",
)
RESPONSES_RECEIVED_ENABLED_KEY = "responses_received_enabled"


def _resolve(
    review_session: ReviewSession, key: str, default: str
) -> str:
    """Return the operator-supplied override for ``key`` if non-empty,
    otherwise ``default``. Treats ``NULL`` (no overrides at all) and
    a missing-or-empty key both as fall-through."""
    overrides = review_session.email_template_overrides or {}
    value = overrides.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return default


def _substitute(template_str: str, **merge: Any) -> str:
    """``string.Template.safe_substitute`` with stringified values.

    ``safe_substitute`` returns the literal placeholder when a key
    is missing or unknown — the editor surface in PR 2 will warn an
    operator who introduces an unrecognised tag, but at send time
    we never want a typo to 500 the request.
    """
    return Template(template_str).safe_substitute(
        {k: ("" if v is None else str(v)) for k, v in merge.items()}
    )


def _format_deadline(review_session: ReviewSession) -> str:
    # Canonical date-time render (Segment 18B PR 1): the deadline
    # is operator-entered with a time component, so the time is
    # shown and an explicit zone token carried.
    return format_datetime(review_session.deadline)


def _merge_context(
    review_session: ReviewSession,
    reviewer: Reviewer | None,
    invite_url: str,
) -> dict[str, str]:
    return {
        "reviewer_name": (reviewer.name if reviewer is not None else ""),
        "session_name": review_session.name,
        "deadline": _format_deadline(review_session),
        "help_contact": review_session.help_contact or "",
        "invite_url": invite_url,
    }


def render_invitation(
    review_session: ReviewSession,
    reviewer: Reviewer,
    invite_url: str,
) -> tuple[str, str]:
    """Returns ``(subject, body)`` for the invitation email."""
    merge = _merge_context(review_session, reviewer, invite_url)
    subject = _substitute(
        _resolve(review_session, "invitation_subject", DEFAULT_INVITATION_SUBJECT),
        **merge,
    )
    body = _substitute(
        _resolve(review_session, "invitation_body", DEFAULT_INVITATION_BODY),
        **merge,
    )
    return subject, body


def render_reminder(
    review_session: ReviewSession,
    reviewer: Reviewer,
    invite_url: str,
) -> tuple[str, str]:
    """Returns ``(subject, body)`` for the reminder email."""
    merge = _merge_context(review_session, reviewer, invite_url)
    subject = _substitute(
        _resolve(review_session, "reminder_subject", DEFAULT_REMINDER_SUBJECT),
        **merge,
    )
    body = _substitute(
        _resolve(review_session, "reminder_body", DEFAULT_REMINDER_BODY),
        **merge,
    )
    return subject, body


def _latest_submitted_at(
    review_session: ReviewSession, reviewer: Reviewer
) -> datetime | None:
    """Most recent ``Response.submitted_at`` across all responses for
    ``reviewer`` in ``review_session``, or ``None`` if nothing has been
    submitted yet.

    Used by ``render_responses_received`` to resolve ``$submitted_at``.
    Pulls the SQLAlchemy session off ``reviewer`` via ``object_session``
    to keep the render signature symmetric with ``render_invitation``
    / ``render_reminder`` (no ``db`` parameter). Returns ``None`` for
    duck-typed test stand-ins (``object_session`` raises
    ``UnmappedInstanceError``) and for mapped instances detached from
    a session — callers fall back to a placeholder string."""
    try:
        db = ORMSession.object_session(reviewer)
    except UnmappedInstanceError:
        return None
    if db is None:
        return None
    return db.execute(
        select(func.max(Response.submitted_at))
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(
            Assignment.session_id == review_session.id,
            Assignment.reviewer_id == reviewer.id,
        )
    ).scalar()


def _format_submitted_at(submitted_at: datetime | None) -> str:
    """Format ``$submitted_at`` for the responses-received body.

    Returns ``"(not yet submitted)"`` when no submission exists yet —
    only the editor preview path hits this branch in practice; the
    live send path always has a stamped ``submitted_at``."""
    if submitted_at is None:
        return "(not yet submitted)"
    return format_datetime(submitted_at)


def render_responses_received(
    review_session: ReviewSession, reviewer: Reviewer
) -> tuple[str, str]:
    """Returns ``(subject, body)`` for the responses-received
    confirmation sent when a reviewer submits their review.

    Drops ``$invite_url`` (moot post-submit); adds ``$submitted_at``,
    formatted ``YYYY-MM-DD HH:MM TZ``. When the operator hasn't
    overridden the body and ``session.help_contact`` is unset, the
    "Questions? Contact …" line is dropped from the default body
    rather than rendering a hollow ``Contact .`` — operator-supplied
    bodies that reference ``$help_contact`` substitute verbatim
    (empty string), preserving operator intent."""
    submitted_at = _latest_submitted_at(review_session, reviewer)
    merge: dict[str, str] = {
        "reviewer_name": (reviewer.name if reviewer is not None else ""),
        "session_name": review_session.name,
        "deadline": _format_deadline(review_session),
        "help_contact": review_session.help_contact or "",
        "submitted_at": _format_submitted_at(submitted_at),
    }
    subject = _substitute(
        _resolve(
            review_session,
            "responses_received_subject",
            DEFAULT_RESPONSES_RECEIVED_SUBJECT,
        ),
        **merge,
    )
    body_override = get_override(review_session, "responses_received_body")
    if body_override is not None and body_override.strip():
        body_template = body_override
    elif review_session.help_contact:
        body_template = DEFAULT_RESPONSES_RECEIVED_BODY
    else:
        body_template = DEFAULT_RESPONSES_RECEIVED_BODY_NO_HELP_CONTACT
    body = _substitute(body_template, **merge)
    return subject, body


def responses_received_enabled(review_session: ReviewSession) -> bool:
    """Per-session toggle: should the responses-received confirmation
    auto-send when a reviewer submits?

    Default ``True`` when the override key is missing or stored as a
    non-bool (the editor's checkbox starts checked). Honours an
    explicit ``True`` and an explicit ``False``. Consumed by Segment
    11C Part 2 PR H's submit-time enqueue."""
    overrides = review_session.email_template_overrides or {}
    value = overrides.get(RESPONSES_RECEIVED_ENABLED_KEY)
    if isinstance(value, bool):
        return value
    return True


def set_responses_received_enabled(
    review_session: ReviewSession, enabled: bool
) -> list[Any] | None:
    """Update the per-session "send on submit" toggle.

    Stores explicit ``False`` when the operator opts out. When
    ``enabled`` is ``True`` (the default), removes the key entirely so
    the JSON stays minimal — the reader treats both "key absent" and
    "explicit ``True``" identically. Returns ``[old, new]`` for the
    audit detail when the effective value changes; ``None`` otherwise."""
    current: dict[str, Any] = dict(review_session.email_template_overrides or {})
    raw = current.get(RESPONSES_RECEIVED_ENABLED_KEY)
    old_effective = raw if isinstance(raw, bool) else True
    if old_effective == enabled:
        return None
    if enabled:
        current.pop(RESPONSES_RECEIVED_ENABLED_KEY, None)
    else:
        current[RESPONSES_RECEIVED_ENABLED_KEY] = False
    review_session.email_template_overrides = current or None
    return [old_effective, enabled]


def cc_bcc_for(
    review_session: ReviewSession, kind: str
) -> tuple[str | None, str | None]:
    """Returns ``(cc, bcc)`` from the override JSON for the given email
    kind. ``kind`` is ``"invitation"``, ``"reminder"``, or
    ``"responses_received"``; values are the raw operator-entered
    comma-separated strings, or ``None`` when the override is unset
    / blank.

    Consumed by the queue path in ``app.services.invitations`` to
    populate ``EmailOutbox.cc_emails`` / ``bcc_emails`` (added by the
    Segment 11C PR 2 outbox-schema slice)."""
    cc_key = f"{kind}_cc"
    bcc_key = f"{kind}_bcc"
    overrides = review_session.email_template_overrides or {}
    cc = overrides.get(cc_key)
    bcc = overrides.get(bcc_key)
    cc_value = cc.strip() if isinstance(cc, str) and cc.strip() else None
    bcc_value = bcc.strip() if isinstance(bcc, str) and bcc.strip() else None
    return cc_value, bcc_value


# ── Editor helpers (Segment 11E PR 2) ────────────────────────────────────


# Maps each (template, field) pair to its override key + default value.
# The editor's GET / POST handlers iterate the appropriate slice; the
# table is the single source of truth for which (template, field)
# pairs the editor surfaces.
TEMPLATE_FIELDS: dict[str, list[dict[str, str]]] = {
    "invitation": [
        {"field": "subject", "key": "invitation_subject", "default": DEFAULT_INVITATION_SUBJECT},
        {"field": "body", "key": "invitation_body", "default": DEFAULT_INVITATION_BODY},
        {"field": "cc", "key": "invitation_cc", "default": ""},
        {"field": "bcc", "key": "invitation_bcc", "default": ""},
    ],
    "reminder": [
        {"field": "subject", "key": "reminder_subject", "default": DEFAULT_REMINDER_SUBJECT},
        {"field": "body", "key": "reminder_body", "default": DEFAULT_REMINDER_BODY},
        {"field": "cc", "key": "reminder_cc", "default": ""},
        {"field": "bcc", "key": "reminder_bcc", "default": ""},
    ],
    "responses_received": [
        {
            "field": "subject",
            "key": "responses_received_subject",
            "default": DEFAULT_RESPONSES_RECEIVED_SUBJECT,
        },
        {
            "field": "body",
            "key": "responses_received_body",
            "default": DEFAULT_RESPONSES_RECEIVED_BODY,
        },
        {"field": "cc", "key": "responses_received_cc", "default": ""},
        {"field": "bcc", "key": "responses_received_bcc", "default": ""},
    ],
}


def get_override(review_session: ReviewSession, key: str) -> str | None:
    """Returns the operator-supplied override for ``key``, or ``None``
    if no override is set. Distinct from ``_resolve`` which falls back
    to the default — the editor needs to know whether an override
    exists so it can decide whether to render a "Reset to default"
    link next to the field."""
    overrides = review_session.email_template_overrides or {}
    value = overrides.get(key)
    if isinstance(value, str):
        return value
    return None


def set_overrides(
    review_session: ReviewSession,
    updates: dict[str, str | None],
) -> dict[str, list[Any]]:
    """Apply per-key updates to the session's
    ``email_template_overrides`` JSON. Returns a ``{key: [old, new]}``
    diff for audit. ``None`` value removes the key (resets to default);
    a string value upserts."""
    current: dict[str, Any] = dict(review_session.email_template_overrides or {})
    changes: dict[str, list[Any]] = {}
    for key, new_value in updates.items():
        if key not in OVERRIDE_KEYS:
            continue
        old_value = current.get(key)
        if new_value is None:
            if old_value is not None:
                changes[key] = [old_value, None]
                del current[key]
        else:
            if old_value != new_value:
                changes[key] = [old_value, new_value]
                current[key] = new_value
    review_session.email_template_overrides = current or None
    return changes


# --------------------------------------------------------------------------- #
# Audit emit helpers (Segment 11K PR 6)
#
# These two helpers were lifted from the ``setupinvite_save`` and
# ``setupinvite_reset`` route handlers in ``app/web/routes_operator.py``
# so the route stays thin and PR 7 of Segment 11K can sweep them
# through the canonical-shape migration alongside the other settings
# emitters in one PR. The emitted ``detail`` shape is byte-identical
# to the pre-relocation form; canonical-shape conversion happens in
# PR 7.
# --------------------------------------------------------------------------- #


def record_template_change(
    db: ORMSession,
    *,
    review_session: ReviewSession,
    user: User,
    template: str,
    changes: dict[str, list[Any]],
    correlation_id: str | None,
) -> None:
    """Emit ``email_template.updated`` for a Save on the editor.

    No-op if ``changes`` is empty (a Save with no diffs writes no
    audit row, matching the pre-relocation behaviour).
    """
    if not changes:
        return
    audit_service.write_event(
        db,
        event_type="email_template.updated",
        summary=(
            f"Session {review_session.code}: "
            f"{template} template updated"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit_service.changes({k: list(v) for k, v in changes.items()}),
        context={"template": template},
        correlation_id=correlation_id,
    )


def record_template_reset(
    db: ORMSession,
    *,
    review_session: ReviewSession,
    user: User,
    template: str,
    field: str,
    changes: dict[str, list[Any]],
    correlation_id: str | None,
) -> None:
    """Emit ``email_template.reset`` for a per-field Reset to default.

    No-op if ``changes`` is empty (the field was already at default).
    """
    if not changes:
        return
    audit_service.write_event(
        db,
        event_type="email_template.reset",
        summary=(
            f"Session {review_session.code}: "
            f"{template}.{field} reset to default"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit_service.changes({k: list(v) for k, v in changes.items()}),
        context={"template": template, "field": field},
        correlation_id=correlation_id,
    )
