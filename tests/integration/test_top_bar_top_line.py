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

