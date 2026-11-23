"""One same-site check for every post (AD-126, segment AD2C rung 7,
`gate.same_site`): a browser naming another site is refused; one that
sends no ``Sec-Fetch-Site`` (Safari before 16.4) must name this origin in
``Origin``, else ``Referer``, or it is refused too."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from applydesk.tests._host import host_with

NEW = "/applydesk/operator/exercises/new"
HERE = "http://testserver"


def _old_browser() -> TestClient:
    """A client sending no ``Sec-Fetch-Site``, as Safari before 16.4."""
    client = TestClient(host_with(("applydesk",))[0], follow_redirects=False)
    client.headers.pop("sec-fetch-site")
    return client


@pytest.mark.parametrize("site", ["cross-site", "same-site"])
def test_a_post_from_another_site_is_refused(site: str) -> None:
    client = TestClient(host_with(("applydesk",))[0], follow_redirects=False)
    reply = client.post(NEW, data={"name": "X"}, headers={"sec-fetch-site": site})
    assert reply.status_code == 403


def test_without_the_header_a_same_origin_post_is_taken() -> None:
    reply = _old_browser().post(NEW, data={"name": "X"}, headers={"origin": HERE})
    assert reply.status_code == 303


def test_without_the_header_or_an_origin_a_same_origin_referer_is_taken() -> None:
    reply = _old_browser().post(
        NEW, data={"name": "X"}, headers={"referer": f"{HERE}/applydesk/operator/exercises"}
    )
    assert reply.status_code == 303


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"origin": "https://elsewhere.example"},
        {"origin": "null"},
        {"referer": "https://elsewhere.example/page"},
        {"origin": "https://elsewhere.example", "referer": f"{HERE}/applydesk/"},
        {"referer": "not a url"},
    ],
)
def test_without_the_header_any_other_post_is_refused(headers: dict[str, str]) -> None:
    reply = _old_browser().post(NEW, data={"name": "X"}, headers=headers)
    assert reply.status_code == 403


def test_the_admin_pages_share_the_check() -> None:
    reply = _old_browser().post("/applydesk/admin/operators/admit", data={})
    assert reply.status_code == 403
