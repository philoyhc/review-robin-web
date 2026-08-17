"""Unit coverage for the config-derived super-admin resolver.

Segment 18S Item 1. ``app/auth/roles.py`` computes super-admin purely
from config: the ``super_admin_emails`` list plus, in a fake-auth
sandbox, the fake identity's email. Never a DB column.
"""
from __future__ import annotations

from app.auth.roles import effective_super_admin_emails, is_super_admin
from app.config import Settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "local",
        "allow_fake_auth": False,
        "fake_auth_super_admin": True,
        "fake_auth_email": "operator@example.edu",
        "super_admin_emails": [],
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


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


def test_fake_email_folded_in_only_under_fake_auth() -> None:
    # Both flags on + allow_fake_auth → fake email is super-admin.
    on = _settings(allow_fake_auth=True, fake_auth_super_admin=True)
    assert is_super_admin("operator@example.edu", on) is True
    assert "operator@example.edu" in effective_super_admin_emails(on)

    # allow_fake_auth off → fold-in inert even with the toggle on.
    fake_off = _settings(allow_fake_auth=False, fake_auth_super_admin=True)
    assert is_super_admin("operator@example.edu", fake_off) is False

    # Toggle off → fold-in inert even under fake auth.
    toggle_off = _settings(allow_fake_auth=True, fake_auth_super_admin=False)
    assert is_super_admin("operator@example.edu", toggle_off) is False


def test_effective_set_combines_config_and_fake_fold_in() -> None:
    s = _settings(
        allow_fake_auth=True,
        fake_auth_super_admin=True,
        super_admin_emails=["boss@example.edu"],
    )
    effective = effective_super_admin_emails(s)
    assert "boss@example.edu" in effective
    assert "operator@example.edu" in effective
