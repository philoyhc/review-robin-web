"""Unit tests for ``app.services.email_templates``.

Pin renderer fall-through behaviour (override → default), the
five-tag merge field set, and ``string.Template.safe_substitute``'s
unknown-key tolerance so a typo'd merge tag in an operator override
doesn't 500 the send path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import email_templates


def _session(
    *,
    name: str = "Spring 2026",
    deadline: datetime | None = None,
    help_contact: str | None = None,
    overrides: dict | None = None,
) -> SimpleNamespace:
    """A duck-typed stand-in for ``ReviewSession`` carrying only the
    attributes the renderer reads."""
    return SimpleNamespace(
        name=name,
        deadline=deadline,
        help_contact=help_contact,
        email_template_overrides=overrides,
    )


def _reviewer(name: str = "Rae Reviewer") -> SimpleNamespace:
    return SimpleNamespace(name=name)


# ── Default rendering (no overrides) ─────────────────────────────────────


def test_render_invitation_uses_defaults_when_overrides_null() -> None:
    session = _session()
    subject, body = email_templates.render_invitation(
        session, _reviewer(), invite_url="https://app/invite/abc"
    )
    assert subject == "Invitation to review: Spring 2026"
    assert body == (
        "You've been invited to review for: Spring 2026.\n"
        "Open this link (sign in with your work email): https://app/invite/abc\n"
    )


def test_render_reminder_uses_defaults_when_overrides_null() -> None:
    session = _session()
    subject, body = email_templates.render_reminder(
        session, _reviewer(), invite_url="https://app/invite/abc"
    )
    assert subject == "Reminder: review for Spring 2026"
    assert body == (
        "Reminder — your review for Spring 2026 isn't complete yet.\n"
        "Open this link (sign in with your work email): https://app/invite/abc\n"
    )


# ── Per-key fall-through ─────────────────────────────────────────────────


def test_invitation_override_subject_only_keeps_default_body() -> None:
    session = _session(overrides={"invitation_subject": "Custom: $session_name"})
    subject, body = email_templates.render_invitation(
        session, _reviewer(), invite_url="https://app/x"
    )
    assert subject == "Custom: Spring 2026"
    # Body falls through to default.
    assert "You've been invited to review for: Spring 2026" in body


def test_empty_string_override_falls_through_to_default() -> None:
    session = _session(overrides={"invitation_subject": "   "})
    subject, _ = email_templates.render_invitation(
        session, _reviewer(), invite_url="https://app/x"
    )
    assert subject == "Invitation to review: Spring 2026"


def test_reminder_override_body_keeps_default_subject() -> None:
    session = _session(overrides={"reminder_body": "Hi $reviewer_name — please complete."})
    subject, body = email_templates.render_reminder(
        session, _reviewer("Carol"), invite_url="https://app/x"
    )
    assert subject == "Reminder: review for Spring 2026"
    assert body == "Hi Carol — please complete."


# ── Merge fields ─────────────────────────────────────────────────────────


def test_all_five_merge_fields_substitute() -> None:
    session = _session(
        deadline=datetime(2026, 6, 30, tzinfo=timezone.utc),
        help_contact="Prof X <x@example.edu>",
        overrides={
            "invitation_body": (
                "Hi $reviewer_name,\n"
                "Please review for $session_name (deadline $deadline).\n"
                "Questions? Contact $help_contact.\n"
                "Link: $invite_url\n"
            ),
        },
    )
    _, body = email_templates.render_invitation(
        session, _reviewer("Rae"), invite_url="https://app/i/abc"
    )
    assert body == (
        "Hi Rae,\n"
        "Please review for Spring 2026 (deadline 2026-06-30).\n"
        "Questions? Contact Prof X <x@example.edu>.\n"
        "Link: https://app/i/abc\n"
    )


def test_unknown_merge_tag_passes_through_safely() -> None:
    """An operator typo'd ``$nonsense_tag`` shouldn't 500 — the
    renderer leaves the literal placeholder in the output."""
    session = _session(overrides={"invitation_subject": "$nonsense_tag — $session_name"})
    subject, _ = email_templates.render_invitation(
        session, _reviewer(), invite_url="https://app/x"
    )
    assert subject == "$nonsense_tag — Spring 2026"


def test_help_contact_unset_renders_empty_string() -> None:
    session = _session(overrides={"invitation_body": "Contact: [$help_contact]"})
    _, body = email_templates.render_invitation(
        session, _reviewer(), invite_url="https://app/x"
    )
    assert body == "Contact: []"


def test_deadline_unset_renders_empty_string() -> None:
    session = _session(overrides={"invitation_body": "Deadline: [$deadline]"})
    _, body = email_templates.render_invitation(
        session, _reviewer(), invite_url="https://app/x"
    )
    assert body == "Deadline: []"
