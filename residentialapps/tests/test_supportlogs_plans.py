"""Support Logs' plans and sharing on sample data, segment 1D item 1 rung 4:
a plan's detail and history, conversion for senior staff, Flag for formal
assignment, and peer-view grants (functional spec §3.1, §7, §8, §11.1)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.main import create_app
from residentialapps.tests._host import host_with


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def section(page: str, heading_id: str) -> str:
    return page.split(f'id="{heading_id}"')[1].split("</section>")[0]


def test_a_formal_assignment_shows_its_facts_and_history(client: TestClient) -> None:
    page = client.get("/plans/P-02").text
    assert "<h1>Formal assignment: Dev Menon</h1>" in page
    facts = section(page, "plan-h")
    for dt, dd in (("Source", "Dean&#39;s Office"), ("Assigned by", "Sam Lee"), ("Cadence", "Fortnightly"),
                   ("Review", "7 Dec"), ("Last contact", "19 Oct"), ("Next expected", "2 Nov"),
                   ("Contacts since it began", "1")):
        assert f"<dt>{dt}</dt><dd>{dd}</dd>" in facts, dt
    history = section(page, "hist-h")
    assert history.index("began following up") < history.index("converted it to a formal assignment")
    assert "senior staff change or close it" in page and "Convert to formal assignment" not in page
    assert 'href="/students/S-04">Dev Menon</a>' in facts


def test_a_safety_plan_carries_its_marker_and_instruction(client: TestClient) -> None:
    page = client.get("/plans/P-01").text
    assert '<span class="chip chip-marker">Safety-plan support</span>' in page
    assert "<span class=\"strong\">Instruction:</span> Weekly check-in; a reminder of the coping plan." in page


def test_the_owner_of_a_follow_up_changes_its_cadence(client: TestClient) -> None:
    page = client.get("/plans/P-03").text
    assert "<h1>Follow-up: Aiden Chen</h1>" in page
    assert ">Save cadence</button>" in page and ">Stop following up</button>" in page
    assert 'aria-current="true">Plans</a>' in page and "‹ My plans" in page


def test_senior_staff_convert_a_follow_up(client: TestClient) -> None:
    """§8: a follow-up becomes a formal assignment without a duplicate."""
    page = client.get("/plans/P-03?as=Sam%20Lee").text
    assert ">Convert to formal assignment</button>" in page
    sources = page.split('id="cv-source"')[1].split("</select>")[0]
    assert re.findall(r"<option>([^<]+)</option>", sources) == [s.replace("'", "&#39;") for s in sample.ASSIGNMENT_SOURCES]
    assert "<dt>With</dt><dd>Daniel Koh</dd>" in page and "‹ Overview" in page
    assert 'href="/students/' not in section(page, "plan-h")  # no student view off the frontline
    formal = client.get("/plans/P-01?as=Sam%20Lee").text
    assert "Convert to formal assignment" not in formal and 'id="st"' in formal


def test_other_staff_identifiable_view_reads_plans_only(client: TestClient) -> None:
    page = client.get("/plans/P-03?as=Siti%20Rahman").text
    assert "You see it read-only (Other Staff view)." in page
    assert "Convert" not in page and "Save cadence" not in page


def test_who_reaches_a_plan(client: TestClient) -> None:
    assert client.get("/plans/P-03?as=Priya%20Raman").status_code == 404  # Daniel's, never shared with her
    assert client.get("/plans/P-05?as=Priya%20Raman").status_code == 200
    assert client.get("/plans/P-99?as=Sam%20Lee").status_code == 404
    assert client.get("/plans/P-01?as=Kenneth%20Lau").status_code == 403  # aggregate view names no one
    assert client.get("/plans/P-01?as=Marcus%20Tan").status_code == 403


def test_plan_chips_open_the_plan(client: TestClient) -> None:
    assert 'href="/plans/P-01" aria-label="Plan · Counselling: Clara Tan">Plan · Counselling</a>' in client.get("/plans/").text
    aiden = client.get("/students/S-01").text
    assert 'href="/plans/P-03">Plan details</a>' in aiden and ">Stop following up</button>" in aiden


def test_a_shared_student_shows_the_grantor_s_plans_read_only(client: TestClient) -> None:
    """§11.1: the grantor's records for the student, plans included."""
    hana = client.get("/students/S-08").text
    assert 'href="/plans/P-05">Priya Raman</a>' in section(hana, "splan-h")
    assert "You have no records of your own for Hana Rahim to share." in hana
    plan = client.get("/plans/P-05").text
    assert "Priya Raman has shared it with you: you see it read-only." in plan
    assert "Save cadence" not in plan and "‹ Hana Rahim" in plan
    assert client.get("/students/S-08/share").status_code == 404  # nothing of his own to share


def test_the_grantor_sees_who_they_shared_with(client: TestClient) -> None:
    shared = section(client.get("/students/S-08?as=Priya%20Raman").text, "shared-h")
    assert '<span class="strong">Daniel Koh</span>' in shared and "Revoke" in shared


def test_overview_lists_every_plan_and_the_flagged_students(client: TestClient) -> None:
    sam = client.get("/overview/?as=Sam%20Lee").text
    assert re.findall(r'href="(/plans/P-\d+)\?as=Sam%20Lee"', section(sam, "plans-h")) == [
        f"/plans/{p.id}" for p in sorted(sample.PLANS, key=lambda p: not p.formal)]
    refs = section(sam, "refs-h")
    assert "Elena Park" in refs and "Flagged 27 Oct by Daniel Koh · suggests weekly" in refs
    siti = client.get("/overview/?as=Siti%20Rahman").text
    assert 'id="plans-h"' in siti and "read-only" in section(siti, "plans-h") and 'id="refs-h"' not in siti
    assert 'id="plans-h"' not in client.get("/overview/?as=Kenneth%20Lau").text  # aggregate only


def test_flag_for_formal_assignment_asks_no_reason(client: TestClient) -> None:
    bao = client.get("/students/S-02").text
    assert 'href="/students/S-02/refer">Flag for formal assignment</a>' in bao
    form = client.get("/students/S-02/refer").text
    assert re.findall(r"<option>([^<]+)</option>", form) == list(sample.ASSIGNMENT_CADENCES)
    assert "<textarea" not in form and "Say nothing of why here" in form
    sent = client.get("/students/S-02/refer/sent?cadence=Weekly").text
    assert "Bao Nguyen is flagged for senior staff to review" in sent and "You suggested weekly check-ins." in sent
    elena = client.get("/students/S-05").text
    assert "Flagged for formal assignment on 27 Oct by Daniel Koh" in elena and "/students/S-05/refer" not in elena
    for sid in ("S-05", "S-03"):  # flagged already; on his formal assignment
        for path in (f"/students/{sid}/refer", f"/students/{sid}/refer/sent"):
            again = client.get(path, follow_redirects=False)
            assert (again.status_code, again.headers["location"]) == (303, f"/students/{sid}"), path


def test_sharing_lists_grants_and_offers_colleagues(client: TestClient) -> None:
    clara = section(client.get("/students/S-03").text, "shared-h")
    assert '<span class="strong">Mei Ling Tan</span>' in clara and "Since 1 Oct" in clara
    assert 'aria-label="Revoke Mei Ling Tan\'s view">Revoke</button>' in clara
    form = client.get("/students/S-03/share").text
    assert re.findall(r"<option>([^<]+)</option>", form) == ["Priya Raman", "Arjun Nair", "Grace Ho"]  # not himself, not Mei Ling again
    sent = client.get("/students/S-03/share/sent?colleague=Grace%20Ho").text
    assert "Grace Ho can see your records for Clara Tan" in sent
    for colleague in ("Nobody", "Mei%20Ling%20Tan", "Daniel%20Koh"):  # unknown, already shared, himself
        back = client.get(f"/students/S-03/share/sent?colleague={colleague}", follow_redirects=False)
        assert (back.status_code, back.headers["location"]) == (303, "/students/S-03/share"), colleague
    assert client.get("/students/S-09/share").status_code == 404
    assert client.get("/students/S-09/refer").status_code == 404


def test_records_shared_with_the_viewer_show_with_their_owner(client: TestClient) -> None:
    """Hana Rahim is Priya's; Priya has shared her records with Daniel."""
    page = client.get("/students/S-08").text
    assert "Priya Raman has shared their records for Hana Rahim with you, since 20 Oct." in page
    assert '<span class="chip chip-mute">Shared by Priya Raman</span>' in section(page, "enc-h")
    shared = section(client.get("/students/").text, "shared-h")
    assert "Hana Rahim" in shared and "Shared by Priya Raman" in shared
    assert client.get("/students/S-09").status_code == 404  # Priya's, never shared


def test_the_rung_4_pages_need_frontline(client: TestClient) -> None:
    for path in ("/students/S-03/share", "/students/S-03/share/sent", "/students/S-03/refer", "/students/S-03/refer/sent"):
        assert client.get(path + "?as=Sam%20Lee").status_code == 403, path


def test_mounted_plan_pages_stay_under_the_mount() -> None:
    host, _ = host_with(("supportlogs",))
    mounted = TestClient(host)
    for path in ("/plans/P-01", "/plans/P-03?as=Sam%20Lee", "/students/S-03/share", "/students/S-02/refer",
                 "/students/S-08", "/overview/?as=Sam%20Lee"):
        page = mounted.get("/supportlogs" + path)
        assert page.status_code == 200, path
        for link in re.findall(r'\b(?:href|action|formaction|src)="([^"]*)"', re.sub(r'<link rel="icon"[^>]*>', "", page.text)):
            assert link == "/" or link.startswith(("/supportlogs/", "#")), (path, link)
    back = mounted.get("/supportlogs/students/S-03/share/sent?colleague=Nobody", follow_redirects=False)
    assert back.headers["location"] == "/supportlogs/students/S-03/share"
