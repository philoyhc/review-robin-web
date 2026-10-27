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


def test_the_organization_page_lists_the_slots_with_staff_and_ra_cells() -> None:
    page = TestClient(ops_app()).get("/rosters/organization")
    assert page.status_code == 200
    assert "Sample data" in page.text
    assert "<h1>Organization</h1>" in page.text
    slots = page.text[page.text.index('id="slots-h"'):]
    headers = re.findall(r'<th scope="col">([^<]*)', slots.split("<tbody>")[0])
    assert headers == ["Wing", "Precinct", "Neighborhood", "Notes", "Staff", "RA"]
    assert "· 30 Neighborhoods in 9 Precincts and 3 Wings" in page.text
    assert 'aria-label="Cypress A 04-05-06: Staff" value="Daniel Koh, Priya Raman"' in page.text
    assert 'aria-label="Cypress A 04-05-06: RA" value="Chloe Lim"' in page.text
    assert page.text.count('<tr class="wing-start">') == 3  # a Wing's name shows on its first row only
    assert "RC1A L4: 101, 102-105" in page.text  # the notes, kept as text
    assert "Appointment types" not in page.text  # they moved to the rosters


def test_levels_and_appointment_types_are_rows() -> None:
    """Levels and appointment types are rows added with + and removed with X,
    after RRW's response-field rows; no fixed count."""
    client = TestClient(ops_app())
    page = client.get("/rosters/organization").text
    for n, label in enumerate(sample_data.LEVEL_LABELS, start=1):
        assert f'aria-label="Add a level below Level {n}"' in page
        assert f'aria-label="Remove Level {n}"' in page
    assert "up to 5;" in page
    for path, heading, types in (
        ("/rosters/staff", "Staff appointment types", sample_data.STAFF_TYPES),
        ("/rosters/ras", "Student appointment types", sample_data.STUDENT_TYPES),
    ):
        roster = client.get(path).text
        assert f'<h2 id="{"staff" if "Staff" in heading else "student"}-types-h">{heading}</h2>' in roster
        for n, (title, abbrev) in enumerate(types, start=1):
            assert f'aria-label="{heading[:-1]} {n}: title" value="{title}"' in roster
            assert f'aria-label="{heading[:-1]} {n}: abbreviation" value="{abbrev}"' in roster
        assert 'title="Add a type below this one"' in roster
        assert "<select" not in roster.split("types-h")[1].split("</section>")[0]  # no level, no type


def test_each_page_shows_its_csv() -> None:
    client = TestClient(ops_app())
    assert "Level1.Wing,Level2.Precinct,Level3.Neighborhood,Notes,Staff,RA" in client.get("/rosters/organization").text
    staff = client.get("/rosters/staff").text
    assert "<h3>Staff appointment types CSV</h3>" in staff
    assert "Name,Email,Appointment,From,To,Enterprise name" in staff
    assert "Name,Email,Appointment,From,To,Enterprise name,Student ID" in client.get("/rosters/ras").text


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
    assert "· 14 people, 13 linked" in page.text
    headers = re.findall(r'<th scope="col">([^<]*)', page.text.split('id="staff-h"')[1].split("<tbody>")[0])
    assert headers == ["Name", "Email", "Appointment", "From – to", "Sign-in", "Access"]
    assert "Not yet signed in</span>" in page.text
    assert "Support Logs · frontline" in page.text


def test_the_ra_roster_holds_people_and_appointments_only() -> None:
    page = TestClient(ops_app()).get("/rosters/ras")
    assert page.status_code == 200
    assert "· 30 RAs, 29 linked" in page.text
    headers = re.findall(r'<th scope="col">([^<]*)', page.text.split('id="ra-h"')[1].split("<tbody>")[0])
    assert headers == ["Name", "Email", "Appointment", "From – to", "Sign-in"]


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
    assert 'placeholder="Name or email"' in page
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


def test_the_slots_tick_into_the_same_expander() -> None:
    page = TestClient(ops_app()).get("/rosters/organization").text
    assert 'aria-label="Select all slots"' in page
    assert 'class="row-select" aria-label="Select Cypress A 04-05-06"' in page
    assert ">Retire</button>" in page and "End appointment" not in page


def test_a_person_s_slots_are_derived_from_organization() -> None:
    client = TestClient(ops_app())
    page = client.get(f"/rosters/people/{sample_data.person_id_of('priya.raman@example.edu')}").text
    assert page.count('<span class="pill-derived">Cypress') == 10  # every slot in her Wing
    assert '<span class="pill-derived">Maple' not in page


def test_rosters_home_explains_setup_until_it_is_done() -> None:
    client = TestClient(ops_app())
    start = client.get("/rosters/?stage=start").text
    assert "<h1>Rosters and setup</h1>" in start
    assert "is not set up yet" in start
    steps = ("1. Slots", "2. Staff roster", "3. RA roster", "4. Staff and RA cells")
    assert [start.index(step) for step in steps] == sorted(start.index(step) for step in steps)
    done = client.get("/rosters/").text
    assert "is not set up yet" not in done
    assert '<h2 id="checks-h">Checks</h2>' in done
    assert "1 staff and 1 RA have not signed in yet." in done


def test_each_setup_step_is_inactive_until_its_prerequisite_exists() -> None:
    client = TestClient(ops_app())
    start = client.get("/rosters/organization?stage=start").text
    assert "Not open yet" not in start and "No slots yet." in start
    for path in ("/rosters/staff", "/rosters/ras"):
        assert '<div class="gated" inert>' in client.get(f"{path}?stage=start").text
        opened = client.get(f"{path}?stage=slots").text
        assert "Not open yet" not in opened and "yet. Add" in opened
    slots = client.get("/rosters/organization?stage=slots").text
    assert "The Staff and RA cells open once both rosters have people." in slots
    assert 'aria-label="Cypress A 04-05-06: Staff" value=""' in slots
    assert "Not open yet" not in client.get("/rosters/organization").text


def test_an_ra_s_one_slot_and_no_slots_section_without_one() -> None:
    client = TestClient(ops_app())
    chloe = client.get(f"/rosters/people/{CHLOE}").text
    assert chloe.count('<span class="pill-derived">') == 1 and "Cypress A 04-05-06</span>" in chloe
    assert "A0230000X" in chloe and "LIM CHLOE" in chloe  # her roster row
    sam = client.get(f"/rosters/people/{sample_data.person_id_of('sam.lee@example.edu')}").text
    assert "<h3 class=\"gap-above-sm\">Slots</h3>" not in sam


def test_home_gives_one_primary_step_at_a_time() -> None:
    page = TestClient(ops_app()).get("/rosters/?stage=slots").text
    steps = page[page.index('class="steps"'):]
    assert steps.count("btn btn-primary") == 1
