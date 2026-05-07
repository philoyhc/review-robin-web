"""Unit tests for the segment 11F PR B email-preview helpers."""

from __future__ import annotations

from types import SimpleNamespace

from app.db.models import User
from app.web import views


# --- resolve_email_preview_tab ------------------------------------------- #


def test_resolve_returns_invitation_when_key_unknown() -> None:
    tab = views.resolve_email_preview_tab("nonsense")

    assert tab.key == "invitation"
    assert tab.is_shipped is True


def test_resolve_returns_invitation_when_key_blank() -> None:
    tab = views.resolve_email_preview_tab("")

    assert tab.key == "invitation"


def test_resolve_returns_invitation_when_key_is_unshipped_reminder() -> None:
    tab = views.resolve_email_preview_tab("reminder")

    # PR B has the Reminder tab in the registry but unshipped, so the
    # caller falls through to the first shipped tab — invitation —
    # rather than rendering an empty region.
    assert tab.key == "invitation"


def test_resolve_returns_responses_received_when_key_matches() -> None:
    # Segment 11E PR 6 ships the render adapter, so ?email=responses_received
    # now resolves to the responses-received tab rather than falling
    # through to invitation.
    tab = views.resolve_email_preview_tab("responses_received")

    assert tab.key == "responses_received"
    assert tab.is_shipped is True


def test_resolve_returns_invitation_when_key_matches() -> None:
    tab = views.resolve_email_preview_tab("invitation")

    assert tab.key == "invitation"


def test_email_preview_tabs_pin_chronological_order() -> None:
    keys = [t.key for t in views.EMAIL_PREVIEW_TABS]

    assert keys == ["invitation", "reminder", "responses_received"]


def test_invitation_and_responses_received_are_shipped() -> None:
    shipped = {t.key for t in views.EMAIL_PREVIEW_TABS if t.is_shipped}

    # Reminder remains unshipped pending Segment 11F PR D.
    assert shipped == {"invitation", "responses_received"}


# --- email_preview_from_display ------------------------------------------ #


def _user(
    *,
    smtp_username: str | None = None,
    smtp_from_display_name: str | None = None,
) -> User:
    """Construct a User with just the SMTP fields the helper reads."""
    return User(
        email="op@example.edu",
        display_name="Op",
        smtp_username=smtp_username,
        smtp_from_display_name=smtp_from_display_name,
    )


def test_from_display_unconfigured_user_returns_settings_pointer() -> None:
    out = views.email_preview_from_display(_user())

    assert "SMTP From not configured" in out
    assert "Settings" in out


def test_from_display_username_only_returns_bare_username() -> None:
    out = views.email_preview_from_display(_user(smtp_username="op@x.edu"))

    assert out == "op@x.edu"


def test_from_display_with_display_name_returns_addr_spec_format() -> None:
    out = views.email_preview_from_display(
        _user(
            smtp_username="op@x.edu",
            smtp_from_display_name="Spring Reviews",
        )
    )

    assert out == "Spring Reviews <op@x.edu>"


def test_from_display_strips_whitespace() -> None:
    out = views.email_preview_from_display(
        _user(
            smtp_username="  op@x.edu  ",
            smtp_from_display_name="  Spring Reviews  ",
        )
    )

    assert out == "Spring Reviews <op@x.edu>"


def test_from_display_blank_display_name_falls_back_to_username() -> None:
    out = views.email_preview_from_display(
        _user(smtp_username="op@x.edu", smtp_from_display_name="   ")
    )

    assert out == "op@x.edu"


# --- build_email_preview_body -------------------------------------------- #


def _session() -> SimpleNamespace:
    return SimpleNamespace(
        name="Spring Reviews",
        deadline=None,
        help_contact="help@example.edu",
        email_template_overrides=None,
    )


def _reviewer() -> SimpleNamespace:
    return SimpleNamespace(name="Alice Smith", email="alice@x.edu")


def test_invitation_render_returns_subject_and_body() -> None:
    tab = views.resolve_email_preview_tab("invitation")

    body = views.build_email_preview_body(
        tab=tab,
        review_session=_session(),  # type: ignore[arg-type]
        reviewer=_reviewer(),  # type: ignore[arg-type]
        from_display="op@x.edu",
    )

    assert body is not None
    assert "Spring Reviews" in body.subject
    # `$reviewer_name` substitution lands the reviewer's name in the
    # body (depending on the seeded default it may or may not appear;
    # the seeded default uses `$session_name` in the body, so just
    # check that's there).
    assert "Spring Reviews" in body.body
    assert body.from_display == "op@x.edu"
    assert body.to_display == "alice@x.edu"


def test_invitation_render_substitutes_invite_url_placeholder() -> None:
    tab = views.resolve_email_preview_tab("invitation")

    body = views.build_email_preview_body(
        tab=tab,
        review_session=_session(),  # type: ignore[arg-type]
        reviewer=_reviewer(),  # type: ignore[arg-type]
        from_display="op@x.edu",
    )

    assert body is not None
    assert views.PREVIEW_INVITE_URL_PLACEHOLDER in body.body


def test_unshipped_tab_returns_none() -> None:
    """If a caller bypasses ``resolve_email_preview_tab`` and asks
    for a tab whose render adapter hasn't shipped, the dispatch
    returns None rather than blowing up."""
    reminder_tab = next(
        t for t in views.EMAIL_PREVIEW_TABS if t.key == "reminder"
    )

    body = views.build_email_preview_body(
        tab=reminder_tab,
        review_session=_session(),  # type: ignore[arg-type]
        reviewer=_reviewer(),  # type: ignore[arg-type]
        from_display="op@x.edu",
    )

    assert body is None


def test_responses_received_render_returns_subject_and_body() -> None:
    tab = views.resolve_email_preview_tab("responses_received")

    body = views.build_email_preview_body(
        tab=tab,
        review_session=_session(),  # type: ignore[arg-type]
        reviewer=_reviewer(),  # type: ignore[arg-type]
        from_display="op@x.edu",
    )

    assert body is not None
    assert body.subject == "Responses received: Spring Reviews"
    # Pre-submit preview surfaces the placeholder for $submitted_at
    # because the duck-typed reviewer isn't attached to a SQLAlchemy
    # session, so the lookup falls through to the placeholder branch.
    assert "(not yet submitted)" in body.body
    assert body.from_display == "op@x.edu"
    assert body.to_display == "alice@x.edu"


# --- merge_tags_for_template -------------------------------------------- #


def test_merge_tags_for_invitation_includes_invite_url() -> None:
    tags = views.merge_tags_for_template("invitation")
    keys = [t["tag"] for t in tags]

    assert "$invite_url" in keys
    assert "$submitted_at" not in keys


def test_merge_tags_for_reminder_matches_invitation() -> None:
    assert (
        views.merge_tags_for_template("reminder")
        == views.merge_tags_for_template("invitation")
    )


def test_merge_tags_for_responses_received_drops_invite_url_adds_submitted_at() -> None:
    tags = views.merge_tags_for_template("responses_received")
    keys = [t["tag"] for t in tags]

    assert "$invite_url" not in keys
    assert "$submitted_at" in keys
    assert keys == [
        "$reviewer_name",
        "$session_name",
        "$deadline",
        "$help_contact",
        "$submitted_at",
    ]
    # Each tag carries a non-empty operator-facing description.
    for tag in tags:
        assert tag["description"]
