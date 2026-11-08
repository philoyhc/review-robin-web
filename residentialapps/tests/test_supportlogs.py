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

from residentialapps.supportlogs import pages as sample_pages
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
    return f"{path}{'&' if '?' in path else '?'}as={quote(name)}"


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
    ("/oversight-students/", "Students Overview", (sample.SENIOR, *sample.VIEW)),
    ("/oversight-staff/", "Staff Overview", (sample.SENIOR, *sample.VIEW)),
    ("/consultation/", "Consultation check", (sample.CONSULTATION,)),
    ("/sys-admin/", "Access", sample.ADMINISTRATION),
    ("/sys-admin/configuration", "Configuration", sample.ADMINISTRATION),
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
    none = next(v for v in sample.UNLISTED_VIEWERS if not v.grants)
    assert none.appointment == "RF"
    page = client.get(at("/", none.name))
    assert page.status_code == 403
    assert "You do not have access to Support Logs." in page.text
    assert 'class="tabs"' not in page.text and 'aria-label="Switch area"' not in page.text
    assert 'aria-label="Sample viewer"' in page.text  # so the sample can switch back


def test_each_grant_gives_its_tabs(client: TestClient) -> None:
    """Author, 2026-10-29: the frontline's Home, Log and Students (Plans
    folded into Students, author, 2026-11-07);
    senior staff and Other Staff view Overview and, beside it, Workload
    (author, 2026-11-08); no Safety flags tab."""
    assert tabs(client.get("/").text) == ["Home", "Log", "Students"]
    assert tabs(client.get(at("/oversight-students/", "Sam Lee")).text) == [
        "Students Overview",
        "Staff Overview",
    ]  # no Home: it would only come back here
    assert tabs(client.get(at("/oversight-students/", "Kenneth Lau")).text) == [
        "Students Overview",
        "Staff Overview",
    ]
    assert tabs(client.get(at("/consultation/", "Marcus Tan")).text) == ["Consultation check"]
    assert tabs(client.get(at("/", "Nadia Hassan")).text) == [
        "Home",
        "Students Overview",
        "Staff Overview",
        "Consultation check",
    ]
    assert tabs(client.get(at("/sys-admin/", "Rachel Yeo")).text) == [
        "Access",
        "Configuration",
        "Audit log",
    ]
    for v in (*sample.VIEWERS, *sample.UNLISTED_VIEWERS):
        assert "Safety flags</a>" not in client.get(at("/", v.name)).text


def test_home_is_the_dashboard_or_goes_where_the_viewer_belongs(client: TestClient) -> None:
    dashboard = client.get("/").text
    assert 'id="due-h">Due and overdue' in dashboard and ">Log encounter</a>" not in dashboard
    assert "The flags you raised" in dashboard
    assert "Every active flag, unacknowledged first" in client.get(at("/", "Priya Raman")).text
    for name, there in [
        ("Sam Lee", "/oversight-students/"),
        ("Siti Rahman", "/oversight-students/"),
        ("Marcus Tan", "/consultation/"),
        ("Rachel Yeo", "/sys-admin/"),
        ("Platform super-admin", "/sys-admin/"),
    ]:
        page = client.get(at("/", name), follow_redirects=False)
        assert (page.status_code, page.headers["location"]) == (302, at(there, name)), name


def test_home_lists_the_pages_of_a_viewer_reaching_more_than_one(client: TestClient) -> None:
    page = client.get(at("/", "Nadia Hassan")).text
    places = page.split('aria-label="Your pages"')[1].split("</ul>")[0]
    assert re.findall(r'href="([^"]*)"><span class="app-name">([^<]*)', places) == [
        (at("/oversight-students/", "Nadia Hassan"), "Students Overview"),
        (at("/consultation/", "Nadia Hassan"), "Consultation check"),
    ]
    assert 'href="/?as=Nadia%20Hassan" aria-current="page">Home</a>' in page
    assert "flags-h" not in page


def test_the_403_page_names_an_area_the_viewer_has(client: TestClient) -> None:
    page = client.get(at("/log", "Rachel Yeo"))
    assert page.status_code == 403
    assert 'aria-label="Switch area: Sys admin"' in page.text
    assert tabs(page.text) == ["Access", "Configuration", "Audit log"]


def test_a_recipient_with_nothing_else_lands_on_the_flags(client: TestClient) -> None:
    page = client.get(at("/", "Farah Aziz"))
    assert page.status_code == 200
    assert 'id="flags-h">Safety flags <span class="count">' in page.text
    assert tabs(page.text) == ["Home"]


def test_the_switcher_shows_the_areas_the_viewer_reaches(client: TestClient) -> None:
    def areas(page: str) -> list[str]:
        menu = page.split('aria-label="Switch area"', 2)[-1].split("</nav>")[0]
        return re.findall(r'href="[^"]*"[^>]*>([^<]+?)\s*(?:<|$)', menu)[
            :-1
        ]  # less All applications

    assert areas(client.get("/").text) == ["Support Logs"]
    # Sys admin is the account's, not a place (author, 2026-11-02): an
    # administrator alone keeps the switcher, for All applications.
    assert areas(client.get(at("/sys-admin/", "Rachel Yeo")).text) == []
    assert areas(client.get(at("/sys-admin/", "Platform super-admin")).text) == []


def test_sys_admin_is_in_the_account_menu(client: TestClient) -> None:
    signed_in = {
        "X-MS-CLIENT-PRINCIPAL-NAME": "rachel@example.edu",
        "X-MS-CLIENT-PRINCIPAL-ID": "rachel-oid",
    }

    def account(path: str, name: str) -> str:
        return (
            client.get(at(path, name), headers=signed_in)
            .text.split('aria-label="Account"')[1]
            .split("</nav>")[0]
        )

    # No sample viewer holds Sys admin beside another page, so it shows
    # only where it is omitted, on its own area; Residential Operations'
    # staff test shows the entry itself. The split is the shared helper's.
    assert web_pages.split_areas(sample_pages.areas_for(sample.viewer("Rachel Yeo")))[1] == (
        {
            "label": "Sys admin",
            "path": "/sys-admin/" + sample.as_query(sample.viewer("Rachel Yeo")),
        },
    )
    assert ">Sys admin</a>" not in account("/sys-admin/", "Rachel Yeo")
    assert ">Sys admin</a>" not in account("/", "Priya Raman")


def test_every_link_keeps_the_sample_viewer(client: TestClient) -> None:
    """Every link carries `?as=`, a form its hidden `as`; the viewer switch
    names each person; only the host's landing page and the in-page jump
    to the switch (the "Viewing as" chip) go without."""
    pages = [
        ("Priya Raman", "/"),
        ("Priya Raman", "/log"),
        ("Priya Raman", "/students/S-08"),
        ("Priya Raman", "/plans/P-05"),
        ("Priya Raman", "/who-can-see-what"),
        ("Rachel Yeo", "/sys-admin/configuration"),
    ]
    for name, path in pages:
        page = client.get(path + ("&" if "?" in path else "?") + "as=" + quote(name)).text
        card = page.split('aria-label="Sample viewer"')[1].split("</nav>")[0]
        rest = page.replace(card, "")
        for link in re.findall(r'\bhref="([^"]*)"', FAVICON.sub("", rest)):
            # Sign out (the host's, RRW segment 20D) carries no viewer either.
            assert (
                link in ("/", "#sample-viewer", "/.auth/logout") or "as=" + quote(name) in link
            ), (path, link)
        assert rest.count("<form") == rest.count(
            f'<input type="hidden" name="as" value="{name}">'
        ), path


def test_the_viewer_switch_lists_every_viewer(client: TestClient) -> None:
    card = client.get("/").text.split('aria-label="Sample viewer"')[1].split("</nav>")[0]
    assert re.findall(r'href="([^"]*)"', card) == ["/" + sample.as_query(v) for v in sample.VIEWERS]
    assert 'href="/" aria-current="true"' in card


def test_support_logs_is_teal_with_its_log_sheet(client: TestClient) -> None:
    page = client.get("/").text
    assert 'data-app="supportlogs"' in page and "fill='%230f766e'" in page
    assert ':root[data-app="supportlogs"] {\n        --accent: #0f766e;' in page
    assert "<title>Home · Support Logs</title>" in page


def test_not_registered_shows_the_message_and_nobody_else(client: TestClient) -> None:
    page = client.get("/not-registered").text
    assert "You are not registered in Residential Apps." in page
    assert 'aria-label="Switch area"' not in page and 'class="tabs"' not in page
    assert "example.edu" not in page and "Example College" not in page


def test_placeholders_are_404_deployed_to_someone_not_previewing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    pages = [
        "/",
        "/not-registered",
        at("/", "Nadia Hassan"),
        at("/log", "Rachel Yeo"),
        at("/", "Wei Jie Ong"),
        "/who-can-see-what",
        *(at(path, holder(*grants).name) for path, _, grants in PAGES),
        at("/sys-admin/", "Platform super-admin"),
    ]
    for path in pages:
        page = mounted.get(MOUNT + path)
        assert page.status_code in (200, 403), path
        for link in LINK.findall(FAVICON.sub("", page.text)):
            assert link in ("/", "/.auth/logout") or link.startswith((f"{MOUNT}/", "#")), (
                path,
                link,
            )
    redirect = mounted.get(MOUNT + at("/", "Rachel Yeo"), follow_redirects=False)
    assert redirect.headers["location"] == MOUNT + at("/sys-admin/", "Rachel Yeo")


def test_the_sample_staff_are_the_roster_s() -> None:
    """Support Logs may not import Residential Operations, so its sample
    staff are copied from the roster's mock; this holds them to it."""
    with ROSTER.open(newline="") as f:
        roster = {row["Name"]: row["Abbrev"] for row in csv.DictReader(f)}
    for v in (*sample.VIEWERS, *sample.UNLISTED_VIEWERS):
        if v.appointment:
            assert roster.get(v.name) == v.appointment, v.name
    assert sample.DEFAULT.grants == {sample.FRONTLINE}
    for name in (
        *sample.FRONTLINE_COLLEAGUES,
        *(g.viewer for g in sample.PEER_GRANTS),
        *(g.grantor for g in sample.PEER_GRANTS),
    ):
        assert roster.get(name) in ("RF", "RSLM"), name


def test_the_sample_viewers_are_the_roles_in_practice(client: TestClient) -> None:
    """Author, 2026-11-06 (`residentialapps/guide/1D_refinements.md`): the
    frontline, office staff with the Consultation check, the Master,
    administration; other combinations off the card but drawn for `?as=`."""
    assert [v.name for v in sample.VIEWERS] == [
        "Daniel Koh",
        "Priya Raman",
        "Sam Lee",
        "Hui Min Goh",
        "Rachel Yeo",
        "Platform super-admin",
    ]
    assert sample.viewer("Hui Min Goh").grants == {sample.CONSULTATION}
    assert sample.VIEW_AGGREGATE in sample.viewer("Sam Lee").grants
    home = client.get(at("/", "Hui Min Goh"), follow_redirects=False)
    assert home.status_code in (302, 303, 307) and "/consultation/" in home.headers["location"]
    card = client.get("/").text
    for v in sample.UNLISTED_VIEWERS:
        assert sample.viewer(v.name) == v
        assert quote(v.name) not in card, v.name


def test_the_working_unit_switcher(client: TestClient) -> None:
    """Unit-scoping rung 3 (author, 2026-11-08): a viewer holding grants in
    more than one Unit picks the working Unit in the switcher; one in a
    single Unit sees none. Choosing sets it for this browser and returns to
    the page; the top line names it."""
    sam = at("/oversight-students/", "Sam Lee")
    page = client.get(sam).text
    menu = page.split('aria-label="Switch area"', 1)[1].split("</nav>", 1)[0]
    assert '<div class="mg-h">Unit</div>' in menu
    for unit in sample.UNITS:
        assert f">{unit}" in menu, unit
    back = "back=%2Foversight-students%2F%3Fas%3DSam%2520Lee"
    assert f'<a href="/unit?name=Example%20College&amp;{back}" aria-current="true">' in menu
    for name in ("Daniel Koh", "Siti Rahman", "Rachel Yeo"):
        assert '<div class="mg-h">Unit</div>' not in client.get(at("/", name)).text, name
    chose = TestClient(create_app())
    before = chose.get(sam).text
    moved = chose.get(
        "/unit?name=Example%20Hall&back=%2Foversight-students%2F%3Fas%3DSam%2520Lee",
        follow_redirects=False,
    )
    assert moved.status_code == 303 and moved.headers["location"].endswith(
        "/oversight-students/?as=Sam%20Lee"
    )
    after = chose.get(sam).text
    assert '<span class="sw-unit">Example Hall</span>' in after
    assert 'aria-current="true">Example Hall' in after
    assert after != before  # rung 4: the page is Example Hall's
    # A Unit the viewer holds no grant in, or an unknown one, is not worked in.
    daniel = TestClient(create_app())
    daniel.get("/unit?name=Example%20Hall&back=%2F")
    assert '<span class="sw-unit">Example College</span>' in daniel.get("/").text
    # The switcher's accessible name carries the working Unit.
    assert ', Unit: Example Hall">' in after
    # A return path off the application goes Home.
    for back in ("%2F%2Fevil.example", "https%3A%2F%2Fevil.example", "javascript%3Aalert(1)", ""):
        location = chose.get(f"/unit?name=Nowhere&back={back}", follow_redirects=False).headers[
            "location"
        ]
        assert location.endswith("/") and "evil" not in location, (back, location)
    absent = chose.get("/unit?name=Nowhere", follow_redirects=False).headers["location"]
    assert absent.endswith("/")
    slash = chose.get("/unit?name=Nowhere&back=%2F%5Cevil.example", follow_redirects=False)
    assert not slash.headers["location"].startswith(("//", "/\\")), slash.headers["location"]


def _content(page: str) -> str:
    """A page without the sample-viewer card, which names every viewer."""
    return page.split('<nav id="sample-viewer"', 1)[0]


def _in_hall() -> TestClient:
    hall = TestClient(create_app())
    hall.get("/unit?name=Example%20Hall&back=%2F")
    return hall


def test_every_page_shows_the_working_unit_s_records_alone() -> None:
    """Unit-scoping rung 4 (author, 2026-11-08; functional spec §3.7): no
    cross-Unit view for anyone. Sam Lee working in Example Hall sees
    Example Hall's staff, students and records only, and in Example
    College none of Example Hall's; a history or plan of the other Unit's
    is not found."""
    with sample.in_unit(sample.UNIT_NAME):
        college = {s.id: s.name for s in sample.STUDENTS if sample.known_here(s.id)}
    with sample.in_unit(sample.HALL):
        hall_ids = {s.id: s.name for s in sample.STUDENTS if sample.known_here(s.id)}
    assert hall_ids and college and not set(hall_ids) & set(college)
    pages = (
        "/oversight-students/",
        "/oversight-staff/",
        "/oversight-staff/?term=all",
        "/oversight-staff/audit",
        "/oversight-staff/access",
        "/oversight-staff/records",
        "/oversight-staff/records?records=open&understood=yes",
        "/oversight-staff/records?records=open&understood=yes&what=plans",
        "/oversight-staff/records.csv?records=open&understood=yes&term=all",
        "/oversight-staff/records.csv?records=open&understood=yes&term=all&what=plans",
        "/who-can-see-what",
    )
    with sample.in_unit(sample.UNIT_NAME):
        college_staff = {n for n, _ in sample.STAFF_ROSTER} - {"Sam Lee"}
    with sample.in_unit(sample.HALL):
        hall_staff = {n for n, _ in sample.STAFF_ROSTER} - {"Sam Lee"}
    hall = _in_hall()
    plain = TestClient(create_app())
    for path in pages:
        at_hall = _content(hall.get(at(path, "Sam Lee")).text)
        at_college = _content(plain.get(at(path, "Sam Lee")).text)
        for sid, name in college.items():
            assert name not in at_hall and f"/{sid}" not in at_hall, (path, name)
        for sid, name in hall_ids.items():
            assert name not in at_college and f"/{sid}" not in at_college, (path, name)
        for name in college_staff:  # nor another Unit's staff, their grants or changes
            assert name not in at_hall, (path, name)
        for name in hall_staff:
            assert name not in at_college, (path, name)
    staff = _content(hall.get(at("/oversight-staff/", "Sam Lee")).text)
    for name in ("Lucas Teo", "Amira Salleh"):
        assert name in staff, name
    for name in ("Daniel Koh", "Priya Raman", "Arjun Nair"):
        assert name not in staff, name
    students = hall.get(at("/oversight-students/", "Sam Lee")).text
    assert "Nikhil Rao" in students  # on Example Hall's formal plan
    # Another Unit's student or plan is not found, either way round.
    assert hall.get(at("/oversight-students/S-08", "Sam Lee")).status_code == 404
    assert plain.get(at("/oversight-students/S-13", "Sam Lee")).status_code == 404
    assert hall.get(at("/plans/P-01", "Sam Lee")).status_code == 404
    assert plain.get(at("/plans/P-11", "Sam Lee")).status_code == 404
    assert hall.get(at("/oversight-students/S-13", "Sam Lee")).status_code == 200
    assert hall.get(at("/plans/P-11", "Sam Lee")).status_code == 200


def test_a_single_unit_viewer_never_works_in_another() -> None:
    """A viewer whose grants are all in Example College cannot choose
    Example Hall: their pages stay Example College's (§3.7)."""
    hall = _in_hall()
    with sample.in_unit(sample.HALL):
        hall_names = {s.name for s in sample.STUDENTS if sample.known_here(s.id)} | {
            "Lucas Teo",
            "Amira Salleh",
            "Example Hall",
        }
    for path, _, grants in PAGES:
        for v in (*sample.VIEWERS, *sample.UNLISTED_VIEWERS):
            if len(v.units) > 1 or not sample.holds(v, *grants):
                continue
            page = _content(hall.get(at(path, v.name), follow_redirects=True).text)
            for name in hall_names:
                assert name not in page, (path, v.name, name)
