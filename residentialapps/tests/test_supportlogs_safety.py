"""Support Logs' safety pages on sample data, segment 1D item 1 rung 3: the
Safety concern form and its confirmation, a flag's detail, and the flags
listed on Home and Overview with the unacknowledged count (UI spec screens
4, 8 and 9; functional spec §5.10)."""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import timedelta
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
    return re.findall(
        r'href="(/flags/F-\d+)[^"]*"[^>]*>[^<]*</a><span class="chip [\w-]+">([^<]+)</span>', html
    )


def badge(page: str) -> list[tuple[str, str]]:
    nav = page.split('<nav class="tabs"')[1].split("</nav>")[0]
    return re.findall(
        (
            r'>([^<>]+) <span class="tab-badge">(\d+)'
            r'<span class="visually-hidden"> unacknowledged safety flags?</span>'
        ),
        nav,
    )


def test_a_raiser_sees_their_own_active_flags_on_home(client: TestClient) -> None:
    home = client.get("/").text
    assert flags(section(home, "flags-h")) == [("/flags/F-01", "Unacknowledged")]
    assert "The flags you raised" in home and badge(home) == []  # no count: not a recipient


def test_a_frontline_recipient_sees_every_flag_and_the_count(client: TestClient) -> None:
    """A recipient can always retrieve an outcome (UI spec screen 9),
    whatever students they follow."""
    card = section(client.get("/?as=Priya%20Raman").text, "flags-h")
    assert flags(card.split("<h3")[0]) == [
        ("/flags/F-01", "Unacknowledged"),
        ("/flags/F-02", "Acknowledged · Sam Lee"),
    ]
    assert ("/flags/F-04", "Closed · No further action") in flags(card.split("<h3")[1])
    assert badge(client.get("/?as=Priya%20Raman").text) == [("Home", "1")]
    assert "<h3" not in section(client.get("/").text, "flags-h")  # a raiser's own active flags only


def test_a_recipient_with_nothing_else_finds_closed_flags_too(client: TestClient) -> None:
    home = client.get("/?as=Farah%20Aziz").text
    card = section(home, "flags-h")
    assert flags(card.split("<h3")[0]) == [
        ("/flags/F-01", "Unacknowledged"),
        ("/flags/F-02", "Acknowledged · Sam Lee"),
    ]
    # Closed (author, 2026-11-08): folded until opened, only those closed
    # in the last 7 days (F-04; F-03 closed in September is found by
    # search), and the search after the names.
    closed = card.split("<h3")[1]
    assert flags(closed) == [("/flags/F-04", "Closed · No further action")]
    assert "· 1 in the last 7 days" in closed
    assert '<details class="fold gap-above-sm"><summary><h3 id="closed-h">' in card
    assert '<details class="fold gap-above-sm" open' not in card
    assert closed.index("/flags/F-04") < closed.index('id="flag-find"')
    assert "Find an older one by student or date" in closed
    assert badge(home) == [("Home", "1")]
    old = next(f for f in sample.FLAGS if f.id == "F-03")
    assert old.closed_at and old.closed_at.date() < sample.TODAY - timedelta(days=6)


def test_closed_lists_the_last_7_days_latest_closed_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The window is the last 7 days, today included (23 to 29 Oct on
    sample data); each closed flag says when it closed."""
    from dataclasses import replace
    from datetime import datetime

    f04 = next(f for f in sample.FLAGS if f.id == "F-04")
    edge = replace(f04, id="F-90", closed_at=datetime(2026, 10, 23, 9, 0))
    before = replace(f04, id="F-91", closed_at=datetime(2026, 10, 22, 23, 0))
    monkeypatch.setattr(sample, "FLAGS", (*sample.FLAGS, edge, before))
    farah = sample.viewer("Farah Aziz")
    assert [f.id for f in sample.recently_closed(farah)] == ["F-04", "F-90"]
    home = TestClient(create_app()).get("/?as=Farah%20Aziz").text
    assert "· closed 27 Oct, 10:00" in section(home, "flags-h").split("<h3")[1]


def test_senior_recipients_find_the_flags_on_overview(client: TestClient) -> None:
    overview = client.get("/overview/?as=Sam%20Lee").text
    assert flags(section(overview, "flags-h"))[0] == ("/flags/F-01", "Unacknowledged")
    assert badge(overview) == [("Overview", "1")]
    viewer = client.get("/overview/?as=Kenneth%20Lau").text
    assert (
        'id="flags-h"' not in viewer and badge(viewer) == []
    )  # Other Staff view receives no flags


def test_the_safety_concern_puts_the_calls_first(client: TestClient) -> None:
    page = client.get("/log/safety").text
    # The calls, then the form; the sample viewer card last (author, 2026-10-31).
    assert (
        page.index('id="call-h"')
        < page.index('id="safety-form"')
        < page.index('aria-label="Sample viewer"')
    )
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
    assert all(
        f'name="{n}" class="input" required' in empty for n in ("student", "duration", "type")
    )
    full = client.get("/log/safety?student=S-02&duration=15%20min&type=Check-in").text
    for name, value in (("student", "S-02"), ("duration", "15 min"), ("type", "Check-in")):
        assert f'<input type="hidden" name="{name}" value="{value}">' in full
    assert 'class="input" required' not in full
    assert 'href="/log?student=S-02&amp;duration=15%20min&amp;type=Check-in">‹ Back</a>' in full
    assert re.search(r"<dt>Duration</dt><dd>15 min</dd>\s*<dt>Type</dt><dd>Check-in</dd>", full)
    back = client.get("/log?student=S-02&duration=15%20min&type=Check-in").text
    assert (
        'name="duration" value="15 min" checked' in back
        and 'name="type" value="Check-in" checked' in back
    )


def test_raising_confirms_or_goes_back_with_what_was_chosen(client: TestClient) -> None:
    raised = client.get(
        "/log/safety/raised?student=S-02&duration=15%20min&type=Check-in&step=Duty%20senior%20staff%20contacted&at=2026-10-29T13:50"
    ).text
    assert "A safety flag is raised for Bao Nguyen" in raised and "No alert is sent" in raised
    assert (
        "Duty senior staff contacted, 2026-10-29 13:50." in raised
        and "on their Home or Overview" in raised
    )
    back = client.get("/log/safety/raised?student=S-02&type=Check-in", follow_redirects=False)
    assert (back.status_code, back.headers["location"]) == (
        303,
        "/log/safety?student=S-02&type=Check-in",
    )
    kept = client.get("/log/safety/raised?as=Priya%20Raman", follow_redirects=False)
    assert kept.headers["location"] == "/log/safety?as=Priya%20Raman"


def test_a_recipient_acts_on_a_flag(client: TestClient) -> None:
    unacked = client.get("/flags/F-01?as=Priya%20Raman").text
    assert "Viewing this flag is recorded." in unacked
    assert ">Acknowledge</button>" in unacked and ">Close with outcome</button>" in unacked
    assert re.findall(
        r"<option>([^<]+)</option>", unacked.split('id="outcome"')[1].split("</select>")[0]
    ) == list(sample.CLOSURE_OUTCOMES)
    acked = client.get("/flags/F-02?as=Priya%20Raman").text
    assert ">Acknowledge</button>" not in acked and ">Close with outcome</button>" in acked
    assert "<dt>Acknowledged</dt><dd>29 Oct, 08:30, by Sam Lee</dd>" in acked
    closed = client.get("/flags/F-03?as=Farah%20Aziz").text
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
    assert client.get("/flags/F-01?as=Farah%20Aziz").status_code == 200
    assert (
        "<dd>Counselling duty line contacted, 26 Oct, 19:25</dd>" in client.get("/flags/F-01").text
    )


SAFETY_PAGES = ("/log/safety", "/log/safety/raised", "/flags/F-01")


def test_the_safety_pages_need_their_grants(client: TestClient) -> None:
    for path in SAFETY_PAGES:
        assert client.get(path + "?as=Marcus%20Tan", follow_redirects=False).status_code == 403, (
            path
        )


def test_the_safety_pages_answer_only_on_a_local_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from residentialapps.web import pages as web_pages

    monkeypatch.setattr(web_pages, "is_local", lambda: False)
    deployed = TestClient(create_app())
    for path in SAFETY_PAGES:
        assert deployed.get(path).status_code == 404, path


def test_the_student_view_lists_the_student_s_flags(client: TestClient) -> None:
    assert flags(section(client.get("/students/S-05").text, "flags-h")) == [
        ("/flags/F-01", "Unacknowledged")
    ]
    assert flags(section(client.get("/students/S-03").text, "flags-h")) == [
        ("/flags/F-03", "Closed · Assessed by counselling")
    ]


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
    for path in (
        "/log/safety",
        "/flags/F-01",
        "/?as=Farah%20Aziz",
        "/overview/?as=Sam%20Lee",
        "/log/safety/raised?student=S-02&duration=15%20min&type=Check-in&step=Duty%20senior%20staff%20contacted",
    ):
        page = mounted.get("/supportlogs" + path)
        assert page.status_code == 200, path
        for link in re.findall(
            r'\b(?:href|action|formaction|src)="([^"]*)"',
            re.sub(r'<link rel="icon"[^>]*>', "", page.text),
        ):
            assert link in ("/", "/.auth/logout") or link.startswith(
                ("/supportlogs/", "#", "tel:")
            ), (path, link)
