"""Residential Operations' pages: the chrome, the placeholder screens of
segment 1B item 1, and the URL rules every page keeps
(`residentialapps/spec/applications.md`, "Pages" and "URLs")."""

from __future__ import annotations

import re
from dataclasses import replace
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
from residentialapps.web import pages as web_pages
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
    headers = re.findall(r'<th scope="col"(?: class="sortable"[^>]*)?>([^<]*)', slots.split("<tbody>")[0])
    assert headers == ["Wing", "Precinct", "Neighborhood", "Notes", "Staff", "RA"]
    assert "· 30 Neighborhoods in 9 Precincts and 3 Wings" in page.text
    staff = page.text.split('aria-label="Cypress A 04-05-06: Staff"')[1].split("</div>")[0]
    assert re.findall(r'<span class="token">([^<]+)<button', staff) == ["Daniel Koh", "Priya Raman"]
    ra = page.text.split('aria-label="Cypress A 04-05-06: RA"')[1].split("</div>")[0]
    assert re.findall(r'<span class="token">([^<]+)<button', ra) == ["Chloe Lim"]
    assert 'aria-label="Remove Chloe Lim from Cypress A 04-05-06: RA"' in ra
    assert page.text.count('<tr data-row class="wing-start">') == 3  # a Wing's name shows on its first row only
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
        headers = re.findall(r'<th scope="col"(?: class="sortable"[^>]*)?>([^<]*)', roster.split("<tbody>")[0])
        assert headers[headers.index("Appointment") + 1] == "Abbrev"
        for person in people:
            assert f'<td data-col="appointment">{person.appointment}</td>\n              <td data-col="abbrev">{person.abbrev}</td>' in roster
        options = roster.split('id="appointment"')[1].split("</select>")[0]
        assert re.findall(r"<option>([^<]*)", options) == ["All", *(a for a, _ in appointments)]
        assert "removes no one" in roster  # an upload appends
    assert "different name or enterprise name." in client.get("/rosters/staff").text
    assert "different name, enterprise name or student ID." in client.get("/rosters/ras").text


def test_home_lists_each_roster_s_appointments() -> None:
    home = TestClient(ops_app()).get("/rosters/").text
    assert "<dt>Appointments</dt><dd>Master, Admin, RSLM, RF, Exec</dd>" in home
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
    assert "· 15 people, 14 linked" in page.text
    headers = re.findall(r'<th scope="col"(?: class="sortable"[^>]*)?>([^<]*)', page.text.split('id="staff-h"')[1].split("<tbody>")[0])
    assert headers == ["Name", "Email", "Appointment", "Abbrev", "From – to", "Oversight", "Sign-in"]
    assert "Not yet signed in</span>" in page.text
    assert "Support Logs" not in page.text and "Team Viewer" not in page.text
    assert '<a href="/sys-admin/">Sys admin</a> page' in page.text
    assert 'colspan="8"' in TestClient(ops_app()).get("/rosters/staff?stage=slots").text
    client = TestClient(ops_app())
    assert "Team Viewer" not in client.get("/sys-admin/").text  # no such grant to audit
    person = client.get(f"/rosters/people/{sample_data.person_id_of('grace.ho@example.edu')}").text
    assert "Access is granted" not in person and "Support Logs" not in person


def test_the_ra_roster_lists_people_appointments_and_neighborhoods() -> None:
    page = TestClient(ops_app()).get("/rosters/ras")
    assert page.status_code == 200
    assert "· 30 RAs, 29 linked" in page.text
    headers = re.findall(r'<th scope="col"(?: class="sortable"[^>]*)?>([^<]*)', page.text.split('id="ra-h"')[1].split("<tbody>")[0])
    assert headers == ["Name", "Email", "Appointment", "Abbrev", "From – to", sample_data.LEVEL_LABELS[-1], "Sign-in"]


def test_the_ra_roster_shows_each_ras_neighborhood(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruled 2026-10-29: as the Staff roster's Oversight, the RA roster
    shows the slot each RA serves for the current term, read from
    Assignments, or None."""
    term = sample_data.CURRENT_TERM
    assert sample_data.assignment("Chloe Lim", term) == ("Cypress A 04-05-06",)
    assert sample_data.assignment("Chloe Lim", sample_data.TERMS[0]) == ()  # a term with no assignments
    assert sample_data.assignment("Daniel Koh", term) == ()  # staff are not an RA cell
    page = TestClient(ops_app()).get("/rosters/ras").text
    row = page.split('aria-label="Select Chloe Lim"')[1].split("</tr>")[0]
    assert '<td data-col="neighborhood" data-sort-value="Cypress A 04-05-06"><span class="pills"><span class="pill-derived">Cypress A 04-05-06</span></span></td>' in row
    shown = re.findall(r'data-col="neighborhood" data-sort-value="([^"]*)"', page)
    assert len(shown) == len(sample_data.RAS) and all(shown)  # every sample RA holds a slot
    assert '<span class="chip chip-mute">None</span>' not in page
    # An RA no slot names shows a None chip, as Oversight does.
    first = sample_data.SLOTS[0]
    monkeypatch.setattr(sample_data, "SLOTS", (replace(first, ras=()), *sample_data.SLOTS[1:]))
    page = TestClient(ops_app()).get("/rosters/ras").text
    row = page.split(f'aria-label="Select {first.ras[0]}"')[1].split("</tr>")[0]
    assert '<td data-col="neighborhood" data-sort-value=""><span class="chip chip-mute">None</span></td>' in row
    assert page.count('<span class="chip chip-mute">None</span>') == 1


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
    assert "Organization" not in page  # Assignments since 2026-10-28
    assert ">Terms imported</span>" in page and ">Assignments imported</span>" in page
    assert "You see this read-only." in page  # no sign-in: not the super-admin


def test_not_registered_shows_the_message_and_nobody_else() -> None:
    page = TestClient(ops_app()).get("/not-registered").text
    assert "You are not registered in Residential Apps." in page
    assert 'aria-label="Switch area"' not in page
    assert 'class="tabs"' not in page
    assert "example.edu" not in page
    assert "Example College" not in page
    assert "signed in as" not in page


def test_placeholders_are_404_deployed_to_someone_not_previewing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sample data, no roster gates yet: deployed, every placeholder is
    404 to a request no preview list admits (`test_preview_gate.py`)."""
    monkeypatch.setattr(web_pages, "is_local", lambda: False)
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
@pytest.mark.parametrize("path", ["/rosters/staff", "/rosters/ras", "/rosters/assignments"])
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
    assert '<span class="token">' not in slots.split('aria-label="Cypress A 04-05-06: Staff"')[1].split("</div>")[0]
    assert "Not open yet" not in client.get("/rosters/assignments").text


def test_an_ra_s_one_slot_and_no_slots_section_without_one() -> None:
    client = TestClient(ops_app())
    chloe = client.get(f"/rosters/people/{CHLOE}").text
    assert chloe.count('<span class="pill-derived">') == 1 and "Cypress A 04-05-06</span>" in chloe
    assert "in a Staff or RA cell, for AY2026-2027, Term 1." in chloe  # the term the pills are for
    assert "A0230000X" in chloe and "LIM CHLOE" in chloe  # her roster row
    sam = client.get(f"/rosters/people/{sample_data.person_id_of('sam.lee@example.edu')}").text
    # The Master is in no Staff cell, but in every slot (ruled 2026-10-29).
    assert f'<span class="pill-derived">{sample_data.UNIT_NAME}</span>' in sam and "In every slot for AY2026-2027, Term 1" in sam
    hui = client.get(f"/rosters/people/{sample_data.person_id_of('huimin.goh@example.edu')}").text
    assert "<h3 class=\"gap-above-sm\">Slots</h3>" not in hui  # in no slot at all
    assert sample_data.oversight("Daniel Koh", sample_data.TERMS[0]) == ()  # a term with no assignments


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
    assert page.split('id="term"')[1].split("</select>")[0].count("<option value=") == len(sample_data.TERMS)
    assert '<button type="submit" class="btn btn-secondary">Show term</button>' in page  # live: navigation
    assert '<span class="token">Chloe Lim<button' in page.split('aria-label="Cypress A 04-05-06: RA"')[1].split("</div>")[0]
    assert "Umairah Salleh's appointment covers all but 14 days of AY2026-2027, Term 1" in page
    term_select = page.split('<select id="term"')[1].split(">")[0]
    assert "disabled" not in term_select  # live: navigation
    assert '<select id="copy-from" class="input" disabled>' in page
    assert "No earlier term has assignments" in page
    upcoming = client.get("/rosters/assignments?term=AY2026-2027.2").text
    assert "No assignments yet for AY2026-2027, Term 2." in upcoming
    assert "Copy AY2026-2027, Term 1's to edit" in upcoming
    assert ">Copy from AY2026-2027, Term 1</button>" in upcoming
    assert '<span class="token">' not in upcoming.split('aria-label="Cypress A 04-05-06: RA"')[1].split("</div>")[0]
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
    assert all("disabled" not in r and "checked" not in r for r in radios)  # live; none chosen at first
    assert 'id="upload" class="btn btn-primary btn-unavailable" disabled aria-disabled="true" title="Choose what the upload does first"' in page
    for n, (mode, what) in enumerate(sample_data.UPLOAD_MODES, start=1):
        assert f'aria-describedby="mode-{n}-what"' in radios[n - 1]  # a short name, the description apart
        assert f'<label for="mode-{n}"><strong>{mode}</strong></label>' in page
        assert f'<span id="mode-{n}-what" class="subtle">{escape(what)}</span>' in page
    assert "a past one is refused" in page
    for side in ("export-from", "export-to"):
        chosen = re.findall(r"<option selected>([^<]*)", page.split(f'id="{side}"')[1].split("</select>")[0])
        assert chosen == ["AY2026-2027, Term 1"]  # the term shown, by default
    assert '<button type="button" class="btn btn-secondary" disabled>Export</button>' in page
    later = TestClient(ops_app()).get("/rosters/assignments?term=AY2026-2027.2").text
    assert re.findall(r"<option selected>([^<]*)", later.split('id="export-to"')[1].split("</select>")[0]) == [
        "AY2026-2027, Term 2"
    ]


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


def test_assignments_sets_who_is_in_every_slot(monkeypatch) -> None:
    """Ruled 2026-10-29: on Assignments, per term, staff in every slot by
    Unit-level appointment or by name, above the slots table; they oversee
    every RA, and rostered staff in no slot and not here oversee none."""
    from residentialapps.residentialops import sample_data, sample_leave

    client = TestClient(ops_app())
    page = client.get("/rosters/assignments").text
    card = page.split('id="every-h"')[1].split("</section>")[0]
    assert page.index('id="every-h"') < page.index('id="slots-h"')
    assert re.findall(r'name="every-slot-types" value="(\w+)"( checked)?', card) == [
        ("Master", " checked"), ("Admin", " checked"), ("Exec", ""),
    ]
    assert "In every slot: Sam Lee, Rachel Yeo." in card
    assert sample_leave.overseers() == ("Sam Lee", "Rachel Yeo")
    # By name too: a named person is in every slot, and oversees every RA.
    term = sample_data.CURRENT_TERM.key
    monkeypatch.setitem(sample_data.EVERY_SLOT, term, {"appointments": ("Master",), "names": ("Hui Min Goh",)})
    assert sample_leave.overseers() == ("Sam Lee", "Hui Min Goh") and len(sample_leave.scope("Hui Min Goh")) == 9
    assert sample_leave.scope("Rachel Yeo") == ()
    later = client.get("/rosters/assignments?term=AY2026-2027.2").text
    assert "No one is in every slot for AY2026-2027, Term 2; copying an earlier term" in later
    assert "set for each term on" in client.get("/ra-leave/admin/policy").text
    # It opens with the Staff cells: before the rosters have people it is
    # shown gated and names no one; a past term has none.
    gated = client.get("/rosters/assignments?stage=slots").text.split('id="every-h"')[1].split("</section>")[0]
    assert "Not open yet." in gated and "Sam Lee" not in gated and " checked" not in gated
    page = client.get("/rosters/assignments").text
    assert page.index("Warning:") < page.index('id="every-h"')  # page-level notices first


def test_every_slot_shows_on_the_slots_and_the_staff_roster(monkeypatch) -> None:
    """Ruled 2026-10-29: the staff in every slot show as pills under each
    slot's Staff cell; the Staff roster's Oversight column reads every
    slot, the slots a person is in, or None."""
    client = TestClient(ops_app())
    page = client.get("/rosters/assignments").text
    table = page.split('id="slots-h"')[1]
    # The Every slot card names them; the cells do not repeat them (2026-10-29).
    assert "Sam Lee" not in table.split("</table>")[0]
    roster = client.get("/rosters/staff").text
    # Named by the levels the slots make up (ruled 2026-10-29): the Unit,
    # a Wing, a Precinct, else the slots themselves.
    term = sample_data.CURRENT_TERM
    assert sample_data.oversight("Sam Lee", term) == (sample_data.UNIT_NAME,)
    assert sample_data.oversight("Priya Raman", term) == ("Cypress",)
    assert sample_data.oversight("Daniel Koh", term) == ("Cypress A 04-12",)
    assert sample_data.oversight("Hui Min Goh", term) == ()
    assert sample_data.coverage({"Cypress A 04-05-06", "Maple 03-04", "Maple 05-06", "Maple 07-08"}) == (
        "Cypress A 04-05-06", "Maple 03-08",
    )
    every = {s.neighborhood for s in sample_data.SLOTS}
    cypress = {s.neighborhood for s in sample_data.SLOTS if s.wing == "Cypress"}
    assert sample_data.coverage(cypress | {"Maple 03-04"}) == ("Cypress", "Maple 03-04")  # a Wing and part of another
    assert sample_data.coverage(every) == (sample_data.UNIT_NAME,)  # every slot by Staff cells
    assert sample_data.coverage(set()) == ()
    assert '<span class="chip chip-mute">None</span>' in roster
    assert f'<span class="pill-derived">{sample_data.UNIT_NAME}</span>' in roster and '<span class="pill-derived">Cypress</span>' in roster
    assert roster.count('<span class="chip chip-mute">None</span>') == 1  # Hui Min Goh alone


def test_the_rosters_have_column_chips_and_sortable_headers() -> None:
    """Ruled 2026-10-29: each roster takes RRW's column chips, every column
    but Name, and a sort button on every header."""
    client = TestClient(ops_app())
    for path, table, cols in (
        ("/rosters/staff", "staff-table", ["email", "appointment", "abbrev", "dates", "oversight", "signin"]),
        ("/rosters/ras", "ra-table", ["email", "appointment", "abbrev", "dates", "neighborhood", "signin"]),
    ):
        page = client.get(path).text
        chips = page.split(f'data-col-toggles-for="{table}"')[1].split("</p>")[0]
        assert re.findall(r'data-col-toggle="(\w+)" aria-pressed="true"', chips) == cols  # Name has none
        head = page.split(f'id="{table}"')[1].split("</thead>")[0]
        assert re.findall(r'class="sortable" data-col="(\w+)"', head) == ["name", *cols]
        assert head.count('class="sort-btn" aria-label="Sort by ') == len(cols) + 1
        row = page.split("<tr data-row>")[1].split("</tr>")[0]
        assert re.findall(r'data-col="(\w+)"', row) == ["name", *cols]  # each cell answers to its chip
        assert f'data-col-toggles-for="{table}"' not in client.get(f"{path}?stage=slots").text  # no rows, no chips


def test_the_slots_table_sorts_with_a_notes_chip_only() -> None:
    """Ruled 2026-10-29: the slots table takes sorting on every header,
    and a column chip for Notes alone."""
    page = TestClient(ops_app()).get("/rosters/assignments").text
    chips = page.split('data-col-toggles-for="slots-table"')[1].split("</p>")[0]
    assert re.findall(r'data-col-toggle="(\w+)"', chips) == ["notes"]
    head = page.split('id="slots-table"')[1].split("</thead>")[0]
    assert re.findall(r'class="sortable" data-col="(\w+)"', head) == ["wing", "precinct", "neighborhood", "notes", "staff", "ra"]
    assert '<td class="cell" data-col="ra" data-sort-value="Chloe Lim">' in page


def test_other_tables_sort_and_applications_has_column_chips() -> None:
    """Ruled 2026-10-29: Leave admin's Applications takes column chips (all
    but ID and RA) and sorting; Entitlements, Approval chain, Sys admin's
    tables and Precinct leave sort (`data-sort-auto`)."""
    client = TestClient(ops_app())
    apps = client.get("/ra-leave/admin/applications").text
    chips = apps.split('data-col-toggles-for="apps-table"')[1].split("</p>")[0]
    assert re.findall(r'data-col-toggle="(\w+)"', chips) == ["precinct", "type", "dates", "days", "cover", "stage", "submitted"]
    head = apps.split('id="apps-table"')[1].split("</thead>")[0]
    assert len(re.findall(r'class="sortable[ "]', head)) == 9 and 'class="sortable num" data-col="days"' in head
    assert 'data-col="dates" data-sort-value="2026-' in apps
    for path, tables in (
        ("/ra-leave/admin/entitlements", 1), ("/ra-leave/admin/routing", 1),
        ("/sys-admin/", 2), ("/ra-leave/staff/precinct?as=Sam%20Lee", 3),
    ):
        assert client.get(path).text.count("<table data-sort-auto>") == tables, path


def test_people_boxes_across_the_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruled 2026-10-29: every box for choosing people shows each verified
    person as a pill with its remove button; a one-person box (a cover,
    the RA an appeal is opened for) offers its typeahead until one is
    chosen."""
    from residentialapps.residentialops import sample_leave

    client = TestClient(ops_app())
    for path, label in (
        ("/ra-leave/apply", "Covering RA"), ("/ra-leave/appeal", "Covering RA"),
        ("/ra-leave/applications/L-0101", "New covering RA"),
        ("/ra-leave/admin/appeals", "RA"), ("/ra-leave/admin/policy", "Staff who may give final approval"),
        ("/ra-leave/admin/policy", "Staff who may open an appeal"),
    ):
        with monkeypatch.context() as m:
            if path == "/ra-leave/admin/appeals":  # opened for an RA only by invitation
                m.setitem(sample_leave.POLICY, "appeals", "By invitation")
            page = client.get(path).text
        assert f'<div class="tokens" role="group" aria-label="{label}"' in page, (path, label)
    assert 'aria-describedby="cover-what" class="token-input"' in client.get("/ra-leave/apply").text
    assert 'placeholder="Start typing a name"' not in client.get("/ra-leave/admin/policy").text
    assert "comma separated" not in client.get("/ra-leave/admin/policy").text


def test_appeals_body_imports_its_own_person_box(monkeypatch: pytest.MonkeyPatch) -> None:
    """The open-an-appeal card renders on the staff page too, not only where
    the page itself imports the macro."""
    from residentialapps.residentialops import sample_leave

    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    page = TestClient(ops_app()).get("/ra-leave/staff/appeals", params={"as": "Sam Lee"}).text
    assert 'id="inv-ra"' in page


def test_a_filled_one_person_box_keeps_its_label_target() -> None:
    """Once a one-person box holds someone, the typeahead goes; its id passes
    to the remove button, so `<label for>` still names a control, and the
    description moves with the group."""
    box = pages.TEMPLATES.env.get_template("residential/_people.html").module.person_tokens
    html = str(box("Covering RA", ("Chloe Lim",), "ra-names", "cover", single=True, describedby="cover-what"))
    assert "token-input" not in html
    assert 'id="cover" class="token-x"' in html
    assert 'role="group" aria-label="Covering RA" aria-describedby="cover-what"' in html


def test_add_new_slot_sits_under_the_slots_table() -> None:
    """Ruled 2026-10-29: the button moves to the table's bottom right."""
    for stage in ("start", "slots", "done"):
        page = TestClient(ops_app()).get("/rosters/assignments", params={"stage": stage}).text
        head = page[page.index('id="slots-h"'):page.index('id="slots-table"')]
        assert "btn-primary" not in head, stage
        table_end = page.index("</table>", page.index('id="slots-table"'))
        button = page.index(">Add new slot</button>")
        assert table_end < button < page.index("</section>", table_end), stage
        assert "btnrow end" in page[page.rindex("<div", 0, button):button], stage
