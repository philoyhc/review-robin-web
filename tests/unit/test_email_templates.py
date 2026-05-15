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
        deadline=datetime(2026, 6, 30, 17, 0, tzinfo=timezone.utc),
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
        "Please review for Spring 2026 (deadline 2026-06-30 17:00).\n"
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


# ── Responses-received render (Segment 11E PR 6) ─────────────────────────


def test_render_responses_received_uses_no_help_contact_default_when_unset() -> None:
    """With no help_contact and no body override, the default body
    drops the trailing "Questions? Contact …" line — printing a
    hollow ``Contact .`` reads worse in a closing confirmation."""
    session = _session()
    subject, body = email_templates.render_responses_received(
        session, _reviewer("Rae")
    )
    assert subject == "Responses received: Spring 2026"
    assert body == (
        "Hi Rae,\n"
        "\n"
        "Thanks. Your responses for Spring 2026 are recorded as of "
        "(not yet submitted).\n"
    )


def test_render_responses_received_uses_help_contact_default_when_set() -> None:
    session = _session(help_contact="help@example.edu")
    _, body = email_templates.render_responses_received(
        session, _reviewer("Rae")
    )
    assert body == (
        "Hi Rae,\n"
        "\n"
        "Thanks. Your responses for Spring 2026 are recorded as of "
        "(not yet submitted).\n"
        "\n"
        "Questions? Contact help@example.edu.\n"
    )


def test_render_responses_received_override_body_substitutes_verbatim() -> None:
    """Operator-supplied bodies that reference ``$help_contact`` get
    the placeholder behaviour (empty string) — that's their decision
    to make."""
    session = _session(
        overrides={
            "responses_received_body": (
                "Submitted at $submitted_at — contact [$help_contact]."
            ),
        },
    )
    _, body = email_templates.render_responses_received(
        session, _reviewer("Rae")
    )
    assert body == "Submitted at (not yet submitted) — contact []."


def test_render_responses_received_override_subject_substitutes() -> None:
    session = _session(
        overrides={"responses_received_subject": "Got it: $session_name"},
    )
    subject, _ = email_templates.render_responses_received(
        session, _reviewer()
    )
    assert subject == "Got it: Spring 2026"


def test_render_responses_received_drops_invite_url_tag() -> None:
    """``$invite_url`` is moot post-submit; an override that
    references it leaves the literal placeholder in the output
    (safe_substitute behaviour)."""
    session = _session(
        overrides={"responses_received_body": "Link was: $invite_url"},
    )
    _, body = email_templates.render_responses_received(
        session, _reviewer()
    )
    assert body == "Link was: $invite_url"


# ── responses_received_enabled toggle ────────────────────────────────────


def test_responses_received_enabled_default_is_true_when_no_overrides() -> None:
    assert email_templates.responses_received_enabled(_session()) is True


def test_responses_received_enabled_default_is_true_when_key_absent() -> None:
    session = _session(overrides={"invitation_subject": "Custom"})
    assert email_templates.responses_received_enabled(session) is True


def test_responses_received_enabled_honours_explicit_false() -> None:
    session = _session(overrides={"responses_received_enabled": False})
    assert email_templates.responses_received_enabled(session) is False


def test_responses_received_enabled_honours_explicit_true() -> None:
    session = _session(overrides={"responses_received_enabled": True})
    assert email_templates.responses_received_enabled(session) is True


def test_responses_received_enabled_ignores_non_bool_value() -> None:
    """Defensive: a stale non-bool value (e.g. operator manually
    poking the JSON) falls through to the default rather than
    truthy-coercing."""
    session = _session(overrides={"responses_received_enabled": "yes"})
    assert email_templates.responses_received_enabled(session) is True


def test_set_responses_received_enabled_returns_none_when_unchanged() -> None:
    session = _session()  # default-on
    assert (
        email_templates.set_responses_received_enabled(session, enabled=True)
        is None
    )
    assert session.email_template_overrides is None


def test_set_responses_received_enabled_to_false_stores_explicit_value() -> None:
    session = _session()
    diff = email_templates.set_responses_received_enabled(session, enabled=False)
    assert diff == [True, False]
    assert session.email_template_overrides == {
        "responses_received_enabled": False
    }


def test_set_responses_received_enabled_back_to_true_removes_key() -> None:
    """Re-checking the editor checkbox returns the JSON to its
    minimal form rather than storing an explicit ``True``."""
    session = _session(overrides={"responses_received_enabled": False})
    diff = email_templates.set_responses_received_enabled(session, enabled=True)
    assert diff == [False, True]
    # Removing the only key empties the dict; the setter coerces an
    # empty dict back to None to keep the column tidy.
    assert session.email_template_overrides is None


def test_set_responses_received_enabled_preserves_other_overrides() -> None:
    session = _session(
        overrides={
            "invitation_subject": "Custom",
            "responses_received_enabled": False,
        },
    )
    diff = email_templates.set_responses_received_enabled(session, enabled=True)
    assert diff == [False, True]
    assert session.email_template_overrides == {"invitation_subject": "Custom"}
