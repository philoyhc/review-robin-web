"""Residential Operations' pages: the chrome, the placeholder screens of
segment 1B item 1, and the URL rules every page keeps
(`residentialapps/spec/applications.md`, "Pages" and "URLs")."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.requests import Request

from residentialapps.residentialops import pages, sample_data
from residentialapps.residentialops.main import create_app as ops_app
from residentialapps.tests._host import host_with
from residentialapps.web.urls import templates

PACKAGE = Path(__file__).resolve().parents[1]
MOUNT = "/residentialops"
CHLOE = sample_data.person_id_of("chloe.lim@example.edu")
SVG_DATA = "data:image/svg+xml;"
FAVICON = re.compile(r'<link rel="icon"[^>]*>')
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


def test_the_organization_page_is_a_labeled_placeholder() -> None:
    page = TestClient(ops_app()).get("/rosters/")
    assert page.status_code == 200
    assert "Sample data" in page.text
    assert "<h1>Organization</h1>" in page.text
    assert page.text.count('<td class="subtle ind">Neighborhood</td>') == 10
    headers = re.findall(r'<th scope="col">([^<]*)', page.text.split("<tbody>")[0])
    assert headers[:4] == ["Level", "Dorms", "Post", "Appointed "]
    assert '<td class="node nowrap">Master, Admin-01</td>' in page.text
    assert '<h2 id="appts-h">Appointment types</h2>' in page.text
    assert '<td class="node nowrap">RSLM-01</td>' in page.text
    assert 'href="/rosters/staff">Staff roster</a> and the <a href="/rosters/ras">RA roster</a>' in page.text


def test_the_organization_page_lists_levels_and_appointments_as_rows() -> None:
    """Levels and appointments are rows added with + and removed with X,
    after RRW's response-field rows; no fixed count, no Used flag."""
    page = TestClient(ops_app()).get("/rosters/").text
    assert 'type="checkbox"' not in page and "> Used<" not in page
    for n, label in enumerate(sample_data.LEVEL_LABELS, start=1):
        assert f'aria-label="Add a level below Level {n}"' in page
        assert f'aria-label="Remove Level {n}"' in page
    assert '<th scope="col">Title</th><th scope="col">Abbrev</th>' in page
    for n, (title, abbrev, _, _) in enumerate(sample_data.APPOINTMENTS, start=1):
        assert f'aria-label="Appointment type {n}: title" value="{title}"' in page
        assert f'aria-label="Appointment type {n}: abbreviation" value="{abbrev}"' in page
        assert f'aria-label="Add an appointment type below appointment type {n}"' in page
        assert f'aria-label="Remove appointment type {n}"' in page
    for kind in sample_data.APPOINTMENT_TYPES:
        expected = sum(1 for _, _, k, _ in sample_data.APPOINTMENTS if k == kind)
        assert page.count(f"<option selected>{kind}</option>") == expected, kind
    assert 'value="Residential Admin"' in page and 'value="Other Staff"' in page
    assert page.count("<option selected>Whole Unit</option>") == 3
    assert "<option selected>Level 1 · Wing</option>" in page
    assert "up to 5;" in page and "Up to 10 appointment types" in page


def test_the_organization_page_shows_both_setup_csvs() -> None:
    page = TestClient(ops_app()).get("/rosters/").text
    assert "<h3>Appointment types CSV</h3>" in page
    assert "Title,Abbrev,Type,Level" in page
    assert "Level,Dorms,Post" in page


def test_every_page_is_labeled_a_placeholder(host_client: TestClient) -> None:
    assert page_routes(), "no pages found"
    for path in page_routes():
        page = host_client.get(MOUNT + path)
        assert page.status_code == 200, path
        assert "Sample data" in page.text or "Placeholder:" in page.text, path


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
    the mount, a fragment, Easy Auth's, or the host's landing page; the
    inline favicon is not a path."""
    for path in [*page_routes(), f"/rosters/people/{CHLOE}"]:
        for link in LINK.findall(FAVICON.sub("", host_client.get(MOUNT + path).text)):
            assert link == "/" or link.startswith((f"{MOUNT}/", "#", "/.auth/")), (path, link)


def favicon(app_key: str) -> str:
    """The favicon link the shared chrome emits for an application."""
    request = Request({"type": "http", "path": "/", "root_path": "", "headers": [], "query_string": b""})
    env = templates([]).env
    page = env.get_template("residential/base.html").render(request=request, app_key=app_key, areas=(), tabs=())
    links = re.findall(r'<link rel="icon"[^>]*href="([^"]*)"', page)
    assert len(links) <= 1, app_key
    return links[0] if links else ""


def test_each_application_has_its_own_favicon(host_client: TestClient) -> None:
    """A house in fuchsia for Residential Operations, a lined notepad in
    teal for Support Logs; nothing for an application not yet given one."""
    house, notepad = favicon("residentialops"), favicon("supportlogs")
    assert house.startswith(SVG_DATA) and "fill='%23a21caf'" in house and "M7 16l9-8 9 8" in house
    assert notepad.startswith(SVG_DATA) and "fill='%230f766e'" in notepad and "M12.5 12h7" in notepad
    assert favicon("other") == ""
    assert f'href="{house}"' in host_client.get(f"{MOUNT}/rosters/").text


def test_every_template_link_goes_through_a_helper() -> None:
    """The leak rule: a link in a template is built by `url()` (inside
    the application) or `host_url()` (the host's), never written out; the
    inline favicon is not a path."""
    templates = sorted(PACKAGE.rglob("templates/**/*.html"))
    assert templates
    for template in templates:
        for link in LINK.findall(FAVICON.sub("", template.read_text())):
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
    assert "RA-10 has no RA." in page.text
    assert "Mei Ling Tan, Grace Ho (to 31 Dec)" in page.text  # every RF on the Precinct


def test_the_roster_tabs_link_all_three_pages(host_client: TestClient) -> None:
    page = host_client.get(f"{MOUNT}/rosters/ras").text
    for path in ("/rosters/", "/rosters/staff"):
        assert f'href="{MOUNT}{path}"' in page
    assert f'href="{MOUNT}/rosters/ras" aria-current="page"' in page


def test_person_detail_shows_identity_status_and_history() -> None:
    client = TestClient(ops_app())
    linked = client.get(f"/rosters/people/{CHLOE}").text
    assert "Sample data" in linked
    assert "chloe.lim@u.example.edu" in linked  # Entra email, apart from the UPN
    assert 'chip-ok">Linked</span>' in linked
    assert "e0234567@u.example.edu" in linked
    assert "Linked on first sign-in" in linked
    unlinked = client.get(f"/rosters/people/{sample_data.person_id_of('nur.aisyah@example.edu')}").text
    assert 'chip-mute">Unlinked</span>' in unlinked
    assert "After first sign-in" in unlinked


def test_an_unknown_person_is_not_found() -> None:
    assert TestClient(ops_app()).get("/rosters/people/nobody").status_code == 404


def test_roster_names_link_to_person_detail(host_client: TestClient) -> None:
    page = host_client.get(f"{MOUNT}/rosters/ras").text
    assert f'href="{MOUNT}/rosters/people/{CHLOE}"' in page


def test_sys_admin_lists_grants_and_the_audit_log() -> None:
    page = TestClient(ops_app()).get("/sys-admin/").text
    assert "<h1>Sys admin</h1>" in page
    assert page.count(">Revoke</button>") == len(sample_data.SYS_ADMINS)
    assert page.count("<tr>") - 2 == len(sample_data.SYS_ADMINS) + len(sample_data.AUDIT_EVENTS)
    assert "You see this read-only." in page  # no sign-in: not the super-admin


def test_not_registered_shows_the_message_and_nobody_else() -> None:
    page = TestClient(ops_app()).get("/not-registered").text
    assert "You are not registered in Residential Apps." in page
    assert 'aria-label="Switch area"' not in page
    assert 'class="tabs"' not in page
    assert "example.edu" not in page
    assert "Example College" not in page
    assert "signed in as" not in page


def test_placeholders_answer_only_on_a_local_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sample data, no gates yet: deployed, every placeholder is 404."""
    monkeypatch.setattr(pages, "is_local", lambda: False)
    client = TestClient(ops_app())
    for path in [*page_routes(), f"/rosters/people/{CHLOE}"]:
        assert client.get(path).status_code == 404, path
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    ("path", "noun", "name"), [("/rosters/staff", "staff", "Sam Lee"), ("/rosters/ras", "RAs", "Chloe Lim")]
)
def test_a_roster_ticks_rows_into_an_expander_and_filters_from_one_box(path: str, noun: str, name: str) -> None:
    page = TestClient(ops_app()).get(path).text
    assert f'<input type="checkbox" class="select-all" aria-label="Select all {noun}">' in page
    assert f'class="row-select" aria-label="Select {name}"' in page
    assert '<label for="q">Filter</label>' in page
    assert 'placeholder="Name, email or post' in page
    assert "Upload roster CSV" not in page
    csv_card = page[page.index('id="csv-h"'):]
    assert "Upload and preview</button>" in csv_card and "Export</button>" in csv_card
    assert "End appointment" in page
    assert 'btn-unavailable" disabled aria-disabled="true" title="Edit takes one row"' in page


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize("path", ["/rosters/staff", "/rosters/ras"])
def test_the_roster_scripts_parse(path: str, tmp_path: Path) -> None:
    page = TestClient(ops_app()).get(path).text
    scripts = re.findall(r"<script>(.*?)</script>", page, re.S)
    assert len(scripts) >= 2  # the theme toggle's and the expander's
    for n, body in enumerate(scripts):
        source = tmp_path / f"s{n}.js"
        source.write_text(body)
        subprocess.run(["node", "--check", str(source)], check=True)
