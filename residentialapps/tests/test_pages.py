"""Residential Operations' pages: the chrome, the placeholder screens of
segment 1B item 1, and the URL rules every page keeps
(`residentialapps/spec/applications.md`, "Pages" and "URLs")."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from markupsafe import escape
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


def test_the_assignments_page_lists_the_slots_with_staff_and_ra_cells() -> None:
    page = TestClient(ops_app()).get("/rosters/assignments")
    assert page.status_code == 200
    assert "Sample data" in page.text
    assert "<h1>Assignments</h1>" in page.text
    slots = page.text[page.text.index('id="slots-h"'):]
    headers = re.findall(r'<th scope="col">([^<]*)', slots.split("<tbody>")[0])
    assert headers == ["Wing", "Precinct", "Neighborhood", "Notes", "Staff", "RA"]
    assert "· 30 Neighborhoods in 9 Precincts and 3 Wings" in page.text
    assert 'aria-label="Cypress A 04-05-06: Staff" value="Daniel Koh, Priya Raman"' in page.text
    assert 'aria-label="Cypress A 04-05-06: RA" value="Chloe Lim"' in page.text
    assert page.text.count('<tr class="wing-start">') == 3  # a Wing's name shows on its first row only
    assert "RC1A L4: 101, 102-105" in page.text  # the notes, kept as text
    assert "Appointment types" not in page.text  # no types tables (2026-10-28)


def test_levels_are_rows() -> None:
    """Levels are rows added with + and removed with X, after RRW's
    response-field rows; no fixed count."""
    page = TestClient(ops_app()).get("/rosters/assignments").text
    for n, label in enumerate(sample_data.LEVEL_LABELS, start=1):
        assert f'aria-label="Add a level below Level {n}"' in page
        assert f'aria-label="Remove Level {n}"' in page
    assert "up to 5;" in page


def test_a_roster_row_carries_its_appointment_and_abbreviation() -> None:
    """No appointment types card (author, 2026-10-28): each row gives its
    appointment and abbreviation, and the filter offers the ones held."""
    client = TestClient(ops_app())
    for path, people, appointments in (
        ("/rosters/staff", sample_data.STAFF, sample_data.STAFF_APPOINTMENTS),
        ("/rosters/ras", sample_data.RAS, sample_data.RA_APPOINTMENTS),
    ):
        roster = client.get(path).text
        assert "appointment types" not in roster.lower()
        assert "Save types" not in roster
        headers = re.findall(r'<th scope="col">([^<]*)', roster.split("<tbody>")[0])
        assert headers[headers.index("Appointment") + 1] == "Abbrev"
        for person in people:
            assert f"<td>{person.appointment}</td>\n              <td>{person.abbrev}</td>" in roster
        options = roster.split('id="appointment"')[1].split("</select>")[0]
        assert re.findall(r"<option>([^<]*)", options) == ["All", *(a for a, _ in appointments)]
        assert "removes no one" in roster  # an upload appends
    assert "different name or enterprise name." in client.get("/rosters/staff").text
    assert "different name, enterprise name or student ID." in client.get("/rosters/ras").text


def test_home_lists_each_roster_s_appointments() -> None:
    home = TestClient(ops_app()).get("/rosters/").text
    assert "<dt>Appointments</dt><dd>Master, Admin, RSLM, RF</dd>" in home
    assert "<dt>Appointments</dt><dd>RA</dd>" in home
    assert "<dt>Types</dt>" not in home


def test_each_page_shows_its_csv() -> None:
    client = TestClient(ops_app())
    assert "Term,Level1.Wing,Level2.Precinct,Level3.Neighborhood,Notes,Staff,RA" in client.get("/rosters/assignments").text
    assert "Name,Email,Appointment,Abbrev,From,To,Enterprise name\n" in client.get("/rosters/staff").text
    assert "Name,Email,Appointment,Abbrev,From,To,Enterprise name,Student ID" in client.get("/rosters/ras").text


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


def test_the_staff_roster_shows_no_access() -> None:
    """No Access column (author, 2026-10-28): other applications' grants
    stay in them, and sys admin, the one grant here, is on Sys admin."""
    page = TestClient(ops_app()).get("/rosters/staff")
    assert page.status_code == 200
    assert "<h1>Staff roster</h1>" in page.text
    assert "· 14 people, 13 linked" in page.text
    headers = re.findall(r'<th scope="col">([^<]*)', page.text.split('id="staff-h"')[1].split("<tbody>")[0])
    assert headers == ["Name", "Email", "Appointment", "Abbrev", "From – to", "Sign-in"]
    assert "Not yet signed in</span>" in page.text
    assert "Support Logs" not in page.text and "Team Viewer" not in page.text
    assert '<a href="/sys-admin/">Sys admin</a> page' in page.text
    assert 'colspan="7"' in TestClient(ops_app()).get("/rosters/staff?stage=slots").text
    client = TestClient(ops_app())
    assert "Team Viewer" not in client.get("/sys-admin/").text  # no such grant to audit
    person = client.get(f"/rosters/people/{sample_data.person_id_of('grace.ho@example.edu')}").text
    assert "Access is granted" not in person and "Support Logs" not in person


def test_the_ra_roster_holds_people_and_appointments_only() -> None:
    page = TestClient(ops_app()).get("/rosters/ras")
    assert page.status_code == 200
    assert "· 30 RAs, 29 linked" in page.text
    headers = re.findall(r'<th scope="col">([^<]*)', page.text.split('id="ra-h"')[1].split("<tbody>")[0])
    assert headers == ["Name", "Email", "Appointment", "Abbrev", "From – to", "Sign-in"]


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
    page = TestClient(ops_app()).get("/rosters/assignments").text
    assert 'aria-label="Select all slots"' in page
    assert 'class="row-select" aria-label="Select Cypress A 04-05-06"' in page
    assert ">Retire</button>" in page and "End appointment" not in page


def test_a_person_s_slots_are_derived_from_assignments() -> None:
    client = TestClient(ops_app())
    page = client.get(f"/rosters/people/{sample_data.person_id_of('priya.raman@example.edu')}").text
    assert page.count('<span class="pill-derived">Cypress') == 10  # every slot in her Wing
    assert '<span class="pill-derived">Maple' not in page


def test_rosters_home_explains_setup_until_it_is_done() -> None:
    client = TestClient(ops_app())
    start = client.get("/rosters/?stage=start").text
    assert "<h1>Rosters and setup</h1>" in start
    assert "is not set up yet" in start
    steps = ("1. Setup", "2. Staff roster", "3. RA roster", "4. Assignments")
    assert [start.index(step) for step in steps] == sorted(start.index(step) for step in steps)
    done = client.get("/rosters/").text
    assert "is not set up yet" not in done
    assert '<h2 id="checks-h">Checks</h2>' in done
    assert "1 staff and 1 RA have not signed in yet." in done


def test_each_setup_step_is_inactive_until_its_prerequisite_exists() -> None:
    client = TestClient(ops_app())
    start = client.get("/rosters/assignments?stage=start").text
    assert '<div class="gated" inert>' in start and "Slots start from a term" in start
    for path in ("/rosters/staff", "/rosters/ras"):
        assert '<div class="gated" inert>' in client.get(f"{path}?stage=start").text
        opened = client.get(f"{path}?stage=slots").text
        assert "Not open yet" not in opened and "yet. Add" in opened
    slots = client.get("/rosters/assignments?stage=slots").text
    assert "The Staff and RA cells open once both rosters have people." in slots
    assert 'aria-label="Cypress A 04-05-06: Staff" value=""' in slots
    assert "Not open yet" not in client.get("/rosters/assignments").text


def test_an_ra_s_one_slot_and_no_slots_section_without_one() -> None:
    client = TestClient(ops_app())
    chloe = client.get(f"/rosters/people/{CHLOE}").text
    assert chloe.count('<span class="pill-derived">') == 1 and "Cypress A 04-05-06</span>" in chloe
    assert "A0230000X" in chloe and "LIM CHLOE" in chloe  # her roster row
    sam = client.get(f"/rosters/people/{sample_data.person_id_of('sam.lee@example.edu')}").text
    assert "<h3 class=\"gap-above-sm\">Slots</h3>" not in sam


def test_the_terms_page_is_a_detour_with_its_own_csv() -> None:
    """Terms (author, 2026-10-28): up to five a year, a past term read-only,
    and a back link to the page it was opened from, else Assignments."""
    client = TestClient(ops_app())
    page = client.get("/rosters/assignments/terms").text
    assert "<h1>Terms</h1>" in page
    assert '<a class="back-link" href="/rosters/assignments">&larr; Back to Assignments</a>' in page
    assert "· 6 in 2 years" in page
    assert page.count("Past · read-only") == 3
    assert page.count("chip-ok\">Current</span>") == 1
    assert 'aria-label="Edit AY2025-2026, Term 1"' not in page  # past: no edit
    assert 'aria-label="Edit AY2026-2027, Term 1"' in page
    assert "Year,Term,Name,Start,End" in page
    for back, label in (("/rosters/", "Home"), ("/rosters/staff", "Staff roster"), ("/rosters/ras", "RA roster")):
        page = client.get("/rosters/assignments/terms", params={"return_to": back}).text
        assert f'<a class="back-link" href="{back}">&larr; Back to {label}</a>' in page
    preview = client.get("/rosters/assignments/terms?return_to=/rosters/&stage=start").text
    assert '<a class="back-link" href="/rosters/?stage=start">' in preview  # the preview carries through
    for elsewhere in ("https://example.com/", "//evil", "/rosters/people/x"):
        assert 'href="/rosters/assignments">&larr; Back to Assignments' in client.get(
            "/rosters/assignments/terms", params={"return_to": elsewhere}
        ).text
    assert 'href="/rosters/assignments/terms?return_to=/rosters/assignments"' in client.get("/rosters/assignments").text
    assert "No terms yet." in client.get("/rosters/assignments/terms?stage=start").text


def test_assignments_show_one_term_at_a_time() -> None:
    """The page opens on the current term; a past term is read-only and an
    upcoming one waits to be copied or uploaded (author, 2026-10-28)."""
    client = TestClient(ops_app())
    page = client.get("/rosters/assignments").text
    assert '<option value="AY2026-2027.1" selected>AY2026-2027, Term 1 · Sem 1 + Winter break (Current)</option>' in page
    assert page.count("<option value=") == len(sample_data.TERMS)
    assert '<button type="submit" class="btn btn-secondary">Show term</button>' in page  # live: navigation
    assert 'aria-label="Cypress A 04-05-06: RA" value="Chloe Lim"' in page
    assert "Umairah Salleh's appointment covers all but 14 days of AY2026-2027, Term 1" in page
    term_select = page.split('<select id="term"')[1].split(">")[0]
    assert "disabled" not in term_select  # live: navigation
    assert '<select id="copy-from" class="input" disabled>' in page
    assert "No earlier term has assignments" in page
    upcoming = client.get("/rosters/assignments?term=AY2026-2027.2").text
    assert "No assignments yet for AY2026-2027, Term 2." in upcoming
    assert "Copy AY2026-2027, Term 1's to edit" in upcoming
    assert ">Copy from AY2026-2027, Term 1</button>" in upcoming
    assert 'aria-label="Cypress A 04-05-06: RA" value=""' in upcoming
    assert "covers all but" not in upcoming
    past = client.get("/rosters/assignments?term=AY2025-2026.3").text
    assert "is past</strong> and read-only. No assignments were recorded for it." in past
    assert 'id="copy-from"' not in past and ">Copy from" not in past  # nothing to copy into a past term
    assert "No slots in AY2025-2026, Term 3: the slots stand from AY2026-2027, Term 1." in past
    assert 'aria-label="Cypress A 04-05-06: RA"' not in past and "covers all but" not in past
    assert "(Current)</option>" in client.get("/rosters/assignments?term=nonsense").text.split(" selected>")[1].split("\n")[0]
    staged = client.get("/rosters/assignments?stage=slots").text
    assert '<input type="hidden" name="stage" value="slots">' in staged


def test_an_assignments_upload_says_what_it_does() -> None:
    page = TestClient(ops_app()).get("/rosters/assignments").text
    assert "<legend>What the upload does</legend>" in page
    radios = re.findall(r'<input type="radio"[^>]*>', page)
    assert [re.search(r'value="([^"]*)"', r).group(1) for r in radios] == [m for m, _ in sample_data.UPLOAD_MODES]
    assert all("disabled" in r and "checked" not in r for r in radios)  # none chosen until the operator picks one
    for n, (mode, what) in enumerate(sample_data.UPLOAD_MODES, start=1):
        assert f'aria-describedby="mode-{n}-what"' in radios[n - 1]  # a short name, the description apart
        assert f'<label for="mode-{n}"><strong>{mode}</strong></label>' in page
        assert f'<span id="mode-{n}-what" class="subtle">{escape(what)}</span>' in page
    assert "a past one is refused" in page
    assert ">Export AY2026-2027, Term 1</button>" in page


def test_home_checks_list_the_partial_overlap() -> None:
    home = TestClient(ops_app()).get("/rosters/").text
    assert "Umairah Salleh's appointment covers all but 14 days of AY2026-2027, Term 1" in home.split('id="checks-h"')[1]


def test_home_names_the_current_term() -> None:
    home = TestClient(ops_app()).get("/rosters/").text
    assert "<dt>Current</dt><dd>AY2026-2027, Term 1 (Sem 1 + Winter break)</dd>" in home
    assert "<dt>Years</dt><dd>AY2025-2026, AY2026-2027</dd>" in home
    start = TestClient(ops_app()).get("/rosters/?stage=start").text
    assert 'href="/rosters/assignments/terms?return_to=/rosters/&amp;stage=start" aria-label="Go to step 1, Setup"' in start
    assert "Name the levels and list the area slots; set out each year&#39;s terms. Assignments are made for a term." in start
    assert 'href="/rosters/assignments" aria-label="Go to step 1, Setup"' in home  # done: Setup opens on Assignments


def test_home_gives_one_primary_step_at_a_time() -> None:
    page = TestClient(ops_app()).get("/rosters/?stage=slots").text
    steps = page[page.index('class="steps"'):]
    assert steps.count("btn btn-primary") == 1
    assert 'btn btn-primary" href="/rosters/staff?stage=slots" aria-label="Go to step 2, Staff roster"' in steps
    assert 'href="/rosters/assignments?stage=slots" aria-label="Go to step 1, Setup"' in steps  # done: no return_to
