"""Support Logs' safety pages on sample data, segment 1D item 1 rung 3: the
Safety concern form and its confirmation, a flag's detail, and the flags
listed on Home and Overview with the unacknowledged count (UI spec screens
4, 8 and 9; functional spec §5.10)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

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


def flags(html: str) -> list[tuple[str, str]]:
    """Each flag item's link and state chip."""
    return re.findall(r'href="(/flags/F-\d+)[^"]*"[^>]*>[^<]*</a><span class="chip [\w-]+">([^<]+)</span>', html)


def badge(page: str) -> list[tuple[str, str]]:
    nav = page.split('<nav class="tabs"')[1].split("</nav>")[0]
    return re.findall(r'>([^<>]+) <span class="tab-badge">(\d+)<span class="visually-hidden"> unacknowledged safety flags?</span>', nav)


def test_a_raiser_sees_their_own_active_flags_on_home(client: TestClient) -> None:
    home = client.get("/").text
    assert flags(section(home, "flags-h")) == [("/flags/F-01", "Unacknowledged")]
    assert "The flags you raised" in home and badge(home) == []  # no count: not a recipient


def test_a_frontline_recipient_sees_every_active_flag_and_the_count(client: TestClient) -> None:
    home = client.get("/?as=Priya%20Raman").text
    assert flags(section(home, "flags-h")) == [("/flags/F-01", "Unacknowledged"), ("/flags/F-02", "Acknowledged · Sam Lee")]
    assert badge(home) == [("Home", "1")]


def test_a_recipient_with_nothing_else_finds_closed_flags_too(client: TestClient) -> None:
    home = client.get("/?as=Hui%20Min%20Goh").text
    card = section(home, "flags-h")
    assert flags(card.split("<h3")[0]) == [("/flags/F-01", "Unacknowledged"), ("/flags/F-02", "Acknowledged · Sam Lee")]
    assert flags(card.split("<h3")[1]) == [("/flags/F-04", "Closed · No further action"), ("/flags/F-03", "Closed · Assessed by counselling")]
    assert 'id="flag-find"' in card and badge(home) == [("Home", "1")]


def test_senior_recipients_find_the_flags_on_overview(client: TestClient) -> None:
    overview = client.get("/overview/?as=Sam%20Lee").text
    assert flags(section(overview, "flags-h"))[0] == ("/flags/F-01", "Unacknowledged")
    assert badge(overview) == [("Overview", "1")]
    viewer = client.get("/overview/?as=Kenneth%20Lau").text
    assert 'id="flags-h"' not in viewer and badge(viewer) == []  # Other Staff view receives no flags


def test_the_safety_concern_puts_the_calls_first(client: TestClient) -> None:
    page = client.get("/log/safety").text
    assert page.index('id="call-h"') < page.index('id="safety-form"')
    assert re.findall(r'<a href="(tel:[^"]+)">([^<]+) <span', page) == [
        (f"tel:{number}", who) for who, number in sample.CRISIS_CONTACTS
    ]
    assert "Placeholder numbers" in page and '<header class="safety-head">' in page
    assert re.findall(r'name="step" value="([^"]+)"', page) == list(sample.ESCALATION_STEPS)
    assert sample.MINIMISE in page and ">Save and raise safety flag</button>" in page
    for step in sample.CRISIS_STEPS:
        assert step in page


def test_the_safety_concern_asks_only_for_what_is_not_chosen(client: TestClient) -> None:
    empty = client.get("/log/safety").text
    assert all(f'name="{n}" class="input" required' in empty for n in ("student", "duration", "type"))
    full = client.get("/log/safety?student=S-02&duration=10%20min&type=Check-in").text
    for name, value in (("student", "S-02"), ("duration", "10 min"), ("type", "Check-in")):
        assert f'<input type="hidden" name="{name}" value="{value}">' in full
    assert 'class="input" required' not in full
    assert 'href="/log?student=S-02">‹ Back</a>' in full


def test_raising_confirms_or_goes_back_with_what_was_chosen(client: TestClient) -> None:
    raised = client.get("/log/safety/raised?student=S-02&duration=10%20min&type=Check-in&step=Duty%20senior%20staff%20contacted").text
    assert "A safety flag is raised for Bao Nguyen" in raised and "No alert is sent" in raised
    back = client.get("/log/safety/raised?student=S-02&type=Check-in", follow_redirects=False)
    assert (back.status_code, back.headers["location"]) == (303, "/log/safety?student=S-02&type=Check-in")
    kept = client.get("/log/safety/raised?as=Priya%20Raman", follow_redirects=False)
    assert kept.headers["location"] == "/log/safety?as=Priya%20Raman"


def test_a_recipient_acts_on_a_flag(client: TestClient) -> None:
    unacked = client.get("/flags/F-01?as=Priya%20Raman").text
    assert "Viewing this flag is recorded." in unacked
    assert ">Acknowledge</button>" in unacked and ">Close with outcome</button>" in unacked
    assert re.findall(r"<option>([^<]+)</option>", unacked.split('id="outcome"')[1].split("</select>")[0]) == list(sample.CLOSURE_OUTCOMES)
    acked = client.get("/flags/F-02?as=Priya%20Raman").text
    assert ">Acknowledge</button>" not in acked and ">Close with outcome</button>" in acked
    assert "<dt>Acknowledged</dt><dd>29 Oct, 08:30, by Sam Lee</dd>" in acked
    closed = client.get("/flags/F-03?as=Hui%20Min%20Goh").text
    assert "Closed: Assessed by counselling." in closed and "Close with outcome" not in closed


def test_a_raiser_sees_state_and_outcome_only(client: TestClient) -> None:
    page = client.get("/flags/F-01").text
    assert "You raised it: you see its state and outcome." in page
    assert "Acknowledge</button>" not in page and "Close with outcome" not in page
    assert 'href="/students/S-05">Elena Park</a>' in page


def test_a_flag_is_seen_only_by_its_raiser_and_recipients(client: TestClient) -> None:
    assert client.get("/flags/F-02").status_code == 404  # Priya's, and Daniel receives none
    assert client.get("/flags/F-99?as=Priya%20Raman").status_code == 404
    assert client.get("/flags/F-01?as=Marcus%20Tan").status_code == 403
    assert client.get("/flags/F-01?as=Hui%20Min%20Goh").status_code == 200


def test_the_student_view_lists_the_student_s_flags(client: TestClient) -> None:
    assert flags(section(client.get("/students/S-05").text, "flags-h")) == [("/flags/F-01", "Unacknowledged")]
    assert flags(section(client.get("/students/S-03").text, "flags-h")) == [("/flags/F-03", "Closed · Assessed by counselling")]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_safety_script_parses(client: TestClient, tmp_path: Path) -> None:
    scripts = re.findall(r"<script>(.*?)</script>", client.get("/log/safety").text, re.S)
    assert len(scripts) >= 3
    for n, body in enumerate(scripts):
        source = tmp_path / f"s{n}.js"
        source.write_text(body)
        subprocess.run(["node", "--check", str(source)], check=True)


def test_mounted_safety_pages_stay_under_the_mount() -> None:
    host, _ = host_with(("supportlogs",))
    mounted = TestClient(host)
    for path in ("/log/safety", "/flags/F-01", "/?as=Hui%20Min%20Goh", "/overview/?as=Sam%20Lee",
                 "/log/safety/raised?student=S-02&duration=10%20min&type=Check-in&step=Duty%20senior%20staff%20contacted"):
        page = mounted.get("/supportlogs" + path)
        assert page.status_code == 200, path
        for link in re.findall(r'\b(?:href|action|formaction|src)="([^"]*)"', re.sub(r'<link rel="icon"[^>]*>', "", page.text)):
            assert link == "/" or link.startswith(("/supportlogs/", "#", "tel:")), (path, link)
