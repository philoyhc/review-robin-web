"""Super-admin as RRW reads it: Cordware's platform role.

Segment 18S Item 1, moved onto Cordware's switches by segment 21C C3.
``app/auth/roles.py`` reads ``cordware.identity``: the
``SUPER_ADMIN_EMAILS`` list plus, under local fake auth, the fake
account's email. Never a DB column.
"""
from __future__ import annotations

import pytest

from app.auth.roles import is_super_admin, super_admin_configured, super_admin_emails
from cordware.identity import Identity
from cordware.settings import identity_settings


@pytest.fixture
def platform(monkeypatch: pytest.MonkeyPatch):
    """Set Cordware's super-admin switches; fake auth starts off."""

    def configure(
        emails: list[str] | None = None, *, fake: bool = False, fold_in: bool = True
    ) -> None:
        monkeypatch.setattr(identity_settings, "super_admin_emails", list(emails or []))
        monkeypatch.setattr(identity_settings, "allow_fake_auth", fake)
        monkeypatch.setattr(identity_settings, "fake_auth_super_admin", fold_in)
        monkeypatch.setattr(identity_settings, "fake_auth_email", "operator@example.edu")

    configure()
    return configure


def test_configured_email_is_super_admin(platform) -> None:
    platform(["boss@example.edu"])
    assert is_super_admin("boss@example.edu") is True


def test_membership_is_case_insensitive(platform) -> None:
    platform(["Boss@Example.EDU"])
    assert is_super_admin("boss@example.edu") is True
    assert super_admin_emails() == ("boss@example.edu",)


def test_non_member_is_not_super_admin(platform) -> None:
    platform(["boss@example.edu"])
    assert is_super_admin("someone@example.edu") is False


def test_empty_or_missing_email_is_never_super_admin(platform) -> None:
    platform(["boss@example.edu"])
    assert is_super_admin(None) is False
    assert is_super_admin("") is False
    assert is_super_admin("   ") is False


def test_fake_email_folded_in_only_under_fake_auth(platform) -> None:
    # Both switches on → the fake email is super-admin.
    platform(fake=True, fold_in=True)
    assert is_super_admin("operator@example.edu") is True
    assert "operator@example.edu" in super_admin_emails()

    # Fake auth off → fold-in inert even with the toggle on.
    platform(fake=False, fold_in=True)
    assert is_super_admin("operator@example.edu") is False

    # Toggle off → fold-in inert even under fake auth.
    platform(fake=True, fold_in=False)
    assert is_super_admin("operator@example.edu") is False


def test_effective_set_combines_config_and_fake_fold_in(platform) -> None:
    platform(["boss@example.edu"], fake=True)
    assert super_admin_emails() == ("boss@example.edu", "operator@example.edu")


@pytest.mark.parametrize(
    ("emails", "fake", "configured"),
    [([], False, False), (["boss@example.edu"], False, True), ([], True, True)],
    ids=["empty", "listed", "fake-only"],
)
def test_configured_follows_the_effective_list(platform, emails, fake, configured) -> None:
    """The fallback's test: with nothing configured, any admin manages
    admins (18S Item 2). Local fake auth with an empty list still counts
    the fake account, as before."""
    platform(emails, fake=fake)
    assert super_admin_configured() is configured


@pytest.mark.parametrize(
    ("emails", "fake"),
    [([], False), (["boss@example.edu"], False), ([], True), (["boss@example.edu"], True)],
)
def test_the_identity_flag_agrees_with_the_predicate(platform, emails, fake) -> None:
    """`Identity.is_super_admin` is computed, never stored, so it and the
    host-level predicate cannot disagree (v0.8 §3)."""
    platform(emails, fake=fake)
    for email in ("boss@example.edu", "operator@example.edu", "other@example.edu"):
        identity = Identity(principal_id="p", email=email, name=None)
        assert identity.is_super_admin is is_super_admin(email)
        assert identity.super_admin_configured is super_admin_configured()
