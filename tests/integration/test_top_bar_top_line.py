"""The top bar's top line: the workspace's institution name, or none
(segment 20D rung 3, `docs/header_chrome.md` §2, §6)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cordware.settings import identity_settings

_PAGES = ["/operator/sessions", "/me", "/about", "/guide", "/auth/me/debug"]


@pytest.mark.parametrize("path", _PAGES)
def test_no_top_line_when_the_name_is_unset(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setattr(identity_settings, "institution_name", "")
    body = client.get(path).text
    assert 'class="tb-app">Review Robin' in body
    assert 'class="tb-top"' not in body


@pytest.mark.parametrize("path", _PAGES)
def test_every_page_shows_the_name_when_set(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setattr(identity_settings, "institution_name", " Example University ")
    body = client.get(path).text
    assert '<span class="tb-top">Example University</span>' in body


def test_the_name_is_escaped(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(identity_settings, "institution_name", "A & <B>")
    body = client.get("/operator/sessions").text
    assert '<span class="tb-top">A &amp; &lt;B&gt;</span>' in body



def test_accounts_management_shows_the_default_unit_as_a_pill(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """20D rung 4 scaffold: the Unit column follows Name; with no Unit
    set, the workspace default shows as a display pill, else a dash."""
    from app.config import settings

    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    monkeypatch.setattr(identity_settings, "institution_name", "")
    body = client.get("/operator/sys-admin/users").text
    assert "<th>Name</th>\n          <th>Unit</th>" in body
    assert "<td data-unit-cell>—</td>" in body

    monkeypatch.setattr(identity_settings, "institution_name", "Example University")
    body = client.get("/operator/sys-admin/users").text
    assert (
        '<td data-unit-cell><span class="pill pill-count" '
        'title="The workspace default">Example University</span></td>'
    ) in body


def test_settings_shows_the_unit_read_only(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(identity_settings, "institution_name", "Example University")
    body = client.get("/operator/settings").text
    assert 'id="unit-settings"' in body
    assert 'title="The workspace default">Example University</span>' in body
    # Read-only: no form posts a Unit.
    assert 'name="unit"' not in body
