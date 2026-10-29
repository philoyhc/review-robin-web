"""Support Logs' screens on sample data, segment 1D item 1: the chrome,
Home, the tabs each grant gives, the `403` page, and the URL rules every
page keeps (`residentialapps/guide/segment_1D_support_logs.md`); Sys admin
(rung 6)."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.main import create_app
from residentialapps.tests._host import host_with
from residentialapps.tests.test_pages import flatten
from residentialapps.web import pages as web_pages

MOUNT = "/supportlogs"
ROSTER = Path(__file__).resolve().parents[1] / "docs" / "sample_data" / "staff_roster.csv"
LINK = re.compile(r'\b(?:href|action|formaction|src)\s*=\s*"([^"]*)"')
FAVICON = re.compile(r'<link rel="icon"[^>]*>')


def at(path: str, name: str) -> str:
    return f"{path}?as={quote(name)}"


def holder(*grants: str) -> sample.Viewer:
    """The first sample viewer holding one of ``grants``."""
    return next(v for v in sample.VIEWERS if sample.holds(v, *grants))


def tabs(page: str) -> list[str]:
    nav = page.split('<nav class="tabs"')[1].split("</nav>")[0]
    return re.findall(r'<a [^>]*>([^<]+?)(?: <span class="tab-badge">.*?</span></span>)?</a>', nav)


# Each tab's page and the grants that reach it: (path, title, grants).
PAGES = (
    ("/log", "Log encounter", (sample.FRONTLINE,)),
    ("/students/", "Students", (sample.FRONTLINE,)),
    ("/plans/", "My plans", (sample.FRONTLINE,)),
    ("/overview/", "Overview", (sample.SENIOR, *sample.VIEW)),
    ("/consultation/", "Consultation check", (sample.CONSULTATION,)),
    ("/sys-admin/", "Access", sample.ADMINISTRATION),
    ("/sys-admin/configuration", "Configuration", sample.ADMINISTRATION),
    ("/sys-admin/clusters", "Clusters", sample.ADMINISTRATION),
    ("/sys-admin/audit", "Audit log", sample.ADMINISTRATION),
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def test_every_page_shows_sample_data_to_whoever_reaches_it(client: TestClient) -> None:
    for path, title, grants in PAGES:
        page = client.get(at(path, holder(*grants).name))
        assert page.status_code == 200, path
        assert "Sample data" in page.text and "Placeholder" not in page.text, path
        assert f"<h1>{title}</h1>" in page.text, path


def test_a_page_beyond_the_viewer_s_grants_is_403(client: TestClient) -> None:
    for path, _, grants in PAGES:
        outsider = next(v for v in sample.VIEWERS if v.grants and not sample.holds(v, *grants))
        page = client.get(at(path, outsider.name))
        assert page.status_code == 403, (path, outsider.name)
        assert "You do not have access to this page." in page.text


def test_no_grant_means_no_support_logs(client: TestClient) -> None:
    """Access is a grant, never an appointment (§3.5): an RF on the roster
    with no grant gets the `403` page, with no tabs or switcher."""
    none = next(v for v in sample.VIEWERS if not v.grants)
    assert none.appointment == "RF"
    page = client.get(at("/", none.name))
    assert page.status_code == 403
    assert "You do not have access to Support Logs." in page.text
    assert 'class="tabs"' not in page.text and 'aria-label="Switch area"' not in page.text
    assert 'aria-label="Sample viewer"' in page.text  # so the sample can switch back


def test_each_grant_gives_its_tabs(client: TestClient) -> None:
    """Author, 2026-10-29: the frontline's Home, Log, Students and Plans;
    senior staff and Other Staff view an Overview tab; no Safety flags tab."""
    assert tabs(client.get("/").text) == ["Home", "Log", "Students", "Plans"]
    assert tabs(client.get(at("/overview/", "Sam Lee")).text) == ["Overview"]  # no Home: it would only come back here
    assert tabs(client.get(at("/overview/", "Kenneth Lau")).text) == ["Overview"]
    assert tabs(client.get(at("/consultation/", "Marcus Tan")).text) == ["Consultation check"]
    assert tabs(client.get(at("/", "Nadia Hassan")).text) == ["Home", "Overview", "Consultation check"]
    assert tabs(client.get(at("/sys-admin/", "Rachel Yeo")).text) == ["Access", "Configuration", "Clusters", "Audit log"]
    for v in sample.VIEWERS:
        assert "Safety flags</a>" not in client.get(at("/", v.name)).text


def test_home_is_the_dashboard_or_goes_where_the_viewer_belongs(client: TestClient) -> None:
    dashboard = client.get("/").text
    assert 'id="due-h">Due and overdue' in dashboard and ">Log encounter</a>" in dashboard
    assert "The flags you raised" in dashboard
    assert "Every active flag, unacknowledged first" in client.get(at("/", "Priya Raman")).text
    for name, there in [("Sam Lee", "/overview/"), ("Siti Rahman", "/overview/"), ("Marcus Tan", "/consultation/"),
                        ("Rachel Yeo", "/sys-admin/"), ("Platform super-admin", "/sys-admin/")]:
        page = client.get(at("/", name), follow_redirects=False)
        assert (page.status_code, page.headers["location"]) == (302, at(there, name)), name


def test_home_lists_the_pages_of_a_viewer_reaching_more_than_one(client: TestClient) -> None:
    page = client.get(at("/", "Nadia Hassan")).text
    places = page.split('aria-label="Your pages"')[1].split("</ul>")[0]
    assert re.findall(r'href="([^"]*)"><span class="app-name">([^<]*)', places) == [
        (at("/overview/", "Nadia Hassan"), "Overview"), (at("/consultation/", "Nadia Hassan"), "Consultation check"),
    ]
    assert 'href="/?as=Nadia%20Hassan" aria-current="page">Home</a>' in page
    assert "flags-h" not in page


def test_the_403_page_names_an_area_the_viewer_has(client: TestClient) -> None:
    page = client.get(at("/log", "Rachel Yeo"))
    assert page.status_code == 403
    assert 'aria-label="Switch area: Sys admin"' in page.text
    assert tabs(page.text) == ["Access", "Configuration", "Clusters", "Audit log"]


def test_a_recipient_with_nothing_else_lands_on_the_flags(client: TestClient) -> None:
    page = client.get(at("/", "Hui Min Goh"))
    assert page.status_code == 200
    assert 'id="flags-h">Safety flags <span class="count">' in page.text
    assert tabs(page.text) == ["Home"]


def test_the_switcher_shows_the_areas_the_viewer_reaches(client: TestClient) -> None:
    def areas(page: str) -> list[str]:
        menu = page.split('aria-label="Switch area"', 2)[-1].split("</nav>")[0]
        return re.findall(r'href="[^"]*"[^>]*>([^<]+?)\s*(?:<|$)', menu)[:-1]  # less All applications

    assert areas(client.get("/").text) == ["Support Logs"]
    assert areas(client.get(at("/sys-admin/", "Rachel Yeo")).text) == ["Sys admin"]
    assert areas(client.get(at("/sys-admin/", "Platform super-admin")).text) == ["Sys admin"]


def test_every_link_keeps_the_sample_viewer(client: TestClient) -> None:
    """Every link carries `?as=`, a form its hidden `as`; the viewer switch
    names each person; only the host's landing page goes without."""
    pages = [("Priya Raman", "/"), ("Priya Raman", "/log"), ("Priya Raman", "/students/S-08"),
             ("Priya Raman", "/plans/?show=week"), ("Rachel Yeo", "/sys-admin/clusters")]
    for name, path in pages:
        page = client.get(path + ("&" if "?" in path else "?") + "as=" + quote(name)).text
        card = page.split('aria-label="Sample viewer"')[1].split("</nav>")[0]
        rest = page.replace(card, "")
        for link in re.findall(r'\bhref="([^"]*)"', FAVICON.sub("", rest)):
            assert link == "/" or "as=" + quote(name) in link, (path, link)
        assert rest.count("<form") == rest.count(f'<input type="hidden" name="as" value="{name}">'), path


def test_the_viewer_switch_lists_every_viewer(client: TestClient) -> None:
    card = client.get("/").text.split('aria-label="Sample viewer"')[1].split("</nav>")[0]
    assert re.findall(r'href="([^"]*)"', card) == ["/" + sample.as_query(v) for v in sample.VIEWERS]
    assert 'href="/" aria-current="true"' in card


def test_support_logs_is_teal_with_its_notepad(client: TestClient) -> None:
    page = client.get("/").text
    assert 'data-app="supportlogs"' in page and "fill='%230f766e'" in page
    assert ':root[data-app="supportlogs"] {\n        --accent: #0f766e;' in page
    assert "<title>Home · Support Logs</title>" in page


def test_not_registered_shows_the_message_and_nobody_else(client: TestClient) -> None:
    page = client.get("/not-registered").text
    assert "You are not registered in Residential Apps." in page
    assert 'aria-label="Switch area"' not in page and 'class="tabs"' not in page
    assert "example.edu" not in page and "Example College" not in page


def test_placeholders_answer_only_on_a_local_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_pages, "is_local", lambda: False)
    local = TestClient(create_app())
    for path in ["/", "/not-registered", *(path for path, _, _ in PAGES)]:
        assert local.get(path).status_code == 404, path
    assert local.get("/health").status_code == 200


def test_route_names_carry_the_application_s_prefix() -> None:
    names = [r.name for r in flatten(create_app().routes) if isinstance(r, APIRoute)]
    assert len(names) > len(PAGES) and all(n.startswith("supportlogs_") for n in names)


def test_mounted_pages_stay_under_the_mount() -> None:
    host, _ = host_with(("supportlogs",))
    mounted = TestClient(host)
    pages = ["/", "/not-registered", at("/", "Nadia Hassan"), at("/log", "Rachel Yeo"), at("/", "Wei Jie Ong"),
             *(at(path, holder(*grants).name) for path, _, grants in PAGES),
             at("/sys-admin/", "Platform super-admin")]
    for path in pages:
        page = mounted.get(MOUNT + path)
        assert page.status_code in (200, 403), path
        for link in LINK.findall(FAVICON.sub("", page.text)):
            assert link == "/" or link.startswith((f"{MOUNT}/", "#")), (path, link)
    redirect = mounted.get(MOUNT + at("/", "Rachel Yeo"), follow_redirects=False)
    assert redirect.headers["location"] == MOUNT + at("/sys-admin/", "Rachel Yeo")


def test_the_sample_staff_are_the_roster_s() -> None:
    """Support Logs may not import Residential Operations, so its sample
    staff are copied from the roster's mock; this holds them to it."""
    with ROSTER.open(newline="") as f:
        roster = {row["Name"]: row["Abbrev"] for row in csv.DictReader(f)}
    for v in sample.VIEWERS:
        if v.appointment:
            assert roster.get(v.name) == v.appointment, v.name
    assert sample.DEFAULT.grants == {sample.FRONTLINE}
    for name in (*sample.FRONTLINE_COLLEAGUES, *(g.viewer for g in sample.PEER_GRANTS), *(g.grantor for g in sample.PEER_GRANTS)):
        assert roster.get(name) in ("RF", "RSLM"), name
