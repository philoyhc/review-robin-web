"""The host's landing page at `/` (segment 21D rung D1,
`guide/archive/segment_21D_prefix_flip.md`).
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cordware.identity import current_identity, missing_header_count
from cordware.main import REGISTRY, AppEntry, create_app
from cordware.settings import IdentitySettings, identity_settings


def stub_factory() -> FastAPI:
    stub = FastAPI()

    @stub.get("/")
    def root() -> dict[str, str]:
        return {"app": "stub"}

    return stub


def _entry(path: str, title: str = "") -> AppEntry:
    return AppEntry(path=path, factory=f"{__name__}:stub_factory", logger="stub", title=title)


def test_the_host_alone_serves_the_page_with_no_applications() -> None:
    response = TestClient(create_app(apps=())).get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "No applications are running here." in response.text
    assert 'href="/.auth/logout"' in response.text


def test_two_applications_are_listed_with_links_and_titles() -> None:
    registry = {"one": _entry("/one", "First App"), "two": _entry("/two")}
    response = TestClient(create_app(apps=("one", "two"), registry=registry)).get("/")
    assert response.status_code == 200
    assert '<a href="/one/">First App</a>' in response.text
    # No title: the registry name stands in.
    assert '<a href="/two/">two</a>' in response.text
    assert "No applications" not in response.text


def test_only_mounted_applications_are_listed() -> None:
    registry = {
        "one": _entry("/one", "First App"),
        "two": _entry("/two", "Second App"),
        "three": _entry("/three", "Not Mounted"),
    }
    host = create_app(apps=("one", "two"), registry=registry)
    assert "Not Mounted" not in TestClient(host).get("/").text


def test_one_application_not_at_root_is_listed_not_redirected_to() -> None:
    """The lone-application redirect is withdrawn (author, 2026-10-31):
    it hid the sign-in details on a deployment mounting only one."""
    registry = {"one": _entry("/one", "First App")}
    client = TestClient(create_app(apps=("one",), registry=registry))
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert '<a href="/one/">First App</a>' in response.text
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/one/").json() == {"app": "stub"}


def test_links_keep_the_host_root_path() -> None:
    one = {"one": _entry("/one")}
    client = TestClient(create_app(apps=("one",), registry=one), root_path="/edge")
    assert 'href="/edge/one/"' in client.get("/").text
    two = {"one": _entry("/one"), "two": _entry("/two")}
    client = TestClient(create_app(apps=("one", "two"), registry=two), root_path="/edge")
    assert 'href="/edge/one/"' in client.get("/").text


def test_an_application_at_root_keeps_root() -> None:
    """The host adds no `/` while an application is mounted there."""
    registry = {"root": _entry("/"), "other": _entry("/other", "Other")}
    client = TestClient(create_app(apps=("root", "other"), registry=registry))
    assert client.get("/").json() == {"app": "stub"}


def test_rrw_alone_is_listed_at_reviewrobin() -> None:
    """RRW as the only application is listed, linking to its root."""
    client = TestClient(create_app(apps=("reviewrobin",)))
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert 'href="/reviewrobin/"' in response.text


def _principal(claims: list[dict[str, str]]) -> str:
    payload = {"auth_typ": "aad", "claims": claims}
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def _two_apps() -> TestClient:
    two = {"one": _entry("/one"), "two": _entry("/two")}
    return TestClient(create_app(apps=("one", "two"), registry=two))


def test_the_page_shows_the_easy_auth_sign_in_and_a_super_admin_its_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    monkeypatch.setattr(identity_settings, "super_admin_emails", ["ada@example.edu"])
    claims = [
        {"typ": "name", "val": "Ada <Lovelace>"},
        {"typ": "preferred_username", "val": "ada@example.edu"},
        {"typ": "http://schemas.microsoft.com/identity/claims/tenantid", "val": "tenant-1"},
    ]
    response = _two_apps().get(
        "/",
        headers={"X-MS-CLIENT-PRINCIPAL": _principal(claims), "X-MS-CLIENT-PRINCIPAL-ID": "oid-1"},
    )
    page = response.text
    assert "Sign-in details" in page
    assert "Ada &lt;Lovelace&gt;" in page and "<Lovelace>" not in page
    assert "ada@example.edu" in page and "oid-1" in page
    assert "Easy Auth headers" in page
    assert "Sign-in claims (3)" in page and "tenant-1" in page
    assert response.headers["cache-control"] == "no-store"


def test_a_non_super_admin_sees_the_rows_but_no_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    """The raw claims are a super-admin's alone (author, 2026-10-31): they
    carry session internals. Everyone signed in sees the curated rows."""
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    monkeypatch.setattr(identity_settings, "super_admin_emails", ["boss@example.edu"])
    claims = [
        {"typ": "preferred_username", "val": "e0123456@example.edu"},
        {"typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress", "val": "jane.tan@example.edu"},
        {"typ": "sid", "val": "session-internal"},
    ]
    response = _two_apps().get("/", headers={"X-MS-CLIENT-PRINCIPAL": _principal(claims)})
    page = response.text
    assert "<dt>Super-admin</dt><dd>No</dd>" in page
    assert "Sign-in claims" not in page and "session-internal" not in page
    assert response.headers["cache-control"] == "no-store"


def test_the_upn_and_mail_rows_render_beside_the_matched_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    claims = [
        {"typ": "preferred_username", "val": "e0123456@example.edu"},
        {"typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress", "val": "jane.tan@example.edu"},
    ]
    page = _two_apps().get("/", headers={"X-MS-CLIENT-PRINCIPAL": _principal(claims)}).text
    assert "<dt>Matched as</dt><dd>jane.tan@example.edu</dd>" in page
    assert "<dt>UPN</dt><dd>e0123456@example.edu</dd>" in page
    assert "<dt>Mail</dt><dd>jane.tan@example.edu</dd>" in page


def test_absent_upn_and_mail_read_as_a_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simple headers only, with no principal claims: nothing to read the
    UPN or mail from, so the rows show "—", never an error."""
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    response = _two_apps().get(
        "/",
        headers={"X-MS-CLIENT-PRINCIPAL-NAME": "someone@example.edu", "X-MS-CLIENT-PRINCIPAL-ID": "oid-2"},
    )
    assert response.status_code == 200
    page = response.text
    assert "<dt>Matched as</dt><dd>someone@example.edu</dd>" in page
    assert "<dt>UPN</dt><dd>—</dd>" in page and "<dt>Mail</dt><dd>—</dd>" in page


def test_the_page_shows_the_fake_identity_without_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", True)
    page = _two_apps().get("/").text
    assert identity_settings.fake_auth_email in page
    assert "Fake local identity" in page
    assert "Sign-in claims" not in page


def test_signed_out_is_shown_and_not_counted_as_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    before = missing_header_count()
    response = _two_apps().get("/")
    assert response.status_code == 200
    assert "Not signed in" in response.text
    assert missing_header_count() == before


def test_easy_auth_wins_over_fake_auth_and_the_super_admin_shows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", True)
    monkeypatch.setattr(identity_settings, "super_admin_emails", ["boss@example.edu"])
    claims = [{"typ": "preferred_username", "val": "boss@example.edu"}]
    page = _two_apps().get("/", headers={"X-MS-CLIENT-PRINCIPAL": _principal(claims)}).text
    assert "Easy Auth headers" in page and "Fake local identity" not in page
    assert "<dt>Super-admin</dt><dd>Yes</dd>" in page
    assert "Sign-in claims (1)" in page


def test_a_malformed_principal_header_shows_empty_details(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    page = _two_apps().get("/", headers={"X-MS-CLIENT-PRINCIPAL": "not base64!"}).text
    assert "Easy Auth headers" in page
    assert "<dt>Matched as</dt><dd>—</dd>" in page
    assert "<dt>UPN</dt><dd>—</dd>" in page and "<dt>Mail</dt><dd>—</dd>" in page
    assert "Sign-in claims" not in page


def test_current_identity_carries_the_settings_it_resolved_under() -> None:
    from starlette.requests import Request

    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    settings = IdentitySettings(allow_fake_auth=True)
    identity = current_identity(request, settings)
    assert identity is not None and identity.is_fake
    assert identity.resolved_with is settings
    assert current_identity(request, IdentitySettings(allow_fake_auth=False)) is None


def test_the_page_carries_the_knot_favicon() -> None:
    """Ruled 2026-10-29: white on black, after Residential's, as inline SVG;
    since 2026-11-01 a trefoil knot running off the tile (author)."""
    page = TestClient(create_app(apps=())).get("/").text
    icons = re.findall(r'<link rel="icon"[^>]*href="([^"]*)"', page)
    assert len(icons) == 1
    icon = icons[0]
    assert icon.startswith("data:image/svg+xml;utf8,<svg ")
    assert "fill='%23000'" in icon and "stroke='%23fff'" in icon
    assert "clip-path='url(%23t)'" in icon  # the knot runs off the clipped tile
    assert "#" not in icon  # every hash escaped, or the data URI ends early


def test_an_application_s_icon_is_drawn_before_its_title() -> None:
    """Author, 2026-10-31: each application's own favicon, decorative."""
    icon = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'/>"
    registry = {
        "one": AppEntry(path="/one", factory=f"{__name__}:stub_factory", logger="stub", title="First", icon=icon),
        "two": _entry("/two", "Second"),
    }
    page = TestClient(create_app(apps=("one", "two"), registry=registry)).get("/").text
    drawn = re.search(r'<a href="/one/"><img src="([^"]*)" alt="" width="24" height="24">First</a>', page)
    assert drawn is not None
    assert drawn.group(1).replace("&lt;", "<").replace("&#39;", "'").replace("&gt;", ">") == icon
    assert '<a href="/two/">Second</a>' in page  # no icon, no image


ICON = re.compile(r'<link rel="icon" type="image/svg\+xml"\s+href="([^"]+)"')
REPO = Path(__file__).resolve().parents[2]


def _own_favicon(name: str) -> str:
    """The favicon an application's own templates carry, read as text (the
    host never imports an application)."""
    if name == "reviewrobin":
        (icon,) = ICON.findall((REPO / "app/web/templates/base.html").read_text(encoding="utf-8"))
        return icon
    if name == "utilities":
        (icon,) = ICON.findall((REPO / "utilityapps/templates/utilities/base.html").read_text(encoding="utf-8"))
        return icon
    text = (REPO / "residentialapps/web/templates/residential/base.html").read_text(encoding="utf-8")
    return ICON.findall(text[text.index(f'app_key == "{name}"'):])[0]


@pytest.mark.parametrize("name", list(REGISTRY))
def test_each_registered_application_s_icon_is_its_own_favicon(name: str) -> None:
    icon = REGISTRY[name].icon
    assert icon.startswith("data:image/svg+xml;utf8,<svg ") and "#" not in icon
    assert icon == _own_favicon(name)
