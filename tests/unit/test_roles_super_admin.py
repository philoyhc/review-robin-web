"""Unit coverage for the config-derived super-admin resolver.

Segment 18S Item 1. ``app/auth/roles.py`` computes super-admin purely
from config: the ``super_admin_emails`` list plus, in a fake-auth
sandbox, the fake identity's email. Never a DB column.
"""
from __future__ import annotations

import pytest

from app.auth.roles import effective_super_admin_emails, is_super_admin
from app.config import Settings
from cordware.settings import identity_settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "fake_auth_super_admin": True,
        "super_admin_emails": [],
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.fixture
def fake_auth(monkeypatch: pytest.MonkeyPatch):
    """Turn Cordware's fake auth on or off (segment 21C); the fake
    account is the default `operator@example.edu`."""
    monkeypatch.setattr(identity_settings, "fake_auth_email", "operator@example.edu")

    def set_on(on: bool) -> None:
        monkeypatch.setattr(identity_settings, "allow_fake_auth", on)

    set_on(False)
    return set_on


def test_configured_email_is_super_admin() -> None:
    s = _settings(super_admin_emails=["boss@example.edu"])
    assert is_super_admin("boss@example.edu", s) is True


def test_membership_is_case_insensitive() -> None:
    s = _settings(super_admin_emails=["Boss@Example.EDU"])
    assert is_super_admin("boss@example.edu", s) is True


def test_non_member_is_not_super_admin() -> None:
    s = _settings(super_admin_emails=["boss@example.edu"])
    assert is_super_admin("someone@example.edu", s) is False


def test_empty_or_missing_email_is_never_super_admin() -> None:
    s = _settings(super_admin_emails=["boss@example.edu"])
    assert is_super_admin(None, s) is False
    assert is_super_admin("", s) is False


def test_fake_email_folded_in_only_under_fake_auth(fake_auth) -> None:
    # Both flags on + fake auth → fake email is super-admin.
    fake_auth(True)
    on = _settings(fake_auth_super_admin=True)
    assert is_super_admin("operator@example.edu", on) is True
    assert "operator@example.edu" in effective_super_admin_emails(on)

    # Toggle off → fold-in inert even under fake auth.
    toggle_off = _settings(fake_auth_super_admin=False)
    assert is_super_admin("operator@example.edu", toggle_off) is False

    # Fake auth off → fold-in inert even with the toggle on.
    fake_auth(False)
    assert is_super_admin("operator@example.edu", on) is False


def test_effective_set_combines_config_and_fake_fold_in(fake_auth) -> None:
    fake_auth(True)
    s = _settings(
        fake_auth_super_admin=True,
        super_admin_emails=["boss@example.edu"],
    )
    effective = effective_super_admin_emails(s)
    assert "boss@example.edu" in effective
    assert "operator@example.edu" in effective
