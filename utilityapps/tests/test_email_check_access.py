"""Who reaches the checker (spec §3, acceptance test 11), and the upload
page's copy (segment U1, rungs 2 and 5)."""

from __future__ import annotations

import base64
import re

import pytest
from fastapi.testclient import TestClient

from cordware.settings import identity_settings
from utilityapps.tests._host import host_with

ROUTES = [
    ("get", "/utilities/email-check/"),
    ("post", "/utilities/email-check/preview"),
    ("post", "/utilities/email-check/check"),
    ("get", "/utilities/email-check/preview"),
]
CSV = {"content": (None, base64.b64encode(b"email\r\njane.tan@example.edu\r\n"))}


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("utilities",))[0])


def _call(client: TestClient, method: str, path: str):
    if method == "post":
        return client.post(path, files=CSV, follow_redirects=False)
    return client.get(path, follow_redirects=False)


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_someone_signed_in_but_not_super_admin_gets_a_plain_403(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, method: str, path: str
) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    page = _call(client, method, path)
    assert page.status_code == 403
    assert "<h1>Not available</h1>" in page.text
    assert "request" not in page.text.lower()  # no invitation to ask for access
    assert "jane.tan" not in page.text


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_nobody_signed_in_gets_a_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, method: str, path: str
) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    assert _call(client, method, path).status_code == 401


def test_a_listed_super_admin_is_let_in(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    monkeypatch.setattr(identity_settings, "super_admin_emails", ["admin@example.edu"])
    assert client.get("/utilities/email-check/").status_code == 200


def test_the_index_and_the_probe_are_not_gated(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    assert client.get("/utilities/").status_code == 200
    assert client.get("/utilities/health").status_code == 200


def test_the_upload_page_states_the_limits_and_the_caveats(client: TestClient) -> None:
    page = client.get("/utilities/email-check/")
    assert page.headers["cache-control"] == "no-store"
    text = page.text
    assert "up to 500 rows and 1 MiB" in text
    assert "Nothing you upload is kept" in text
    assert "is not proof that it" in text
    assert 'method="post" action="/utilities/email-check/preview" enctype="multipart/form-data"' in text
    assert "Placeholder" not in text


def test_every_app_link_carries_the_mount(client: TestClient) -> None:
    for href in re.findall(r'href="(/[^"]*)"', client.get("/utilities/email-check/").text):
        assert href in ("/", "/.auth/logout") or href.startswith("/utilities/"), href
