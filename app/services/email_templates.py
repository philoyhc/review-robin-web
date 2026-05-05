"""Email-template rendering for invitations + reminders.

Layered between ``app/services/invitations.py`` (which writes outbox
rows) and the ``email_template_overrides`` JSON column on
``ReviewSession`` (which an operator-facing editor — Segment 11E PR 2
— will populate). Per-session overrides fall through key-by-key to
the in-code defaults below; rendering uses
``string.Template.safe_substitute`` so a typo'd merge tag in an
override doesn't 500 the send path.

Merge-field set is closed and small: ``$reviewer_name``,
``$session_name``, ``$deadline``, ``$help_contact``, ``$invite_url``.
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

from string import Template
from typing import Any

from app.db.models import ReviewSession, Reviewer

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


# Override-keys recognised on ``ReviewSession.email_template_overrides``.
# Listed here so a future addition (or the editor in PR 2) has one
# place to update.
OVERRIDE_KEYS = (
    "invitation_subject",
    "invitation_body",
    "invitation_cc",
    "invitation_bcc",
    "reminder_subject",
    "reminder_body",
    "reminder_cc",
    "reminder_bcc",
)


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
    if review_session.deadline is None:
        return ""
    # Render in ISO date form (UTC). The editor preview will format
    # the same way; reviewer-side display formatting (timezone /
    # locale) is a separate concern.
    return review_session.deadline.strftime("%Y-%m-%d")


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
