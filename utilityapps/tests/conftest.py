"""Utilities' tests run signed in as the fake local super-admin, whatever
the developer's `.env` says; a test that needs someone else changes the
settings itself."""

from __future__ import annotations

import pytest

from cordware.settings import identity_settings


@pytest.fixture(autouse=True)
def _fake_super_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "app_env", "local")
    monkeypatch.setattr(identity_settings, "allow_fake_auth", True)
    monkeypatch.setattr(identity_settings, "fake_auth_email", "admin@example.edu")
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", True)
    monkeypatch.setattr(identity_settings, "super_admin_emails", [])
