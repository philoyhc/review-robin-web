"""Support Logs' frontline pages on sample data, segment 1D item 1 rung 2:
the dashboard, Log encounter and its confirmation, Students, the student
view and My plans (UI spec screens 1–3, 5–7)."""

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

PRIYA = "?as=Priya%20Raman"
FRONTLINE_PAGES = ("/", "/log", "/students/", "/students/S-03", "/plans/",
                   "/log/saved?student=S-02&duration=10%20min&type=Check-in")


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def section(page: str, heading_id: str) -> str:
    return page.split(f'id="{heading_id}"')[1].split("</section>")[0]


def names(html: str) -> list[str]:
    return re.findall(r'<a class="strong" href="[^"]*">([^<]+)</a>', html)


def test_the_dashboard_puts_the_most_urgent_first(client: TestClient) -> None:
    """§10.1: due and overdue, overdue first, each with Log; the chips say
    the state in words."""
    due = section(client.get("/").text, "due-h")
    assert names(due) == ["Clara Tan", "Aiden Chen", "Dev Menon"]
    assert re.findall(r'<span class="chip (chip-\w+)">((?:Overdue|Due)[^<]*)</span>', due) == [
        ("chip-warn", "Overdue 2 days"), ("chip-info", "Due today"), ("chip-mute", "Due Mon 2 Nov"),
    ]
    assert 'href="/log?student=S-03" aria-label="Log an encounter with Clara Tan">Log</a>' in due
    assert '<span class="chip chip-marker">Safety-plan support</span>' in due


def test_the_dashboard_follows_recent_and_the_last_14_days(client: TestClient) -> None:
    page = client.get("/").text
    following = section(page, "following-h")
    assert "· 4</span>" in following and names(following) == ["Clara Tan", "Dev Menon", "Aiden Chen"]
    assert ">All 4</a>" in following
    assert names(section(page, "recent-h")) == ["Farid Osman", "Elena Park", "Bao Nguyen", "Aiden Chen"]
    days = section(page, "mine-h")
    assert "<dt>Encounters</dt><dd>6</dd><dt>Support time</dt><dd>105 min</dd><dt>Students</dt><dd>6</dd>" in days
    assert "<dt>Check-in</dt><dd>2</dd>" in days
    assert "The flags you raised" in page  # rung 3 fills the flags


def test_log_renders_the_configured_lists_as_choice_chips(client: TestClient) -> None:
    page = client.get("/log").text
    for name, values in [("duration", sample.DURATIONS), ("type", sample.ENCOUNTER_TYPES),
                         ("mode", sample.MODES), ("started", sample.STARTED_BY)]:
        assert re.findall(rf'<input type="radio" name="{name}" value="([^"]+)"', page) == list(values), name
    assert re.findall(r'name="concern" value="([^"]+)"', page) == [a for a, _ in sample.CONCERN_AREAS]
    assert page.count(" data-says-who>") == len(sample.SAYS_WHO)
    assert f'maxlength="{sample.NOTE_LIMIT}"' in page and sample.NOTE_GUIDANCE in page
    assert '<textarea id="note"' in page and 'name="note"' not in page  # a sample sends no note
    assert page.count('data-clear="') == 3  # the optional single choices clear
    assert "<dt>Health and accessibility</dt><dd>medical matters" in page  # guidance without hover
    assert ' title="' not in page.split('id="log-form"')[1]
    assert page.index('id="log-h"') < page.index("Add details") < page.index('id="save"')  # details on the page
    assert ">Mark a safety concern</a>" in page


def test_log_offers_the_viewer_s_students_or_the_one_chosen(client: TestClient) -> None:
    offered = re.findall(r'name="student" value="([^"]+)"', client.get("/log").text)
    assert offered == [s.id for s, _, _ in sample.working_set("Daniel Koh")][:6]
    chosen = client.get("/log?student=S-03").text
    assert '<input type="hidden" name="student" value="S-03">' in chosen
    assert '<span class="strong">Clara Tan</span><a href="/log">Change</a>' in chosen
    assert 'name="student" value="S-01"' not in chosen
    assert '<input type="hidden" name="as" value="Priya Raman">' in client.get("/log" + PRIYA).text


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_log_s_script_parses(client: TestClient, tmp_path: Path) -> None:
    scripts = re.findall(r"<script>(.*?)</script>", client.get("/log").text, re.S)
    assert len(scripts) >= 3  # the theme's, the sort's, and the form's
    for n, body in enumerate(scripts):
        source = tmp_path / f"s{n}.js"
        source.write_text(body)
        subprocess.run(["node", "--check", str(source)], check=True)


def test_the_confirmation_says_what_was_saved_and_offers_follow_up(client: TestClient) -> None:
    bao = client.get("/log/saved?student=S-02&duration=10%20min&type=Practical%20support").text
    assert "Practical support with Bao Nguyen, 10 min" in bao
    assert "Bao Nguyen is not on your follow-ups." in bao and ">Add to my follow-ups</button>" in bao
    clara = client.get("/log/saved?student=S-03&duration=15%20min&type=Check-in").text
    assert "Add to my follow-ups" not in clara  # Clara is on a plan already
    added = client.get("/log/saved?student=S-02&duration=10%20min&type=Check-in&follow=yes").text
    assert "Added to your follow-ups." in added
    assert "nothing is stored" in bao
    following = client.get("/log/saved?student=S-03&duration=15%20min&type=Check-in&follow=yes").text
    assert "Added to your follow-ups." not in following  # on a plan already: nothing was added
    assert ">Open Bao Nguyen</a>" in bao
    stranger = client.get("/log/saved?student=S-09&duration=10%20min&type=Check-in").text
    assert "Open Ivan Seet" not in stranger  # not one of Daniel's: the view would be not found


def test_log_shows_the_plan_a_chosen_student_is_on(client: TestClient) -> None:
    clara = client.get("/log?student=S-03").text
    assert "On your plans: weekly, set by Sam Lee." in clara and 'name="follow"' not in clara
    aiden = client.get("/log?student=S-01").text
    assert "On your follow-ups: weekly." in aiden and "Keep or change the cadence" in aiden
    assert "<option selected>Weekly</option>" in aiden
    assert 'name="follow"' in client.get("/log?student=S-02").text


def test_pages_naming_students_say_they_are_recorded(client: TestClient) -> None:
    for path in ("/", "/log", "/students/", "/plans/", "/log/saved?student=S-02&duration=10%20min&type=Check-in"):
        assert "Pages that name students are recorded when opened." in client.get(path).text, path
    assert "Opening this view is recorded." in client.get("/students/S-03").text


def test_a_custom_cadence_says_so() -> None:
    plan = sample.Plan("P-99", "S-01", "Daniel Koh", False, sample.TODAY, "Custom")
    assert sample.due(plan) == ("none", "Custom cadence")


def test_an_incomplete_save_goes_back_to_the_form(client: TestClient) -> None:
    for query in ("", "?student=S-02&duration=10%20min", "?student=S-99&duration=10%20min&type=Check-in",
                  "?student=S-02&duration=7%20min&type=Check-in"):
        page = client.get("/log/saved" + query, follow_redirects=False)
        assert (page.status_code, page.headers["location"]) == (303, "/log"), query
    kept = client.get("/log/saved" + PRIYA, follow_redirects=False)
    assert kept.headers["location"] == "/log" + PRIYA


def test_students_lists_the_working_set(client: TestClient) -> None:
    """§4.3: plans and follow-ups first, then everyone seen, the latest
    first; each says why it is the viewer's."""
    page = client.get("/students/").text
    mine = section(page, "mine-h")
    assert names(mine) == ["Clara Tan", "Dev Menon", "Aiden Chen", "Elena Park", "Farid Osman", "Bao Nguyen"]
    assert '<span class="chip chip-accent">Plan · Counselling</span>' in mine
    assert "bao.nguyen@u.example.edu · seen 24 Oct" in mine
    assert names(section(client.get("/students/" + PRIYA).text, "mine-h")) == ["Hana Rahim", "Jia Wen Lee", "Ivan Seet"]


def test_the_student_view_shows_the_viewer_s_records(client: TestClient) -> None:
    page = client.get("/students/S-03").text
    assert "<h1>Clara Tan</h1>" in page and "clara.tan@u.example.edu" in page
    assert "Opening this view is recorded." in page
    assert re.findall(r'<span class="tile-n">([^<]+)</span><span class="tile-l">([^<]+)', page) == [
        ("Weekly", "Cadence"), ("20 Oct", "Last contact"), ("27 Oct", "Next due"),
    ]
    assert 'href="/log?student=S-03">Log encounter with Clara Tan</a>' in page
    assert section(page, "enc-h").count("<li>") == 2
    plan = section(page, "plan-h")
    assert "Safety-plan support" in plan and "Overdue 2 days" in plan and "<dd>Sam Lee</dd>" in plan
    assert "Flag for formal assignment" not in plan  # formally assigned already
    bao = client.get("/students/S-02").text
    assert "Not on your follow-ups." in bao and ">Start following up</button>" in bao
    assert 'aria-current="true">Students</a>' in page


def test_a_student_outside_the_working_set_is_not_found(client: TestClient) -> None:
    assert client.get("/students/S-09").status_code == 404  # Priya's, not Daniel's
    assert client.get("/students/S-09" + PRIYA).status_code == 200
    assert client.get("/students/S-99").status_code == 404


def test_my_plans_lists_assignments_then_follow_ups_and_filters(client: TestClient) -> None:
    page = client.get("/plans/").text
    assert names(section(page, "formal-h")) == ["Clara Tan", "Dev Menon"]
    assert names(section(page, "informal-h")) == ["Aiden Chen", "Elena Park"]
    assert "Weekly check-in; a reminder of the coping plan." in section(page, "formal-h")
    overdue = client.get("/plans/?show=overdue").text
    assert names(section(overdue, "formal-h")) == ["Clara Tan"] and names(section(overdue, "informal-h")) == []
    week = client.get("/plans/?show=week").text
    assert names(section(week, "formal-h")) + names(section(week, "informal-h")) == ["Clara Tan", "Dev Menon", "Aiden Chen"]
    assert 'href="/plans/?show=overdue" aria-current="true">✓ Overdue</a>' in overdue
    assert 'href="/plans/?as=Priya%20Raman&amp;show=week"' in client.get("/plans/" + PRIYA).text


def test_the_frontline_pages_are_the_frontline_s(client: TestClient) -> None:
    for path in (*FRONTLINE_PAGES[1:], "/students/S-99"):
        assert client.get(path + ("&" if "?" in path else "?") + "as=Sam%20Lee").status_code == 403, path


def test_mounted_frontline_pages_stay_under_the_mount() -> None:
    host, _ = host_with(("supportlogs",))
    mounted = TestClient(host)
    for path in FRONTLINE_PAGES:
        page = mounted.get("/supportlogs" + path)
        assert page.status_code == 200, path
        for link in re.findall(r'\b(?:href|action|src)="([^"]*)"', re.sub(r'<link rel="icon"[^>]*>', "", page.text)):
            assert link == "/" or link.startswith(("/supportlogs/", "#")), (path, link)
    back = mounted.get("/supportlogs/log/saved", follow_redirects=False)
    assert back.headers["location"] == "/supportlogs/log"
