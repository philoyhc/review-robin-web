"""Switching between two fake accounts on a local run (segment AD2X):
`SWITCH_PATH` sets or clears `FAKE_AS_COOKIE`, `current_identity` honors
it only while `switch_allowed` holds, and the account menu offers
*Switch to …* (`fake_switch`)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from cordware.identity import (
    FAKE_AS_COOKIE,
    SWITCH_PATH,
    current_identity,
    fake_switch,
    switch_allowed,
)
from cordware.main import AppEntry, create_app
from cordware.settings import identity_settings


def whoami_factory() -> FastAPI:
    app = FastAPI()

    @app.get("/")
    def root(request: Request) -> dict[str, object]:
        signed_in = current_identity(request)
        switch = fake_switch(request)
        return {
            "email": signed_in.email if signed_in else None,
            "super_admin": signed_in.is_super_admin if signed_in else None,
            "switch": None if switch is None else {"label": switch.label, "href": switch.href},
        }

    return app


def _client() -> TestClient:
    entry = AppEntry(path="/one", factory=f"{__name__}:whoami_factory", logger="stub")
    return TestClient(create_app(apps=("one",), registry={"one": entry}))


@pytest.fixture
def local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "app_env", "local")
    monkeypatch.setattr(identity_settings, "allow_fake_auth", True)
    monkeypatch.setattr(identity_settings, "fake_auth_email", "operator@example.edu")
    monkeypatch.setattr(identity_settings, "fake_auth_name", "Local Operator")
    monkeypatch.setattr(identity_settings, "fake_auth_alt_email", "divya.petrova@example.edu")
    monkeypatch.setattr(identity_settings, "fake_auth_alt_name", "Divya Petrova")


@pytest.mark.usefixtures("local")
def test_switching_flips_the_signed_in_account_and_back() -> None:
    client = _client()
    first = client.get("/one/").json()
    assert first["email"] == "operator@example.edu" and first["super_admin"] is True
    assert first["switch"]["label"] == "Switch to Divya Petrova"
    assert first["switch"]["href"].startswith(f"{SWITCH_PATH}?to=alt&return_to=%2Fone%2F")

    moved = client.get(first["switch"]["href"], follow_redirects=False)
    assert moved.status_code == 303 and moved.headers["location"] == "/one/"
    second = client.get("/one/").json()
    assert second["email"] == "divya.petrova@example.edu"
    assert second["super_admin"] is False  # never the super-admin
    assert second["switch"]["label"] == "Switch to Local Operator"

    client.get(second["switch"]["href"], follow_redirects=False)
    assert client.get("/one/").json()["email"] == "operator@example.edu"


@pytest.mark.usefixtures("local")
@pytest.mark.parametrize("target", ["//evil.example", "https://evil.example/", "/\\evil"])
def test_the_switch_never_returns_off_the_host(target: str) -> None:
    moved = _client().get(
        SWITCH_PATH, params={"to": "alt", "return_to": target}, follow_redirects=False
    )
    assert moved.headers["location"] == "/"


@pytest.mark.usefixtures("local")
def test_no_second_account_means_no_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_alt_email", "")
    client = _client()
    assert client.get("/one/").json()["switch"] is None
    assert client.get(SWITCH_PATH, follow_redirects=False).status_code == 404


@pytest.mark.usefixtures("local")
def test_outside_local_the_cookie_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    client.cookies.set(FAKE_AS_COOKIE, "alt")
    assert client.get("/one/").json()["email"] == "divya.petrova@example.edu"
    monkeypatch.setattr(identity_settings, "app_env", "production")
    assert not switch_allowed()
    seen = client.get("/one/").json()
    assert seen["email"] == "operator@example.edu" and seen["switch"] is None
    assert client.get(SWITCH_PATH, follow_redirects=False).status_code == 404


@pytest.mark.usefixtures("local")
def test_fake_auth_off_offers_no_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    client = _client()
    client.cookies.set(FAKE_AS_COOKIE, "alt")
    assert client.get(SWITCH_PATH, follow_redirects=False).status_code == 404
    assert client.get("/one/").json()["email"] is None


@pytest.mark.usefixtures("local")
def test_easy_auth_headers_win_over_the_cookie() -> None:
    client = _client()
    client.cookies.set(FAKE_AS_COOKIE, "alt")
    seen = client.get(
        "/one/",
        headers={
            "X-MS-CLIENT-PRINCIPAL-NAME": "ada@example.edu",
            "X-MS-CLIENT-PRINCIPAL-ID": "ada-oid",
            "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
        },
    ).json()
    assert seen["email"] == "ada@example.edu" and seen["switch"] is None


@pytest.mark.usefixtures("local")
def test_the_second_account_is_never_the_super_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "super_admin_emails", ["divya.petrova@example.edu"])
    client = _client()
    client.cookies.set(FAKE_AS_COOKIE, "alt")
    assert client.get("/one/").json()["super_admin"] is False


@pytest.mark.usefixtures("local")
def test_the_same_address_twice_is_no_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_alt_email", "Operator@Example.edu")
    assert not switch_allowed()


@pytest.mark.usefixtures("local")
def test_the_landing_page_offers_the_switch() -> None:
    page = TestClient(create_app(apps=())).get("/").text
    assert "data-switch-identity>Switch to Divya Petrova</a>" in page
