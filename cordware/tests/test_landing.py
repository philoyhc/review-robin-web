"""The host's landing page at `/` (segment 21D rung D1,
`guide/segment_21D_prefix_flip.md`).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cordware.main import AppEntry, create_app


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


def test_one_application_not_at_root_takes_the_redirect() -> None:
    registry = {"one": _entry("/one", "First App")}
    client = TestClient(create_app(apps=("one",), registry=registry))
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/one/"
    assert client.get("/").json() == {"app": "stub"}


def test_the_redirect_and_links_keep_the_host_root_path() -> None:
    one = {"one": _entry("/one")}
    client = TestClient(create_app(apps=("one",), registry=one), root_path="/edge")
    assert client.get("/", follow_redirects=False).headers["location"] == "/edge/one/"
    two = {"one": _entry("/one"), "two": _entry("/two")}
    client = TestClient(create_app(apps=("one", "two"), registry=two), root_path="/edge")
    assert 'href="/edge/one/"' in client.get("/").text


def test_an_application_at_root_keeps_root() -> None:
    """The host adds no `/` while an application is mounted there."""
    registry = {"root": _entry("/"), "other": _entry("/other", "Other")}
    client = TestClient(create_app(apps=("root", "other"), registry=registry))
    assert client.get("/").json() == {"app": "stub"}


def test_rrw_alone_opens_at_reviewrobin() -> None:
    """The deployed shape: RRW is the only application, so `/` sends the
    browser to it (D2)."""
    client = TestClient(create_app(apps=("reviewrobin",)))
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/reviewrobin/"
