"""Support Logs' plans and sharing on sample data, segment 1D item 1 rung 4:
a plan's detail and history, a follow-up its owner's alone, Flag for
formal assignment, and peer-view grants (functional spec §3.1, §7, §8, §11.1)."""

from __future__ import annotations

import re
from datetime import date

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
    for dt, dd in (
        ("Source", "College"),
        ("Assigned by", "Sam Lee"),
        ("Cadence", "Fortnightly"),
        ("Review", "7 Dec"),
        ("Last contact", "19 Oct"),
        ("Next expected", "2 Nov"),
        ("Contacts since it began", "1"),
    ):
        assert f"<dt>{dt}</dt><dd>{dd}</dd>" in facts, dt
    history = section(page, "hist-h")
    assert history.index("began following up") < history.index(
        "converted it to a formal assignment"
    )
    assert "senior staff change or close it" in page and "Convert to formal assignment" not in page
    assert 'href="/students/S-04">Dev Menon</a>' in facts


def test_a_safety_plan_carries_its_marker_and_instruction(client: TestClient) -> None:
    page = client.get("/plans/P-01").text
    assert '<span class="chip chip-marker">Safety-plan support</span>' in page
    assert (
        '<span class="strong">Instruction:</span> Weekly check-in; a reminder of the coping plan.'
        in page
    )


def test_the_owner_of_a_follow_up_changes_its_cadence(client: TestClient) -> None:
    page = client.get("/plans/P-03").text
    assert "<h1>Follow-up: Aiden Chen</h1>" in page
    assert ">Save cadence</button>" in page and ">Stop following up</button>" in page
    assert 'aria-current="true">Students</a>' in page and "‹ Students" in page


def test_a_follow_up_is_its_owner_s_alone(client: TestClient) -> None:
    """Author, 2026-11-08: a follow-up is frontline-initiated, so senior
    staff and Other Staff view reach it only through a share: no page, no
    Convert. A follow-up becomes formal through the frontliner's Flag for
    formal assignment. A formal plan stays theirs to change."""
    for name in ("Sam%20Lee", "Siti%20Rahman"):
        assert client.get(f"/plans/P-03?as={name}").status_code == 404, name
    assert client.get("/plans/P-03").status_code == 200  # Daniel's own
    formal = client.get("/plans/P-01?as=Sam%20Lee").text
    assert "Convert to formal assignment" not in formal and 'id="st"' in formal
    assert "<dt>With</dt><dd>Daniel Koh</dd>" in formal and "‹ Students Overview" in formal


def test_other_staff_identifiable_view_reads_plans_only(client: TestClient) -> None:
    page = client.get("/plans/P-01?as=Siti%20Rahman").text
    assert "You see it read-only (Other Staff view)." in page
    assert "Convert" not in page and "Save cadence" not in page


def test_who_reaches_a_plan(client: TestClient) -> None:
    assert (
        client.get("/plans/P-03?as=Priya%20Raman").status_code == 404
    )  # Daniel's, never shared with her
    assert client.get("/plans/P-05?as=Priya%20Raman").status_code == 200
    assert client.get("/plans/P-99?as=Sam%20Lee").status_code == 404
    assert (
        client.get("/plans/P-01?as=Kenneth%20Lau").status_code == 403
    )  # aggregate view names no one
    assert client.get("/plans/P-01?as=Marcus%20Tan").status_code == 403


def test_plan_chips_open_the_plan(client: TestClient) -> None:
    assert (
        'href="/plans/P-01" aria-label="Plan · Counselling: Clara Tan">Plan · Counselling</a>'
        in client.get("/students/").text
    )
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
    assert '<span class="strong">Daniel Koh</span>' in shared and ">Withdraw</button>" in shared


def test_overview_lists_every_plan_and_the_flagged_students(client: TestClient) -> None:
    sam = client.get("/overview/?as=Sam%20Lee").text
    assert re.findall(r'href="(/plans/P-\d+)\?as=Sam%20Lee"', section(sam, "plans-h")) == [
        f"/plans/{p.id}" for p in sample.PLANS if p.formal
    ]  # formal plans only: a follow-up is its staff member's own
    refs = section(sam, "refs-h")
    assert "Elena Park" in refs and "Flagged 27 Oct by Daniel Koh · suggests weekly" in refs
    siti = client.get("/overview/?as=Siti%20Rahman").text
    assert (
        'id="plans-h"' in siti
        and "read-only" in section(siti, "plans-h")
        and 'id="refs-h"' not in siti
    )
    assert 'id="plans-h"' not in client.get("/overview/?as=Kenneth%20Lau").text  # aggregate only


def test_flag_for_formal_assignment_asks_no_reason(client: TestClient) -> None:
    bao = client.get("/students/S-02").text
    assert 'href="/students/S-02/refer">Flag for formal assignment</a>' in bao
    form = client.get("/students/S-02/refer").text
    assert re.findall(r"<option>([^<]+)</option>", form) == list(sample.ASSIGNMENT_CADENCES)
    assert "<textarea" not in form and "Say nothing of why here" in form
    sent = client.get("/students/S-02/refer/sent?cadence=Weekly").text
    assert (
        "Bao Nguyen is flagged for senior staff to review" in sent
        and "You suggested weekly check-ins." in sent
    )
    elena = client.get("/students/S-05").text
    assert (
        "Flagged for formal assignment on 27 Oct by Daniel Koh" in elena
        and "/students/S-05/refer" not in elena
    )
    for sid in ("S-05", "S-03"):  # flagged already; on his formal assignment
        for path in (f"/students/{sid}/refer", f"/students/{sid}/refer/sent"):
            again = client.get(path, follow_redirects=False)
            assert (again.status_code, again.headers["location"]) == (303, f"/students/{sid}"), path


def test_sharing_lists_grants_and_offers_colleagues(client: TestClient) -> None:
    """Share past records (sharing screens rung 3, author, 2026-11-07)."""
    clara = section(client.get("/students/S-03").text, "shared-h")
    assert '<span class="strong">Mei Ling Tan</span>' in clara and "since 1 Oct" in clara
    assert '<span class="chip chip-ok">Agreed</span>' in clara
    assert 'aria-label="Withdraw your share with Mei Ling Tan">Withdraw</button>' in clara
    bao = section(client.get("/students/S-02").text, "shared-h")
    assert '<span class="chip chip-mute">Pending</span>' in bao and "1 encounter · offered" in bao
    form = client.get("/students/S-03/share").text
    assert re.findall(r"<option>([^<]+)</option>", form) == [
        "Priya Raman",
        "Arjun Nair",
        "Grace Ho",
    ]  # not himself, not Mei Ling again
    assert "<h1>Share past records" in form and 'name="record"' in form
    assert form.count('name="record"') == len(sample.encounters_by("Daniel Koh", "S-03"))
    sent = client.get("/students/S-03/share/sent?colleague=Grace%20Ho").text
    total = len(sample.encounters_by("Daniel Koh", "S-03"))
    assert total and "Grace Ho is asked to agree to all your records for Clara Tan" in sent
    assert "not who the student is, and none of the records" in sent
    first = sample.encounters_by("Daniel Koh", "S-03")[0].id
    some = client.get(
        f"/students/S-03/share/sent?colleague=Grace%20Ho&scope=some&record={first}&record=E-99"
    ).text
    assert (
        "Grace Ho is asked to agree to 1 of your encounters for Clara Tan" in some
    )  # E-99: not his
    for ticked in ("", "&record=E-99"):  # only some, but none of his own ticked
        back = client.get(
            f"/students/S-03/share/sent?colleague=Grace%20Ho&scope=some{ticked}",
            follow_redirects=False,
        )
        assert (back.status_code, back.headers["location"]) == (303, "/students/S-03/share")
    for colleague in (
        "Nobody",
        "Mei%20Ling%20Tan",
        "Daniel%20Koh",
    ):  # unknown, already shared, himself
        back = client.get(
            f"/students/S-03/share/sent?colleague={colleague}", follow_redirects=False
        )
        assert (back.status_code, back.headers["location"]) == (303, "/students/S-03/share"), (
            colleague
        )
    assert client.get("/students/S-09/share").status_code == 404
    assert client.get("/students/S-09/refer").status_code == 404


def test_records_shared_with_the_viewer_show_with_their_owner(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hana Rahim is Priya's; Priya has shared her records with Daniel.
    Their team lists her under Teams, so Shared with me waits on no team."""
    page = client.get("/students/S-08").text
    assert "Priya Raman has shared their records for Hana Rahim with you, since 20 Oct." in page
    assert '<span class="chip chip-mute">Shared by Priya Raman</span>' in section(page, "enc-h")
    assert 'id="shared-h"' not in client.get("/students/").text  # her team's row instead
    monkeypatch.setattr(sample, "TEAMS", ())
    shared = section(client.get("/students/").text, "shared-h")
    assert "Hana Rahim" in shared and "Shared by Priya Raman" in shared
    assert client.get("/students/S-09").status_code == 404  # Priya's, never shared


def test_the_rung_4_pages_need_frontline(client: TestClient) -> None:
    for path in (
        "/students/S-03/share",
        "/students/S-03/share/sent",
        "/students/S-03/refer",
        "/students/S-03/refer/sent",
    ):
        assert client.get(path + "?as=Sam%20Lee").status_code == 403, path


def test_mounted_plan_pages_stay_under_the_mount() -> None:
    host, _ = host_with(("supportlogs",))
    mounted = TestClient(host)
    for path in (
        "/plans/P-01",
        "/plans/P-02?as=Sam%20Lee",
        "/students/S-03/share",
        "/students/S-02/refer",
        "/students/S-08",
        "/overview/?as=Sam%20Lee",
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
    back = mounted.get(
        "/supportlogs/students/S-03/share/sent?colleague=Nobody", follow_redirects=False
    )
    assert back.headers["location"] == "/supportlogs/students/S-03/share"


def test_a_formal_assignment_comes_from_three_sources() -> None:
    """Author, 2026-11-06: Counselling, College and Other for the mock-up."""
    assert sample.ASSIGNMENT_SOURCES == ("Counselling", "College", "Other")
    assert {p.source for p in sample.PLANS if p.formal} <= set(sample.ASSIGNMENT_SOURCES)


def test_a_plan_seen_by_senior_staff_shows_no_contact_facts(client: TestClient) -> None:
    """The wall (author, 2026-11-07): a plan's due state, last contact,
    next expected and contacts come from its encounters' content, so
    senior staff and Other Staff view do not see them; its owner does."""
    owner = client.get("/plans/P-01").text
    assert "<dt>Last contact</dt>" in owner and "Overdue" in owner
    for name in ("Sam%20Lee", "Siti%20Rahman"):
        page = client.get(f"/plans/P-01?as={name}").text
        for fact in ("Last contact", "Next expected", "Contacts since it began", "Overdue"):
            assert fact not in page, (name, fact)
        assert client.get(f"/plans/P-03?as={name}").status_code == 404  # Daniel's own
        # P-02 began as Daniel's follow-up: its history starts at the
        # conversion, never the follow-up's start and cadence.
        converted = client.get(f"/plans/P-02?as={name}").text
        assert "began following up" not in converted, name
    # A formal plan's facts are senior staff's own setting: Sam sees them,
    # with its history from the conversion; Other Staff view sees only
    # who, whom, kind and status (author, 2026-11-07).
    sam = client.get("/plans/P-01?as=Sam%20Lee").text
    assert "<dt>Source</dt><dd>Counselling</dd>" in sam and "<dt>Cadence</dt>" in sam
    assert "converted it to a formal assignment" in client.get("/plans/P-02?as=Sam%20Lee").text
    siti = client.get("/plans/P-01?as=Siti%20Rahman").text
    for fact in ("<dt>Source</dt>", "<dt>Since</dt>", "<dt>Cadence</dt>", "<dt>Review</dt>"):
        assert fact not in siti, fact
    assert "Instruction:" not in siti and 'id="hist-h"' not in siti
    assert "<dt>Status</dt>" in siti and "<dt>Assigned by</dt>" in siti
    assert "Safety-plan support" not in siti and "Safety-plan support" in sam
    # Overview's Every plan: the source for senior staff only.
    every = client.get("/overview/?as=Siti%20Rahman").text.split('id="plans-h"', 1)[1]
    assert "Plan · Counselling" not in every and "Plan · " in every
    assert "Plan · Counselling" in client.get("/overview/?as=Sam%20Lee").text


def test_a_walled_history_shows_nothing_without_an_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fails closed: a formal plan whose history names no assignment or
    conversion shows senior staff nothing of it, never the follow-up."""
    assert sample.walled_history("P-02")[0][1].startswith("Sam Lee converted it")
    assert sample.walled_history("P-01") == sample.PLAN_HISTORY["P-01"]
    monkeypatch.setitem(
        sample.PLAN_HISTORY, "P-02", ((date(2026, 9, 28), "Daniel Koh began following up"),)
    )
    assert sample.walled_history("P-02") == ()


def test_a_share_not_yet_agreed_shows_nothing_to_its_receiver(client: TestClient) -> None:
    """Sharing model 1: Arjun Nair (no sample viewer) sees nothing of Bao
    Nguyen until he agrees to Daniel Koh's share."""
    pending = {(g.grantor, g.viewer, g.student) for g in sample.PEER_GRANTS if not g.agreed}
    assert ("Daniel Koh", "Arjun Nair", "S-02") in pending
    assert all(g.student != "S-02" for g in sample.shared_with("Arjun Nair"))
    assert not sample.shared_encounters("Arjun Nair", "S-02")
    # Each share waiting on its receiver is the one their Waiting for you lists.
    offered = {
        (p.sender, p.to, p.student) for p in sample.PENDING if p.kind == sample.SHARE_OFFERED
    }
    assert pending == offered
    assert client.get("/students/S-09").status_code == 404  # Priya's offer: not yet agreed


def test_a_share_of_chosen_encounters_shows_only_those(monkeypatch) -> None:
    """A share of chosen encounters shows the receiver those, and none of
    the sharer's plans; only a share of all records takes the plans."""
    chosen = sample.PeerGrant("S-08", "Priya Raman", "Mei Ling Tan", sample.TODAY, ("E-09",))
    monkeypatch.setattr(sample, "PEER_GRANTS", (chosen,))
    assert [e.id for e in sample.shared_encounters("Mei Ling Tan", "S-08")] == ["E-09"]
    assert sample.plans_of("Priya Raman", "S-08")  # she has a plan for Hana Rahim
    assert not sample.shared_plans("Mei Ling Tan", "S-08")  # which stays hers
    p05 = sample.plan("P-05")
    assert p05 is not None and not sample.may_read_plan("Mei Ling Tan", p05)
