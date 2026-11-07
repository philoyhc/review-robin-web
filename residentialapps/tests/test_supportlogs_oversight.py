"""Support Logs on sample data, segment 1D item 1 rung 10: administration
and senior staff, each in view of the other (author, 2026-10-30). Senior
staff see who holds each grant; administrators see how many identifiable
reads each senior made, never of whom; Access warns when no one holds
Senior identifiable; a sys admin's self-grant is a setting, off by
default; and senior staff share a staff member's records on their behalf."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.main import create_app

SAM, RACHEL = "?as=Sam%20Lee", "?as=Rachel%20Yeo"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def section(page: str, heading_id: str) -> str:
    return page.split(f'id="{heading_id}"')[1].split("</section>")[0]


def test_senior_staff_see_who_holds_access(client: TestClient) -> None:
    card = section(client.get("/overview/" + SAM).text, "who-h")
    assert f"<dt>{sample.SENIOR}</dt><dd>Sam Lee</dd>" in card
    assert 'href="/overview/access?as=Sam%20Lee"' in card
    page = client.get("/overview/access" + SAM).text
    grants = section(page, "grants-h")
    for g in sample.ACCESS_GRANTS:
        assert f"<dt>{g}</dt><dd>{', '.join(sample.holders(g)) or 'No one'}</dd>" in grants, g
    changes = section(page, "changes-h")
    access = [a for a in sample.ADMIN_AUDIT if a.kind == "Access"]
    shown = re.findall(r'<span class="strong">([^<]+)</span>', changes.replace("&#39;", "'"))
    assert shown == [a.action for a in access]
    assert "<button" not in grants + changes  # read-only


def test_who_holds_access_is_senior_only(client: TestClient) -> None:
    assert 'id="who-h"' not in client.get("/overview/?as=Siti%20Rahman").text
    for name in ("Siti Rahman", "Kenneth Lau", "Daniel Koh", "Rachel Yeo"):
        assert client.get(f"/overview/access?as={name.replace(' ', '%20')}").status_code == 403, (
            name
        )


def test_administrators_see_counts_of_senior_reads_never_whom(client: TestClient) -> None:
    page = client.get("/sys-admin/audit" + RACHEL).text
    table = section(page, "reads-h")
    rows = re.findall(r"<tr><td[^>]*>([^<]+)</td><td[^>]*>(\d+)</td><td[^>]*>(\d+)</td>", table)
    assert rows == [
        ("Sam Lee", "3", "1")
    ]  # a history, the audit and a download; not the flag he read as recipient
    assert [r["staff"] for r in sample.senior_reads()] == sample.holders(sample.SENIOR)
    for s in sample.STUDENTS:
        assert s.name not in page and s.id not in page, s.name


def test_access_warns_when_no_one_holds_senior_identifiable(client: TestClient) -> None:
    assert 'id="no-senior"' not in client.get("/sys-admin/" + RACHEL).text
    page = client.get("/sys-admin/" + RACHEL + "&preview=no-senior").text
    assert 'id="no-senior"' in page and "No one holds Senior identifiable" in page


def test_the_self_grant_is_a_setting_off_by_default(client: TestClient, monkeypatch) -> None:
    assert sample.SELF_GRANT_SENIOR is False
    config = section(client.get("/sys-admin/configuration" + RACHEL).text, "self-h")
    assert '<input type="checkbox" disabled>' in config
    assert "except a sys admin" not in client.get("/sys-admin/" + RACHEL).text
    monkeypatch.setattr(sample, "SELF_GRANT_SENIOR", True)
    assert '<input type="checkbox" checked disabled>' in section(
        client.get("/sys-admin/configuration" + RACHEL).text, "self-h"
    )
    assert (
        "except a sys admin granting itself Senior identifiable"
        in client.get("/sys-admin/" + RACHEL).text
    )


def test_senior_staff_request_a_share_and_no_longer_share_on_behalf(client: TestClient) -> None:
    """The wall (author, 2026-11-07): to read records, a senior asks the
    staff member to share; Share on their behalf is gone."""
    page = client.get("/overview/students/S-08" + SAM).text
    card = section(page, "staff-h")
    assert 'aria-label="Request a share from Priya Raman">Request a share</button>' in card
    assert "Share on their behalf" not in page and 'id="peer-h"' not in page


def test_hand_over_and_acknowledge_on_behalf_scaffolds(client: TestClient) -> None:
    """Sharing screens rung 6 (author, 2026-11-07): Hand over on a student's
    page and a senior's view of a student; Sys admin acknowledges for
    someone who cannot be reached, seeing no student."""
    mine = section(client.get("/students/S-03").text, "handover-h")  # Daniel's own
    assert ">Hand over records</button>" in mine
    assert "Only the encounters ticked below" in mine
    ticks = mine.count('<input type="checkbox" disabled>')
    assert ticks == len(sample.encounters_by("Daniel Koh", "S-03")) > 0
    found = re.search(r'<select id="ho-to"[^>]*>(.*?)</select>', mine)
    assert found
    to = found.group(1)
    assert "Daniel Koh" not in to and "Mei Ling Tan" in to  # never to yourself
    # Shared (S-08, Priya's) or a team's (S-08, Daniel's team): none his own.
    assert 'id="handover-h"' not in client.get("/students/S-08").text
    senior = section(client.get("/overview/students/S-08" + SAM).text, "handover-h")
    assert '<label for="ho-from">From</label>' in senior and ">Hand over</button>" in senior
    found = re.search(r'<select id="ho-from"[^>]*>(.*?)</select>', senior)
    assert found
    frm = found.group(1)
    assert re.findall(r"<option>([^<]+)</option>", frm) == ["Priya Raman", "Arjun Nair"]
    assert "Someone other than From." in senior
    assert "you see none of them" in senior and "checkbox" not in senior
    admin = client.get("/sys-admin/?as=Rachel%20Yeo").text
    owed = section(admin, "behalf-h")
    assert owed.count("<li>") == len(sample.on_behalf()) == 2
    assert "Handover of Mei Ling Tan&#39;s records to Daniel Koh, started by Sam Lee" in owed
    assert "Sam Lee&#39;s request to Arjun Nair to share" in owed
    assert 'aria-label="Acknowledge for Mei Ling Tan"' in owed
    assert 'aria-label="Acknowledge for Arjun Nair"' in owed
    assert not re.search(r"\b3 records?\b", owed)  # no record count
    for s in sample.STUDENTS:
        assert s.name not in owed and s.id not in owed, s.name
