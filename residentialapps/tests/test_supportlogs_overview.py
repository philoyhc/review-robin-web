"""Support Logs' Overview on sample data, segment 1D item 1 rung 5: team
workload, hotspots and coverage for senior staff and Other Staff view (no
cluster view: §10.5 is deferred), a student's history across staff and
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
NOT_SENIOR = ("Siti Rahman", "Kenneth Lau", "Daniel Koh", "Priya Raman", "Hui Min Goh")


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def section(page: str, heading_id: str) -> str:
    return page.split(f'id="{heading_id}"')[1].split("</section>")[0]


def cells(table: str) -> list[list[str]]:
    rows = re.findall(r"<tr>(.*?)</tr>", table.split("<tbody>")[1], re.S)
    return [[c.strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)] for row in rows]


def plain(cell: str) -> str:
    return re.sub(r"<[^>]+>", "", cell)


def test_workload_weighs_formal_assignments_by_cadence(client: TestClient) -> None:
    rows = cells(section(client.get("/overview/?as=Sam%20Lee").text, "load-h"))
    assert [plain(r[0]) for r in rows] == [r["staff"] for r in sample.workload()]
    assert rows[0][1:] == ["2", "2", "6", "8", "145", "6"]  # Daniel Koh: assigned, following, students, encounters, minutes, load
    daniel = next(r for r in sample.workload() if r["staff"] == "Daniel Koh")
    assert daniel["load"] == sum(sample.WEIGHTS[p.cadence] for p in sample.plans_of("Daniel Koh") if p.formal)


def test_hotspots_name_students_for_identifiable_views_only(client: TestClient) -> None:
    sam = section(client.get("/overview/?as=Sam%20Lee").text, "hot-h")
    assert 'href="/overview/students/S-07?as=Sam%20Lee">Gwyneth Low</a>' in sam
    rows = cells(sam)
    assert [plain(r[0]) for r in rows] == [r["student"].name for r in sample.hotspots()]
    assert [r[1:5] for r in rows] == [[str(r[k]) for k in ("contacts", "before", "minutes", "staff")] for r in sample.hotspots()]
    hana = next(r for r in sample.hotspots() if r["student"].id == "S-08")
    assert (hana["contacts"], hana["staff"]) == (1, 1)  # staff counted over the same 14 days as contacts
    assert [plain(r[0]) for r in rows if "Rising" in r[5]] == ["Gwyneth Low"]
    siti = section(client.get("/overview/?as=Siti%20Rahman").text, "hot-h")
    assert "Gwyneth Low" in siti and "/overview/students/" not in siti  # named, but no history
    kenneth = client.get("/overview/?as=Kenneth%20Lau").text
    assert "<dt>Rising</dt><dd>1</dd>" in section(kenneth, "hot-h")


def test_the_aggregate_view_names_no_student(client: TestClient) -> None:
    page = client.get("/overview/?as=Kenneth%20Lau").text
    for s in sample.STUDENTS:
        assert s.name not in page and s.id not in page, s.name
    for heading in ("load-h", "hot-h", "cov-h"):
        assert f'id="{heading}"' in page, heading
    assert "Counts only" in page and "Opening this" not in page


def test_coverage_lists_overdue_due_and_review(client: TestClient) -> None:
    cov = section(client.get("/overview/?as=Sam%20Lee").text, "cov-h")
    assert "Overdue <span class=\"count\">· 1</span>" in cov and 'href="/plans/P-01?as=Sam%20Lee">Clara Tan</a>' in cov
    assert "Review " + sample.short_date(sample.plan("P-01").review) in cov
    aggregate = section(client.get("/overview/?as=Kenneth%20Lau").text, "cov-h")
    assert "Overdue <span class=\"count\">· 1</span>" in aggregate and "<a " not in aggregate


def test_no_cluster_view_until_students_have_a_location(client: TestClient) -> None:
    """Nothing ties a student to a housing location, so §10.5's cluster
    view is deferred (author, 2026-10-30): no card, and no student's
    cluster on their history."""
    for path in ("/overview/?as=Sam%20Lee", "/overview/?as=Kenneth%20Lau", "/overview/students/S-08?as=Sam%20Lee"):
        page = client.get(path)
        assert page.status_code == 200 and "cluster" not in page.text.lower(), path


def test_history_is_senior_only_and_spans_every_staff_member(client: TestClient) -> None:
    page = client.get("/overview/students/S-08?as=Sam%20Lee").text
    assert "<h1>Hana Rahim" in page and "Opening this history is recorded" in page
    staff = section(page, "staff-h")
    assert re.findall(r"<li>([^<]+)</li>", staff) == ["Arjun Nair", "Priya Raman"]  # not Daniel: shared with, never seen her
    encounters = section(page, "enc-h")
    assert encounters.count("<li>") == sum(1 for e in sample.ENCOUNTERS if e.student == "S-08")
    for name in NOT_SENIOR:
        for sid in ("S-08", "S-99"):  # an unknown id is 403 too: no probing
            assert client.get(f"/overview/students/{sid}?as={name.replace(' ', '%20')}").status_code == 403, (name, sid)
    assert client.get("/overview/students/S-99?as=Sam%20Lee").status_code == 404


def test_the_audit_is_senior_only_and_its_review_recorded(client: TestClient) -> None:
    page = client.get("/overview/audit?as=Sam%20Lee").text
    assert "Reviewing this log is recorded." in page
    rows = cells(section(page, "audit-h"))
    assert len(rows) == len(sample.AUDIT)
    for row, event in zip(rows, sample.AUDIT):
        if not event.student:  # a read of no one student: the audit itself, or a download
            assert row[3] == ""
            continue
        assert f'<a href="/overview/students/{event.student}?as=Sam%20Lee">{sample.student(event.student).name}</a>' == row[3]
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
    for path in ("/overview/?as=Sam%20Lee", "/overview/?as=Kenneth%20Lau", "/overview/students/S-08?as=Sam%20Lee",
                 "/overview/audit?as=Sam%20Lee"):
        page = mounted.get("/supportlogs" + path)
        assert page.status_code == 200, path
        for link in re.findall(r'\b(?:href|action|formaction|src)="([^"]*)"', re.sub(r'<link rel="icon"[^>]*>', "", page.text)):
            assert link == "/" or link.startswith(("/supportlogs/", "#")), (path, link)
