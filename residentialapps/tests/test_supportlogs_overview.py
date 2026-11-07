"""Support Logs' Overview on sample data, segment 1D item 1 rung 5, as
the sharing screens' rung 1 left it (author, 2026-11-07): who supports
whom and students across staff, metadata only, for senior staff and
Other Staff view (no cluster view: §10.5 is deferred), a student's history across staff and
the support-activity audit for senior staff (functional spec §4.5, §10,
§11.2–11.3)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.main import create_app
from residentialapps.tests._host import host_with

# Identifiable and aggregate view, frontline, frontline and recipient, recipient only.
NOT_SENIOR = ("Siti Rahman", "Kenneth Lau", "Daniel Koh", "Priya Raman", "Farah Aziz")


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def section(page: str, heading_id: str) -> str:
    return page.split(f'id="{heading_id}"')[1].split("</section>")[0]


def cells(table: str) -> list[list[str]]:
    rows = re.findall(r"<tr>(.*?)</tr>", table.split("<tbody>")[1], re.S)
    return [[c.strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)] for row in rows]


# A withheld name's disclosure as plain text, ahead of the name it holds.
HIDDEN = "Show nameHide name"


def plain(cell: str) -> str:
    return re.sub(r"<[^>]+>", "", cell)


def test_who_supports_whom_counts_students_not_encounters(client: TestClient) -> None:
    """Author, 2026-11-07: per staff member, students with records and
    plans; nothing drawn from content (no encounters, minutes or load)."""
    page = client.get("/overview/?as=Sam%20Lee").text
    card = section(page, "support-h")
    rows = cells(card)
    assert [plain(r[0]) for r in rows] == [r["staff"] for r in sample.who_supports_whom()]
    daniel = next(r for r in rows if plain(r[0]) == "Daniel Koh")
    assert daniel[1:] == [
        str(len(sample.students_with_records("Daniel Koh"))),
        "2",
        "2",
    ]  # students, assigned, following
    for gone in ("load-h", "hot-h", "cov-h", "Minutes", "Encounters,", "Rising", "Overdue"):
        assert gone not in page, gone


def test_students_across_staff_shows_staff_never_content(client: TestClient) -> None:
    sam = section(client.get("/overview/?as=Sam%20Lee").text, "across-h")
    rows = cells(sam)
    across = sample.students_across_staff()
    assert [plain(r[0]).removeprefix(HIDDEN) for r in rows] == [r["student"].name for r in across]
    assert [r[1] for r in rows] == [", ".join(r["staff"]) for r in across]
    hana = next(r for r in across if r["student"].id == "S-08")
    assert hana["staff"] == ["Arjun Nair", "Priya Raman"]
    siti = section(client.get("/overview/?as=Siti%20Rahman").text, "across-h")
    assert "Clara Tan" in siti and "/overview/students/" not in siti  # named, but no history
    kenneth = section(client.get("/overview/?as=Kenneth%20Lau").text, "across-h")
    assert f"<dt>Students with records</dt><dd>{len(across)}</dd>" in kenneth


def test_overview_withholds_a_name_off_a_plan_until_shown(client: TestClient) -> None:
    """Author, 2026-11-07: Overview names by default only students on a
    formal plan or with an active flag; any other is one click away, in
    every card but the flags."""
    hidden = {s.name for s in sample.STUDENTS if not sample.named_on_overview(s.id)}
    shown = {r["student"].name for r in sample.students_across_staff()} & hidden
    assert {"Gwyneth Low", "Aiden Chen", "Bao Nguyen", "Farid Osman"} <= shown
    assert "Hana Rahim" not in hidden  # her team names her (rung 5)
    for name in ("Sam%20Lee", "Siti%20Rahman"):
        page = client.get(f"/overview/?as={name}").text
        for r in cells(section(page, "across-h")):
            if plain(r[0]).removeprefix(HIDDEN) in hidden:
                assert r[0].startswith('<details class="reveal"><summary>'), r[0]
            else:
                assert "<details" not in r[0], r[0]
        flags = (
            page.split('id="flags-h"', 1)[1].split("</section>", 1)[0] if "flags-h" in page else ""
        )
        rest = re.sub(
            r'<details class="reveal">.*?</details>', "", page.replace(flags, ""), flags=re.S
        )
        for student in hidden:
            assert student not in rest, (name, student)  # nowhere else on the page
    raw = section(client.get("/overview/?as=Sam%20Lee").text, "across-h")
    assert raw.count('<td data-sort-value=""><details class="reveal">') == len(shown)


def test_the_aggregate_view_names_no_student(client: TestClient) -> None:
    page = client.get("/overview/?as=Kenneth%20Lau").text
    for s in sample.STUDENTS:
        assert s.name not in page and s.id not in page, s.name
    for heading in ("support-h", "across-h"):
        assert f'id="{heading}"' in page, heading
    assert "Counts only" in page and "Opening this" not in page


def test_every_plan_carries_no_due_state(client: TestClient) -> None:
    plans = section(client.get("/overview/?as=Sam%20Lee").text, "plans-h")
    assert "Overdue" not in plans and "Due " not in plans
    for p in sample.PLANS:
        assert p.cadence not in plans, p.cadence


def test_no_cluster_view_until_students_have_a_location(client: TestClient) -> None:
    """Nothing ties a student to a housing location, so §10.5's cluster
    view is deferred (author, 2026-10-30): no card, and no student's
    cluster on their history."""
    for path in (
        "/overview/?as=Sam%20Lee",
        "/overview/?as=Kenneth%20Lau",
        "/overview/students/S-08?as=Sam%20Lee",
    ):
        page = client.get(path)
        assert page.status_code == 200 and "cluster" not in page.text.lower(), path


def test_history_is_senior_only_and_spans_every_staff_member(client: TestClient) -> None:
    page = client.get("/overview/students/S-08?as=Sam%20Lee").text
    assert "<h1>Hana Rahim" in page and "Opening this history is recorded" in page
    staff = section(page, "staff-h")
    assert re.findall(r'<span class="strong">([^<]+)</span>', staff) == [
        "Priya Raman",
        "Arjun Nair",
    ]  # in roster order; not Daniel: shared with, never seen her
    assert staff.count(">Request a share</button>") == 2 and "disabled" in staff
    assert 'id="enc-h"' not in page and 'id="peer-h"' not in page  # no content, no sharing
    for e in sample.ENCOUNTERS:
        if e.student == "S-08" and e.note:
            assert e.note not in page
    for name in NOT_SENIOR:
        for sid in ("S-08", "S-99"):  # an unknown id is 403 too: no probing
            assert (
                client.get(f"/overview/students/{sid}?as={name.replace(' ', '%20')}").status_code
                == 403
            ), (name, sid)
    assert client.get("/overview/students/S-99?as=Sam%20Lee").status_code == 404


def test_the_audit_is_senior_only_and_its_review_recorded(client: TestClient) -> None:
    page = client.get("/overview/audit?as=Sam%20Lee").text
    assert "Reviewing this log is recorded." in page
    rows = cells(section(page, "audit-h"))
    shown = sample.senior_audit()
    assert len(rows) == len(shown) < len(sample.AUDIT)
    assert sample.LOGGED not in page  # a record's time is its content
    for row, event in zip(rows, shown, strict=True):
        if not event.student:  # a read of no one student: the audit itself, or a download
            assert row[3] == ""
            continue
        named = sample.student(event.student)
        assert named is not None
        link = f'<a href="/overview/students/{event.student}?as=Sam%20Lee">{named.name}</a>'
        if sample.named_on_overview(event.student):
            assert row[3] == link
        else:
            assert row[3].startswith('<details class="reveal">') and link in row[3]
    assert 'href="/overview/audit?as=Sam%20Lee"' in client.get("/overview/?as=Sam%20Lee").text
    assert "/overview/audit" not in client.get("/overview/?as=Siti%20Rahman").text
    for name in NOT_SENIOR:
        assert client.get(f"/overview/audit?as={name.replace(' ', '%20')}").status_code == 403, name


def test_the_overview_pages_answer_only_on_a_local_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from residentialapps.web import pages as web_pages

    monkeypatch.setattr(web_pages, "is_local", lambda: False)
    deployed = TestClient(create_app())
    for path in ("/overview/", "/overview/students/S-08", "/overview/audit"):
        assert deployed.get(path + "?as=Sam%20Lee").status_code == 404, path


def test_mounted_overview_pages_stay_under_the_mount() -> None:
    host, _ = host_with(("supportlogs",))
    mounted = TestClient(host)
    for path in (
        "/overview/?as=Sam%20Lee",
        "/overview/?as=Kenneth%20Lau",
        "/overview/students/S-08?as=Sam%20Lee",
        "/overview/audit?as=Sam%20Lee",
    ):
        page = mounted.get("/supportlogs" + path)
        assert page.status_code == 200, path
        for link in re.findall(
            r'\b(?:href|action|formaction|src)="([^"]*)"',
            re.sub(r'<link rel="icon"[^>]*>', "", page.text),
        ):
            assert link in ("/", "/.auth/logout") or link.startswith(("/supportlogs/", "#")), (
                path,
                link,
            )
