"""Segment AD2X: Apply Desk's account menu offers *Switch to …* on a local
run with two fake accounts, and following it signs in the second one."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from applydesk.tests._host import host_with
from cordware.settings import identity_settings

pytestmark = pytest.mark.usefixtures("applydesk_db")


def test_the_account_menu_switches_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_alt_email", "divya.petrova@example.edu")
    monkeypatch.setattr(identity_settings, "fake_auth_alt_name", "Divya Petrova")
    client = TestClient(host_with(("applydesk",))[0])
    page = client.get("/applydesk/me").text
    assert "data-switch-identity>Switch to Divya Petrova</a>" in page
    href = page.split("data-switch-identity")[0].rsplit('href="', 1)[1].split('"')[0]
    client.get(href.replace("&amp;", "&"), follow_redirects=False)
    assert "data-switch-identity>Switch to Local Operator</a>" in client.get("/applydesk/me").text


def test_no_second_account_no_menu_item(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_alt_email", "")
    page = TestClient(host_with(("applydesk",))[0]).get("/applydesk/me").text
    assert "data-switch-identity" not in page


def test_the_second_account_is_its_directory_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex on #4278: the local directory's Divya Petrova and the switched-to
    account are one object ID, so a directory pick and a sign-in bind one
    person."""
    from applydesk import directory
    from cordware.identity import (
        alternate_identity,
    )

    monkeypatch.setattr(identity_settings, "fake_auth_alt_email", "divya.petrova@example.edu")
    monkeypatch.setattr(identity_settings, "fake_auth_alt_principal_id", "")
    entry = next(u for u in directory._local_users() if u.mail == "divya.petrova@example.edu")  # pyright: ignore[reportPrivateUsage]  -- the local list
    alternate = alternate_identity(identity_settings)
    assert alternate is not None and alternate.principal_id == entry.id
