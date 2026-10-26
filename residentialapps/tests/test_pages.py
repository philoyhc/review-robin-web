"""Residential Operations' pages: the chrome, the placeholder screens of
segment 1B item 1, and the URL rules every page keeps
(`residentialapps/spec/applications.md`, "Pages" and "URLs")."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from residentialapps.ops.main import create_app as ops_app
from residentialapps.tests._host import host_with

PACKAGE = Path(__file__).resolve().parents[1]
MOUNT = "/residentialops"
LINK = re.compile(r'\b(?:href|action|formaction|src)\s*=\s*"([^"]*)"')


def page_routes() -> list[str]:
    """Every GET page of the application: its routes, less health, with no
    path parameters (the screens' detail pages arrive with their data)."""
    routes = [r for r in flatten(ops_app().routes) if isinstance(r, APIRoute) and "GET" in r.methods]
    return sorted(r.path for r in routes if r.name != "residentialops_health" and "{" not in r.path)


def flatten(routes: list[object]) -> list[object]:
    """FastAPI nests an included router behind its include context."""
    found: list[object] = []
    for route in routes:
        context = getattr(route, "include_context", None)
        found += flatten(context.included_router.routes) if context is not None else [route]
    return found


@pytest.fixture(scope="module")
def host_client() -> TestClient:
    host, _ = host_with(["residentialops"])
    return TestClient(host)


def test_the_organization_page_is_a_labelled_placeholder() -> None:
    page = TestClient(ops_app()).get("/rosters/")
    assert page.status_code == 200
    assert "Sample data" in page.text
    assert "<h1>Organization</h1>" in page.text
    assert page.text.count('<td style="color: var(--text-subtle)">Neighborhood</td>') == 10


def test_every_page_is_labelled_sample_data(host_client: TestClient) -> None:
    assert page_routes(), "no pages found"
    for path in page_routes():
        page = host_client.get(MOUNT + path)
        assert page.status_code == 200, path
        assert "Sample data" in page.text, path


def test_the_chrome_carries_the_switcher_tabs_and_theme(host_client: TestClient) -> None:
    page = host_client.get(f"{MOUNT}/rosters/").text
    assert 'data-app="residentialops"' in page
    assert 'aria-label="Switch area"' in page
    assert f'href="{MOUNT}/rosters/" aria-current="page"' in page
    assert 'data-theme-choice="dark"' in page
    # RRW's key, so one choice holds across the host's applications.
    assert page.count('"rrw-theme"') == 2


def test_no_page_emits_a_path_outside_its_mount(host_client: TestClient) -> None:
    """The GET crawl: every link, form and source on every page is under
    the mount, a fragment, Easy Auth's, or the host's landing page."""
    for path in page_routes():
        for link in LINK.findall(host_client.get(MOUNT + path).text):
            assert link == "/" or link.startswith((f"{MOUNT}/", "#", "/.auth/")), (path, link)


def test_every_template_link_goes_through_a_helper() -> None:
    """The leak rule: a link in a template is built by `url()` (inside
    the application) or `host_url()` (the host's), never written out."""
    templates = sorted(PACKAGE.rglob("templates/**/*.html"))
    assert templates
    for template in templates:
        for link in LINK.findall(template.read_text()):
            assert link.startswith(("{{ url(", "{{ host_url(", "#")), (template.name, link)


def test_the_leak_rule_catches_a_written_out_link() -> None:
    assert LINK.findall('<a href="/rosters/">x</a> <form action="{{ url(\'/x\') }}">') == [
        "/rosters/",
        "{{ url('/x') }}",
    ]


def test_unmounted_links_carry_no_prefix() -> None:
    page = TestClient(ops_app()).get("/rosters/").text
    assert 'href="/rosters/"' in page
    assert MOUNT not in page


def test_the_staff_roster_shows_access_read_only() -> None:
    page = TestClient(ops_app()).get("/rosters/staff")
    assert page.status_code == 200
    assert "<h1>Staff roster</h1>" in page.text
    assert "· 8 people, 7 linked" in page.text
    assert "Not yet signed in</span>" in page.text
    assert "Support Logs · frontline" in page.text


def test_the_ra_roster_derives_reporting_and_flags_a_vacancy() -> None:
    page = TestClient(ops_app()).get("/rosters/ras")
    assert page.status_code == 200
    assert "· 9 RAs, 8 linked" in page.text
    assert "RA10 has no RA." in page.text
    assert "Backup: Grace Ho to 31 Dec" in page.text


def test_the_roster_tabs_link_all_three_pages(host_client: TestClient) -> None:
    page = host_client.get(f"{MOUNT}/rosters/ras").text
    for path in ("/rosters/", "/rosters/staff"):
        assert f'href="{MOUNT}{path}"' in page
    assert f'href="{MOUNT}/rosters/ras" aria-current="page"' in page
